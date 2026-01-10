"""
Socket Command Handlers for Animation Library

This module registers command handlers for the socket server,
allowing the desktop app to trigger animation/pose application.
"""

import bpy
import os
import json
from pathlib import Path
from typing import Dict, Any

from .socket_server import register_command_handler
from .logger import get_logger

logger = get_logger()


def _get_active_armature():
    """Get the active armature object, or find one in the scene"""
    obj = bpy.context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj

    # Try to find an armature in selection
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj

    # Try to find any armature in scene
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj

    return None


def handle_apply_animation(command: dict, client_id: str) -> dict:
    """
    Handle apply_animation command from desktop app.

    Expected command format:
    {
        "type": "apply_animation",
        "animation_id": "uuid",
        "animation_name": "Walk Cycle",
        "options": {
            "apply_mode": "NEW" | "INSERT",
            "mirror": false,
            "reverse": false,
            "selected_bones_only": false,
            "use_slots": false
        }
    }
    """
    try:
        animation_id = command.get('animation_id')
        animation_name = command.get('animation_name', 'Unknown')
        options = command.get('options', {})

        if not animation_id:
            return {
                'status': 'error',
                'message': 'Missing animation_id'
            }

        # Check for armature
        armature = _get_active_armature()
        if not armature:
            return {
                'status': 'error',
                'message': 'No armature selected. Please select an armature in Blender.'
            }

        # Make sure the armature is active
        bpy.context.view_layer.objects.active = armature

        logger.info(f"Socket: Applying animation '{animation_name}' to {armature.name}")

        # Get options
        apply_mode = options.get('apply_mode', 'NEW')
        mirror = options.get('mirror', False)
        reverse = options.get('reverse', False)
        selected_bones_only = options.get('selected_bones_only', False)
        use_slots = options.get('use_slots', False)

        # Handle selected bones
        selected_bones_list = ''
        if selected_bones_only and bpy.context.mode == 'POSE':
            selected_bones = [bone.name for bone in bpy.context.selected_pose_bones or []]
            selected_bones_list = ','.join(selected_bones)
            if not selected_bones:
                selected_bones_only = False

        # Call the apply animation operator
        result = bpy.ops.animlib.apply_animation(
            animation_id=animation_id,
            apply_selected_bones_only=selected_bones_only,
            selected_bones_list=selected_bones_list,
            apply_mode=apply_mode,
            use_slots=use_slots,
            mirror_animation=mirror,
            reverse_animation=reverse,
            options_from_queue=True
        )

        if result == {'FINISHED'}:
            return {
                'status': 'success',
                'message': f"Applied animation '{animation_name}' to {armature.name}"
            }
        else:
            return {
                'status': 'error',
                'message': f"Failed to apply animation: {result}"
            }

    except Exception as e:
        logger.error(f"Error in handle_apply_animation: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'message': str(e)
        }


