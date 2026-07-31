import logging

import logstash
from django.conf import settings
from loguru import logger as loguru_logger


def initialize_logstash(loglevel=logging.DEBUG, **kwargs):
    logger = loguru_logger
    if settings.DEBUG:
        logger.add("logfile.log", rotation="100 MB")

    return logger
