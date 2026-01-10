"""Utility functions for Animation Library Blender addon"""

from .logger import get_logger, set_debug_mode
from .queue_client import animation_queue_client, AnimationLibraryQueueClient

# Socket server functions (lazy import to avoid import-time side effects)
_socket_commands_registered = False

def start_socket_server():
    """Start the socket server for real-time communication with desktop app"""
    global _socket_commands_registered
    from .socket_server import start_server

    # Register command handlers only once
    if not _socket_commands_registered:
        from .socket_commands import register_socket_commands
        register_socket_commands()
        _socket_commands_registered = True

    return start_server()


def stop_socket_server():
    """Stop the socket server"""
    from .socket_server import stop_server
    stop_server()


def is_socket_server_running():
    """Check if socket server is running"""
    from .socket_server import is_server_running
    return is_server_running()


__all__ = [
    'get_logger',
    'set_debug_mode',
    'animation_queue_client',
    'AnimationLibraryQueueClient',
    'start_socket_server',
    'stop_socket_server',
    'is_socket_server_running',
]
