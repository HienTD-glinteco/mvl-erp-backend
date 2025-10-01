# Audit Logging System

This module provides a comprehensive audit logging solution using RabbitMQ Stream for message queuing, AWS S3 for long-term storage, and OpenSearch for real-time querying and filtering.

## Architecture

- **Producer**: Logs audit events to RabbitMQ Stream
- **Consumer**: Reads from RabbitMQ Stream, indexes to OpenSearch, and archives to S3
- **Storage**: 
  - S3: Long-term persistent storage in Parquet format
  - OpenSearch: Real-time indexing for fast querying and filtering
- **API**: REST endpoints for searching and filtering audit logs

## Setup

### 1. RabbitMQ Stream Setup

Enable RabbitMQ Stream plugin:

```bash
# Run rabbitmq container with stream plugin
docker run -d --name rabbitmq \
  -p 5552:5552 \
  -p 15672:15672 \
  -p 5672:5672 \
  -e RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS='-rabbitmq_stream advertised_host localhost' \
  rabbitmq:4-management

# Enable stream plugin
docker exec rabbitmq rabbitmq-plugins enable rabbitmq_stream rabbitmq_stream_management
```

### 2. OpenSearch Setup

You can use either AWS OpenSearch Service or a self-hosted OpenSearch instance.

#### Option A: Docker (for local development)

```bash
# Run OpenSearch (single node for development)
docker run -d --name opensearch \
  -p 9200:9200 \
  -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=Admin@123" \
  opensearchproject/opensearch:latest
```

#### Option B: AWS OpenSearch Service

1. Create an OpenSearch domain in AWS
2. Configure access policies
3. Update `.env` with the domain endpoint and credentials

### 3. Environment Configuration

Update your `.env` file with the following settings:

```bash
# OpenSearch settings
OPENSEARCH_HOST=localhost  # or your AWS OpenSearch endpoint
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin  # if using authentication
OPENSEARCH_PASSWORD=Admin@123  # if using authentication
OPENSEARCH_USE_SSL=false  # true for AWS OpenSearch
OPENSEARCH_VERIFY_CERTS=false  # true for production AWS OpenSearch
OPENSEARCH_INDEX_PREFIX=audit-logs

# Audit Logging
AUDIT_LOG_AWS_S3_BUCKET=backend-audit-logs
AUDIT_LOG_BATCH_SIZE=1000
AUDIT_LOG_FLUSH_INTERVAL=60

# RabbitMQ Stream settings
RABBITMQ_STREAM_HOST=localhost
RABBITMQ_STREAM_PORT=5552
RABBITMQ_STREAM_USER=guest
RABBITMQ_STREAM_PASSWORD=guest
RABBITMQ_STREAM_VHOST=/
RABBITMQ_STREAM_NAME=audit_logs_stream

# AWS credentials (for S3 storage)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION_NAME=us-east-1
```

### 4. AWS S3 Setup

Ensure your S3 bucket exists and the server has the correct IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::backend-audit-logs/*"
    }
  ]
}
```

### 5. Run Migrations

```bash
python manage.py migrate
```

## Usage

### Starting the Consumer

Run the audit log consumer as a Django management command:

```bash
# Default settings
python manage.py consume_audit_logs

# Custom batch size
python manage.py consume_audit_logs --batch-size 500

# Custom consumer name (for multiple consumers)
python manage.py consume_audit_logs --consumer-name worker-01
```

The consumer will:
1. Read messages from RabbitMQ Stream
2. Index each log to OpenSearch immediately for real-time search
3. Batch logs and upload to S3 for long-term storage
4. Use RabbitMQ's server-side offset tracking (no database model needed)

### Logging Events

Use the producer to log audit events:

```python
from apps.audit_logging.producer import log_audit_event

log_audit_event(
    user_id="user_123",
    username="john.doe",
    action="CREATE",
    object_type="Customer",
    object_id="cus_456",
    object_repr="John Smith",
    change_message="Created new customer",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    session_key="session_key_here"
)
```

### Querying Logs via API

The API provides two endpoints:

1. **Search endpoint** (`/api/audit-logs/search/`) - Returns summary fields for listing
2. **Detail endpoint** (`/api/audit-logs/detail/<log_id>/`) - Returns full log data

#### Search Logs (Summary)

The search endpoint returns a subset of fields suitable for list views:
- `log_id`, `timestamp`, `user_id`, `username`, `action`, `object_type`, `object_id`, `object_repr`

```bash
# Get recent logs
curl -X GET "http://localhost:8000/api/audit-logs/search/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by user
curl -X GET "http://localhost:8000/api/audit-logs/search/?user_id=user_123" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by date range
curl -X GET "http://localhost:8000/api/audit-logs/search/?start_time=2024-01-01T00:00:00Z&end_time=2024-12-31T23:59:59Z" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Free text search
curl -X GET "http://localhost:8000/api/audit-logs/search/?search_term=customer" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Pagination
curl -X GET "http://localhost:8000/api/audit-logs/search/?page_size=20&from_offset=40" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Log Detail

The detail endpoint returns all fields for a specific log:

```bash
# Get full details of a specific log
curl -X GET "http://localhost:8000/api/audit-logs/detail/<log_id>/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Example with a specific log_id
curl -X GET "http://localhost:8000/api/audit-logs/detail/550e8400-e29b-41d4-a716-446655440000/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

The detail endpoint returns all fields including:
- `log_id`, `timestamp`, `user_id`, `username`, `action`, `object_type`, `object_id`
- `object_repr`, `change_message`, `ip_address`, `user_agent`, `session_key`

## Data Lifecycle

1. **Real-time**: Logs are indexed to OpenSearch immediately for fast querying
2. **Batch Archive**: Logs are batched and uploaded to S3 in Parquet format
3. **Long-term**: S3 serves as the source of truth for historical data
4. **Search**: OpenSearch provides the last 12 months of data for querying

## Production Deployment

### Systemd Service (Recommended)

Create `/etc/systemd/system/audit-log-consumer.service`:

```ini
[Unit]
Description=Audit Log Consumer
After=network.target rabbitmq.service opensearch.service

[Service]
Type=simple
User=backend
WorkingDirectory=/path/to/backend
Environment="ENVIRONMENT=production"
ExecStart=/path/to/venv/bin/python manage.py consume_audit_logs
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable audit-log-consumer
sudo systemctl start audit-log-consumer
sudo systemctl status audit-log-consumer
```

### Monitoring

Monitor the consumer with:

```bash
# Check service status
sudo systemctl status audit-log-consumer

# View logs
sudo journalctl -u audit-log-consumer -f

# Check OpenSearch indices
curl -X GET "http://localhost:9200/_cat/indices/audit-logs-*?v"

# Check RabbitMQ stream
# Access RabbitMQ management UI at http://localhost:15672
```

## Troubleshooting

### Consumer not receiving messages

1. Check RabbitMQ stream plugin is enabled
2. Verify RabbitMQ connection settings in `.env`
3. Check RabbitMQ logs: `docker logs rabbitmq`

### OpenSearch indexing failures

1. Verify OpenSearch is running: `curl http://localhost:9200`
2. Check OpenSearch logs
3. Verify index mapping matches log structure

### S3 upload failures

1. Verify AWS credentials are correct
2. Check IAM permissions for S3 bucket
3. Verify bucket exists and is accessible
