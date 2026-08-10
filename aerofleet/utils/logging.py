"""
Logging configuration for Space Mission Architect.

Provides structured logging with JSON formatting, multiple handlers,
and context injection for better debugging and monitoring.
"""

import logging
import logging.handlers
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import os


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields from extra kwargs
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "mission_id"):
            log_data["mission_id"] = record.mission_id
        
        return json.dumps(log_data)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for better readability in terminal."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for console output."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format: [TIMESTAMP] LEVEL | module.function:line | message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        location = f"{record.module}.{record.funcName}:{record.lineno}"
        
        formatted = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} | "
            f"{location:30s} | {record.getMessage()}"
        )
        
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_json: bool = False,
    enable_console: bool = True
) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. If None, only console logging is enabled
        enable_json: Use JSON formatting for file logs
        enable_console: Enable console output
    
    Returns:
        Configured root logger
    """
    # Get root logger
    root_logger = logging.getLogger("aerofleet")
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console Handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(ColoredConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # File Handlers
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Main log file with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "aerofleet.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        
        if enable_json:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
                )
            )
        root_logger.addHandler(file_handler)
        
        # Error log file
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            JSONFormatter() if enable_json else
            logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
        )
        root_logger.addHandler(error_handler)
    
    # Prevent propagation to avoid duplicate logs
    root_logger.propagate = False
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(f"aerofleet.{name}")


# Context manager for adding context to logs
class LogContext:
    """Context manager for adding contextual information to logs."""
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self.old_factory = logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


# Initialize default logging on module import
_default_level = os.getenv("LOG_LEVEL", "INFO")
_log_dir = os.getenv("LOG_DIR", None)
_enable_json = os.getenv("LOG_JSON", "false").lower() == "true"

if _log_dir:
    setup_logging(
        level=_default_level,
        log_dir=Path(_log_dir),
        enable_json=_enable_json
    )
else:
    setup_logging(level=_default_level)
