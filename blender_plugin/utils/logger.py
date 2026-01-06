"""
Logging system for Animation Library Blender Addon

Provides a Blender-compatible logging interface that supports:
- Console output for debugging
- Blender operator reporting for user feedback
- Debug mode toggle via addon preferences
"""

import bpy
from typing import Optional


class AddonLogger:
    """
    Logger for Blender addon that integrates with Blender's reporting system

    Usage:
        from .logger import get_logger

        logger = get_logger()
        logger.info("Animation saved successfully")
        logger.error("Failed to save animation")
        logger.debug("Detailed debug information")  # Only shown if debug mode enabled
    """

    def __init__(self, addon_name: str = "Animation Library"):
        self.addon_name = addon_name
        self._debug_mode = False

    @property
    def debug_mode(self) -> bool:
        """Get debug mode from addon preferences"""
        try:
            # Try to get debug mode from preferences
            addon_prefs = bpy.context.preferences.addons.get(__package__.split('.')[0])
            if addon_prefs and hasattr(addon_prefs.preferences, 'debug_mode'):
                return addon_prefs.preferences.debug_mode
        except:
            pass
        return self._debug_mode

    @debug_mode.setter
    def debug_mode(self, value: bool):
        """Set debug mode"""
        self._debug_mode = value

    def _log(self, level: str, message: str, operator: Optional[bpy.types.Operator] = None):
        """
        Internal logging method

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            message: Log message
            operator: Optional Blender operator for reporting to user
        """
        # Always print to console if debug mode or if it's an error/warning
        if self.debug_mode or level in ('ERROR', 'WARNING'):
            prefix = f"[{self.addon_name}] {level}:"
            print(f"{prefix} {message}")

        # Report to operator if available (shows in Blender UI)
        if operator and hasattr(operator, 'report'):
            report_type = {'INFO', 'WARNING', 'ERROR'}.intersection({level})
            if report_type:
                operator.report(report_type, message)

    def info(self, message: str, operator: Optional[bpy.types.Operator] = None):
        """Log info message"""
        self._log('INFO', message, operator)

    def warning(self, message: str, operator: Optional[bpy.types.Operator] = None):
        """Log warning message"""
        self._log('WARNING', message, operator)

    def error(self, message: str, operator: Optional[bpy.types.Operator] = None):
        """Log error message"""
        self._log('ERROR', message, operator)

    def debug(self, message: str):
        """Log debug message (only shown if debug mode enabled)"""
        if self.debug_mode:
            self._log('DEBUG', message, None)


# Global logger instance
_logger: Optional[AddonLogger] = None


def get_logger() -> AddonLogger:
    """
    Get the global addon logger instance

    Returns:
        AddonLogger instance
    """
    global _logger
    if _logger is None:
        _logger = AddonLogger()
    return _logger


def set_debug_mode(enabled: bool):
    """
    Enable or disable debug mode

    Args:
        enabled: True to enable debug logging
    """
    logger = get_logger()
    logger.debug_mode = enabled
