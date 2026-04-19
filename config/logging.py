import json
import logging
import uuid


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'time': self.formatTime(record),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
        }
        return json.dumps(log_record)


class RequestIDFilter(logging.Filter):
    """Add a request_id to log records."""

    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = str(uuid.uuid4())[:8]
        return True
