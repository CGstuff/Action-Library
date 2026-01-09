"""
Version Choice Dialog - Ask user whether to create new version or new animation

When capturing an action that was imported from the library, this dialog
prompts the user to choose between:
- Creating a new version of the original animation
- Creating a completely new animation
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, StringProperty, IntProperty
from ..utils.logger import get_logger

logger = get_logger()


class ANIMLIB_OT_version_choice(Operator):
    """Choose whether to create a new version or new animation"""
    bl_idname = "animlib.version_choice"
    bl_label = "Library Action Detected"
    bl_description = "This action was imported from the library. Choose how to save it."
    bl_options = {'REGISTER', 'INTERNAL'}

    # Properties to pass source animation info
    source_name: StringProperty(
        name="Source Animation",
        description="Name of the source animation",
        default=""
    )

    source_version_label: StringProperty(
        name="Source Version",
        description="Version label of the source animation",
        default="v001"
    )

    source_version: IntProperty(
        name="Version Number",
        description="Current version number",
        default=1
    )

    source_version_group_id: StringProperty(
        name="Version Group ID",
        description="UUID of the version group",
        default=""
    )

    # User choice
    choice: EnumProperty(
        name="Save As",
        description="How to save this animation",
        items=[
            ('NEW_VERSION', "New Version", "Create a new version of the original animation"),
            ('NEW_ANIMATION', "New Animation", "Create a completely new animation"),
        ],
        default='NEW_VERSION'
    )

    # Result storage (read by capture operator)
    _result = None
    _result_data = None

    @classmethod
    def reset_result(cls):
        """Reset the result before showing dialog"""
        cls._result = None
        cls._result_data = None

    @classmethod
    def get_result(cls):
        """Get the result after dialog closes"""
        return cls._result, cls._result_data

    def invoke(self, context, event):
        """Show the dialog"""
        # Calculate next version
        self.next_version = self.source_version + 1
        self.next_version_label = f"v{self.next_version:03d}"

        # Calculate base name (strip version suffix for display)
        self.base_name = self._strip_version_suffix(self.source_name)

        # Reset result
        ANIMLIB_OT_version_choice.reset_result()

        # Show dialog
        return context.window_manager.invoke_props_dialog(self, width=350)

    def _strip_version_suffix(self, name: str) -> str:
        """Strip version suffix like _v001, _v002 from name"""
        import re
        pattern = r'_v\d{1,4}$'
        return re.sub(pattern, '', name)

    def draw(self, context):
        """Draw the dialog UI"""
        layout = self.layout

        # Header info
        box = layout.box()
        box.label(text="This action was imported from the library:", icon='INFO')

        # Source animation info
        col = box.column(align=True)
        col.label(text=f"Source: {self.source_name}")
        col.label(text=f"Current Version: {self.source_version_label}")

        layout.separator()

        # Choice
        layout.label(text="What would you like to do?")

        # Option 1: New Version
        version_box = layout.box()
        row = version_box.row()
        row.prop(self, "choice", expand=True)

        # Show what will happen based on choice
        info_box = layout.box()
        if self.choice == 'NEW_VERSION':
            info_box.label(text=f"Will create: {self.base_name}_{self.next_version_label}", icon='FILE_REFRESH')
            info_box.label(text="Linked to original animation's version history")
        else:
            info_box.label(text="Will create a new animation with v001", icon='FILE_NEW')
            info_box.label(text="Not linked to the original animation")

    def execute(self, context):
        """Handle the user's choice"""
        scene = context.scene

        if self.choice == 'NEW_VERSION':
            # Set up versioning mode
            scene.animlib_is_versioning = True
            scene.animlib_version_source_group_id = self.source_version_group_id
            scene.animlib_version_source_name = self.source_name
            scene.animlib_version_next_number = self.source_version + 1

            # Store result
            ANIMLIB_OT_version_choice._result = 'NEW_VERSION'
            ANIMLIB_OT_version_choice._result_data = {
                'version_group_id': self.source_version_group_id,
                'source_name': self.source_name,
                'next_version': self.source_version + 1,
                'next_version_label': f"v{self.source_version + 1:03d}"
            }

            logger.info(f"User chose NEW_VERSION: {self.source_name} -> v{self.source_version + 1:03d}")
            self.report({'INFO'}, f"Will create new version: {self.source_name}_v{self.source_version + 1:03d}")

        else:
            # Clear any versioning state
            scene.animlib_is_versioning = False
            scene.animlib_version_source_group_id = ""
            scene.animlib_version_source_name = ""
            scene.animlib_version_next_number = 1

            # Store result
            ANIMLIB_OT_version_choice._result = 'NEW_ANIMATION'
            ANIMLIB_OT_version_choice._result_data = None

            logger.info(f"User chose NEW_ANIMATION (ignoring library source)")
            self.report({'INFO'}, "Will create new animation")

        return {'FINISHED'}

    def cancel(self, context):
        """Handle dialog cancel"""
        ANIMLIB_OT_version_choice._result = 'CANCELLED'
        ANIMLIB_OT_version_choice._result_data = None
        logger.info("User cancelled version choice dialog")


__all__ = ['ANIMLIB_OT_version_choice']
