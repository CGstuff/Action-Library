import bpy
from bpy.utils import register_class, unregister_class
from bpy.app.handlers import persistent

from .AL_apply_animation import (
    ANIMLIB_OT_apply_animation,
    ANIMLIB_OT_check_apply_queue,
    start_queue_poll_timer,
    stop_queue_poll_timer,
)
from .AL_capture_animation import ANIMLIB_OT_capture_animation, ANIMLIB_OT_cancel_versioning
from .AL_capture_pose import ANIMLIB_OT_capture_pose
from .AL_version_choice import ANIMLIB_OT_version_choice
from .AL_launch_desktop_app import ANIMLIB_OT_launch_desktop_app
from .AL_slots_manager import (
    ANIMLIB_OT_delete_slot,
    ANIMLIB_OT_activate_slot,
    ANIMLIB_OT_duplicate_slot,
    ANIMLIB_OT_toggle_slot_selection,
    ANIMLIB_OT_select_all_slots,
    ANIMLIB_OT_deselect_all_slots,
    ANIMLIB_OT_merge_slots,
)
from .AL_create_library_folder import ANIMLIB_OT_create_library_folder
from .AL_update_preview import ANIMLIB_OT_update_preview
from .AL_socket_listener import (
    ANIMLIB_OT_start_socket_listener,
    ANIMLIB_OT_stop_socket_listener,
    start_listener as start_socket_listener,
    stop_listener as stop_socket_listener,
)


classes = (
    ANIMLIB_OT_apply_animation,
    ANIMLIB_OT_check_apply_queue,
    ANIMLIB_OT_capture_animation,
    ANIMLIB_OT_capture_pose,
    ANIMLIB_OT_cancel_versioning,
    ANIMLIB_OT_version_choice,
    ANIMLIB_OT_launch_desktop_app,
    ANIMLIB_OT_delete_slot,
    ANIMLIB_OT_activate_slot,
    ANIMLIB_OT_duplicate_slot,
    ANIMLIB_OT_toggle_slot_selection,
    ANIMLIB_OT_select_all_slots,
    ANIMLIB_OT_deselect_all_slots,
    ANIMLIB_OT_merge_slots,
    ANIMLIB_OT_create_library_folder,
    ANIMLIB_OT_update_preview,
    ANIMLIB_OT_start_socket_listener,
    ANIMLIB_OT_stop_socket_listener,
)

def _safe_register(cls):
    try:
        register_class(cls)
    except ValueError:
        # stale or duplicate class object: clean and retry
        try:
            unregister_class(cls)
        except Exception:
            pass
        register_class(cls)

def _safe_unregister(cls):
    try:
        unregister_class(cls)
    except Exception:
        pass

__OPS_REGISTERED = False
_load_handler_added = False


@persistent
def _on_load_post(dummy):
    """Handler called after a blend file is loaded - start socket listener"""
    _start_socket_system()


def _start_socket_system():
    """Start the socket server and listener"""
    from ..utils import start_socket_server, is_socket_server_running

    # Start socket server if not running
    if not is_socket_server_running():
        socket_started = start_socket_server()
        if not socket_started:
            start_queue_poll_timer()
            return

    # Start the modal listener operator
    try:
        if bpy.context.window:
            start_socket_listener()
    except Exception:
        pass


def register_operators():
    global __OPS_REGISTERED, _load_handler_added
    if __OPS_REGISTERED:
        return
    for cls in classes:
        _safe_register(cls)
    __OPS_REGISTERED = True

    # Add load handler to restart listener after file loads
    if not _load_handler_added:
        bpy.app.handlers.load_post.append(_on_load_post)
        _load_handler_added = True

    # Try to start socket system (may fail if no window context yet)
    # Use a timer to delay startup slightly to ensure window is ready
    def _delayed_start():
        _start_socket_system()
        return None  # Don't repeat

    bpy.app.timers.register(_delayed_start, first_interval=1.0)


def unregister_operators():
    global __OPS_REGISTERED, _load_handler_added
    if not __OPS_REGISTERED:
        return

    # Remove load handler
    if _load_handler_added and _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
        _load_handler_added = False

    # Stop socket listener
    stop_socket_listener()

    # Stop socket server
    from ..utils import stop_socket_server, is_socket_server_running
    if is_socket_server_running():
        stop_socket_server()

    # Stop the file-based polling timer (in case it was running as fallback)
    stop_queue_poll_timer()

    for cls in reversed(classes):
        _safe_unregister(cls)
    __OPS_REGISTERED = False