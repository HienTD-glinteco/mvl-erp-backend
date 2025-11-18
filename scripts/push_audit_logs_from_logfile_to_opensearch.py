#!/usr/bin/env python
"""
Push audit logs from file to OpenSearch.

This script reads audit log records from a JSON/JSONL file and pushes them to OpenSearch.
It checks for existing documents by log_id to avoid duplicates and handles conflicts.

Usage:
    python scripts/push_audit_logs_to_opensearch.py --input logs/audit.log --dry-run
    python scripts/push_audit_logs_to_opensearch.py --input logs/audit.log --batch-size 100

Environment variables required:
    OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD,
    OPENSEARCH_USE_SSL, OPENSEARCH_VERIFY_CERTS, OPENSEARCH_INDEX_PREFIX
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Add project root to path for Django imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import django

# Setup Django before importing Django models/settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from django.conf import settings  # noqa: E402

from apps.audit_logging.opensearch_client import OpenSearchClient  # noqa: E402

# Constants
DEFAULT_PROBLEM_FILE = "problematic_audit_logs.jsonl"
DEFAULT_BATCH_SIZE = 100
LOG_ID_FIELD = "log_id"

logger = logging.getLogger(__name__)


def parse_jsonl_file(path: str) -> Iterable[Dict[str, Any]]:
    """
    Parse audit log file from Django logging output.

    The log file format is:
    INFO 2025-11-10 17:04:57,440 producer {json...}

    This function extracts the JSON part from each log line.

    Args:
        path: Path to the log file

    Yields:
        dict: Individual log records
    """
    with open(path, "r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue

            # Find the JSON part (starts with '{' and ends with '}')
            json_start = line.find("{")
            if json_start == -1:
                logger.debug(f"Line {line_num}: No JSON object found, skipping")
                continue

            json_part = line[json_start:]

            try:
                record = json.loads(json_part)
                yield record
            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: Failed to parse JSON: {e}")
                logger.debug(f"Line {line_num} content: {json_part[:200]}")


def extract_log_id(record: Dict[str, Any]) -> Optional[str]:
    """
    Extract log_id from record.

    Args:
        record: Log record dictionary

    Returns:
        str: The log_id if found, None otherwise
    """
    return record.get(LOG_ID_FIELD) or record.get("_id")


def bulk_get_existing_docs(client: OpenSearchClient, log_ids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Bulk check if documents exist in OpenSearch.

    Args:
        client: OpenSearchClient instance
        log_ids: List of log_ids to check

    Returns:
        dict: Mapping of log_id to document data (None if not found)
    """
    if not log_ids:
        return {}

    # Use OpenSearch's multi-get API
    index_pattern = f"{client.index_prefix}-*"

    # Build search query to get multiple docs by log_id
    search_body = {
        "query": {"terms": {"log_id": log_ids}},
        "size": len(log_ids),
        "_source": True,
    }

    try:
        response = client.client.search(index=index_pattern, body=search_body)
        hits = response["hits"]["hits"]

        # Create mapping of log_id to document
        result = dict.fromkeys(log_ids)
        for hit in hits:
            source = hit["_source"]
            log_id = source.get("log_id")
            if log_id:
                result[log_id] = source

        return result

    except Exception as e:
        logger.error(f"Failed to bulk get documents: {e}")
        raise


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a log record to match expected format.

    Args:
        record: Raw log record

    Returns:
        dict: Normalized record
    """
    normalized = record.copy()

    # Ensure change_message is properly formatted
    if "change_message" in normalized:
        if isinstance(normalized["change_message"], str):
            normalized["change_message"] = {"message": normalized["change_message"]}

    return normalized


def records_are_identical(record1: Dict[str, Any], record2: Dict[str, Any]) -> bool:
    """
    Compare two records for equality.

    Args:
        record1: First record
        record2: Second record

    Returns:
        bool: True if records are identical
    """
    # Normalize both records for comparison
    norm1 = normalize_record(record1)
    norm2 = normalize_record(record2)

    # Use canonical JSON serialization for comparison
    json1 = json.dumps(norm1, sort_keys=True, separators=(",", ":"))
    json2 = json.dumps(norm2, sort_keys=True, separators=(",", ":"))

    return json1 == json2


def append_problem_log(
    problem_file: str,
    record: Dict[str, Any],
    existing_doc: Optional[Dict[str, Any]],
    log_id: str,
    reason: str,
) -> None:
    """
    Append a problematic log entry to the problem file.

    Args:
        problem_file: Path to the problem log file
        record: The record from the input file
        existing_doc: The existing document in OpenSearch (if any)
        log_id: The log_id
        reason: Reason for the problem
    """
    problem_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "log_id": log_id,
        "reason": reason,
        "file_record": record,
        "opensearch_record": existing_doc,
    }

    os.makedirs(os.path.dirname(problem_file) or ".", exist_ok=True)
    with open(problem_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(problem_entry, ensure_ascii=False) + "\n")

    logger.debug(f"Recorded problem for log_id {log_id}: {reason}")


def process_records_bulk(
    client: OpenSearchClient,
    records: List[Dict[str, Any]],
    existing_docs: Dict[str, Optional[Dict[str, Any]]],
    problem_file: str,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Process multiple records and determine which should be indexed.

    Args:
        client: OpenSearchClient instance
        records: List of log records to process
        existing_docs: Mapping of log_id to existing documents
        problem_file: Path to problem log file

    Returns:
        tuple: (records_to_index, skipped_count, problem_count)
    """
    records_to_index = []
    skipped = 0
    problems = 0

    for record in records:
        if not isinstance(record, dict):
            logger.warning("Skipping non-dictionary record")
            problems += 1
            continue

        log_id = extract_log_id(record)
        if not log_id:
            logger.warning("Record missing log_id, cannot process")
            append_problem_log(problem_file, record, None, "UNKNOWN", "missing_log_id")
            problems += 1
            continue

        existing_doc = existing_docs.get(log_id)

        if existing_doc is None:
            # New document - will be indexed
            normalized = normalize_record(record)
            records_to_index.append(normalized)
            logger.debug(f"Will index new document: {log_id}")
            continue

        # Document exists - compare for conflicts
        if records_are_identical(record, existing_doc):
            logger.debug(f"Document {log_id} already exists and is identical, skipping")
            skipped += 1
            continue

        logger.warning(f"Document {log_id} exists but differs from file version")
        append_problem_log(problem_file, record, existing_doc, log_id, "conflict")
        problems += 1

    return records_to_index, skipped, problems


