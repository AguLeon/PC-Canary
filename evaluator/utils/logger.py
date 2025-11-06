import os
import logging


def setup_logger(name: str, log_dir: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger.

    Args:
        name: The name of the logger.
        log_dir: Directory where log files will be stored.
        level: Logging level.

    Returns:
        logging.Logger: A configured logger instance.
    """
    # Ensure the log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Create the logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Create file handler
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Set log format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
