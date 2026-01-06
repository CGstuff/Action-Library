from bpy.utils import register_class, unregister_class

from .AL_main_panel import (
    ANIMLIB_UL_slots,
    ANIMLIB_PT_main_panel,
)

classes = (
    ANIMLIB_UL_slots,
    ANIMLIB_PT_main_panel,
)

def register_panels():
    """Register all panel classes"""
    for cls in classes:
        register_class(cls)

def unregister_panels():
    """Unregister all panel classes"""
    for cls in reversed(classes):
        unregister_class(cls)