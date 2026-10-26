import logging
import re

ACCESS_CODE_RE = re.compile(r"[0-9a-fA-F]{64}")


class RedactAccessCodes(logging.Filter):
    """Replace kingdom access codes in log messages before they are written."""

    def filter(self, record):
        record.msg = ACCESS_CODE_RE.sub("[redacted]", record.getMessage())
        record.args = ()
        return True
