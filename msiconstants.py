AWS_BUCKET_FILEADD = 'mcis3fladdnsb700'
AWS_BUCKET_NLPRES = 'mcis3nlpresnsb700'
AWS_SQS_QUEUE = 'mcisqsqnsb700'
KB = 1024
MB = 1024*KB
MAX_SIZE_IN_MB = 2
SUPPORTED_FILE_TYPES = {
    'application/pdf': 'pdf'
}
BATCH_SIZE = 100
THRESHOLD = 0.6
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(name)s %(asctime)s %(levelname)s %(filename)s %(lineno)s %(process)d %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        }
    },
    "handlers": {
        "runlogfile": {
            "class": "logging.FileHandler",
            "filename": "mcirunlog.txt",
            "formatter": "json",
            "level": "INFO",
        }
    },
    "loggers": {
        "": {
            "handlers": ["runlogfile"], 
            "level": "DEBUG"
        }
    },
}