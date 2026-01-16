import bpy
import sys
import os
import addon_utils

def install_addon(zip_path, storage_path=None, exe_path=None):
    print(f"Starting installation of addon from: {zip_path}")
    
    if not os.path.exists(zip_path):
        print(f"Error: Zip file not found at {zip_path}")
        return False

    try:
        # Install the addon
        print("Installing addon...")
        bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
        
        # The addon name is typically the folder name inside the zip
        # For this project it is 'animation_library_addon'
        addon_name = "animation_library_addon"
        
        # Enable the addon
        print(f"Enabling addon '{addon_name}'...")
        addon_utils.enable(addon_name, default_set=True)
        
        # Get preferences object
        prefs = None
        if addon_name in bpy.context.preferences.addons:
            prefs = bpy.context.preferences.addons[addon_name].preferences
        else:
            print(f"Warning: Addon '{addon_name}' not found in preferences after enabling.")
        
        if prefs:
            # Configure storage path if provided
            if storage_path and storage_path.lower() != "none":
                print(f"Configuring storage path: {storage_path}")
                try:
                    prefs.actions_library_path = storage_path
                    print("Storage path set successfully.")
                except Exception as e:
                    print(f"Error setting storage path: {e}")

            # Configure executable path if provided
            if exe_path and exe_path.lower() != "none":
                print(f"Configuring executable path: {exe_path}")
                try:
                    prefs.desktop_app_exe_path = exe_path
                    # Also force mode to PRODUCTION as requested
                    prefs.desktop_app_launch_mode = 'PRODUCTION'
                    print("Executable path and PRODUCTION mode set successfully.")
                except Exception as e:
                    print(f"Error setting executable path: {e}")
        
        # Save preferences to make it persistent
        print("Saving user preferences...")
        bpy.ops.wm.save_userpref()
        
        print("Action Library installed and enabled successfully.")
        return True
        
    except Exception as e:
        print(f"Error during installation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Get arguments after "--"
    try:
        args_idx = sys.argv.index("--")
        args = sys.argv[args_idx + 1:]
        
        if not args:
            print("Error: No zip path provided")
            sys.exit(1)
            
        zip_path = args[0]
        
        # Check for optional arguments
        storage_path = None
        exe_path = None
        
        if len(args) > 1:
            storage_path = args[1]
            
        if len(args) > 2:
            exe_path = args[2]
            
        success = install_addon(zip_path, storage_path, exe_path)
        
        if not success:
            sys.exit(1)
            
    except ValueError:
        print("Error: Arguments not found. Use '--' to separate arguments.")
        sys.exit(1)