def handle_apply_pose(command: dict, client_id: str) -> dict:
    """
    Handle apply_pose command from desktop app.

    Expected command format:
    {
        "type": "apply_pose",
        "pose_id": "uuid",
        "pose_name": "T-Pose",
        "blend_file_path": "path/to/pose.blend",
        "mirror": false  // optional
    }
    """
    try:
        pose_id = command.get('pose_id') or command.get('animation_id')
        pose_name = command.get('pose_name') or command.get('animation_name', 'Unknown Pose')
        blend_file_path = command.get('blend_file_path')
        mirror = command.get('mirror', False)

        if not pose_id:
            return {
                'status': 'error',
                'message': 'Missing pose_id'
            }

        if not blend_file_path or not os.path.exists(blend_file_path):
            return {
                'status': 'error',
                'message': f'Pose blend file not found: {blend_file_path}'
            }

        # Check for armature
        armature = _get_active_armature()
        if not armature:
            return {
                'status': 'error',
                'message': 'No armature selected. Please select an armature in Blender.'
            }

        # Make sure the armature is active
        bpy.context.view_layer.objects.active = armature

        logger.info(f"Socket: Applying pose '{pose_name}' to {armature.name}")

        # Load the pose action from blend file
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            data_to.actions = data_from.actions

        if not data_to.actions:
            return {
                'status': 'error',
                'message': 'No actions found in pose file'
            }

        pose_action = data_to.actions[0]

        # Ensure armature has pose data
        if not armature.pose:
            bpy.data.actions.remove(pose_action)
            return {
                'status': 'error',
                'message': 'Armature has no pose data'
            }

        # Apply the pose using Blender's built-in method
        if mirror:
            # Apply with mirroring (swap L/R bones)
            logger.info(f"Applying pose with mirror")
            _apply_pose_mirrored(armature, pose_action)
        else:
            try:
                armature.pose.apply_pose_from_action(pose_action, evaluation_time=0.0)
                logger.info(f"Applied pose using apply_pose_from_action()")
            except AttributeError:
                # Fallback for older Blender versions
                logger.debug("apply_pose_from_action not available, using manual method")
                _apply_pose_manually(armature, pose_action)

        # Check if auto-key is enabled - if so, insert keyframes
        autokey_msg = ""
        use_autokey = bpy.context.scene.tool_settings.use_keyframe_insert_auto

        if use_autokey:
            # Get bone names from the pose action before we remove it
            from .utils import get_action_fcurves
            bone_names = set()
            for fcurve in get_action_fcurves(pose_action):
                data_path = fcurve.data_path
                if 'pose.bones[' in data_path:
                    try:
                        bone_name = data_path.split('"')[1]
                        bone_names.add(bone_name)
                    except (IndexError, KeyError):
                        pass

            # Clean up - remove the loaded action BEFORE keyframing
            bpy.data.actions.remove(pose_action)
            pose_action = None

            # Now insert keyframes
            keyframe_count = _insert_pose_keyframes_for_bones(armature, bone_names)
            if keyframe_count > 0:
                autokey_msg = f" (keyframed {keyframe_count} bones)"
        else:
            # Clean up - remove the loaded action
            bpy.data.actions.remove(pose_action)

        # Force viewport update
        bpy.context.view_layer.update()

        mirror_msg = " (mirrored)" if mirror else ""
        return {
            'status': 'success',
            'message': f"Applied pose '{pose_name}'{mirror_msg} to {armature.name}{autokey_msg}"
        }

    except Exception as e:
        logger.error(f"Error in handle_apply_pose: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'message': str(e)
        }


def _insert_pose_keyframes_for_bones(armature, bone_names):
    """
    Insert keyframes for specified bones at the current frame.

    Args:
        armature: The armature object
        bone_names: Set of bone names to keyframe

    Returns:
        Number of bones keyframed
    """
    # Get current frame
    current_frame = bpy.context.scene.frame_current

    # Make sure armature has animation data
    if not armature.animation_data:
        armature.animation_data_create()

    # Create action if none exists
    if not armature.animation_data.action:
        action_name = f"{armature.name}_Action"
        armature.animation_data.action = bpy.data.actions.new(name=action_name)

    # Insert keyframes for each bone
    keyframed_count = 0
    for bone_name in bone_names:
        if bone_name not in armature.pose.bones:
            continue

        pose_bone = armature.pose.bones[bone_name]

        try:
            # Insert keyframes for location, rotation, and scale
            pose_bone.keyframe_insert(data_path="location", frame=current_frame)

            # Handle rotation based on rotation mode
            if pose_bone.rotation_mode == 'QUATERNION':
                pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=current_frame)
            elif pose_bone.rotation_mode == 'AXIS_ANGLE':
                pose_bone.keyframe_insert(data_path="rotation_axis_angle", frame=current_frame)
            else:
                pose_bone.keyframe_insert(data_path="rotation_euler", frame=current_frame)

            pose_bone.keyframe_insert(data_path="scale", frame=current_frame)
            keyframed_count += 1
        except Exception:
            pass

    return keyframed_count


