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
import zipfile
import tempfile
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
            # Locate the installation script in bundled mode
            # It should be in animation_library/services/utils/install_addon.py
            # But in PyInstaller it might be flattened or structured differently depending on spec
            # We will assume it is at base_path/animation_library/services/utils/install_addon.py
            self.install_script_path = base_path / "animation_library" / "services" / "utils" / "install_addon.py"
            logger.info(f"Running as bundled exe, using internal plugin path: {self.addon_source_path}")
        else:
            # Running in development mode - auto-detect v2 root
            # This file is at: animation_library_v2/animation_library/services/addon_installer_service.py
            current_file = Path(__file__)
            v2_root = current_file.parent.parent.parent  # Up 3 levels
            self.addon_source_path = v2_root / "blender_plugin"
            
            # Script is at animation_library/services/utils/install_addon.py
            self.install_script_path = current_file.parent / "utils" / "install_addon.py"
            
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

    def _create_addon_zip(self) -> str:
        """
        Creates a temporary zip file of the addon.
        
        Returns:
            Path to the created zip file
        """
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f"{self.ADDON_FOLDER_NAME}.zip")
        
        logger.info(f"Creating addon zip at: {zip_path}")
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Walk the directory structure
                for root, dirs, files in os.walk(self.addon_source_path):
                    for file in files:
                        if file.endswith('.pyc') or file.endswith('__pycache__'):
                            continue
                            
                        file_path = os.path.join(root, file)
                        # Calculate relative path for zip
                        # We want the folder inside the zip to be 'animation_library_addon'
                        rel_path = os.path.relpath(file_path, self.addon_source_path)
                        zip_path_in_archive = os.path.join(self.ADDON_FOLDER_NAME, rel_path)
                        
                        zipf.write(file_path, zip_path_in_archive)
            
            logger.info("Zip created successfully")
            return zip_path
            
        except Exception as e:
            logger.error(f"Failed to zip addon: {e}")
            raise

    def install_addon(self, blender_path: str, storage_path: str = None, exe_path: str = None) -> Tuple[bool, str]:
        """
        Install the addon to Blender using a zip file and background script.
        
        Args:
            blender_path: Path to blender.exe
            storage_path: Optional path to the animation library storage to configure in the addon
            exe_path: Optional path to the current application executable to configure in the addon
            
        Returns:
            Tuple of (success, message)
        """
        # Verify Blender executable
        is_valid, verify_msg, version = self.verify_blender_executable(blender_path)
        if not is_valid:
            return False, verify_msg

        # Check source addon exists
        if not self.addon_source_path.exists():
            return False, f"Addon source not found at: {self.addon_source_path}"

        # Check installation script exists
        if not self.install_script_path.exists():
             # Fallback check for dev environment vs packaged inconsistencies
             # If we can't find it where we expect, try to find it relative to this file
             current_dir = Path(__file__).parent
             alt_path = current_dir / "utils" / "install_addon.py"
             if alt_path.exists():
                 self.install_script_path = alt_path
             else:
                return False, f"Installation script not found at: {self.install_script_path}"

        zip_path = None
        try:
            # 1. Create Zip
            zip_path = self._create_addon_zip()
            
            # 2. Run Blender with install script
            logger.info("Running Blender to install addon...")
            
            # Command: blender.exe --background --python install_addon.py -- path/to/zip [storage_path] [exe_path]
            cmd = [
                str(blender_path),
                "--background",
                "--python", str(self.install_script_path),
                "--", str(zip_path)
            ]
            
            # Add storage path (pass "None" string if not provided but we need to pass exe_path)
            if storage_path:
                cmd.append(str(storage_path))
            elif exe_path:
                cmd.append("None")
                
            # Add exe path if provided
            if exe_path:
                cmd.append(str(exe_path))
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Log output for debugging
            logger.info(f"Blender Install Output (stdout): {process.stdout}")
            if process.stderr:
                logger.warning(f"Blender Install Output (stderr): {process.stderr}")
                
            # Check success based on output or exit code
            if process.returncode == 0 and "Action Library installed and enabled successfully" in process.stdout:
                return True, "Action Library installed and enabled successfully."
            else:
                # Try to extract error message
                error_lines = [line for line in process.stdout.split('\n') if "Error" in line]
                error_msg = "\n".join(error_lines) if error_lines else "Unknown error during installation"
                return False, f"Installation failed:\n{error_msg}\n\nCheck logs for details."

        except Exception as e:
            logger.error(f"Error installing addon: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, f"Error installing addon: {str(e)}"
            
        finally:
            # Cleanup zip
            if zip_path and os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                    # Try to remove temp dir if empty
                    os.rmdir(os.path.dirname(zip_path))
                except:
                    pass

    def check_addon_installed(self, blender_path: str) -> Tuple[bool, Optional[Path], Optional[Tuple[int, int, int]]]:
        """
        Check if the addon is currently installed

        Args:
            blender_path: Path to blender.exe

        Returns:
            Tuple of (is_installed, installation_path, version_tuple)
        """
        addons_dir = self.get_blender_addons_directory(blender_path)
        if not addons_dir:
            return False, None, None

        addon_dest_path = addons_dir / self.ADDON_FOLDER_NAME

        if addon_dest_path.exists() and addon_dest_path.is_dir():
            # Check if it has the __init__.py file
            init_file = addon_dest_path / "__init__.py"
            if init_file.exists():
                # Parse version from __init__.py
                try:
                    with open(init_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Simple parsing for bl_info dictionary
                    # Looking for: "version": (1, 3, 1),
                    import re
                    match = re.search(r'"version"\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)', content)
                    if match:
                        version = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                        return True, addon_dest_path, version
                    
                    # Try finding without quotes (some styles)
                    match = re.search(r"'version'\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)", content)
                    if match:
                        version = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                        return True, addon_dest_path, version
                        
                except Exception as e:
                    logger.warning(f"Failed to parse installed addon version: {e}")
                
                return True, addon_dest_path, None

        return False, None, None
