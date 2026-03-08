"""
Logger Configuration Module

Sets up logging for the missing URL ingestion pipeline.
Logs to both console and file with proper formatting.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "missing_ingestion", log_dir: str = None) -> logging.Logger:
    """
    Configure logger with console and file handlers.
    
    Args:
        name: Logger name
        log_dir: Directory for log file (defaults to ./logs/)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger
    
    # Log directory
    if log_dir is None:
        log_dir = Path(__file__).parent / "logs"
    else:
        log_dir = Path(log_dir)
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log file path
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Formatter
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "missing_ingestion") -> logging.Logger:
    """
    Get logger instance by name.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
