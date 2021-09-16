"""Main analysis package"""
from functools import wraps
from pathlib import Path

__version__ = "0.1.0"
ROOT_DIR = Path(__file__).resolve().parents[1]


def log_program(task_name, timeit=False):
    def decorator(orig_func):
        import logging
        import coloredlogs

        if timeit:
            import time

        log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(level=logging.INFO, format=log_fmt)
        logger = logging.getLogger(__name__)
        coloredlogs.install()

        @wraps(orig_func)
        def wrapper(*args, **kwargs):
            logger.info(task_name)
            if timeit:
                t1 = time.time()
            result = orig_func(*args, **kwargs)
            logger.info("Done!")
            if timeit:
                t2 = time.time() - t1
                logger.info(f"Task {orig_func.__name__} finished in {t2//3600}h {(t2//60)%60}min and {t2%60:.4f}s")
            return result

        return wrapper

    return decorator
