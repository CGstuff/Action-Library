import bpy

class ANIMLIB_WMProperties(bpy.types.PropertyGroup):
    # WindowManager property for tracking capture state (persists across scenes)
    bpy.types.WindowManager.animlib_is_capturing = bpy.props.BoolProperty(
        name="Is Capturing",
        description="Whether an animation capture is currently in progress",
        default=False
    )
    bpy.types.WindowManager.animlib_is_updating_preview = bpy.props.BoolProperty(
        name="Is Updating Preview",
        description="Whether an animation preview update is currently in progress",
        default=False
    )