def _apply_pose_manually(armature, pose_action):
    """Manually apply pose transforms from an action (fallback method)"""
    from .utils import get_action_fcurves

    for fcurve in get_action_fcurves(pose_action):
        if not fcurve.keyframe_points:
            continue

        value = fcurve.evaluate(0)
        data_path = fcurve.data_path

        if 'pose.bones[' not in data_path:
            continue

        try:
            bone_name = data_path.split('"')[1]

            if bone_name not in armature.pose.bones:
                continue

            pose_bone = armature.pose.bones[bone_name]

            if '.location' in data_path:
                pose_bone.location[fcurve.array_index] = value
            elif '.rotation_quaternion' in data_path:
                pose_bone.rotation_quaternion[fcurve.array_index] = value
            elif '.rotation_euler' in data_path:
                pose_bone.rotation_euler[fcurve.array_index] = value
            elif '.scale' in data_path:
                pose_bone.scale[fcurve.array_index] = value
        except (IndexError, KeyError) as e:
            logger.debug(f"Could not apply fcurve {data_path}: {e}")


def _apply_pose_mirrored(armature, pose_action):
    """
    Apply pose with mirroring using Blender's native pose.paste(flipped=True).

    This properly handles all the complex bone orientation mirroring that
    manual axis flipping cannot handle correctly (especially for fingers).

    Mimics: Select all bones → Ctrl+C → Ctrl+Shift+V in viewport
    """
    # Find a VIEW_3D area for proper context
    area = bpy.context.area
    window = bpy.context.window

    if area is None or area.type != 'VIEW_3D':
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    area = a
                    window = w
                    break
            if area and area.type == 'VIEW_3D':
                break

    if area is None:
        logger.error("No VIEW_3D area found for pose mirror")
        # Fallback to non-mirrored apply
        try:
            armature.pose.apply_pose_from_action(pose_action, evaluation_time=0.0)
        except AttributeError:
            _apply_pose_manually(armature, pose_action)
        return

    # Find region for context override
    region = None
    for r in area.regions:
        if r.type == 'WINDOW':
            region = r
            break

    # Step 1: Apply the pose normally first
    try:
        armature.pose.apply_pose_from_action(pose_action, evaluation_time=0.0)
    except AttributeError:
        _apply_pose_manually(armature, pose_action)

    # Ensure we're in pose mode with armature active
    bpy.context.view_layer.objects.active = armature
    if bpy.context.mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    # Use context override for pose operators
    with bpy.context.temp_override(window=window, area=area, region=region):
        # Step 2: Select all pose bones
        bpy.ops.pose.select_all(action='SELECT')

        # Step 3: Copy the current pose (Ctrl+C)
        bpy.ops.pose.copy()

        # Step 4: Reset to rest pose
        for bone in armature.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)

        # Step 5: Paste with flipping (Ctrl+Shift+V)
        bpy.ops.pose.paste(flipped=True)

    logger.info("Applied pose using native paste(flipped=True)")


# Global state for pose blending session
_blend_session = {
    'active': False,
    'pose_action': None,
    'armature': None,
    'original_transforms': {},  # Store original bone transforms for cancel
}


def handle_blend_pose_start(command: dict, client_id: str) -> dict:
    """
    Start a pose blending session. Loads the target pose action.

    Expected command format:
    {
        "type": "blend_pose_start",
        "pose_id": "uuid",
        "pose_name": "T-Pose",
        "blend_file_path": "path/to/pose.blend"
    }
    """
    global _blend_session

    try:
        pose_name = command.get('pose_name', 'Unknown Pose')
        blend_file_path = command.get('blend_file_path')

        if not blend_file_path or not os.path.exists(blend_file_path):
            return {
                'status': 'error',
                'message': f'Pose blend file not found: {blend_file_path}'
            }

        # Check for armature
        armature = _get_active_armature()
        if not armature:
            return {
                'status': 'error',
                'message': 'No armature selected. Please select an armature in Blender.'
            }

        # Make sure the armature is active
        bpy.context.view_layer.objects.active = armature

        # Store original bone transforms for potential cancel
        original_transforms = {}
        for pose_bone in armature.pose.bones:
            original_transforms[pose_bone.name] = {
                'location': pose_bone.location.copy(),
                'rotation_quaternion': pose_bone.rotation_quaternion.copy(),
                'rotation_euler': pose_bone.rotation_euler.copy(),
                'scale': pose_bone.scale.copy(),
            }

        # Load the pose action from blend file
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            data_to.actions = data_from.actions

        if not data_to.actions:
            return {
                'status': 'error',
                'message': 'No actions found in pose file'
            }

        pose_action = data_to.actions[0]

        # Store session state
        _blend_session = {
            'active': True,
            'pose_action': pose_action,
            'armature': armature,
            'original_transforms': original_transforms,
            'pose_name': pose_name,
        }

        logger.info(f"Blend session started for '{pose_name}'")

        return {
            'status': 'success',
            'message': f"Blend session started for '{pose_name}'"
        }

    except Exception as e:
        logger.error(f"Error in handle_blend_pose_start: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'message': str(e)
        }


