import bpy
import os

class ANIMLIB_OT_create_library_folder(bpy.types.Operator):
    """Create the actions library folder"""
    bl_idname = "animlib.create_library_folder"
    bl_label = "Create Library Folder"
    bl_description = "Create the actions library folder at the specified path"
    
    def execute(self, context):
        prefs = context.preferences.addons[__name__.split('.')[0]].preferences
        
        if not prefs.actions_library_path:
            self.report({'ERROR'}, "Please set the actions library path first")
            return {'CANCELLED'}
        
        try:
            os.makedirs(prefs.actions_library_path, exist_ok=True)
            actions_dir = os.path.join(prefs.actions_library_path, "actions")
            metadata_dir = os.path.join(prefs.actions_library_path, "metadata")
            previews_dir = os.path.join(prefs.actions_library_path, "previews")
            
            os.makedirs(actions_dir, exist_ok=True)
            os.makedirs(metadata_dir, exist_ok=True)
            os.makedirs(previews_dir, exist_ok=True)
            
            self.report({'INFO'}, f"Created library folders at {prefs.actions_library_path}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create folders: {str(e)}")
            return {'CANCELLED'}
