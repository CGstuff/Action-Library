"""
Socket Server for Animation Library - Real-time Blender Communication

This module implements a TCP socket server that allows the desktop app
to instantly trigger actions in Blender without file-based polling.

Architecture:
    [ Desktop App ]  ─── TCP Socket ───▶  [ Blender Addon Server ]
         Client                              Listener

The server runs on a background thread, but all bpy operations are
queued and executed on Blender's main thread via bpy.app.timers.

Protocol:
    - JSON messages over TCP
    - Each message ends with newline delimiter
    - Commands are processed immediately upon receipt

Message Format:
    {
        "type": "apply_animation" | "apply_pose" | "ping",
        "animation_id": "uuid",
        "animation_name": "Walk Cycle",
        "options": {...}
    }

Response Format:
    {
        "status": "success" | "error",
        "message": "...",
        "data": {...}
    }
"""

import bpy
import socket
import threading
import queue
import json
import os
import time
from typing import Optional, Dict, Any, Callable, Set
from ..utils.logger import get_logger

logger = get_logger()

# Configuration
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 9876
SOCKET_TIMEOUT = 2.0  # Seconds
BUFFER_SIZE = 4096
QUEUE_TIME_BUDGET_MS = 16  # Max time per timer tick for light commands
MAX_HEAVY_COMMANDS_PER_TICK = 1  # Heavy commands are file I/O bound

# Heavy command types that should be limited per tick (file I/O operations)
HEAVY_COMMAND_TYPES: Set[str] = {'apply_animation', 'apply_pose', 'blend_pose_end'}

# Global state
_server_socket: Optional[socket.socket] = None
_server_thread: Optional[threading.Thread] = None
_client_threads: list = []
_command_queue: queue.Queue = queue.Queue()
_response_queues: Dict[str, queue.Queue] = {}  # Per-client response queues
_keep_running = False
_is_initialized = False
_timer_tick_count = 0  # Debug counter

# Command handlers registry
_command_handlers: Dict[str, Callable] = {}


def register_command_handler(command_type: str, handler: Callable):
    """
    Register a handler function for a command type.

    Args:
        command_type: The 'type' field value in incoming messages
        handler: Function that takes (command_data, client_id) and returns response dict
    """
    _command_handlers[command_type] = handler
    logger.debug(f"Registered command handler for '{command_type}'")


def get_server_port() -> int:
    """Get server port from preferences, environment, or default"""
    # First check environment variable (for advanced users)
    env_port = os.environ.get('ANIMLIB_SOCKET_PORT')
    if env_port:
        return int(env_port)

    # Then check addon preferences
    try:
        addon_name = __name__.split('.')[0]
        prefs = bpy.context.preferences.addons.get(addon_name)
        if prefs and hasattr(prefs.preferences, 'socket_port'):
            return prefs.preferences.socket_port
    except:
        pass

    return DEFAULT_PORT


def get_server_host() -> str:
    """Get server host from environment or default"""
    return os.environ.get('ANIMLIB_SOCKET_HOST', DEFAULT_HOST)


def is_server_running() -> bool:
    """Check if socket server is running"""
    return _keep_running and _server_thread is not None and _server_thread.is_alive()


def get_connected_clients_count() -> int:
    """Get the number of currently connected clients"""
    if not is_server_running():
        return 0
    # Count active client threads
    return sum(1 for t in _client_threads if t.is_alive())


