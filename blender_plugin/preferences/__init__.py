from bpy.utils import register_class, unregister_class

from .AL_preferences import ANIMLIB_AddonPreferences
from .AL_preferences import get_library_path, get_preview_settings #register these?


classes = (
    ANIMLIB_AddonPreferences,
)


def register_preferences():
    """Register addon preferences"""
    for cls in classes:
        register_class(cls)
def unregister_preferences():
    """Unregister addon preferences"""
    for cls in reversed(classes):
        unregister_class(cls)
