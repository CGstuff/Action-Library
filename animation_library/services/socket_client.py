"""
Socket Client for Animation Library Desktop App

This module provides real-time communication with Blender via TCP socket.
It connects to the Blender addon's socket server for instant animation/pose application.

Usage:
    client = BlenderSocketClient()
    if client.connect():
        result = client.apply_animation(animation_id, animation_name, options)
        client.disconnect()

The client automatically falls back to file-based communication if the socket
server is not available.
"""

import socket
import json
import logging
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Socket connection configuration"""
    host: str = '127.0.0.1'
    port: int = 9876
    timeout: float = 5.0  # Connection timeout in seconds
    recv_timeout: float = 30.0  # Response timeout in seconds (increased for slow operations)


class BlenderSocketClient:
    """
    TCP Socket client for communicating with Blender addon.

    This client sends JSON commands to the Blender socket server
    and receives JSON responses.

    Thread Safety:
        This client is thread-safe. Uses RLock to prevent race conditions
        during connection check and reconnection.
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        """
        Initialize socket client.

        Args:
            config: Connection configuration. Uses defaults if not provided.
        """
        self.config = config or ConnectionConfig()
        self._socket: Optional[socket.socket] = None
        self._connected = False
        # Use RLock (reentrant lock) to allow same thread to acquire multiple times
        # This prevents race conditions when send_command() calls connect()
        self._lock = threading.RLock()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to Blender (thread-safe)"""
        with self._lock:
            return self._connected and self._socket is not None

    def connect(self) -> bool:
        """
        Connect to Blender socket server.

        Returns:
            True if connection successful, False otherwise.
        """
        with self._lock:
            if self._connected:
                return True

            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.config.timeout)
                self._socket.connect((self.config.host, self.config.port))
                self._connected = True
                logger.debug(f"Connected to Blender at {self.config.host}:{self.config.port}")
                return True
            except socket.timeout:
                logger.debug(f"Connection timeout to {self.config.host}:{self.config.port}")
                self._cleanup_socket()
                return False
            except ConnectionRefusedError:
                logger.debug("Connection refused - Blender socket server not running")
                self._cleanup_socket()
                return False
            except Exception as e:
                logger.debug(f"Connection error: {e}")
                self._cleanup_socket()
                return False

    def disconnect(self):
        """Disconnect from Blender socket server"""
        with self._lock:
            self._cleanup_socket()
            logger.debug("Disconnected from Blender")

    def _cleanup_socket(self):
        """Clean up socket resources"""
        self._connected = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def send_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a command to Blender and wait for response (thread-safe).

        Uses RLock to hold lock across check-and-reconnect sequence,
        preventing race conditions between multiple threads.

        Args:
            command: Command dictionary to send

        Returns:
            Response dictionary, or None if failed
        """
        with self._lock:
            # Check connection status - reconnect if needed (all under same lock)
            if not (self._connected and self._socket is not None):
                # Try to connect (RLock allows re-acquiring by same thread)
                if not self.connect():
                    return None

            # Now send the command
            return self._send_command_unlocked(command)

    def _send_command_unlocked(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Internal method to send command - must be called with lock held.

        Args:
            command: Command dictionary to send

        Returns:
            Response dictionary, or None if failed
        """
        try:
            # Send command as JSON with newline delimiter
            message = json.dumps(command) + '\n'
            logger.debug(f"Sending command: {command.get('type')}")
            self._socket.sendall(message.encode('utf-8'))
            logger.debug("Command sent, waiting for response...")

            # Set receive timeout
            self._socket.settimeout(self.config.recv_timeout)

            # Receive response
            buffer = ""
            while '\n' not in buffer:
                data = self._socket.recv(4096)
                if not data:
                    # Server closed connection
                    logger.warning("Server closed connection")
                    self._cleanup_socket()
                    return None
                buffer += data.decode('utf-8')
                logger.debug(f"Received {len(data)} bytes")

            # Parse JSON response
            response_str = buffer.split('\n')[0]
            response = json.loads(response_str)
            logger.debug(f"Response received: {response.get('status')}")
            return response

        except socket.timeout:
            logger.warning(f"Response timeout after {self.config.recv_timeout}s")
            # Don't cleanup on timeout - connection may still be valid
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON response: {e}")
            # Don't cleanup on parse error - connection may still be valid
            return None
        except BrokenPipeError:
            logger.warning("Broken pipe - connection lost")
            self._cleanup_socket()
            return None
        except ConnectionResetError:
            logger.warning("Connection reset by server")
            self._cleanup_socket()
            return None
        except OSError as e:
            logger.warning(f"Socket error: {e}")
            self._cleanup_socket()
            return None
        except Exception as e:
            logger.warning(f"Send error: {e}")
            self._cleanup_socket()
            return None

    def ping(self) -> bool:
        """
        Test connection to Blender.

        Returns:
            True if Blender responds, False otherwise
        """
        response = self.send_command({'type': 'ping'})
        return response is not None and response.get('status') == 'success'

    def apply_animation(
        self,
        animation_id: str,
        animation_name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply an animation to the active armature in Blender.

        Args:
            animation_id: UUID of the animation
            animation_name: Display name of the animation
            options: Apply options (apply_mode, mirror, reverse, etc.)

        Returns:
            Response dict with 'status' and 'message'
        """
        command = {
            'type': 'apply_animation',
            'animation_id': animation_id,
            'animation_name': animation_name,
            'options': options or {
                'apply_mode': 'NEW',
                'mirror': False,
                'reverse': False,
                'selected_bones_only': False,
                'use_slots': False
            }
        }

        response = self.send_command(command)

        if response is None:
            return {
                'status': 'error',
                'message': 'Failed to communicate with Blender'
            }

        return response

    def apply_pose(
        self,
        pose_id: str,
        pose_name: str,
        blend_file_path: str,
        mirror: bool = False
    ) -> Dict[str, Any]:
        """
        Apply a pose to the active armature in Blender.

        Args:
            pose_id: UUID of the pose
            pose_name: Display name of the pose
            blend_file_path: Path to the .blend file containing the pose
            mirror: If True, apply pose mirrored (swap L/R bones)

        Returns:
            Response dict with 'status' and 'message'
        """
        command = {
            'type': 'apply_pose',
            'pose_id': pose_id,
            'pose_name': pose_name,
            'blend_file_path': blend_file_path,
            'mirror': mirror
        }

        response = self.send_command(command)

        if response is None:
            return {
                'status': 'error',
                'message': 'Failed to communicate with Blender'
            }

        return response

    def get_armature_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the active armature in Blender.

        Returns:
            Dict with armature info, or None if failed
        """
        response = self.send_command({'type': 'get_armature_info'})

        if response and response.get('status') == 'success':
            return response.get('data')

        return None

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get Blender status information.

        Returns:
            Dict with Blender version, active object, mode, etc.
        """
        response = self.send_command({'type': 'get_status'})

        if response and response.get('status') == 'success':
            return response.get('data')

        return None

    def get_plugin_version(self) -> Optional[tuple]:
        """
        Get Blender plugin version.

        Returns:
            Tuple (major, minor, patch) or None if failed
        """
        response = self.send_command({'type': 'get_version'})

        if response and response.get('status') == 'success':
            data = response.get('data', {})
            version = data.get('version')
            if isinstance(version, list):
                return tuple(version)
            return version

        return None

    # ==================== POSE BLENDING ====================

    def blend_pose_start(
        self,
        pose_id: str,
        pose_name: str,
        blend_file_path: str
    ) -> Dict[str, Any]:
        """
        Start a pose blending session.

        Args:
            pose_id: UUID of the target pose
            pose_name: Display name of the pose
            blend_file_path: Path to the .blend file containing the pose

        Returns:
            Response dict with 'status' and 'message'
        """
        command = {
            'type': 'blend_pose_start',
            'pose_id': pose_id,
            'pose_name': pose_name,
            'blend_file_path': blend_file_path
        }

        response = self.send_command(command)

        if response is None:
            return {
                'status': 'error',
                'message': 'Failed to communicate with Blender'
            }

        return response

    def blend_pose(self, blend_factor: float, mirror: bool = False) -> Dict[str, Any]:
        """
        Update blend factor during a blending session.

        Args:
            blend_factor: Blend amount (0.0 = original, 1.0 = fully applied)
            mirror: Apply pose mirrored (swap L/R bones)

        Returns:
            Response dict with 'status' and current blend_factor
        """
        command = {
            'type': 'blend_pose',
            'blend_factor': max(0.0, min(1.0, blend_factor)),  # Clamp 0-1
            'mirror': mirror
        }

        response = self.send_command(command)

        if response is None:
            return {
                'status': 'error',
                'message': 'Failed to communicate with Blender'
            }

        return response

    def blend_pose_end(self, cancelled: bool = False, insert_keyframes: bool = False) -> Dict[str, Any]:
        """
        End the pose blending session.

        Args:
            cancelled: If True, restore original pose
            insert_keyframes: If True, insert keyframes for affected bones

        Returns:
            Response dict with 'status' and 'message'
        """
        command = {
            'type': 'blend_pose_end',
            'cancelled': cancelled,
            'insert_keyframes': insert_keyframes
        }

        response = self.send_command(command)

        if response is None:
            return {
                'status': 'error',
                'message': 'Failed to communicate with Blender'
            }

        return response


# Singleton instance
_socket_client_instance: Optional[BlenderSocketClient] = None


def get_socket_client() -> BlenderSocketClient:
    """
    Get global socket client singleton.

    Returns:
        Global BlenderSocketClient instance
    """
    global _socket_client_instance
    if _socket_client_instance is None:
        # Load port from settings
        try:
            from ..config import Config
            settings = Config.load_blender_settings()
            port = settings.get('socket_port', 9876)
        except Exception:
            port = 9876

        config = ConnectionConfig(port=port)
        _socket_client_instance = BlenderSocketClient(config)
    return _socket_client_instance


def try_socket_apply(
    animation_id: str,
    animation_name: str,
    options: Optional[Dict[str, Any]] = None,
    is_pose: bool = False,
    blend_file_path: Optional[str] = None,
    mirror: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Try to apply animation/pose via socket, returns None if socket unavailable.

    This is a convenience function that tries socket communication first
    and returns None if it fails, allowing the caller to fall back to
    file-based communication.

    Args:
        animation_id: UUID of the animation/pose
        animation_name: Display name
        options: Apply options (for animations)
        is_pose: True if this is a pose, False for animation
        blend_file_path: Path to blend file (required for poses)
        mirror: If True, apply mirrored (for poses)

    Returns:
        Response dict if successful, None if socket unavailable
    """
    client = get_socket_client()

    # Quick connection test
    if not client.is_connected:
        if not client.connect():
            return None

    if is_pose:
        if not blend_file_path:
            return {'status': 'error', 'message': 'blend_file_path required for poses'}
        return client.apply_pose(animation_id, animation_name, blend_file_path, mirror=mirror)
    else:
        return client.apply_animation(animation_id, animation_name, options)


__all__ = [
    'BlenderSocketClient',
    'ConnectionConfig',
    'get_socket_client',
    'try_socket_apply',
]
