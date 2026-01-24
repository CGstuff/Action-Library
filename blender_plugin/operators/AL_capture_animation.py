import bpy
import os
import shutil
import subprocess
import json
from bpy.types import Operator
from ..utils.queue_client import animation_queue_client
from ..utils.utils import (get_action_keyframe_range, get_active_armature,
                   has_animation_data, safe_report_error,
                   DEFAULT_ANIMATION_NAME,)
from ..utils.logger import get_logger
from ..utils.naming_engine import get_naming_engine, BlenderNamingEngine

# Initialize logger
logger = get_logger()


class ANIMLIB_OT_cancel_versioning(Operator):
    """Cancel versioning mode"""
    bl_idname = "animlib.cancel_versioning"
    bl_label = "Cancel Version Mode"
    bl_description = "Cancel creating a new version and return to normal capture mode"

    def execute(self, context):
        scene = context.scene
        scene.animlib_is_versioning = False
        scene.animlib_version_source_group_id = ""
        scene.animlib_version_source_name = ""
        scene.animlib_version_next_number = 1
        self.report({'INFO'}, "Version mode cancelled")
        return {'FINISHED'}


class ANIMLIB_OT_capture_animation(Operator):
    """Capture current Action and send to library"""
    bl_idname = "animlib.capture_animation"
    bl_label = "Capture Action"
    bl_description = "Capture the current Action and save it to the library"

    # Modal operator state tracking
    _timer = None
    _state = None
    _context_data = None
    _start_time = None
    _last_activity_time = None

    # Timeout configuration (in seconds)
    MODAL_TIMEOUT = 300  # 5 minutes total timeout
    STATE_TIMEOUT = 60   # 1 minute per state (watchdog)

    def invoke(self, context, event):
        """Start the modal capture operation"""
        wm = context.window_manager
        scene = context.scene

        # Set capture flag immediately - this will trigger UI update!
        armature = get_active_armature(context)
        if not armature:
            safe_report_error(self, "Please select an armature object")
            return {'CANCELLED'}

        if not has_animation_data(armature):
            safe_report_error(self, "No Action data found on selected armature")
            return {'CANCELLED'}

        if not armature.animation_data or not armature.animation_data.action:
            self.report({'ERROR'}, "No Action found on armature")
            return {'CANCELLED'}
        
        wm.animlib_is_capturing = True

        # Validate selection before starting

        # Initialize state machine
        self._state = 'DETECT_RIG'
        self._context_data = {
            'scene': scene,
            'armature': armature,
            'action': armature.animation_data.action,
            'wm': wm
        }

        # Initialize timeout tracking
        import time
        self._start_time = time.time()
        self._last_activity_time = time.time()

        # Add timer for modal updates (runs every 0.1 seconds)
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        # Force UI update to hide button immediately
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        # Return RUNNING_MODAL - this returns control to Blender's event loop
        # The UI will now update and the button will disappear!
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle modal execution - called periodically by timer"""
        # Only process on timer events
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time

        # Timeout watchdog - prevent indefinite hangs
        current_time = time.time()

        # Check total operation timeout
        if self._start_time and (current_time - self._start_time) > self.MODAL_TIMEOUT:
            logger.error(f"Capture operation timed out after {self.MODAL_TIMEOUT}s")
            self.report({'ERROR'}, "Capture timed out - operation took too long")
            self.cleanup(context)
            return {'CANCELLED'}

        # Check state timeout (watchdog for stuck states)
        if self._last_activity_time and (current_time - self._last_activity_time) > self.STATE_TIMEOUT:
            logger.error(f"Capture stuck in state '{self._state}' for {self.STATE_TIMEOUT}s")
            self.report({'ERROR'}, f"Capture stuck in '{self._state}' - cancelling")
            self.cleanup(context)
            return {'CANCELLED'}

        wm = self._context_data['wm']
        scene = self._context_data['scene']

        try:
            if self._state == 'DETECT_RIG':
                # Check if user wants to use custom rig type or auto-detected
                armature = self._context_data['armature']

                if scene.animlib_use_detected_rig_type:
                    # Use auto-detected rig type
                    rig_type, confidence = animation_queue_client.detect_rig_type(armature)
                    if rig_type == 'unknown':
                        self.report({'WARNING'}, f"Could not detect rig type (confidence: {confidence:.2f})")
                else:
                    # Use custom rig type from user input
                    rig_type = scene.animlib_rig_type.strip()
                    if not rig_type:
                        rig_type = 'custom'
                    self.report({'INFO'}, f"Using custom rig type: {rig_type}")

                # Store rig type and move to next state
                self._context_data['rig_type'] = rig_type
                self._state = 'CHECK_LIBRARY_SOURCE'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CHECK_LIBRARY_SOURCE':
                # Check if this action came from the library
                action = self._context_data['action']
                is_library_action = action.get("animlib_imported", False)

                # ONE-TIME v1.2→v1.3 migration: detect legacy actions
                # Legacy v1.2 actions have animlib_imported but NO animlib_app_version
                if is_library_action and not action.get("animlib_app_version"):
                    logger.info("[MIGRATION] Legacy v1.2 action detected - treating as fresh animation")
                    self._clear_library_metadata(action)
                    is_library_action = False  # Force fresh capture

                # If already in versioning mode (user already chose), skip dialog
                if scene.animlib_is_versioning:
                    logger.debug("Already in versioning mode, skipping dialog")
                    self._state = 'DETERMINE_NAME'
                    self._last_activity_time = time.time()  # Reset watchdog
                    return {'RUNNING_MODAL'}

                # If action came from library, validate metadata is still current
                if is_library_action:
                    source_uuid = action.get("animlib_uuid", "")
                    source_name = action.get("animlib_name", "Unknown")

                    # Validate that the UUID still exists with the same name
                    # If animation was renamed in desktop app, metadata is stale
                    if source_uuid and source_name:
                        is_valid = self._validate_library_metadata(source_uuid, source_name)

                        if not is_valid:
                            # Library animation was renamed or deleted - clear metadata
                            self._clear_library_metadata(action)
                            logger.info(f"Cleared stale library metadata for action (was: {source_name})")

                            # Treat as new animation - skip version dialog
                            self._state = 'DETERMINE_NAME'
                            return {'RUNNING_MODAL'}

                    # Metadata is valid - show version choice dialog
                    source_version = action.get("animlib_version", 1)
                    source_version_label = action.get("animlib_version_label", "v001")
                    source_version_group_id = action.get("animlib_version_group_id", "")

                    logger.info(f"Library action detected: {source_name} ({source_version_label})")

                    # Call the version choice dialog
                    bpy.ops.animlib.version_choice(
                        'INVOKE_DEFAULT',
                        source_name=source_name,
                        source_version=source_version,
                        source_version_label=source_version_label,
                        source_version_group_id=source_version_group_id
                    )

                    # Wait for dialog result in next state
                    self._state = 'WAIT_FOR_DIALOG'
                    self._last_activity_time = time.time()  # Reset watchdog
                    return {'RUNNING_MODAL'}
                else:
                    # Not a library action, proceed normally
                    self._state = 'DETERMINE_NAME'
                    self._last_activity_time = time.time()  # Reset watchdog
                    return {'RUNNING_MODAL'}

            elif self._state == 'WAIT_FOR_DIALOG':
                # Check dialog result
                from .AL_version_choice import ANIMLIB_OT_version_choice
                result, result_data = ANIMLIB_OT_version_choice.get_result()

                if result is None:
                    # Dialog still open, wait (but reset watchdog - user interaction in progress)
                    self._last_activity_time = time.time()
                    return {'RUNNING_MODAL'}
                elif result == 'CANCELLED':
                    # User cancelled, abort capture
                    self.report({'INFO'}, "Capture cancelled")
                    self.cleanup(context)
                    return {'CANCELLED'}
                else:
                    # User made a choice, proceed
                    # Scene properties already set by the dialog
                    self._state = 'DETERMINE_NAME'
                    self._last_activity_time = time.time()  # Reset watchdog
                    return {'RUNNING_MODAL'}

            elif self._state == 'DETERMINE_NAME':
                # Check if we're in versioning mode (set by dialog or pre-existing)
                is_versioning = scene.animlib_is_versioning
                version_source_name = scene.animlib_version_source_name
                version_next_number = scene.animlib_version_next_number

                # Determine animation name
                action = self._context_data['action']

                # Check for studio naming mode
                from ..preferences import get_library_path
                library_path = get_library_path()
                naming_engine = get_naming_engine(library_path)

                if is_versioning and version_source_name:
                    # Creating a new version - strip any existing version suffix first
                    base_name = self._strip_version_suffix(version_source_name)
                    version_label = f"v{version_next_number:03d}"
                    animation_name = f"{base_name}_{version_label}"
                    self._context_data['is_versioning'] = True
                    self._context_data['version_number'] = version_next_number
                    self._context_data['version_label'] = version_label
                    self._context_data['version_group_id'] = scene.animlib_version_source_group_id
                    logger.info(f"Creating new version: {animation_name} (base: {base_name})")
                elif scene.animlib_use_studio_naming and naming_engine.is_studio_mode_enabled:
                    # Studio naming mode - use template-based naming
                    try:
                        # Collect field data from scene properties (pass naming_engine for custom field mapping)
                        field_data = self._collect_naming_fields(scene, naming_engine)

                        # Extract context if not manual mode
                        context_fields = naming_engine.extract_context()
                        # Merge context with manual overrides (manual takes precedence)
                        for key, value in context_fields.items():
                            if key not in field_data or not field_data[key]:
                                field_data[key] = value

                        # Get version number
                        version = 1  # New animation starts at v001

                        # Generate name from template
                        animation_name = naming_engine.generate_name(field_data, version)

                        # Store naming data for save
                        self._context_data['naming_fields'] = field_data
                        self._context_data['naming_template'] = naming_engine._settings.get('naming_template', '')
                        self._context_data['is_versioning'] = False

                        logger.info(f"Studio naming: {animation_name} (fields: {field_data})")
                    except ValueError as e:
                        # Missing required fields - fall back to simple name
                        logger.warning(f"Studio naming failed: {e}, falling back to action name")
                        animation_name = scene.animlib_animation_name
                        self._context_data['is_versioning'] = False
                elif scene.animlib_use_action_name and action.name:
                    animation_name = action.name
                    self._context_data['is_versioning'] = False
                else:
                    animation_name = scene.animlib_animation_name
                    self._context_data['is_versioning'] = False

                self._context_data['animation_name'] = animation_name
                self._state = 'CHECK_COLLISION'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CHECK_COLLISION':
                # Check if folder with same base name already exists (collision detection)
                animation_name = self._context_data['animation_name']
                is_versioning = self._context_data.get('is_versioning', False)

                # Skip collision check if we're already creating a version
                if is_versioning:
                    self._state = 'SAVE_ACTION'
                    self._last_activity_time = time.time()  # Reset watchdog
                    return {'RUNNING_MODAL'}

                # Get base name and check if folder exists
                from pathlib import Path
                from ..preferences import get_library_path
                library_path = get_library_path()
                if library_path:
                    import re
                    base_name = self._strip_version_suffix(animation_name)
                    safe_base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
                    safe_base_name = safe_base_name.strip(' .')
                    safe_base_name = re.sub(r'_+', '_', safe_base_name) or 'unnamed'

                    library_dir = Path(library_path)
                    existing_folder = library_dir / "library" / "actions" / safe_base_name

                    if existing_folder.exists() and any(existing_folder.iterdir()):
                        # Folder exists with files - COLLISION! Stop and ask user to rename.
                        logger.error(f"Collision: folder '{safe_base_name}' already exists")
                        self.report({'ERROR'}, f"Animation '{base_name}' already exists! Please choose a different name, or use 'New Version' to add a version.")
                        self.cleanup(context)
                        return {'CANCELLED'}

                self._state = 'SAVE_ACTION'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'SAVE_ACTION':
                # Save action to library (this includes rendering - will block)
                # But the button is already hidden at this point!
                action = self._context_data['action']
                animation_name = self._context_data['animation_name']
                rig_type = self._context_data['rig_type']

                # Build versioning info dict
                version_info = None
                if self._context_data.get('is_versioning'):
                    version_info = {
                        'version': self._context_data.get('version_number', 1),
                        'version_label': self._context_data.get('version_label', 'v001'),
                        'version_group_id': self._context_data.get('version_group_id'),
                        'is_latest': 1  # New versions are always latest
                    }

                # Build naming info for studio mode
                naming_info = None
                if self._context_data.get('naming_fields'):
                    naming_info = {
                        'naming_fields': self._context_data.get('naming_fields'),
                        'naming_template': self._context_data.get('naming_template', '')
                    }

                blend_file_path, json_file_path, saved_metadata = self.save_action_to_library(
                    action, animation_name, rig_type, scene, version_info, naming_info
                )

                if not blend_file_path or not json_file_path:
                    self.report({'ERROR'}, "Failed to save Action files")
                    self.cleanup(context)
                    return {'CANCELLED'}

                # Store saved metadata for updating action properties
                self._context_data['saved_metadata'] = saved_metadata

                self._state = 'CLEANUP'
                self._last_activity_time = time.time()  # Reset watchdog
                return {'RUNNING_MODAL'}

            elif self._state == 'CLEANUP':
                # Update action's library metadata so subsequent captures know the new version
                action = self._context_data['action']
                saved_metadata = self._context_data.get('saved_metadata')
                if saved_metadata and action:
                    self._update_action_library_metadata(action, saved_metadata)
                    logger.info(f"Updated action metadata: uuid={saved_metadata.get('id')}, version={saved_metadata.get('version')}")

                # Clear form fields
                scene.animlib_animation_name = DEFAULT_ANIMATION_NAME
                scene.animlib_description = ""
                scene.animlib_tags = ""

                # Clear versioning properties
                scene.animlib_is_versioning = False
                scene.animlib_version_source_group_id = ""
                scene.animlib_version_source_name = ""
                scene.animlib_version_next_number = 1

                # Report success
                animation_name = self._context_data['animation_name']
                is_versioning = self._context_data.get('is_versioning', False)
                if is_versioning:
                    version_label = self._context_data.get('version_label', 'v001')
                    self.report({'INFO'}, f"New version '{animation_name}' ({version_label}) saved successfully")
                else:
                    self.report({'INFO'}, f"Action '{animation_name}' saved successfully")

                # Cleanup and finish
                self.cleanup(context)
                return {'FINISHED'}

        except Exception as e:
            logger.error(f"Error during capture: {str(e)}")
            self.report({'ERROR'}, f"Capture failed: {str(e)}")
            self.cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def cleanup(self, context):
        """Cleanup modal operation resources"""
        wm = context.window_manager

        # Remove timer
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        # Clear capture flag - button will reappear
        wm.animlib_is_capturing = False

        # Force UI update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        # Clear state
        self._state = None
        self._context_data = None
        self._start_time = None
        self._last_activity_time = None

    def cancel(self, context):
        """Called when user cancels (ESC key)"""
        self.report({'INFO'}, "Capture cancelled")
        self.cleanup(context)

    def _strip_version_suffix(self, name: str) -> str:
        """
        Strip version suffix from animation name.

        Examples:
            "Jump_v001" -> "Jump"
            "Walk_Cycle_v002" -> "Walk_Cycle"
            "Run" -> "Run" (no suffix)
            "Jump_v001_v002" -> "Jump_v001" (only strips last suffix)

        Args:
            name: Animation name potentially with version suffix

        Returns:
            Base name without version suffix
        """
        import re
        # Match _v followed by 1-4 digits at end of string
        pattern = r'_v\d{1,4}$'
        return re.sub(pattern, '', name)

    def _validate_library_metadata(self, uuid: str, expected_name: str) -> bool:
        """
        Check if UUID exists in library with the expected name.

        This validates that the action's library metadata is still current.
        If the animation was renamed in the desktop app, the metadata is stale.

        Args:
            uuid: The animation UUID from action metadata
            expected_name: The name stored in action metadata

        Returns:
            True if UUID found with matching name, False otherwise
        """
        from pathlib import Path
        import json
        from ..preferences import get_library_path

        library_path = get_library_path()
        if not library_path:
            return False

        library_dir = Path(library_path)

        # Search for JSON file with this UUID in library folders
        for subfolder in ['library/actions', 'library/poses', 'library']:
            search_dir = library_dir / subfolder
            if not search_dir.exists():
                continue

            for anim_folder in search_dir.iterdir():
                if not anim_folder.is_dir():
                    continue

                for json_file in anim_folder.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        if data.get('id') == uuid or data.get('uuid') == uuid:
                            # Found UUID - check if name matches
                            library_name = data.get('name', '')
                            return library_name == expected_name
                    except Exception:
                        continue

        # UUID not found in library
        return False

    def _clear_library_metadata(self, action):
        """
        Clear all library-related metadata from action.

        This is called when the library animation was renamed or deleted,
        making the action's metadata stale. Clearing it allows the action
        to be captured as a new animation.

        Args:
            action: Blender action to clear metadata from
        """
        props_to_clear = [
            "animlib_imported",
            "animlib_uuid",
            "animlib_name",
            "animlib_version",
            "animlib_version_label",
            "animlib_version_group_id",
            "animlib_rig_type"
        ]

        for prop in props_to_clear:
            if prop in action:
                del action[prop]

    def _collect_naming_fields(self, scene, naming_engine=None) -> dict:
        """
        Collect naming field values from scene properties.

        Args:
            scene: Blender scene
            naming_engine: Optional naming engine to get required fields from template

        Returns:
            Dict of field_name -> value
        """
        fields = {}

        # Map of field names to scene properties (expanded list)
        field_props = {
            # Core fields
            'show': 'animlib_naming_show',
            'seq': 'animlib_naming_seq',
            'sequence': 'animlib_naming_seq',
            'shot': 'animlib_naming_shot',
            'asset': 'animlib_naming_asset',
            'task': 'animlib_naming_task',
            'variant': 'animlib_naming_variant',
            # Common aliases
            'showname': 'animlib_naming_showname',
            'project': 'animlib_naming_project',
            'character': 'animlib_naming_character',
            'char': 'animlib_naming_character',
            'episode': 'animlib_naming_episode',
            'ep': 'animlib_naming_episode',
            'name': 'animlib_naming_asset',
            'anim': 'animlib_naming_asset',
            'animation': 'animlib_naming_asset',
        }

        # Fields that map to asset (can use action name)
        asset_field_names = {'asset', 'name', 'anim', 'animation', 'assettype'}

        # Check if we should use action name for asset fields
        use_action_name = getattr(scene, 'animlib_asset_use_action_name', False)
        action_name = ""
        if use_action_name and self._context_data:
            armature = self._context_data.get('armature')
            if armature and armature.animation_data and armature.animation_data.action:
                action_name = armature.animation_data.action.name

        # Custom field slots for unmapped template fields
        custom_fields = ['animlib_naming_custom1', 'animlib_naming_custom2', 'animlib_naming_custom3']

        # If we have a naming engine, use its required fields to properly map custom slots
        if naming_engine:
            required_fields = naming_engine.get_required_fields()
            custom_field_index = 0

            for field_name in required_fields:
                field_lower = field_name.lower()
                prop_name = field_props.get(field_lower)

                if prop_name and hasattr(scene, prop_name):
                    # Use action name for asset fields if toggle is enabled
                    if field_lower in asset_field_names and use_action_name and action_name:
                        fields[field_name] = action_name.strip()
                    else:
                        value = getattr(scene, prop_name, '')
                        if value:
                            fields[field_name] = value.strip()
                elif custom_field_index < len(custom_fields):
                    # This field uses a custom slot
                    custom_prop = custom_fields[custom_field_index]
                    value = getattr(scene, custom_prop, '')
                    if value:
                        fields[field_name] = value.strip()
                    custom_field_index += 1
        else:
            # No naming engine, collect all standard fields
            for field_name, prop_name in field_props.items():
                # Use action name for asset fields if toggle is enabled
                if field_name.lower() in asset_field_names and use_action_name and action_name:
                    fields[field_name] = action_name.strip()
                else:
                    value = getattr(scene, prop_name, '')
                    if value:
                        fields[field_name] = value.strip()

        return fields

    def _update_action_library_metadata(self, action, metadata: dict):
        """
        Update the action's library metadata after saving.

        This allows subsequent captures to know the current version,
        so if user captures v002 and continues editing, next capture
        will correctly offer v003 instead of v002 again.

        Args:
            action: Blender action to update
            metadata: Saved animation metadata dict
        """
        try:
            # Update all library tracking properties
            action["animlib_imported"] = True
            action["animlib_app_version"] = "1.3.0"  # For one-time v1.2→v1.3 migration detection
            action["animlib_uuid"] = metadata.get('id', '')
            action["animlib_version_group_id"] = metadata.get('version_group_id', metadata.get('id', ''))
            action["animlib_version"] = metadata.get('version', 1)
            action["animlib_version_label"] = metadata.get('version_label', 'v001')
            action["animlib_name"] = metadata.get('name', '')
            action["animlib_rig_type"] = metadata.get('rig_type', '')

            logger.debug(f"Updated action '{action.name}' with library metadata: "
                        f"uuid={metadata.get('id')}, version={metadata.get('version')}, "
                        f"version_group_id={metadata.get('version_group_id')}")
        except Exception as e:
            logger.error(f"Error updating action library metadata: {e}")

    def _get_source_animation_metadata(self, version_group_id: str) -> dict:
        """
        Get metadata from source animation for version inheritance.

        When creating a new version, we need to inherit folder_id, folder_path,
        and tags from the source animation. This searches for the source
        animation's JSON file and reads its metadata.

        Args:
            version_group_id: The version group UUID to search for

        Returns:
            dict with 'folder_id', 'folder_path', and 'tags' from source
        """
        from pathlib import Path
        import json
        from ..preferences import get_library_path

        result = {'folder_id': None, 'folder_path': None, 'tags': []}

        library_path = get_library_path()
        if not library_path or not version_group_id:
            return result

        library_dir = Path(library_path)

        # Search for animations in the version group
        # Check both hot storage (library/) and cold storage (_versions/)
        search_locations = [
            library_dir / "library" / "actions",
            library_dir / "library" / "poses",
            library_dir / "library",
            library_dir / "_versions",
        ]

        for search_dir in search_locations:
            if not search_dir.exists():
                continue

            # Walk through all subdirectories
            for json_file in search_dir.rglob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Check if this animation belongs to the same version group
                    file_version_group = data.get('version_group_id')
                    file_uuid = data.get('id') or data.get('uuid')

                    # Match if version_group_id matches OR if UUID matches (for original v001)
                    if file_version_group == version_group_id or file_uuid == version_group_id:
                        # Found a member of this version group
                        # Get folder_id if present
                        if data.get('folder_id') is not None:
                            result['folder_id'] = data['folder_id']
                            logger.debug(f"Found source folder_id: {result['folder_id']}")

                        # Get folder_path if present (more portable than folder_id)
                        if data.get('folder_path'):
                            result['folder_path'] = data['folder_path']
                            logger.debug(f"Found source folder_path: {result['folder_path']}")

                        # Get tags if present
                        source_tags = data.get('tags', [])
                        if source_tags:
                            if isinstance(source_tags, list):
                                result['tags'] = source_tags
                            elif isinstance(source_tags, str):
                                result['tags'] = [t.strip() for t in source_tags.split(',') if t.strip()]
                            logger.debug(f"Found source tags: {result['tags']}")

                        # If we found folder info and tags, we can stop
                        if (result['folder_id'] is not None or result['folder_path']) and result['tags']:
                            return result

                except Exception as e:
                    logger.debug(f"Error reading {json_file}: {e}")
                    continue

        return result

    def save_action_to_library(self, action, animation_name, rig_type, scene, version_info=None, naming_info=None):
        """Save action to library .blend file and create JSON metadata

        Args:
            action: Blender action to save
            animation_name: Name for the animation
            rig_type: Detected or custom rig type
            scene: Blender scene
            version_info: Optional dict with version, version_label, version_group_id, is_latest
            naming_info: Optional dict with naming_fields, naming_template (studio naming)
        """
        try:
            import tempfile
            import shutil
            import json
            import uuid
            from pathlib import Path
            from datetime import datetime
            from ..preferences import get_library_path
            from ..utils.queue_client import animation_queue_client
            
            # Get library path from preferences
            library_path = get_library_path()
            if not library_path:
                logger.error("No library path set in preferences")
                return None, None
            
            library_dir = Path(library_path)

            # Create unique animation ID
            animation_id = str(uuid.uuid4())

            # Get base name without version suffix for folder name
            base_name = self._strip_version_suffix(animation_name)
            # Sanitize for filesystem
            import re
            safe_base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
            safe_base_name = safe_base_name.strip(' .')
            safe_base_name = re.sub(r'_+', '_', safe_base_name) or 'unnamed'

            # Sanitize animation name for filename (includes version)
            safe_anim_name = re.sub(r'[<>:"/\\|?*]', '_', animation_name)
            safe_anim_name = safe_anim_name.strip(' .')
            safe_anim_name = re.sub(r'_+', '_', safe_anim_name) or 'unnamed'

            # Create animation folder: library/actions/{base_name}/
            animation_folder = library_dir / "library" / "actions" / safe_base_name
            animation_folder.mkdir(parents=True, exist_ok=True)

            # HOT/COLD STORAGE: If creating a new version, move ALL existing files to _versions/
            if version_info and version_info.get('version_group_id'):
                # Group files by their version (detected from filename pattern)
                version_files = {}  # version_label -> list of files

                for f in list(animation_folder.iterdir()):
                    if f.is_file():
                        # Try to detect version from filename (e.g., name_v002.blend -> v002)
                        match = re.search(r'_v(\d{3,4})\.\w+$', f.name)
                        if match:
                            version_label = f"v{match.group(1)}"
                        else:
                            # No version suffix - assume v001
                            version_label = "v001"

                        if version_label not in version_files:
                            version_files[version_label] = []
                        version_files[version_label].append(f)

                # Move each version's files to cold storage with transaction-like rollback
                # Track all successful moves for potential rollback
                completed_moves = []  # List of (source, dest) tuples
                json_files_to_update = []  # Track JSON files to update AFTER all moves succeed
                move_failed = False

                for version_label, files in version_files.items():
                    if move_failed:
                        break

                    cold_folder = library_dir / "_versions" / safe_base_name / version_label
                    cold_folder.mkdir(parents=True, exist_ok=True)

                    for f in files:
                        if move_failed:
                            break

                        dest = cold_folder / f.name
                        try:
                            shutil.move(str(f), str(dest))
                            completed_moves.append((str(dest), str(f)))  # Store for rollback
                            logger.info(f"Moved to cold storage: {f.name} -> {version_label}/")

                            # Track JSON files to update AFTER all moves complete
                            if f.suffix == '.json':
                                json_files_to_update.append(dest)
                        except Exception as e:
                            logger.error(f"Failed to move {f.name}: {e}")
                            move_failed = True
                            break

                # Rollback if any move failed
                if move_failed and completed_moves:
                    logger.warning(f"Rolling back {len(completed_moves)} cold storage moves due to failure")
                    for src, dest in reversed(completed_moves):
                        try:
                            shutil.move(src, dest)
                            logger.info(f"Rollback: moved {Path(src).name} back to hot storage")
                        except Exception as re:
                            logger.error(f"Rollback failed for {Path(src).name}: {re}")
                elif not move_failed and json_files_to_update:
                    # Only update is_latest AFTER all files moved successfully (no rollback needed)
                    for json_dest in json_files_to_update:
                        try:
                            with open(json_dest, 'r', encoding='utf-8') as jf:
                                json_data = json.load(jf)
                            json_data['is_latest'] = 0
                            with open(json_dest, 'w', encoding='utf-8') as jf:
                                json.dump(json_data, jf, indent=2)
                            logger.info(f"Updated {json_dest.name}: is_latest = 0")
                        except Exception as je:
                            logger.warning(f"Failed to update is_latest in {json_dest.name}: {je}")

            # Files use animation name (with version) for clarity: walk_cycle_v001.blend
            blend_path = animation_folder / f"{safe_anim_name}.blend"
            json_path = animation_folder / f"{safe_anim_name}.json"
            preview_path = animation_folder / f"{safe_anim_name}.webm"
            thumbnail_path = animation_folder / f"{safe_anim_name}.png"

            # Create minimal blend file with just the action
            temp_fd, temp_path = tempfile.mkstemp(suffix='.blend')
            os.close(temp_fd)

            # Create a minimal blend file containing only our action
            bpy.data.libraries.write(temp_path, {action}, compress=True)

            # Move to final location
            shutil.move(temp_path, str(blend_path))

            # Get armature info
            armature = bpy.context.active_object

            # Detect actual keyframe range from the action
            keyframe_start, keyframe_end = get_action_keyframe_range(action)

            # Fallback to current frame if no keyframes found
            if keyframe_start is None or keyframe_end is None:
                current_frame = bpy.context.scene.frame_current
                keyframe_start = keyframe_end = current_frame

            # Create thumbnail from first frame
            self.create_thumbnail(armature, scene, str(thumbnail_path), keyframe_start)

            # Create preview video in the same folder (using keyframe range)
            self.create_animation_preview(armature, scene, str(preview_path), keyframe_start, keyframe_end)
            bone_names = [bone.name for bone in armature.data.bones]

            # Get tags from UI input
            ui_tags = [tag.strip() for tag in scene.animlib_tags.split(',') if tag.strip()]

            # Inherit folder_id, folder_path and tags from source animation when versioning
            inherited_folder_id = None
            inherited_folder_path = None
            inherited_tags = []

            if version_info and version_info.get('version_group_id'):
                source_metadata = self._get_source_animation_metadata(version_info['version_group_id'])
                inherited_folder_id = source_metadata.get('folder_id')
                inherited_folder_path = source_metadata.get('folder_path')
                inherited_tags = source_metadata.get('tags', [])
                logger.info(f"Inherited from source: folder_id={inherited_folder_id}, folder_path={inherited_folder_path}, tags={inherited_tags}")

            # Merge tags: inherited + UI (deduplicated, preserving order)
            tags = inherited_tags.copy()
            for tag in ui_tags:
                if tag not in tags:
                    tags.append(tag)

            # Create JSON metadata
            # Determine version_group_id - use provided one or default to animation_id
            # Important: use `or` to handle empty strings, not just None
            if version_info and version_info.get('version_group_id'):
                final_version_group_id = version_info['version_group_id']
                logger.info(f"Using version_group_id from version_info: {final_version_group_id}")
            else:
                final_version_group_id = animation_id
                logger.info(f"Using animation_id as version_group_id: {final_version_group_id}")

            if version_info:
                logger.info(f"Version info: version={version_info.get('version')}, label={version_info.get('version_label')}, group_id={version_info.get('version_group_id')}")

            metadata = {
                'id': animation_id,
                'app_version': '1.3.0',  # For one-time v1.2→v1.3 migration detection
                'name': animation_name,
                'description': scene.animlib_description,
                'author': scene.animlib_author,
                'tags': tags,
                'rig_type': rig_type,
                'armature_name': armature.name,
                'bone_count': len(bone_names),
                'bone_names': bone_names,
                'action_name': action.name,
                'frame_start': keyframe_start,
                'frame_end': keyframe_end,
                'frame_count': keyframe_end - keyframe_start + 1,
                'duration_seconds': (keyframe_end - keyframe_start + 1) / scene.render.fps,
                'fps': scene.render.fps,
                'json_file_path': str(json_path),     # Added for consistency
                'blend_file_path': str(blend_path),
                'preview_path': str(preview_path),
                'thumbnail_path': str(thumbnail_path),
                'created_date': datetime.now().isoformat(),
                'file_size_mb': blend_path.stat().st_size / (1024 * 1024),
                # Versioning fields (v5)
                'version': version_info.get('version', 1) if version_info else 1,
                'version_label': version_info.get('version_label', 'v001') if version_info else 'v001',
                'version_group_id': final_version_group_id,
                'is_latest': version_info.get('is_latest', 1) if version_info else 1,
                # Folder inheritance for versioning
                'folder_id': inherited_folder_id,
                'folder_path': inherited_folder_path,
                # Studio naming fields (v9)
                'naming_fields': json.dumps(naming_info.get('naming_fields', {})) if naming_info else None,
                'naming_template': naming_info.get('naming_template', '') if naming_info else None
            }
            
            # Save JSON metadata
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved animation: {blend_path}")
            logger.debug(f"Saved metadata: {json_path}")
            return str(blend_path), str(json_path), metadata

        except Exception as e:
            logger.error(f"Error saving action to library: {e}")
            return None, None, None

    def create_thumbnail(self, armature, scene, thumbnail_path, first_frame):
        """Create thumbnail from first frame of animation"""
        try:
            from ..preferences import get_preview_settings
            prefs = get_preview_settings()

            # Store ALL current settings
            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_color_mode = scene.render.image_settings.color_mode
            original_frame = scene.frame_current
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            # Store media_type if available (Blender 4.5+/5.0)
            original_media_type = None
            if hasattr(scene.render.image_settings, 'media_type'):
                original_media_type = scene.render.image_settings.media_type

            try:
                # Set to first frame
                scene.frame_set(first_frame)

                # Temporarily switch to PNG image format
                # IMPORTANT: In Blender 4.5+/5.0, must set media_type to 'IMAGE' first
                if hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = 'IMAGE'
                scene.render.image_settings.file_format = 'PNG'
                scene.render.image_settings.color_mode = 'RGBA'
                scene.render.filepath = thumbnail_path
                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100
                scene.render.film_transparent = True

                # Configure viewport for clean preview with transparent background
                viewport_settings = self.setup_viewport_for_preview(scene, prefs, transparent_bg=True)

                # Render single frame
                bpy.ops.render.opengl(write_still=True)

                logger.debug(f"Created transparent thumbnail: {thumbnail_path}")

            finally:
                # Always restore viewport settings
                self.restore_viewport_settings(viewport_settings)

                # Restore ALL original settings
                scene.render.filepath = original_filepath
                # Restore media_type first (Blender 4.5+/5.0), then file_format
                if original_media_type and hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = original_media_type
                scene.render.image_settings.file_format = original_format
                scene.render.image_settings.color_mode = original_color_mode
                scene.frame_set(original_frame)
                scene.render.resolution_x = original_resolution_x
                scene.render.resolution_y = original_resolution_y
                scene.render.resolution_percentage = original_resolution_percentage
                scene.render.film_transparent = original_film_transparent

        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")

    def create_animation_preview(self, armature, scene, preview_path, keyframe_start=None, keyframe_end=None):
        """Create transparent WebM preview using Blender's viewport render"""
        try:
            # Get preview settings from preferences
            from ..preferences import get_preview_settings
            prefs = get_preview_settings()
            
            # Use detected keyframe range or fallback to scene range
            if keyframe_start is None or keyframe_end is None:
                keyframe_start = scene.frame_start
                keyframe_end = scene.frame_end
            
            # Store current settings
            original_filepath = scene.render.filepath
            original_format = scene.render.image_settings.file_format
            original_frame_start = scene.frame_start
            original_frame_end = scene.frame_end
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y
            original_resolution_percentage = scene.render.resolution_percentage
            original_engine = scene.render.engine
            original_film_transparent = scene.render.film_transparent
            viewport_settings = None

            # Store media_type if available (Blender 4.5+/5.0)
            original_media_type = None
            if hasattr(scene.render.image_settings, 'media_type'):
                original_media_type = scene.render.image_settings.media_type

            try:
                # Store original timeline (we'll restore it completely)
                # DON'T modify scene timeline - use internal frame range for rendering only

                # Configure render settings for viewport animation (OpenGL playblast)
                # In Blender 5.0+, 'FFMPEG' is no longer a valid file_format enum
                # We render to PNG frames and combine with FFmpeg externally
                use_ffmpeg_direct = False

                # Check if media_type exists (Blender 4.5+/5.0)
                has_media_type = hasattr(scene.render.image_settings, 'media_type')

                try:
                    # Try Blender 4.x direct FFMPEG approach
                    if has_media_type:
                        scene.render.image_settings.media_type = 'VIDEO'
                    scene.render.image_settings.file_format = 'FFMPEG'
                    scene.render.ffmpeg.format = 'WEBM'
                    scene.render.ffmpeg.codec = 'WEBM'
                    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
                    scene.render.ffmpeg.audio_codec = 'NONE'
                    scene.render.filepath = str(preview_path).replace('.webm', '')
                    use_ffmpeg_direct = True
                    logger.debug("Using direct FFMPEG video output (Blender 4.x)")
                except (TypeError, AttributeError):
                    # Blender 5.0+ - render to PNG frames, combine later
                    if has_media_type:
                        scene.render.image_settings.media_type = 'IMAGE'
                    scene.render.image_settings.file_format = 'PNG'
                    # Use #### for frame number padding (Blender convention)
                    scene.render.filepath = str(preview_path).replace('.webm', '_frame_####')
                    use_ffmpeg_direct = False
                    logger.debug("Using PNG frame sequence (Blender 5.0+)")

                # Resolution from preferences
                scene.render.resolution_x = prefs['resolution_x']
                scene.render.resolution_y = prefs['resolution_y']
                scene.render.resolution_percentage = 100

                # Keep viewport background visible (no transparency needed)
                scene.render.film_transparent = False

                # Configure viewport for clean preview (but restore properly)
                # Uses the user's current viewport angle (no preset override)
                viewport_settings = self.setup_viewport_for_preview(scene, prefs)

                # Manually render keyframe range without touching scene timeline
                self.render_keyframe_range(scene, keyframe_start, keyframe_end)

                # Handle output files
                import glob
                import os
                from pathlib import Path

                preview_path_obj = Path(preview_path)
                parent_dir = preview_path_obj.parent
                base_name = preview_path_obj.stem

                # Log all files in directory for debugging
                all_files = list(parent_dir.glob("*"))
                logger.debug(f"Files in {parent_dir}: {[f.name for f in all_files]}")

                if use_ffmpeg_direct:
                    # Blender 4.x - rename the video file with frame numbers
                    pattern = str(parent_dir / f"{base_name}*.webm")
                    rendered_files = glob.glob(pattern)
                    logger.debug(f"Looking for rendered files with pattern: {pattern}")
                    logger.debug(f"Found files: {rendered_files}")

                    if rendered_files:
                        for actual_file in rendered_files:
                            if actual_file != str(preview_path):
                                logger.debug(f"Renaming {actual_file} to {preview_path}")
                                if os.path.exists(str(preview_path)):
                                    os.remove(str(preview_path))
                                os.rename(actual_file, str(preview_path))
                                logger.info(f"Renamed video file: {preview_path}")
                                break
                    else:
                        logger.warning(f"Could not find rendered video file")
                else:
                    # Blender 5.0+ - combine PNG frames into WebM using FFmpeg
                    # Blender outputs: uuid_frame_0001.png, uuid_frame_0002.png, etc.
                    frame_pattern = str(parent_dir / f"{base_name}_frame_*.png")
                    png_files = sorted(glob.glob(frame_pattern))
                    logger.debug(f"Found {len(png_files)} PNG frames matching {frame_pattern}")

                    if png_files:
                        # Use FFmpeg to combine frames into video
                        success = self.combine_frames_to_video(
                            parent_dir,
                            f"{base_name}_frame_",
                            preview_path,
                            scene.render.fps,
                            png_files
                        )
                        if not success:
                            logger.warning("Failed to create video from frames")
                        # Clean up PNG frames
                        for png_file in png_files:
                            try:
                                os.remove(png_file)
                            except Exception as e:
                                logger.debug(f"Could not remove temp PNG {png_file}: {e}")
                    else:
                        logger.warning("No PNG frames rendered")

                logger.debug(f"Created viewport animation preview: {preview_path}")

            finally:
                # Always restore viewport settings first (critical for user experience)
                # This will restore saved settings or force visible defaults
                self.restore_viewport_settings(viewport_settings)

                # Always restore original render settings, even if error occurs
                scene.render.filepath = original_filepath
                # Restore media_type first (Blender 4.5+/5.0), then file_format
                if original_media_type and hasattr(scene.render.image_settings, 'media_type'):
                    scene.render.image_settings.media_type = original_media_type
                scene.render.image_settings.file_format = original_format
                scene.frame_start = original_frame_start
                scene.frame_end = original_frame_end
                scene.render.resolution_x = original_resolution_x
                scene.render.resolution_y = original_resolution_y
                scene.render.resolution_percentage = original_resolution_percentage
                scene.render.film_transparent = original_film_transparent
            
        except Exception as e:
            logger.error(f"Error creating animation preview: {e}")
    
    def render_keyframe_range(self, scene, keyframe_start, keyframe_end):
        """Render animation using keyframe range without modifying scene timeline"""
        try:
            # Store current frame and timeline
            original_frame = scene.frame_current
            original_start = scene.frame_start
            original_end = scene.frame_end

            # Temporarily set the scene range for the animation render only
            scene.frame_start = keyframe_start
            scene.frame_end = keyframe_end

            logger.debug(f"Rendering viewport animation: frames {keyframe_start} to {keyframe_end}")
            logger.debug(f"Output path: {scene.render.filepath}")
            logger.debug(f"Format: {scene.render.image_settings.file_format}")

            # Use built-in OpenGL animation render with context override for 5.0 compatibility
            # Find a 3D View area for context
            view3d_area = None
            view3d_region = None
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    view3d_area = area
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            view3d_region = region
                            break
                    break

            if view3d_area and view3d_region:
                # Use temp_override for Blender 4.0+ context override
                with bpy.context.temp_override(area=view3d_area, region=view3d_region):
                    result = bpy.ops.render.opengl(animation=True, view_context=True)
                    logger.debug(f"render.opengl result: {result}")
            else:
                logger.warning("No 3D View found for viewport render, trying without override")
                result = bpy.ops.render.opengl(animation=True, view_context=True)
                logger.debug(f"render.opengl result: {result}")

            # Immediately restore original timeline
            scene.frame_start = original_start
            scene.frame_end = original_end
            scene.frame_current = original_frame

        except Exception as e:
            logger.error(f"Error rendering keyframe range: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Make sure we restore timeline even if there's an error
            try:
                scene.frame_start = original_start
                scene.frame_end = original_end
                scene.frame_current = original_frame
            except Exception as restore_err:
                logger.debug(f"Could not restore timeline state: {restore_err}")
    
    def setup_viewport_for_preview(self, scene, prefs, transparent_bg=False):
        """Configure viewport shading for preview rendering and return settings to restore

        Args:
            scene: Blender scene
            prefs: Preview preferences dict
            transparent_bg: If True, set viewport background to transparent (for thumbnails).
                          If False, keep default background (for videos with FFmpeg colorkey).
        """
        try:
            viewport_settings = {}

            # Get the current 3D viewport
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Store original settings
                            viewport_settings['show_overlays'] = space.overlay.show_overlays
                            viewport_settings['show_gizmo'] = space.show_gizmo
                            viewport_settings['show_region_ui'] = space.show_region_ui
                            viewport_settings['show_region_toolbar'] = space.show_region_toolbar
                            viewport_settings['show_region_header'] = space.show_region_header
                            viewport_settings['shading_type'] = space.shading.type
                            viewport_settings['background_type'] = space.shading.background_type
                            viewport_settings['background_color'] = tuple(space.shading.background_color)

                            # Store viewport view settings (camera angle)
                            viewport_settings['view_location'] = space.region_3d.view_location.copy()
                            viewport_settings['view_rotation'] = space.region_3d.view_rotation.copy()
                            viewport_settings['view_distance'] = space.region_3d.view_distance
                            viewport_settings['view_perspective'] = space.region_3d.view_perspective

                            # Configure for clean preview
                            space.shading.type = 'SOLID'
                            space.overlay.show_overlays = False
                            space.show_gizmo = False
                            space.show_region_ui = False
                            space.show_region_toolbar = False
                            space.show_region_header = False

                            # Set viewport background to transparent for thumbnails
                            # For videos, keep default background so FFmpeg colorkey has black to remove
                            if transparent_bg:
                                space.shading.background_type = 'VIEWPORT'
                                space.shading.background_color = (0.0, 0.0, 0.0)  # RGB only (no alpha)

                            # Use STUDIO lighting for quality previews
                            space.shading.light = 'STUDIO'
                            # Try studio lights in order of preference
                            for light in ['studio.sl', 'rim.sl', 'outdoor.sl', 'Default']:
                                try:
                                    space.shading.studio_light = light
                                    logger.debug(f"Using studio light: {light}")
                                    break
                                except TypeError:
                                    continue
                            space.shading.studiolight_intensity = 1.0

                            return viewport_settings
                    break
            
            return viewport_settings
            
        except Exception as e:
            logger.error(f"Error setting up viewport for preview: {e}")
            return {}
    
    def restore_viewport_settings(self, viewport_settings):
        """Restore original viewport settings after preview generation"""
        try:
            # Get the current 3D viewport and restore settings
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Restore original settings (or defaults if not saved)
                            # Using True as default to ensure UI is visible again
                            if viewport_settings:
                                space.overlay.show_overlays = viewport_settings.get('show_overlays', True)
                                space.show_gizmo = viewport_settings.get('show_gizmo', True)
                                space.show_region_ui = viewport_settings.get('show_region_ui', True)
                                space.show_region_toolbar = viewport_settings.get('show_region_toolbar', True)
                                space.show_region_header = viewport_settings.get('show_region_header', True)
                                space.shading.type = viewport_settings.get('shading_type', 'SOLID')
                                space.shading.background_type = viewport_settings.get('background_type', 'THEME')
                                space.shading.background_color = viewport_settings.get('background_color', (0.05, 0.05, 0.05))

                                # Restore viewport view (camera angle)
                                if 'view_location' in viewport_settings:
                                    space.region_3d.view_location = viewport_settings['view_location']
                                if 'view_rotation' in viewport_settings:
                                    space.region_3d.view_rotation = viewport_settings['view_rotation']
                                if 'view_distance' in viewport_settings:
                                    space.region_3d.view_distance = viewport_settings['view_distance']
                                if 'view_perspective' in viewport_settings:
                                    space.region_3d.view_perspective = viewport_settings['view_perspective']
                            else:
                                # Force restore to visible defaults if no settings were saved
                                space.overlay.show_overlays = True
                                space.show_gizmo = True
                                space.show_region_ui = True
                                space.show_region_toolbar = True
                                space.show_region_header = True
                                space.shading.background_type = 'THEME'

                            logger.debug("Viewport overlays, UI, and view angle restored")
                            break
                    break

        except Exception as e:
            logger.error(f"Error restoring viewport settings: {e}")
    
    def find_ffmpeg_executable(self):
        """Find FFmpeg executable using hybrid detection: system PATH -> bundled -> None"""
        try:
            # First, check system PATH using shutil.which()
            system_ffmpeg = shutil.which('ffmpeg')
            if system_ffmpeg:
                logger.debug(f"Found FFmpeg in system PATH: {system_ffmpeg}")
                return system_ffmpeg

            # Second, check bundled bin/ directory
            addon_dir = os.path.dirname(__file__)
            bundled_ffmpeg = os.path.join(addon_dir, '..', 'bin', 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
            bundled_ffmpeg = os.path.abspath(bundled_ffmpeg)

            if os.path.isfile(bundled_ffmpeg) and os.access(bundled_ffmpeg, os.X_OK):
                logger.debug(f"Found bundled FFmpeg: {bundled_ffmpeg}")
                return bundled_ffmpeg

            # Not found anywhere - provide helpful message
            logger.warning("FFmpeg not found. Video previews will not be generated.")
            logger.warning("To fix: Install FFmpeg and add to system PATH, or place ffmpeg.exe in:")
            logger.warning(f"  {os.path.dirname(bundled_ffmpeg)}")
            logger.warning("Download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/")
            return None

        except Exception as e:
            logger.error(f"Error finding FFmpeg: {e}")
            return None

    def combine_frames_to_video(self, frames_dir, frame_prefix, output_path, fps, png_files):
        """Combine PNG frames into WebM video using FFmpeg (for Blender 5.0+)"""
        try:
            ffmpeg_path = self.find_ffmpeg_executable()
            if not ffmpeg_path:
                logger.warning("FFmpeg not available - cannot create video from frames")
                return False

            if not png_files:
                logger.warning("No PNG files provided")
                return False

            # Use glob pattern with wildcard instead of numbered sequence
            # This is more reliable since Blender's frame numbers vary
            import re
            from pathlib import Path

            # Extract the first frame number to determine start_number
            first_file = Path(png_files[0]).name
            # Match pattern like: uuid_frame_0001.png
            match = re.search(r'(\d+)\.png$', first_file)
            if match:
                start_number = int(match.group(1))
            else:
                start_number = 1

            input_pattern = str(frames_dir / f"{frame_prefix}%04d.png")
            logger.debug(f"FFmpeg input pattern: {input_pattern}, start_number: {start_number}")

            ffmpeg_cmd = [
                ffmpeg_path,
                '-framerate', str(int(fps)),
                '-start_number', str(start_number),
                '-i', input_pattern,
                '-c:v', 'libvpx-vp9',
                '-b:v', '0',
                '-crf', '30',
                '-pix_fmt', 'yuv420p',
                '-y',
                str(output_path)
            ]

            logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Created video from frames: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error combining frames to video: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def convert_to_transparent_webm(self, mp4_path, webm_path):
        """Convert MP4 with black background to transparent WebM using FFmpeg"""
        try:
            # Find FFmpeg executable
            ffmpeg_path = self.find_ffmpeg_executable()
            if not ffmpeg_path:
                logger.warning("FFmpeg not available - cannot create transparent WebM")
                logger.info("Falling back to MP4 with black background")
                # Rename MP4 to WebM as fallback
                if os.path.exists(mp4_path):
                    os.rename(mp4_path, webm_path)
                return

            # FFmpeg command to create transparent WebM
            # Strategy: Use colorkey to make black transparent, output as VP9 with alpha
            ffmpeg_cmd = [
                ffmpeg_path,
                '-i', mp4_path,
                '-vf', 'colorkey=0x000000:0.3:0.2',  # Make black transparent
                '-c:v', 'libvpx-vp9',  # VP9 codec
                '-pix_fmt', 'yuva420p',  # Pixel format with alpha channel
                '-auto-alt-ref', '0',  # Required for VP9 with alpha
                '-b:v', '0',  # Use CRF mode
                '-crf', '18',  # Quality (lower = better, 15-25 recommended)
                '-y',  # Overwrite output
                webm_path
            ]

            logger.debug("Converting to transparent WebM...")
            logger.debug(f"Input MP4: {mp4_path}")
            logger.debug(f"Output WebM: {webm_path}")
            logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

            # Run FFmpeg
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )

            logger.debug(f"FFmpeg return code: {result.returncode}")

            if result.returncode == 0:
                # Check if output file exists
                if os.path.exists(webm_path):
                    webm_size = os.path.getsize(webm_path)
                    logger.info(f"Transparent WebM created successfully: {webm_size} bytes")

                    # Delete temporary MP4
                    try:
                        os.remove(mp4_path)
                        logger.debug(f"Deleted temporary MP4: {mp4_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete temp MP4: {e}")
                else:
                    logger.error("WebM output file not created")
                    # Keep MP4 as fallback
                    if os.path.exists(mp4_path):
                        os.rename(mp4_path, webm_path)
            else:
                logger.error("FFmpeg conversion failed")
                if result.stderr:
                    logger.error(f"FFmpeg error: {result.stderr}")
                # Keep MP4 as fallback
                if os.path.exists(mp4_path):
                    os.rename(mp4_path, webm_path)

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg conversion timed out")
            # Keep MP4 as fallback
            if os.path.exists(mp4_path):
                os.rename(mp4_path, webm_path)
        except Exception as e:
            logger.error(f"Error converting to transparent WebM: {e}")
            # Keep MP4 as fallback
            if os.path.exists(mp4_path):
                os.rename(mp4_path, webm_path)
