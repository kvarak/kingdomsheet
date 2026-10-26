import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
timeout = 30
accesslog = "-"
errorlog = "-"

# Access logs contain request paths, which include sharing-link codes.
# The filter redacts them before they reach stdout.
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_access_codes": {"()": "kingdoms.redaction.RedactAccessCodes"},
    },
    "formatters": {
        "plain": {"format": "%(asctime)s [%(process)d] [%(levelname)s] %(message)s"},
        "access": {"format": "%(message)s"},
    },
    "handlers": {
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stderr",
            "filters": ["redact_access_codes"],
        },
        "access_console": {
            "class": "logging.StreamHandler",
            "formatter": "access",
            "stream": "ext://sys.stdout",
            "filters": ["redact_access_codes"],
        },
    },
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["error_console"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_console"],
            "propagate": False,
        },
    },
    "root": {"level": "INFO", "handlers": ["error_console"]},
}