def start_server(host: Optional[str] = None, port: Optional[int] = None) -> bool:
    """
    Start the TCP socket server.

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to bind to (default: 9876)

    Returns:
        True if server started successfully
    """
    global _server_socket, _server_thread, _keep_running, _is_initialized

    if is_server_running():
        logger.info("Socket server already running")
        return True

    host = host or get_server_host()
    port = port or get_server_port()

    _keep_running = True

    try:
        _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow port reuse to avoid "Address already in use" errors
        _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _server_socket.bind((host, port))
        _server_socket.listen(5)  # Queue up to 5 connections
        _server_socket.settimeout(SOCKET_TIMEOUT)

        _server_thread = threading.Thread(
            target=_accept_connections,
            name="AnimLib-SocketServer",
            daemon=False  # Not daemon - we want proper cleanup
        )
        _server_thread.start()

        _is_initialized = True
        # Note: Timer is now handled by modal operator in socket_operator.py
        logger.info(f"Socket server started on {host}:{port}")
        return True

    except OSError as e:
        if e.errno == 10048 or 'Address already in use' in str(e):
            # Port already in use - try to find an available port
            logger.warning(f"Port {port} in use, trying to find available port...")
            available_port = _find_available_port(port + 1)
            if available_port:
                return start_server(host, available_port)
            else:
                logger.error("No available ports found")
                return False
        else:
            logger.error(f"Failed to start socket server: {e}")
            return False
    except Exception as e:
        logger.error(f"Failed to start socket server: {e}")
        return False


