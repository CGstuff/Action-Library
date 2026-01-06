import bpy
from bpy.utils import register_class, unregister_class

from .AL_preferences_properties import ANIMLIB_PreferencesProperties
from .AL_scene_properties import ANIMLIB_SceneProperties
from .AL_wm_properties import ANIMLIB_WMProperties
from bpy.props import PointerProperty

classes = (
    ANIMLIB_PreferencesProperties,
    ANIMLIB_SceneProperties,
    ANIMLIB_WMProperties,
)

_POINTERS = {
    bpy.types.Scene: [
        ("scene_props", ANIMLIB_PreferencesProperties),
        ("preference_props", ANIMLIB_SceneProperties),
        ("wm_props", ANIMLIB_WMProperties),
    ]
}

def _safe_register_class(cls):
    try:
        register_class(cls)
    except ValueError:
        try: unregister_class(cls)
        except Exception: pass
        register_class(cls)

def _safe_unregister_class(cls):
    try:
        unregister_class(cls)
    except Exception:
        pass

def register_properties():
    # 1) classes first
    for cls in classes:
        _safe_register_class(cls)
    # 2) pointers after classes
    for host, pairs in _POINTERS.items():
        for attr, pg in pairs:
            if not hasattr(host, attr):
                setattr(host, attr, PointerProperty(type=pg))

def unregister_properties():
    # 1) remove pointers first
    for host, pairs in _POINTERS.items():
        for attr, _ in reversed(pairs):
            if hasattr(host, attr):
                delattr(host, attr)
    # 2) classes after pointers
    for cls in reversed(classes):
        _safe_unregister_class(cls)