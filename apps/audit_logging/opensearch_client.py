# audit_logging/opensearch_client.py
import datetime
import logging
from typing import Any, Dict, List

from django.conf import settings
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import OpenSearchException, RequestError

from .exceptions import AuditLogException

logger = logging.getLogger(__name__)

# Index name pattern: audit-logs-YYYY-MM
INDEX_NAME_TEMPLATE = "{prefix}-{year}-{month:02d}"


class OpenSearchClient:
    """Provides an interface to index and query audit logs in OpenSearch."""

    def __init__(self):
        self.client = self._create_client()
        self.index_prefix = settings.OPENSEARCH_INDEX_PREFIX

    def _create_client(self) -> OpenSearch:
        """Creates and returns an OpenSearch client instance."""
        auth = None
        if settings.OPENSEARCH_USERNAME and settings.OPENSEARCH_PASSWORD:
            auth = (settings.OPENSEARCH_USERNAME, settings.OPENSEARCH_PASSWORD)

        return OpenSearch(
            hosts=[{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
            http_auth=auth,
            use_ssl=settings.OPENSEARCH_USE_SSL,
            verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
            connection_class=RequestsHttpConnection,
        )

    def _get_index_name(self, timestamp: str) -> str:
        """Generate index name based on timestamp."""
        dt = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return INDEX_NAME_TEMPLATE.format(prefix=self.index_prefix, year=dt.year, month=dt.month)

    def _ensure_index_exists(self, index_name: str):
        """Create index if it doesn't exist with proper mapping."""
        if self.client.indices.exists(index=index_name):
            return

        # TODO: Add user org data fields when Org feature is implemented
        # Fields to add: department, position, org, etc.
        #
        # TODO (Nice to have): Consider supporting dynamic fields for additional
        # fields not known at audit log app level. This would make the app more
        # portable to other projects by reducing domain knowledge requirements.
        # If this adds too much complexity or causes performance issues, can skip.

        mapping = {
            "mappings": {
                "properties": {
                    "log_id": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "user_id": {"type": "keyword"},
                    "username": {"type": "keyword"},
                    "employee_code": {"type": "keyword"},
                    "full_name": {"type": "text", "analyzer": "standard"},
                    "action": {"type": "keyword"},
                    "object_type": {"type": "keyword"},
                    "object_id": {"type": "keyword"},
                    "object_repr": {"type": "text", "analyzer": "standard"},
                    "change_message": {"type": "flattened"},
                    "ip_address": {"type": "ip"},
                    "user_agent": {"type": "text"},
                    "session_key": {"type": "keyword"},
                }
            },
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        }

        try:
            self.client.indices.create(index=index_name, body=mapping)
            logger.info(f"Created OpenSearch index: {index_name}")
        except RequestError as e:
            if e.error == "resource_already_exists_exception":
                # Index was created by another process
                logger.debug(f"Index {index_name} already exists")
            else:
                logger.error(f"Failed to create index {index_name}: {e}")
                raise AuditLogException(f"Failed to create OpenSearch index: {e}") from e

    def index_log(self, log_data: Dict[str, Any]):
        """Index a single log entry in OpenSearch."""
        index_name = self._get_index_name(log_data["timestamp"])
        self._ensure_index_exists(index_name)

        try:
            response = self.client.index(index=index_name, id=log_data["log_id"], body=log_data)
            logger.debug(f"Indexed log {log_data['log_id']} to {index_name}")
            return response
        except OpenSearchException as e:
            logger.error(f"Failed to index log {log_data.get('log_id', 'unknown')}: {e}")
            raise AuditLogException(f"Failed to index log: {e}") from e

    def bulk_index_logs(self, logs: List[Dict[str, Any]]):
        """Index multiple log entries using bulk API."""
        if not logs:
            return

        # Group logs by index
        grouped_logs: Dict[str, List[Dict[str, Any]]] = {}
        for log in logs:
            index_name = self._get_index_name(log["timestamp"])
            if index_name not in grouped_logs:
                grouped_logs[index_name] = []
            grouped_logs[index_name].append(log)

        # Ensure all indices exist
        for index_name in grouped_logs.keys():
            self._ensure_index_exists(index_name)

        # Prepare bulk request
        bulk_body = []
        for index_name, index_logs in grouped_logs.items():
            for log in index_logs:
                bulk_body.append({"index": {"_index": index_name, "_id": log["log_id"]}})
                bulk_body.append(log)

        try:
            response = self.client.bulk(body=bulk_body)
            if response.get("errors"):
                error_count = sum(1 for item in response["items"] if "error" in item.get("index", {}))
                logger.warning(f"Bulk indexing completed with {error_count} errors")
            else:
                logger.info(f"Successfully indexed {len(logs)} logs to OpenSearch")
            return response
        except OpenSearchException as e:
            logger.error(f"Failed to bulk index logs: {e}")
            raise AuditLogException(f"Failed to bulk index logs: {e}") from e

    def _get_last_12_months_indices(self) -> str:
        """
        Generate index pattern for last 12 months to ensure we serve recent logs.

        Returns:
            str: Comma-separated list of index names or pattern
        """
        # For simplicity and performance, we use a wildcard pattern
        # OpenSearch will automatically search only existing indices
        # The index pattern audit-logs-* will match all monthly indices
        # This ensures we always search the last 12 months of data
        return f"{self.index_prefix}-*"

    def get_log_by_id(self, log_id: str) -> Dict[str, Any]:
        """
        Retrieve a single audit log by its log_id.

        Args:
            log_id: The unique identifier of the log

        Returns:
            dict: Full log data with all fields

        Raises:
            AuditLogException: If log is not found or retrieval fails
        """
        # Search across all indices for the log_id
        index_pattern = self._get_last_12_months_indices()

        search_body: Dict[str, Any] = {
            "query": {"term": {"log_id": log_id}},
            "size": 1,
        }

        try:
            response = self.client.search(index=index_pattern, body=search_body)

            hits = response["hits"]["hits"]
            if not hits:
                raise AuditLogException(f"Log with id {log_id} not found")

            return hits[0]["_source"]

        except OpenSearchException as e:
            logger.error(f"Failed to retrieve log {log_id}: {e}")
            raise AuditLogException(f"Failed to retrieve log: {e}") from e

    def search_logs(
        self,
        *,
        filters: Dict[str, Any],
        page_size: int = 50,
        from_offset: int = 0,
        sort_order: str = "desc",
        summary_fields_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Search audit logs with filters.

        Args:
            filters: Dictionary of filter criteria
            page_size: Number of results per page
            from_offset: Offset for pagination
            sort_order: Sort order ('asc' or 'desc')
            summary_fields_only: If True, return only summary fields (log_id, timestamp, user_id,
                                 username, full_name, employee_code, action, object_type, object_id, object_repr)

        Returns:
            dict: Search results with items, total, pagination info
        """
        query = self._build_search_query(filters)

        # Use index pattern to search across last 12 months of indices
        index_pattern = self._get_last_12_months_indices()

        search_body: Dict[str, Any] = {
            "query": query,
            "sort": [{"timestamp": {"order": sort_order}}],
            "size": page_size,
            "from": from_offset,
        }

        # If summary fields only, use _source filtering
        if summary_fields_only:
            search_body["_source"] = [
                "log_id",
                "timestamp",
                "user_id",
                "username",
                "employee_code",
                "full_name",
                "action",
                "object_type",
                "object_id",
                "object_repr",
            ]

        try:
            response = self.client.search(index=index_pattern, body=search_body)

            hits = response["hits"]
            logs = [hit["_source"] for hit in hits["hits"]]
            total = hits["total"]["value"] if isinstance(hits["total"], dict) else hits["total"]

            has_next = from_offset + page_size < total
            next_offset = from_offset + page_size if has_next else None

            return {
                "items": logs,
                "total": total,
                "next_offset": next_offset,
                "has_next": has_next,
            }
        except OpenSearchException as e:
            logger.error(f"Failed to search logs: {e}")
            raise AuditLogException(f"Failed to search logs: {e}") from e

    def _build_search_query(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build OpenSearch query from filters."""
        must_clauses: List[Dict[str, Any]] = []

        for key, value in filters.items():
            if not value:
                continue

            if key == "from_date":
                must_clauses.append({"range": {"timestamp": {"gte": value}}})
            elif key == "to_date":
                must_clauses.append({"range": {"timestamp": {"lte": value}}})
            elif key == "search_term":
                must_clauses.append(
                    {
                        "multi_match": {
                            "query": value,
                            "fields": ["employee_code", "full_name"],
                        }
                    }
                )
            else:
                # Exact match for other fields
                must_clauses.append({"term": {key: value}})

        if must_clauses:
            return {"bool": {"must": must_clauses}}
        else:
            return {"match_all": {}}


# Singleton instance
_opensearch_client = None


def get_opensearch_client() -> OpenSearchClient:
    """Get the singleton OpenSearch client instance."""
    global _opensearch_client
    if _opensearch_client is None:
        _opensearch_client = OpenSearchClient()
    return _opensearch_client