def process_batch(
    client: OpenSearchClient,
    batch: List[Dict[str, Any]],
    problem_file: str,
    dry_run: bool,
) -> Tuple[int, int, int]:
    """
    Process a batch of log records using bulk operations.

    Args:
        client: OpenSearchClient instance
        batch: List of log records to process
        problem_file: Path to problem log file
        dry_run: If True, don't actually write to OpenSearch

    Returns:
        tuple: (indexed_count, skipped_count, problem_count)
    """
    if not batch:
        return 0, 0, 0

    # Extract all log_ids from batch
    log_ids = []
    for record in batch:
        if isinstance(record, dict):
            log_id = extract_log_id(record)
            if log_id:
                log_ids.append(log_id)

    # Bulk fetch existing documents
    logger.debug(f"Bulk checking {len(log_ids)} log_ids in OpenSearch")
    try:
        existing_docs = bulk_get_existing_docs(client, log_ids)
    except Exception as e:
        return _handle_bulk_fetch_error(e, batch, problem_file)

    # Process records using pre-fetched data
    records_to_index, skipped, problems = process_records_bulk(client, batch, existing_docs, problem_file)

    # Bulk index new records
    indexed = _index_records(client, records_to_index, problem_file, dry_run)
    if indexed == 0 and records_to_index:
        problems += len(records_to_index)

    return indexed, skipped, problems


def _handle_bulk_fetch_error(error: Exception, batch: List[Dict[str, Any]], problem_file: str) -> Tuple[int, int, int]:
    """Handle errors during bulk fetch of existing documents."""
    logger.error(f"Failed to bulk fetch existing documents: {error}")
    for record in batch:
        log_id = extract_log_id(record) or "UNKNOWN"
        append_problem_log(problem_file, record, None, log_id, f"bulk_fetch_error: {str(error)}")
    return 0, 0, len(batch)


