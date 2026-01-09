from bpy.utils import register_class, unregister_class

from .AL_apply_animation import (
    ANIMLIB_OT_apply_animation,
    ANIMLIB_OT_check_apply_queue,
    start_queue_poll_timer,
    stop_queue_poll_timer,
)
from .AL_capture_animation import ANIMLIB_OT_capture_animation, ANIMLIB_OT_cancel_versioning
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


classes = (
    ANIMLIB_OT_apply_animation,
    ANIMLIB_OT_check_apply_queue,
    ANIMLIB_OT_capture_animation,
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

def register_operators():
    global __OPS_REGISTERED
    if __OPS_REGISTERED:
        return
    for cls in classes:
        _safe_register(cls)
    __OPS_REGISTERED = True

    # Start auto-polling timer (uses temp_override for proper context)
    start_queue_poll_timer()


def unregister_operators():
    global __OPS_REGISTERED
    if not __OPS_REGISTERED:
        return

    # Stop the auto-polling timer
    stop_queue_poll_timer()

    for cls in reversed(classes):
        _safe_unregister(cls)
    __OPS_REGISTERED = False