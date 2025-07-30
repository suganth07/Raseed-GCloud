import logging
import structlog
from typing import Any, Dict


def configure_logging(debug: bool = False) -> None:
    """Configure structured logging for the application."""
    
    # Set log level
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger instance for this class."""
        return get_logger(self.__class__.__name__)
    
    def log_operation(self, operation: str, **kwargs: Any) -> None:
        """Log an operation with context."""
        self.logger.info(f"Operation: {operation}", **kwargs)
    
    def log_error(self, operation: str, error: Exception, **kwargs: Any) -> None:
        """Log an error with context."""
        self.logger.error(
            f"Operation failed: {operation}",
            error=str(error),
            error_type=type(error).__name__,
            **kwargs
        )