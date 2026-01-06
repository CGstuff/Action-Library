"""
Centralized logging configuration for Animation Library v2
"""
import logging
import sys
from pathlib import Path
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtCore import QObject, pyqtSignal, Qt


class LoggingConfig:
    """Central logging configuration"""

    _initialized = False
    _log_file_path = None
    _widget_handler = None

    @classmethod
    def setup_logging(cls, log_dir: Path):
        """Setup logging system"""
        if cls._initialized:
            return

        log_dir.mkdir(parents=True, exist_ok=True)
        cls._log_file_path = log_dir / "animation_library.log"

        # Root logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # File handler
        file_handler = logging.FileHandler(cls._log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler (for terminal output)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        cls._initialized = True
        logger.info("Logging system initialized")

    @classmethod
    def add_widget_handler(cls, text_widget: QPlainTextEdit, log_level="DEBUG"):
        """Add a QPlainTextEdit as a log handler"""
        handler = QtLogHandler(text_widget)
        handler.setLevel(getattr(logging, log_level))
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        handler.setFormatter(formatter)

        logger = logging.getLogger()
        logger.addHandler(handler)

        cls._widget_handler = handler
        return handler

    @classmethod
    def remove_widget_handler(cls):
        """Remove the widget handler"""
        if cls._widget_handler:
            logger = logging.getLogger()
            logger.removeHandler(cls._widget_handler)
            cls._widget_handler = None

    @classmethod
    def get_logger(cls, name: str):
        """Get a logger instance"""
        return logging.getLogger(name)

    @classmethod
    def get_log_file_path(cls) -> Path:
        """Get the log file path"""
        return cls._log_file_path


class QtLogHandler(logging.Handler, QObject):
    """Custom logging handler that emits to a Qt text widget"""

    log_signal = pyqtSignal(str)

    def __init__(self, text_widget: QPlainTextEdit):
        logging.Handler.__init__(self)
        QObject.__init__(self)

        self.text_widget = text_widget
        self.log_signal.connect(self.append_log, Qt.ConnectionType.QueuedConnection)

    def emit(self, record):
        """Emit a log record"""
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except Exception:
            self.handleError(record)

    def append_log(self, message: str):
        """Append log message to widget (thread-safe)"""
        self.text_widget.appendPlainText(message)


__all__ = ['LoggingConfig']
