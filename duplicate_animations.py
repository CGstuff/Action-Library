"""
Script to duplicate animations for stress testing UI loading times
"""

import sys
import uuid
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from animation_library.services.database_service import get_database_service


def duplicate_animations(target_count: int = 200):
    """
    Duplicate existing animations to reach target count

    Args:
        target_count: Total number of animations to have
    """
    db = get_database_service()

    # Get existing animations
    existing_anims = db.get_all_animations()
    current_count = len(existing_anims)

    print(f"Current animation count: {current_count}")
    print(f"Target animation count: {target_count}")

    if current_count >= target_count:
        print(f"Already have {current_count} animations. No duplication needed.")
        return

    if current_count == 0:
        print("No animations to duplicate!")
        return

    # Calculate how many duplicates we need
    duplicates_needed = target_count - current_count
    print(f"Creating {duplicates_needed} duplicate animations...")

    # Duplicate animations in batches
    template_anims = existing_anims.copy()
    duplicates_created = 0

    while duplicates_created < duplicates_needed:
        # Use existing animations as templates (cycle through them)
        template = template_anims[duplicates_created % len(template_anims)]

        # Create new animation data with unique UUID
        new_uuid = str(uuid.uuid4())
        new_name = f"{template['name']}_copy_{duplicates_created + 1}"

        # Prepare animation data (keeping same file paths for stress test)
        anim_data = {
            'uuid': new_uuid,
            'name': new_name,
            'description': template.get('description', ''),
            'folder_id': template['folder_id'],
            'rig_type': template.get('rig_type', 'unknown'),
            'armature_name': template.get('armature_name', ''),
            'bone_count': template.get('bone_count', 0),
            'frame_start': template.get('frame_start', 0),
            'frame_end': template.get('frame_end', 0),
            'frame_count': template.get('frame_count', 0),
            'duration_seconds': template.get('duration_seconds', 0),
            'fps': template.get('fps', 30),
            'blend_file_path': template.get('blend_file_path', ''),
            'json_file_path': template.get('json_file_path', ''),
            'preview_path': template.get('preview_path', ''),
            'thumbnail_path': template.get('thumbnail_path', ''),
            'file_size_mb': template.get('file_size_mb', 0),
            'tags': template.get('tags', []),
            'author': template.get('author', ''),
            'use_custom_thumbnail_gradient': template.get('use_custom_thumbnail_gradient', 0),
            'thumbnail_gradient_top': template.get('thumbnail_gradient_top'),
            'thumbnail_gradient_bottom': template.get('thumbnail_gradient_bottom'),
        }

        # Add to database
        result = db.add_animation(anim_data)
        if result:
            duplicates_created += 1
            if duplicates_created % 50 == 0:
                print(f"  Created {duplicates_created}/{duplicates_needed} duplicates...")
        else:
            print(f"  Failed to create duplicate {duplicates_created + 1}")

    print(f"\n✅ Duplication complete!")
    print(f"Total animations now: {current_count + duplicates_created}")

    # Verify
    final_anims = db.get_all_animations()
    print(f"Verified count: {len(final_anims)}")


if __name__ == "__main__":
    import time

    print("=" * 60)
    print("Animation Duplication Script - Stress Testing")
    print("=" * 60)
    print()

    start_time = time.time()
    duplicate_animations(target_count=200)
    end_time = time.time()

    print(f"\nTime taken: {end_time - start_time:.2f} seconds")
    print("\nYou can now test UI loading performance with 200 animations!")
