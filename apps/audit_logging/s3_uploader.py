# audit_logging/s3_uploader.py
import datetime
import io
import logging
import uuid
from typing import List, Dict, Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


def process_and_upload_batch(logs: List[Dict[str, Any]]):
    """
    Takes a list of log dictionaries, groups them by partition key,
    serializes each group to Parquet, and uploads to S3 for long-term storage.
    No Glue/Athena integration - just pure S3 storage.
    """
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION_NAME,
    )
    base_prefix = "audit_logs/"

    # Group logs by partition key (object_type, YYYY, MM, DD)
    grouped_logs: Dict[tuple, list] = {}
    for log in logs:
        dt = datetime.datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
        key = (
            log.get("object_type", "unknown"),
            dt.strftime("%Y"),
            dt.strftime("%m"),
            dt.strftime("%d"),
        )
        if key not in grouped_logs:
            grouped_logs[key] = []
        grouped_logs[key].append(log)

    # Upload one file per group
    for (object_type, year, month, day), batch in grouped_logs.items():
        s3_key = (
            f"{base_prefix}"
            f"object_type={object_type}/"
            f"year={year}/month={month}/day={day}/"
            f"batch-{uuid.uuid4()}.parquet"
        )

        try:
            # Get all keys from the first log to create a consistent schema
            all_keys = list(batch[0].keys())
            # Build a dictionary of lists for pyarrow
            table_data = {key: [d.get(key) for d in batch] for key in all_keys}

            table = pa.Table.from_pydict(table_data)
            with io.BytesIO() as sink:
                pq.write_table(table, sink, compression="SNAPPY")
                parquet_data = sink.getvalue()

            s3_client.put_object(
                Bucket=settings.AUDIT_LOG_AWS_S3_BUCKET, Key=s3_key, Body=parquet_data
            )
            logger.info("Uploaded batch of %d logs to %s", len(batch), s3_key)
        except (BotoCoreError, ClientError, pa.ArrowInvalid) as e:
            logger.error(
                "Failed to serialize or upload batch for key %s: %s", s3_key, e
            )
            # Re-raise the exception to let the caller handle retries
            raise
