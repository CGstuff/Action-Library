import bpy
from bpy.types import PropertyGroup
from ..utils.utils import DEFAULT_ANIMATION_NAME, DEFAULT_POSE_NAME

class ANIMLIB_SceneProperties(PropertyGroup):
    # Basic metadata
    bpy.types.Scene.animlib_animation_name = bpy.props.StringProperty(
        name="Action Name",
        description="Name for the Action",
        default=DEFAULT_ANIMATION_NAME
    )

    bpy.types.Scene.animlib_use_action_name = bpy.props.BoolProperty(
        name="Use Action Name",
        description="Automatically use the active action's name",
        default=False
    )

    # Pose capture properties
    bpy.types.Scene.animlib_pose_name = bpy.props.StringProperty(
        name="Pose Name",
        description="Name for the Pose",
        default=DEFAULT_POSE_NAME
    )

    bpy.types.Scene.animlib_selected_bones_only = bpy.props.BoolProperty(
        name="Selected Bones Only",
        description="Only capture selected bones (for partial poses like hands)",
        default=False
    )

    bpy.types.Scene.animlib_description = bpy.props.StringProperty(
        name="Description",
        description="Description of the Action",
        default=""
    )
    
    bpy.types.Scene.animlib_tags = bpy.props.StringProperty(
        name="Tags",
        description="Comma-separated tags for the Action",
        default=""
    )
    
    bpy.types.Scene.animlib_author = bpy.props.StringProperty(
        name="Author",
        description="Author of the Action",
        default="Unknown"
    )

    # Rig type override
    bpy.types.Scene.animlib_rig_type = bpy.props.StringProperty(
        name="Rig Type",
        description="Custom rig type name (e.g., 'my_custom_rig')",
        default=""
    )

    bpy.types.Scene.animlib_use_detected_rig_type = bpy.props.BoolProperty(
        name="Use Detected Rig Type",
        description="Use auto-detected rig type instead of custom",
        default=True
    )

    # Apply settings
    bpy.types.Scene.animlib_apply_selected_bones_only = bpy.props.BoolProperty(
        name="Selected Bones Only",
        description="Apply Action only to currently selected bones",
        default=False
    )

    bpy.types.Scene.animlib_mirror_animation = bpy.props.BoolProperty(
        name="Mirror Action",
        description="Mirror the Action to the opposite side (Left↔Right). Only available for Actions with proper L/R bone naming conventions",
        default=False
    )

    bpy.types.Scene.animlib_reverse_animation = bpy.props.BoolProperty(
        name="Reverse Action",
        description="Reverse the Action timeline so it plays backwards",
        default=False
    )

    bpy.types.Scene.animlib_apply_mode = bpy.props.EnumProperty(
        name="Apply Mode",
        description="How to apply the Action",
        items=[
            ('NEW', 'Add New', 'Create a new action and replace the Action'),
            ('INSERT', 'Insert at Playhead', 'Insert Action at current playhead position, blending with existing keyframes')
        ],
        default='NEW'
    )

    bpy.types.Scene.animlib_use_slots = bpy.props.BoolProperty(
        name="Use Slots",
        description="Enable Action slots (Blender 4.5+). NEW mode: Creates a new slot on the current action. INSERT mode: Adds keyframes to the active slot at playhead. Allows multiple Actions on one action",
        default=False
    )

    bpy.types.Scene.animlib_active_slot_index = bpy.props.IntProperty(
        name="Active Slot Index",
        description="Index of the currently selected slot in the UIList",
        default=0
    )

    # UI collapsible section toggles
    bpy.types.Scene.animlib_show_action_details = bpy.props.BoolProperty(
        name="Show Action Details",
        description="Toggle Action Details section",
        default=False
    )

    bpy.types.Scene.animlib_show_desktop_integration = bpy.props.BoolProperty(
        name="Show Desktop Integration",
        description="Toggle Desktop Integration section",
        default=False
    )

    # Merge-related properties
    bpy.types.Scene.animlib_merge_selected_slots = bpy.props.StringProperty(
        name="Merge Selected Slots",
        description="JSON string storing {slot_name: is_selected} for merge operations",
        default="{}"
    )

    bpy.types.Scene.animlib_merge_mode = bpy.props.EnumProperty(
        name="Merge Mode",
        description="How to blend keyframe values when merging",
        items=[
            ('AVERAGE', 'Average', 'Average keyframe values across slots'),
            ('ADD', 'Additive', 'Sum keyframe values'),
        ],
        default='AVERAGE'
    )

    bpy.types.Scene.animlib_merge_include_unique = bpy.props.BoolProperty(
        name="Include Unique FCurves",
        description="Include fcurves that only exist in one slot",
        default=True
    )

    bpy.types.Scene.animlib_enable_root_motion_continuity = bpy.props.BoolProperty(
        name="Enable Root Motion Continuity",
        description="Maintain continuous root motion when applying the Action",
        default=False
    )

    bpy.types.Scene.animlib_root_bone_name= bpy.props.StringProperty(
        name="Root Motion Bone",
        description="Name of the bone to use for root motion continuity",
        default=""
    )

    bpy.types.Scene.animlib_root_motion_x = bpy.props.BoolProperty(
        name="Root Motion X",
        description="Maintain continuity on the X axis",
        default=False
    )
    bpy.types.Scene.animlib_root_motion_y = bpy.props.BoolProperty(
        name="Root Motion Y",
        description="Maintain continuity on the Y axis",
        default=False
    )
    bpy.types.Scene.animlib_root_motion_z = bpy.props.BoolProperty(
        name="Root Motion Z",
        description="Maintain continuity on the Z axis",
        default=False
    )

    # Versioning properties (for "Create New Version" flow)
    bpy.types.Scene.animlib_version_source_group_id = bpy.props.StringProperty(
        name="Version Source Group ID",
        description="UUID of version group when creating a new version (set by desktop app)",
        default=""
    )

    bpy.types.Scene.animlib_version_source_name = bpy.props.StringProperty(
        name="Version Source Name",
        description="Base name of animation being versioned",
        default=""
    )

    bpy.types.Scene.animlib_version_next_number = bpy.props.IntProperty(
        name="Next Version Number",
        description="Next version number to use",
        default=1,
        min=1
    )

    bpy.types.Scene.animlib_is_versioning = bpy.props.BoolProperty(
        name="Is Versioning",
        description="True if next capture should create a new version",
        default=False
    )

    # Custom property group for animations
    class ANIMLIB_AnimationItem(bpy.types.PropertyGroup):
        animation_id: bpy.props.IntProperty()
        name: bpy.props.StringProperty()
        rig_type: bpy.props.StringProperty()
    
    bpy.utils.register_class(ANIMLIB_AnimationItem)
    
    bpy.types.Scene.animlib_animations = bpy.props.CollectionProperty(
        type=ANIMLIB_AnimationItem,
        name="Available Actions"
    )
