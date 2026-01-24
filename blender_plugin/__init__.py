bl_info = {
    "name": "Action Library",
    "author": "CG_stuff",
    "version": (1, 4),
    "blender": (4, 5, 0),  # Minimum version; supports up to 5.0+
    "location": "3D Viewport > Sidebar > Animation Library",
    "description": "Capture and manage Actions across different rig types",
    "category": "Animation",
}

import bpy
from .utils import icon_loader
from .registration import register_all, unregister_all

def register():
    # Register icon loader first
    icon_loader.register()   
    # Register all classes AFTER properties are defined
    register_all()

def unregister():
    unregister_all()

    # Unregister icon loader last
    icon_loader.unregister()

if __name__ == "__main__":
    register()