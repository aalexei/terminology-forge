import logging
import sys
from loguru import logger
from core.config import config

# Adapted from
# https://medium.com/@muh.bazm/how-i-unified-logging-in-fastapi-with-uvicorn-and-loguru-6813058c48fc
    
class InterceptHandler(logging.Handler):
    '''
    Intercept standard logging
    '''
    def emit(self, record):
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller to get correct stack depth
        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging():
    '''
    Setup the logging using loguru
    '''
    # Remove existing logging handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(handlers=[InterceptHandler()], level=config.loglevel)

    # Remove default logger
    logger.remove()
    # handle logs and output to sys.stderr and file
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>|<level>{level: <8}</level>|<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>|<level>{message}</level>"

    # Stderr
    logger.add(
        sys.stderr,
        level=config.loglevel,
        backtrace=True,
        diagnose=True,
        colorize=True,
        enqueue=True, # safe concurrent logging
        format=log_format,
    )
    # Also mirror to file
    logger.add(
        config.logfile,
        rotation="10 MB",
        compression="zip",
        level=config.loglevel,
        backtrace=True,
        colorize=False,
        diagnose=True,
        enqueue=True, # safe concurrent logging
        format=log_format,
    )

    # Propagate Uvicorn and FastAPI up to the root logger 
    loggers = ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "asyncio", "starlette")
    for logger_name in loggers:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = []
        logging_logger.propagate = True

 
