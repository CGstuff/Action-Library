"""
Socket Listener

Processes queued socket commands on Blender's main thread using
``bpy.app.timers``.

IMPORTANT (auto-save):
    This used to run as a *permanent modal operator* (one that returned
    ``RUNNING_MODAL`` and never finished). Blender refuses to auto-save while
    any modal operator is running - it silently reschedules the auto-save
    timer instead. Because this listener never stopped, Blender's auto-save
    never fired for as long as the addon was enabled.

    ``bpy.app.timers`` do NOT block auto-save, so the queue is now drained from
    a timer callback instead. The operator classes are kept as thin wrappers
    for backwards compatibility (e.g. UI buttons / external ``bpy.ops`` calls).
"""

import bpy
from bpy.types import Operator


# Timer interval: 0.05s = 50ms = 20 checks per second (matches the previous
# modal timer cadence so command latency is unchanged).
SOCKET_TIMER_INTERVAL = 0.05        # while a client is connected or work is queued
SOCKET_TIMER_IDLE_INTERVAL = 0.5    # nothing connected - nothing can arrive

# Tracks whether the listener is meant to be running. The timer callback reads
# this to decide whether to reschedule itself or unregister.
_timer_running = False


def _socket_timer_tick():
    """Drain the socket command queue on the main thread.

    Returns the next interval to keep the timer alive, or ``None`` to
    unregister it.
    """
    if not _timer_running:
        return None  # Stop: unregister the timer

    try:
        from ..utils.socket_server import (process_command_queue,
                                           is_server_running, has_pending_work)
        if is_server_running():
            process_command_queue()
            # Tick fast only when it can achieve something. With no client
            # connected nothing can arrive, so waking 20x a second is pure
            # overhead - and a connecting client makes the very next tick fast.
            if not has_pending_work():
                return SOCKET_TIMER_IDLE_INTERVAL
    except Exception:
        # Never let an exception kill the timer - keep listening.
        pass

    return SOCKET_TIMER_INTERVAL


def is_listener_running() -> bool:
    """Check if the socket listener timer is active."""
    return _timer_running


def start_listener():
    """Start draining the socket queue via a main-thread timer.

    Idempotent: safe to call repeatedly and after a .blend file load (the
    timer is registered as persistent, so it survives file loads; the
    registration guard prevents duplicates either way).
    """
    global _timer_running
    _timer_running = True

    if not bpy.app.timers.is_registered(_socket_timer_tick):
        bpy.app.timers.register(
            _socket_timer_tick,
            first_interval=0.0,
            persistent=True,
        )


def stop_listener():
    """Stop the socket listener timer."""
    global _timer_running
    _timer_running = False

    if bpy.app.timers.is_registered(_socket_timer_tick):
        try:
            bpy.app.timers.unregister(_socket_timer_tick)
        except (ValueError, RuntimeError):
            # Already unregistered (e.g. by a file load) - nothing to do.
            pass


class ANIMLIB_OT_start_socket_listener(Operator):
    """Start the socket command listener"""
    bl_idname = "animlib.start_socket_listener"
    bl_label = "Start Socket Listener"
    bl_description = "Start listening for commands from desktop app"

    def execute(self, context):
        start_listener()
        return {'FINISHED'}


class ANIMLIB_OT_stop_socket_listener(Operator):
    """Stop the socket listener"""
    bl_idname = "animlib.stop_socket_listener"
    bl_label = "Stop Socket Listener"
    bl_description = "Stop listening for commands"

    def execute(self, context):
        stop_listener()
        return {'FINISHED'}


# Registration
classes = [
    ANIMLIB_OT_start_socket_listener,
    ANIMLIB_OT_stop_socket_listener,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    # Ensure the timer is stopped before classes go away.
    stop_listener()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


__all__ = [
    'ANIMLIB_OT_start_socket_listener',
    'ANIMLIB_OT_stop_socket_listener',
    'is_listener_running',
    'start_listener',
    'stop_listener',
    'register',
    'unregister',
]
