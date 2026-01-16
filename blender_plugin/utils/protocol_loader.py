"""
Protocol Loader - Dynamically loads protocol from library/.schema/protocol/

This allows the Blender addon to use the same protocol schema as the desktop app
without needing a bundled copy that could get out of sync.
"""

import sys
import importlib.util
from pathlib import Path
from typing import Optional, Any

from .logger import get_logger
from ..preferences import get_library_path

logger = get_logger()

# Cache for loaded protocol module
_protocol_module = None
_protocol_load_attempted = False


def get_protocol_path() -> Optional[Path]:
    """Get the path to the protocol directory in the library."""
    library_path = get_library_path()
    if not library_path:
        return None

    protocol_path = Path(library_path) / '.schema' / 'protocol'
    if protocol_path.exists():
        return protocol_path

    return None


def load_protocol() -> Optional[Any]:
    """
    Load the protocol module from library/.schema/protocol/

    Returns:
        The protocol module, or None if not available
    """
    global _protocol_module, _protocol_load_attempted

    # Return cached module if already loaded
    if _protocol_module is not None:
        return _protocol_module

    # Don't retry if we already failed
    if _protocol_load_attempted:
        return None

    _protocol_load_attempted = True

    protocol_path = get_protocol_path()
    if not protocol_path:
        logger.debug("Protocol not found in library/.schema/protocol/")
        return None

    try:
        # Add protocol path to sys.path temporarily
        protocol_parent = str(protocol_path.parent)
        if protocol_parent not in sys.path:
            sys.path.insert(0, protocol_parent)

        # Load the protocol __init__.py
        init_path = protocol_path / '__init__.py'
        if not init_path.exists():
            logger.warning(f"Protocol __init__.py not found at {init_path}")
            return None

        spec = importlib.util.spec_from_file_location("protocol", init_path)
        if spec is None or spec.loader is None:
            logger.warning("Could not create module spec for protocol")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules['animation_library_protocol'] = module
        spec.loader.exec_module(module)

        _protocol_module = module
        logger.info(f"Loaded protocol from {protocol_path}")
        return module

    except Exception as e:
        logger.warning(f"Failed to load protocol from library: {e}")
        return None


def get_protocol_function(name: str) -> Optional[Any]:
    """
    Get a specific function/class from the protocol module.

    Args:
        name: Name of the function/class to get (e.g., 'validate_message')

    Returns:
        The function/class, or None if not available
    """
    protocol = load_protocol()
    if protocol is None:
        return None

    return getattr(protocol, name, None)


# Convenience functions that try protocol first, return None if unavailable
def validate_message(message: dict, message_type: str = None):
    """Validate a message using the protocol schema."""
    func = get_protocol_function('validate_message')
    if func:
        return func(message, message_type)
    return True, None  # No validation if protocol unavailable


def build_message(message_type: str, data: dict):
    """Build a message using the protocol schema."""
    func = get_protocol_function('build_message')
    if func:
        return func(message_type, data)
    # Fallback: just add type to data
    return {'type': message_type, **data}


# Constants - try to get from protocol, fall back to defaults
def get_constant(name: str, default: Any) -> Any:
    """Get a constant from the protocol, with fallback."""
    protocol = load_protocol()
    if protocol:
        return getattr(protocol, name, default)
    return default


# Common constants with fallbacks
QUEUE_DIR_NAME = property(lambda self: get_constant('QUEUE_DIR_NAME', '.queue'))
FALLBACK_QUEUE_DIR = property(lambda self: get_constant('FALLBACK_QUEUE_DIR', 'animation_library_queue'))
QUEUE_FILE_PATTERN = property(lambda self: get_constant('QUEUE_FILE_PATTERN', 'apply_*.json'))


def reload_protocol():
    """Force reload of protocol (call when library path changes)."""
    global _protocol_module, _protocol_load_attempted
    _protocol_module = None
    _protocol_load_attempted = False


__all__ = [
    'load_protocol',
    'get_protocol_function',
    'validate_message',
    'build_message',
    'get_constant',
    'reload_protocol',
    'get_protocol_path',
]
