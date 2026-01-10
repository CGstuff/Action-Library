"""
Socket Listener Modal Operator

Uses a modal timer to process socket commands on the main thread.
This approach is more reliable than bpy.app.timers.
"""

import bpy
from bpy.types import Operator


class ANIMLIB_OT_start_socket_listener(Operator):
    """Start the socket command listener"""
    bl_idname = "animlib.start_socket_listener"
    bl_label = "Start Socket Listener"
    bl_description = "Start listening for commands from desktop app"

    _timer = None
    _is_running = False

    def modal(self, context, event):
        if not ANIMLIB_OT_start_socket_listener._is_running:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # Process any queued socket commands
            from ..utils.socket_server import process_command_queue, is_server_running
            if is_server_running():
                process_command_queue()

        return {'PASS_THROUGH'}

    def execute(self, context):
        if ANIMLIB_OT_start_socket_listener._is_running:
            return {'CANCELLED'}

        wm = context.window_manager
        # Timer interval of 0.05 = 50ms = 20 checks per second
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)

        ANIMLIB_OT_start_socket_listener._is_running = True

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        ANIMLIB_OT_start_socket_listener._is_running = False


class ANIMLIB_OT_stop_socket_listener(Operator):
    """Stop the socket listener"""
    bl_idname = "animlib.stop_socket_listener"
    bl_label = "Stop Socket Listener"
    bl_description = "Stop listening for commands"

    def execute(self, context):
        ANIMLIB_OT_start_socket_listener._is_running = False
        return {'FINISHED'}


def is_listener_running() -> bool:
    """Check if the socket listener is running"""
    return ANIMLIB_OT_start_socket_listener._is_running


def start_listener():
    """Start the socket listener operator"""
    if not is_listener_running():
        try:
            bpy.ops.animlib.start_socket_listener()
        except RuntimeError:
            try:
                bpy.ops.animlib.start_socket_listener('INVOKE_DEFAULT')
            except Exception:
                pass


def stop_listener():
    """Stop the socket listener"""
    if is_listener_running():
        bpy.ops.animlib.stop_socket_listener()


# Registration
classes = [
    ANIMLIB_OT_start_socket_listener,
    ANIMLIB_OT_stop_socket_listener,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    ANIMLIB_OT_start_socket_listener._is_running = False
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