def _find_available_port(start_port: int, max_attempts: int = 100) -> Optional[int]:
    """Find first available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((get_server_host(), port))
            s.close()
            return port
        except OSError:
            continue
    return None


def _accept_connections():
    """
    Accept client connections (runs in background thread).

    This function runs in an infinite loop until _keep_running is False.
    Each accepted connection spawns a new client handler thread.
    """
    global _client_threads

    logger.debug("Socket server accepting connections...")

    while _keep_running:
        try:
            client_socket, addr = _server_socket.accept()
            client_id = f"{addr[0]}:{addr[1]}"

            logger.info(f"Client connected: {client_id}")

            # Create response queue for this client
            _response_queues[client_id] = queue.Queue()

            # Handle client in separate thread
            client_thread = threading.Thread(
                target=_handle_client,
                args=(client_socket, client_id),
                name=f"AnimLib-Client-{client_id}",
                daemon=False
            )
            client_thread.start()
            _client_threads.append(client_thread)

            # Clean up finished threads
            _client_threads = [t for t in _client_threads if t.is_alive()]

        except socket.timeout:
            # Timeout is expected - just continue loop
            continue
        except OSError as e:
            if _keep_running:
                logger.error(f"Accept error: {e}")
            break
        except Exception as e:
            if _keep_running:
                logger.error(f"Unexpected accept error: {e}")


def _handle_client(client_socket: socket.socket, client_id: str):
    """
    Handle individual client connection (runs in client thread).

    Receives JSON commands and queues them for main thread execution.
    Sends responses back to client.
    """
    buffer = ""

    try:
        client_socket.settimeout(1.0)

        while _keep_running:
            try:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    # Client disconnected
                    logger.info(f"Client {client_id} disconnected")
                    break

                # Accumulate data in buffer
                buffer += data.decode('utf-8')

                # Process complete messages (newline-delimited JSON)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    message = message.strip()

                    if not message:
                        continue

                    try:
                        command = json.loads(message)
                        logger.debug(f"Received command from {client_id}: {command.get('type')}")

                        # Handle ping immediately (no main thread needed)
                        if command.get('type') == 'ping':
                            response = {'status': 'success', 'message': 'pong'}
                            _send_response(client_socket, response)
                            continue

                        # Queue command for main thread execution
                        _command_queue.put({
                            'command': command,
                            'client_id': client_id,
                            'client_socket': client_socket
                        })

                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from {client_id}: {e}")
                        _send_response(client_socket, {
                            'status': 'error',
                            'message': f'Invalid JSON: {e}'
                        })

            except socket.timeout:
                # Check for responses to send
                try:
                    response_queue = _response_queues.get(client_id)
                    if response_queue:
                        while not response_queue.empty():
                            response = response_queue.get_nowait()
                            _send_response(client_socket, response)
                except queue.Empty:
                    pass
                continue

    except Exception as e:
        logger.error(f"Error handling client {client_id}: {e}")
    finally:
        client_socket.close()
        # Clean up response queue
        if client_id in _response_queues:
            del _response_queues[client_id]


def _send_response(client_socket: socket.socket, response: dict):
    """Send JSON response to client"""
    try:
        message = json.dumps(response) + '\n'
        client_socket.sendall(message.encode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to send response: {e}")


def process_command_queue():
    """
    Process queued commands on main thread.
    Called by the modal operator timer.

    Uses time budget for light commands and limits heavy commands
    to prevent blocking Blender's UI.
    """
    global _timer_tick_count
    _timer_tick_count += 1

    try:
        if not _keep_running:
            return

        start_time = time.perf_counter()
        heavy_commands_processed = 0

        # Process commands with time awareness
        while True:
            # Check time budget for non-heavy commands
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            try:
                item = _command_queue.get_nowait()
                command = item['command']
                client_id = item['client_id']
                client_socket = item['client_socket']

                command_type = command.get('type', 'unknown')
                is_heavy = command_type in HEAVY_COMMAND_TYPES

                # Limit heavy commands per tick to keep UI responsive
                if is_heavy:
                    if heavy_commands_processed >= MAX_HEAVY_COMMANDS_PER_TICK:
                        # Re-queue for next tick
                        _command_queue.put(item)
                        logger.debug(f"Deferred heavy command '{command_type}' to next tick")
                        break
                    heavy_commands_processed += 1
                else:
                    # For light commands, check time budget
                    if elapsed_ms >= QUEUE_TIME_BUDGET_MS and not _command_queue.empty():
                        # Re-queue for next tick
                        _command_queue.put(item)
                        logger.debug(f"Time budget exceeded, deferring '{command_type}'")
                        break

                logger.debug(f"Processing command: {command_type}")

                # Execute command handler
                response = _execute_command(command, client_id)

                # Send response back to client
                try:
                    _send_response(client_socket, response)
                except Exception as e:
                    logger.error(f"Failed to send response: {e}")

            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error processing command: {e}")

    except Exception as e:
        logger.error(f"Queue processing error: {e}")


def _execute_command(command: dict, client_id: str) -> dict:
    """
    Execute a command and return response.

    This runs on the main thread and can safely use bpy operations.
    """
    command_type = command.get('type', 'unknown')

    # Check for registered handler
    handler = _command_handlers.get(command_type)
    if handler:
        try:
            return handler(command, client_id)
        except Exception as e:
            logger.error(f"Command handler error for '{command_type}': {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'message': f'Handler error: {str(e)}'
            }

    # Built-in commands
    if command_type == 'get_status':
        return {
            'status': 'success',
            'data': {
                'blender_version': bpy.app.version_string,
                'active_object': bpy.context.active_object.name if bpy.context.active_object else None,
                'mode': bpy.context.mode
            }
        }

    return {
        'status': 'error',
        'message': f'Unknown command type: {command_type}'
    }


def stop_server():
    """Stop the socket server and clean up resources"""
    global _keep_running, _server_socket, _server_thread, _client_threads

    if not _is_initialized:
        return

    logger.info("Stopping socket server...")
    _keep_running = False

    # Close server socket
    if _server_socket:
        try:
            _server_socket.close()
        except Exception as e:
            logger.debug(f"Error closing server socket: {e}")
        _server_socket = None

    # Wait for server thread
    if _server_thread and _server_thread.is_alive():
        _server_thread.join(timeout=3.0)
        if _server_thread.is_alive():
            logger.warning("Server thread did not terminate cleanly")
    _server_thread = None

    # Wait for client threads
    for thread in _client_threads:
        if thread.is_alive():
            thread.join(timeout=1.0)
    _client_threads.clear()

    # Clear queues
    _response_queues.clear()
    while not _command_queue.empty():
        try:
            _command_queue.get_nowait()
        except queue.Empty:
            break

    logger.info("Socket server stopped")


def send_to_client(client_id: str, message: dict):
    """
    Queue a message to be sent to a specific client.

    Args:
        client_id: The client identifier (host:port)
        message: Dict to send as JSON
    """
    response_queue = _response_queues.get(client_id)
    if response_queue:
        response_queue.put(message)
    else:
        logger.warning(f"No response queue for client {client_id}")


# Cleanup handlers
def _on_blender_quit():
    """Called when Blender is quitting"""
    stop_server()


# Module exports
__all__ = [
    'start_server',
    'stop_server',
    'is_server_running',
    'register_command_handler',
    'send_to_client',
    'get_server_port',
    'get_server_host',
    'process_command_queue',
]
