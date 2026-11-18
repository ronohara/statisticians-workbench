import os
import time
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

# Anchored on the repository root — never on the working directory.
#
# This module is `backend/src/utils/logger.py`, so four `dirname` calls reach the
# repository root; that is the same place `main.py` writes `backend.log`, and the
# same rule: `scripts/start-backend.sh` `cd`s to the repo root, a developer may start
# from anywhere, and uvicorn's reloader watches the working directory.
#
# It was `./logs/` until 2026-11-10 — relative, and therefore inside whatever
# directory the process was started from. Started from `backend/`, those files landed
# in `backend/logs/`, inside the tree the reloader watches; a write there produced a
# `1 change detected` line, which (once the root logger's own file moved out on the
# same day) no longer feeds a loop, but which still put four log files in a place the
# watcher scans. Relative also meant the same logger wrote to different directories
# depending on where the backend was launched — `logs/dspy_utils.log` at the repo root
# and `backend/logs/llm_connection.log` existed side by side for exactly that reason.
_LOG_ROOT = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    ),
    "logs",
)


class Logger:
    def __init__(self, name: str, see_time: bool = False, console_log: bool = False, level: int = logging.INFO):
        self.is_dev = os.getenv("ENVIRONMENT", "development") == "development"
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if not self.is_dev:
            self.logger.addHandler(logging.NullHandler())
            return

        os.makedirs(_LOG_ROOT, exist_ok=True)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s" if see_time else "%(asctime)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler(os.path.join(_LOG_ROOT, f"{name}.log"), encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        if console_log:
            # Console handler with UTF-8 encoding
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            # Force UTF-8 encoding for console output
            if hasattr(console_handler.stream, 'reconfigure'):
                console_handler.stream.reconfigure(encoding='utf-8')
            self.logger.addHandler(console_handler)

    def log_message(self, message: str, level: int = logging.INFO):
        if not self.is_dev:
            return
        try:
            if level == logging.INFO:
                self.logger.info(message)
            elif level == logging.ERROR:
                self.logger.error(message)
            elif level == logging.WARNING:
                self.logger.warning(message)
            elif level == logging.DEBUG:
                self.logger.debug(message)
            else:
                self.logger.info(message)
        except UnicodeEncodeError:
            # Fallback: remove emoji characters if encoding fails
            safe_message = message.encode('ascii', 'ignore').decode('ascii')
            if level == logging.INFO:
                self.logger.info(safe_message)
            elif level == logging.ERROR:
                self.logger.error(safe_message)
            elif level == logging.WARNING:
                self.logger.warning(safe_message)
            elif level == logging.DEBUG:
                self.logger.debug(safe_message)
            else:
                self.logger.info(safe_message)

    def disable_logging(self):
        self.logger.disabled = True


def log_time(func):
    def wrapper(*args, **kwargs):
        # `ENVIRONMENT`, not `ENV`: this read `ENV` until 2026-11-18, a name nothing
        # in the tree sets, so it was always absent and always resolved to the
        # default — meaning the timing ran in every environment, including
        # production, while reading as though it were gated. It is the same
        # predicate `main.py:105` and `Logger.__init__` use, so there is one
        # definition of "development" rather than three.
        if os.getenv("ENVIRONMENT", "development") != "development":
            return func(*args, **kwargs)
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger = Logger(func.__name__ + "_time", see_time=True, level=logging.INFO)
        logger.log_message(f"Function: {func.__name__}, Execution time: {round(end_time - start_time, 5)} seconds")
        return result
    return wrapper


# Explicitly export Logger and log_time
__all__ = ["Logger", "log_time"]