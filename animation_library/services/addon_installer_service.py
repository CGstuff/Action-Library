"""
Blender Addon Installation Service

Handles automatic installation of the Animation Library addon to Blender.
Requires manual path specification for reliability (no auto-detection).
Compatible with Blender 4.4+, tested on 4.5.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class AddonInstallerService:
    """Service for installing Blender addon programmatically"""

    ADDON_FOLDER_NAME = "animation_library_addon"

    def __init__(self):
        """
        Initialize addon installer service (v2)

        Auto-detects project root based on file location or PyInstaller bundle
        """
        # Check if running as PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # Running as compiled exe - use internal _MEIPASS path
            base_path = Path(sys._MEIPASS)
            self.addon_source_path = base_path / "blender_plugin"
            logger.info(f"Running as bundled exe, using internal plugin path: {self.addon_source_path}")
        else:
            # Running in development mode - auto-detect v2 root
            # This file is at: animation_library_v2/animation_library/services/addon_installer_service.py
            # Plugin is at: animation_library_v2/blender_plugin/
            current_file = Path(__file__)
            v2_root = current_file.parent.parent.parent  # Up 3 levels
            self.addon_source_path = v2_root / "blender_plugin"
            logger.info(f"Running in dev mode, using project plugin path: {self.addon_source_path}")

    def verify_blender_executable(self, blender_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        Verify that the provided path is a valid Blender executable

        Args:
            blender_path: Path to blender.exe

        Returns:
            Tuple of (is_valid, message, version_string)
        """
        blender_path = Path(blender_path)

        # Check if file exists
        if not blender_path.exists():
            return False, "Blender executable not found at specified path", None

        # Check if it's an executable
        if not blender_path.is_file():
            return False, "Specified path is not a file", None

        # Check if filename is blender.exe (Windows) or blender (Unix)
        if blender_path.name.lower() not in ['blender.exe', 'blender']:
            return False, "File does not appear to be a Blender executable", None

        # Try to get Blender version
        try:
            result = subprocess.run(
                [str(blender_path), '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            version_output = result.stdout.strip()

            # Parse version (e.g., "Blender 4.5.0")
            if "Blender" in version_output:
                version_line = version_output.split('\n')[0]
                logger.info(f"Found Blender: {version_line}")
                return True, f"Valid Blender installation: {version_line}", version_line
            else:
                return False, "Could not verify Blender version", None

        except subprocess.TimeoutExpired:
            return False, "Blender executable timed out during verification", None
        except Exception as e:
            return False, f"Error verifying Blender: {str(e)}", None

    def get_blender_addons_directory(self, blender_path: str) -> Optional[Path]:
        """
        Get the Blender addons directory for the user

        Args:
            blender_path: Path to blender.exe

        Returns:
            Path to addons directory or None if not found
        """
        blender_path = Path(blender_path)
        logger.info(f"Attempting to locate Blender addons directory for: {blender_path}")

        # First, get the Blender version from the executable
        _, _, version_str = self.verify_blender_executable(str(blender_path))
        blender_version = None

        if version_str:
            # Parse version like "Blender 4.4.3" -> "4.4"
            try:
                parts = version_str.split()
                for part in parts:
                    if part[0].isdigit() and '.' in part:
                        # Found version number like "4.4.3"
                        version_parts = part.split('.')
                        blender_version = f"{version_parts[0]}.{version_parts[1]}"
                        logger.info(f"Detected Blender version: {blender_version}")
                        break
            except Exception as e:
                logger.warning(f"Could not parse Blender version: {e}")

        # Get Blender config path
        try:
            # Run Blender to get config directory
            logger.info("Attempting to get config directory from Blender...")
            script = "import bpy; print(bpy.utils.resource_path('USER'))"
            result = subprocess.run(
                [str(blender_path), '--background', '--python-expr', script],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse output for config path
            lines = result.stdout.strip().split('\n')
            logger.debug(f"Blender output: {lines}")
            for line in lines:
                potential_path = Path(line.strip())
                if potential_path.exists() and 'Blender' in str(potential_path):
                    # Navigate to scripts/addons
                    addons_dir = potential_path / "scripts" / "addons"
                    if addons_dir.exists() or addons_dir.parent.exists():
                        addons_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Found Blender addons directory via config path: {addons_dir}")
                        return addons_dir

            # Fallback: construct path manually using detected version
            # Windows: C:\Users\<user>\AppData\Roaming\Blender Foundation\Blender\4.4\scripts\addons
            # Linux: ~/.config/blender/4.4/scripts/addons
            # macOS: ~/Library/Application Support/Blender/4.4/scripts/addons

            logger.info("Config path method failed, using fallback path construction...")

            if not blender_version:
                logger.error("Could not determine Blender version for fallback path")
                return None

            if sys.platform == 'win32':
                base = Path(os.environ.get('APPDATA', '')) / "Blender Foundation" / "Blender"
            elif sys.platform == 'darwin':
                base = Path.home() / "Library" / "Application Support" / "Blender"
            else:  # Linux
                base = Path.home() / ".config" / "blender"

            logger.info(f"Base Blender config path: {base}")

            # Use the specific version directory that matches the blender.exe
            version_dir = base / blender_version
            addons_dir = version_dir / "scripts" / "addons"

            logger.info(f"Constructed addons path: {addons_dir}")

            # Create the directory structure even if it doesn't exist yet
            # Blender will use it once the addon is installed
            try:
                addons_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Successfully created/verified Blender {blender_version} addons directory: {addons_dir}")
                return addons_dir
            except Exception as mkdir_error:
                logger.error(f"Could not create addons directory at {addons_dir}: {mkdir_error}")
                return None

        except Exception as e:
            logger.error(f"Error getting Blender addons directory: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def install_addon(self, blender_path: str) -> Tuple[bool, str]:
        """
        Install the addon to Blender

        Args:
            blender_path: Path to blender.exe

        Returns:
            Tuple of (success, message)
        """
        # Verify Blender executable
        is_valid, verify_msg, version = self.verify_blender_executable(blender_path)
        if not is_valid:
            return False, verify_msg

        # Check source addon exists FIRST
        if not self.addon_source_path.exists():
            error_msg = f"Addon source not found at: {self.addon_source_path}\n\n"
            error_msg += "This usually means the Blender plugin was not bundled with the application.\n"
            error_msg += "If you're running from source, make sure 'blender_plugin' folder exists.\n"
            error_msg += "If you're running the compiled exe, the plugin should be embedded."
            logger.error(error_msg)
            return False, error_msg

        # Get addons directory
        logger.info(f"Looking for Blender addons directory for version: {version}")
        addons_dir = self.get_blender_addons_directory(blender_path)
        if not addons_dir:
            error_msg = f"Could not locate Blender addons directory for version {version}\n\n"
            error_msg += "Tried to create directory structure but failed.\n"
            error_msg += f"Expected path: %APPDATA%\\Blender Foundation\\Blender\\{version if version else 'VERSION'}\\scripts\\addons\n\n"
            error_msg += "Please check the application logs for more details."
            logger.error(error_msg)
            return False, error_msg

        # Destination path
        addon_dest_path = addons_dir / self.ADDON_FOLDER_NAME

        try:
            # Remove existing installation if present
            if addon_dest_path.exists():
                logger.info(f"Removing existing addon at {addon_dest_path}")
                shutil.rmtree(addon_dest_path)

            # Copy addon files
            logger.info(f"Installing addon to {addon_dest_path}")
            shutil.copytree(self.addon_source_path, addon_dest_path)

            return True, f"Successfully installed addon to:\n{addon_dest_path}\n\nPlease restart Blender and enable the addon in:\nEdit > Preferences > Add-ons > Search for 'Action Library'"

        except Exception as e:
            logger.error(f"Error installing addon: {e}")
            return False, f"Error installing addon: {str(e)}"

    def check_addon_installed(self, blender_path: str) -> Tuple[bool, Optional[Path]]:
        """
        Check if the addon is currently installed

        Args:
            blender_path: Path to blender.exe

        Returns:
            Tuple of (is_installed, installation_path)
        """
        addons_dir = self.get_blender_addons_directory(blender_path)
        if not addons_dir:
            return False, None

        addon_dest_path = addons_dir / self.ADDON_FOLDER_NAME

        if addon_dest_path.exists() and addon_dest_path.is_dir():
            # Check if it has the __init__.py file
            init_file = addon_dest_path / "__init__.py"
            if init_file.exists():
                return True, addon_dest_path

        return False, None