def _index_records(
    client: OpenSearchClient,
    records_to_index: List[Dict[str, Any]],
    problem_file: str,
    dry_run: bool,
) -> int:
    """Index records to OpenSearch or simulate in dry-run mode."""
    if not records_to_index:
        return 0

    if dry_run:
        logger.info(f"[DRY RUN] Would index {len(records_to_index)} records")
        return len(records_to_index)

    try:
        client.bulk_index_logs(records_to_index)
        logger.info(f"Successfully indexed batch of {len(records_to_index)} records")
        return len(records_to_index)
    except Exception as e:
        logger.error(f"Failed to bulk index batch: {e}")
        for rec in records_to_index:
            log_id = extract_log_id(rec)
            append_problem_log(problem_file, rec, None, log_id or "UNKNOWN", f"bulk_index_error: {str(e)}")
        return 0


def push_logs_to_opensearch(
    input_path: str,
    problem_file: str,
    batch_size: int = 100,
    dry_run: bool = True,
) -> None:
    """
    Main function to push audit logs to OpenSearch.

    Args:
        input_path: Path to the input log file
        problem_file: Path to the problem log file
        batch_size: Number of records to process in each batch
        dry_run: If True, simulate without writing
    """
    logger.info(f"Starting audit log push from {input_path}")
    logger.info(f"OpenSearch host: {settings.OPENSEARCH_HOST}:{settings.OPENSEARCH_PORT}")
    logger.info(f"Index prefix: {settings.OPENSEARCH_INDEX_PREFIX}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Dry run: {dry_run}")

    # Initialize OpenSearch client
    try:
        client = OpenSearchClient()
        logger.info("OpenSearch client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenSearch client: {e}")
        sys.exit(1)

    # Statistics
    total_records = 0
    total_indexed = 0
    total_skipped = 0
    total_problems = 0

    # Process records in batches
    batch: List[Dict[str, Any]] = []

    try:
        for record in parse_jsonl_file(input_path):
            total_records += 1
            batch.append(record)

            if len(batch) >= batch_size:
                indexed, skipped, problems = process_batch(client, batch, problem_file, dry_run)
                total_indexed += indexed
                total_skipped += skipped
                total_problems += problems
                batch = []

        # Process remaining records
        if batch:
            indexed, skipped, problems = process_batch(client, batch, problem_file, dry_run)
            total_indexed += indexed
            total_skipped += skipped
            total_problems += problems

    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
    except Exception as e:
        logger.exception(f"Unexpected error during processing: {e}")
        sys.exit(2)

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total records processed: {total_records}")
    logger.info(f"Successfully indexed: {total_indexed}")
    logger.info(f"Skipped (identical): {total_skipped}")
    logger.info(f"Problems (conflicts/errors): {total_problems}")
    logger.info("=" * 60)

    if total_problems > 0:
        logger.warning(f"Found {total_problems} problematic records. Check {problem_file} for details.")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Push audit logs from file to OpenSearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be indexed
  python scripts/push_audit_logs_to_opensearch.py --input logs/audit.log --dry-run

  # Actually push logs with custom batch size
  python scripts/push_audit_logs_to_opensearch.py --input logs/audit.log --batch-size 200

  # Verbose output
  python scripts/push_audit_logs_to_opensearch.py --input logs/audit.log --verbose

Environment variables:
  OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD,
  OPENSEARCH_USE_SSL, OPENSEARCH_VERIFY_CERTS, OPENSEARCH_INDEX_PREFIX
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to audit log file (JSON, JSON array, or JSONL format)",
    )

    parser.add_argument(
        "--problem-file",
        "-p",
        default=DEFAULT_PROBLEM_FILE,
        help=f"File to log problematic records (default: {DEFAULT_PROBLEM_FILE})",
    )

    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of records to process in each batch (default: {DEFAULT_BATCH_SIZE})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without actually writing to OpenSearch",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG level) logging",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Validate input file exists
    if not os.path.isfile(args.input):
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    try:
        push_logs_to_opensearch(
            input_path=args.input,
            problem_file=args.problem_file,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
