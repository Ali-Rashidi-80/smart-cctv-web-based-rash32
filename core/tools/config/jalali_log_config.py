# JalaliFormatter is defined in core.tools.jalali_formatter

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "jalali": {
            "()": "core.tools.jalali_formatter.JalaliFormatter",
            "fmt": "%(asctime)s - %(levelname)s - %(message)s\n"
        },
        "jalali_file": {
            "()": "core.tools.jalali_formatter.JalaliFileFormatter",
            "fmt": "%(asctime)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "formatter": "jalali",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "formatter": "jalali_file",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8"
        },
        "error_file": {
            "formatter": "jalali_file",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/error.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
            "level": "ERROR"
        }
    },
    "loggers": {
        "": {
            "handlers": ["console", "file", "error_file"], 
            "level": "INFO",
            "propagate": False
        },
        "uvicorn": {
            "handlers": ["console", "file"], 
            "level": "WARNING", 
            "propagate": False
        },
        "uvicorn.error": {
            "handlers": ["console", "file"], 
            "level": "WARNING", 
            "propagate": False
        },
        "uvicorn.access": {
            "handlers": ["console", "file"], 
            "level": "ERROR", 
            "propagate": False
        },
        "fastapi": {
            "handlers": ["console", "file"], 
            "level": "WARNING", 
            "propagate": False
        },
        "app": {
            "handlers": ["console", "file", "error_file"], 
            "level": "INFO", 
            "propagate": False
        },
        "db": {
            "handlers": ["console", "file", "error_file"], 
            "level": "INFO", 
            "propagate": False
        },
        "asyncio": {
            "handlers": ["file"], 
            "level": "ERROR", 
            "propagate": False
        },
        "websockets": {
            "handlers": ["file"], 
            "level": "WARNING", 
            "propagate": False
        }
    }
} 