def handle_blend_pose(command: dict, client_id: str) -> dict:
    """
    Blend toward the target pose with given factor. Called repeatedly during drag.

    Expected command format:
    {
        "type": "blend_pose",
        "blend_factor": 0.5,  # 0.0 to 1.0
        "mirror": false       # Ctrl held = mirror
    }
    """
    global _blend_session

    try:
        if not _blend_session['active']:
            return {
                'status': 'error',
                'message': 'No active blend session. Call blend_pose_start first.'
            }

        blend_factor = command.get('blend_factor', 0.0)
        mirror = command.get('mirror', False)

        armature = _blend_session['armature']
        pose_action = _blend_session['pose_action']
        original_transforms = _blend_session['original_transforms']

        if not armature or not pose_action:
            return {
                'status': 'error',
                'message': 'Invalid blend session state'
            }

        # First restore original transforms (so we blend from original, not accumulated)
        for bone_name, transforms in original_transforms.items():
            if bone_name in armature.pose.bones:
                pose_bone = armature.pose.bones[bone_name]
                pose_bone.location = transforms['location'].copy()
                pose_bone.rotation_quaternion = transforms['rotation_quaternion'].copy()
                pose_bone.rotation_euler = transforms['rotation_euler'].copy()
                pose_bone.scale = transforms['scale'].copy()

        # Now blend toward target pose
        # Note: blend_pose_from_action blends FROM current pose TOWARD the action
        # So we need blend_factor to work correctly
        try:
            if mirror:
                # For mirroring, we need to flip bone names and negate X transforms
                _blend_pose_mirrored(armature, pose_action, blend_factor)
            else:
                armature.pose.blend_pose_from_action(
                    pose_action,
                    blend_factor=blend_factor,
                    evaluation_time=0.0
                )
        except AttributeError:
            # Fallback for older Blender versions
            _blend_pose_manually(armature, pose_action, blend_factor, mirror)

        # Force viewport update
        bpy.context.view_layer.update()

        return {
            'status': 'success',
            'blend_factor': blend_factor,
            'mirror': mirror
        }

    except Exception as e:
        logger.error(f"Error in handle_blend_pose: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


def handle_blend_pose_end(command: dict, client_id: str) -> dict:
    """
    End the blend session. Optionally insert keyframes.

    Expected command format:
    {
        "type": "blend_pose_end",
        "cancelled": false,  # If true, restore original pose
        "insert_keyframes": false  # If true, insert keyframes for affected bones
    }
    """
    global _blend_session

    try:
        if not _blend_session['active']:
            return {
                'status': 'error',
                'message': 'No active blend session'
            }

        cancelled = command.get('cancelled', False)
        insert_keyframes = command.get('insert_keyframes', False)

        armature = _blend_session['armature']
        pose_action = _blend_session['pose_action']
        original_transforms = _blend_session['original_transforms']
        pose_name = _blend_session.get('pose_name', 'Unknown')

        if cancelled and armature:
            # Restore original transforms
            for bone_name, transforms in original_transforms.items():
                if bone_name in armature.pose.bones:
                    pose_bone = armature.pose.bones[bone_name]
                    pose_bone.location = transforms['location'].copy()
                    pose_bone.rotation_quaternion = transforms['rotation_quaternion'].copy()
                    pose_bone.rotation_euler = transforms['rotation_euler'].copy()
                    pose_bone.scale = transforms['scale'].copy()
            bpy.context.view_layer.update()
            message = f"Blend cancelled, restored original pose"
        else:
            message = f"Blended to '{pose_name}'"

            # Insert keyframes if requested or auto-key is enabled
            use_autokey = bpy.context.scene.tool_settings.use_keyframe_insert_auto
            if insert_keyframes or use_autokey:
                if pose_action and armature:
                    from .utils import get_action_fcurves
                    bone_names = set()
                    for fcurve in get_action_fcurves(pose_action):
                        data_path = fcurve.data_path
                        if 'pose.bones[' in data_path:
                            try:
                                bone_name = data_path.split('"')[1]
                                bone_names.add(bone_name)
                            except (IndexError, KeyError):
                                pass

                    keyframe_count = _insert_pose_keyframes_for_bones(armature, bone_names)
                    if keyframe_count > 0:
                        message += f" (keyframed {keyframe_count} bones)"

        # Clean up the loaded action
        if pose_action:
            bpy.data.actions.remove(pose_action)

        # Reset session
        _blend_session = {
            'active': False,
            'pose_action': None,
            'armature': None,
            'original_transforms': {},
        }

        logger.info(f"Blend session ended: {message}")

        return {
            'status': 'success',
            'message': message
        }

    except Exception as e:
        logger.error(f"Error in handle_blend_pose_end: {e}")
        import traceback
        traceback.print_exc()
        # Try to clean up
        if _blend_session.get('pose_action'):
            try:
                bpy.data.actions.remove(_blend_session['pose_action'])
            except:
                pass
        _blend_session = {
            'active': False,
            'pose_action': None,
            'armature': None,
            'original_transforms': {},
        }
        return {
            'status': 'error',
            'message': str(e)
        }


def _blend_pose_mirrored(armature, pose_action, blend_factor):
    """Blend pose with mirroring (swap L/R bones and flip X axis)"""
    from .utils import get_action_fcurves

    # Common mirror name patterns
    def get_mirror_name(name):
        """Get the mirrored bone name"""
        # Try common patterns: .L/.R, _L/_R, .l/.r, _l/_r, Left/Right
        replacements = [
            ('.L', '.R'), ('.R', '.L'),
            ('_L', '_R'), ('_R', '_L'),
            ('.l', '.r'), ('.r', '.l'),
            ('_l', '_r'), ('_r', '_l'),
            ('Left', 'Right'), ('Right', 'Left'),
            ('left', 'right'), ('right', 'left'),
        ]
        for old, new in replacements:
            if old in name:
                return name.replace(old, new)
        return name  # No mirror found, use same bone

    for fcurve in get_action_fcurves(pose_action):
        if not fcurve.keyframe_points:
            continue

        data_path = fcurve.data_path
        if 'pose.bones[' not in data_path:
            continue

        try:
            bone_name = data_path.split('"')[1]
            mirror_bone_name = get_mirror_name(bone_name)

            if mirror_bone_name not in armature.pose.bones:
                continue

            pose_bone = armature.pose.bones[mirror_bone_name]
            value = fcurve.evaluate(0)

            # Apply with blend factor
            if '.location' in data_path:
                idx = fcurve.array_index
                current = pose_bone.location[idx]
                # Mirror X axis for location
                if idx == 0:  # X axis
                    value = -value
                pose_bone.location[idx] = current + (value - current) * blend_factor

            elif '.rotation_quaternion' in data_path:
                idx = fcurve.array_index
                current = pose_bone.rotation_quaternion[idx]
                # Mirror Y and Z components for quaternion
                if idx in (2, 3):  # Y and Z
                    value = -value
                pose_bone.rotation_quaternion[idx] = current + (value - current) * blend_factor

            elif '.rotation_euler' in data_path:
                idx = fcurve.array_index
                current = pose_bone.rotation_euler[idx]
                # Mirror Y and Z rotation for euler
                if idx in (1, 2):  # Y and Z
                    value = -value
                pose_bone.rotation_euler[idx] = current + (value - current) * blend_factor

            elif '.scale' in data_path:
                idx = fcurve.array_index
                current = pose_bone.scale[idx]
                pose_bone.scale[idx] = current + (value - current) * blend_factor

        except (IndexError, KeyError) as e:
            logger.debug(f"Could not mirror fcurve {data_path}: {e}")


def _blend_pose_manually(armature, pose_action, blend_factor, mirror=False):
    """Manually blend pose transforms (fallback for older Blender)"""
    from .utils import get_action_fcurves

    def get_mirror_name(name):
        replacements = [
            ('.L', '.R'), ('.R', '.L'),
            ('_L', '_R'), ('_R', '_L'),
            ('.l', '.r'), ('.r', '.l'),
            ('_l', '_r'), ('_r', '_l'),
        ]
        for old, new in replacements:
            if old in name:
                return name.replace(old, new)
        return name

    for fcurve in get_action_fcurves(pose_action):
        if not fcurve.keyframe_points:
            continue

        data_path = fcurve.data_path
        if 'pose.bones[' not in data_path:
            continue

        try:
            bone_name = data_path.split('"')[1]
            target_bone_name = get_mirror_name(bone_name) if mirror else bone_name

            if target_bone_name not in armature.pose.bones:
                continue

            pose_bone = armature.pose.bones[target_bone_name]
            target_value = fcurve.evaluate(0)

            if '.location' in data_path:
                idx = fcurve.array_index
                current = pose_bone.location[idx]
                if mirror and idx == 0:
                    target_value = -target_value
                pose_bone.location[idx] = current + (target_value - current) * blend_factor

            elif '.rotation_quaternion' in data_path:
                idx = fcurve.array_index
                current = pose_bone.rotation_quaternion[idx]
                if mirror and idx in (2, 3):
                    target_value = -target_value
                pose_bone.rotation_quaternion[idx] = current + (target_value - current) * blend_factor

            elif '.rotation_euler' in data_path:
                idx = fcurve.array_index
                current = pose_bone.rotation_euler[idx]
                if mirror and idx in (1, 2):
                    target_value = -target_value
                pose_bone.rotation_euler[idx] = current + (target_value - current) * blend_factor

            elif '.scale' in data_path:
                idx = fcurve.array_index
                current = pose_bone.scale[idx]
                pose_bone.scale[idx] = current + (target_value - current) * blend_factor

        except (IndexError, KeyError) as e:
            logger.debug(f"Could not blend fcurve {data_path}: {e}")


def handle_get_armature_info(command: dict, client_id: str) -> dict:
    """
    Handle get_armature_info command - returns info about active armature.

    Useful for desktop app to know current state.
    """
    armature = _get_active_armature()

    if not armature:
        return {
            'status': 'success',
            'data': {
                'has_armature': False,
                'armature_name': None,
                'mode': bpy.context.mode
            }
        }

    return {
        'status': 'success',
        'data': {
            'has_armature': True,
            'armature_name': armature.name,
            'mode': bpy.context.mode,
            'bone_count': len(armature.data.bones),
            'has_action': armature.animation_data.action is not None if armature.animation_data else False,
            'current_action': armature.animation_data.action.name if armature.animation_data and armature.animation_data.action else None
        }
    }


def register_socket_commands():
    """Register all socket command handlers"""
    register_command_handler('apply_animation', handle_apply_animation)
    register_command_handler('apply_pose', handle_apply_pose)
    register_command_handler('get_armature_info', handle_get_armature_info)
    # Pose blending commands
    register_command_handler('blend_pose_start', handle_blend_pose_start)
    register_command_handler('blend_pose', handle_blend_pose)
    register_command_handler('blend_pose_end', handle_blend_pose_end)
    logger.info("Socket command handlers registered")


__all__ = ['register_socket_commands']
