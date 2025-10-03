from .base import config

RABBITMQ_STREAM_HOST = config("RABBITMQ_STREAM_HOST", default="localhost")
RABBITMQ_STREAM_PORT = config("RABBITMQ_STREAM_PORT", default=5552, cast=int)
RABBITMQ_STREAM_USER = config("RABBITMQ_STREAM_USER", default="guest")
RABBITMQ_STREAM_PASSWORD = config("RABBITMQ_STREAM_PASSWORD", default="guest")
RABBITMQ_STREAM_VHOST = config("RABBITMQ_STREAM_VHOST", default="/")
RABBITMQ_STREAM_NAME = config("RABBITMQ_STREAM_NAME", default="audit_logs_stream")
