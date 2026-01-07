"""
Queue-based client for Animation Library v2

Replaces network_client.py with file-based queue communication
Maintains rig detection functionality for compatibility checking
"""

import tempfile
from pathlib import Path
import json
from .logger import get_logger

# Initialize logger
logger = get_logger()

# Blender addon rig signatures (keep local for addon isolation)
RIG_SIGNATURES = {
    'rigify': {
        'required_bones': ['spine_fk', 'torso'],
        'patterns': ['.L', '.R', '_fk', '_ik'],
        'common_bones': ['spine_fk.001', 'spine_fk.002', 'upper_arm_fk.L', 'upper_arm_fk.R',
                        'forearm_fk.L', 'forearm_fk.R', 'thigh_fk.L', 'thigh_fk.R', 'torso',
                        'hips', 'chest', 'shoulder.L', 'shoulder.R']
    },
    'mixamo': {
        'required_bones': ['Hips', 'Spine'],
        'patterns': ['Left', 'Right'],
        'common_bones': ['Spine1', 'Spine2', 'LeftArm', 'RightArm', 'LeftLeg', 'RightLeg',
                        'LeftShoulder', 'RightShoulder', 'LeftForeArm', 'RightForeArm']
    },
    'auto_rig_pro': {
        'required_bones': ['c_spine_01.x'],
        'patterns': ['c_', '.x', '.l', '.r'],
        'common_bones': ['c_spine_02.x', 'c_spine_03.x', 'c_shoulder.l', 'c_shoulder.r',
                        'c_arm_fk.l', 'c_arm_fk.r', 'c_forearm_fk.l', 'c_forearm_fk.r']
    },
    'epic_skeleton': {
        'required_bones': ['pelvis', 'spine_01'],
        'patterns': ['_01', '_02', '_03', '_l', '_r'],
        'common_bones': ['spine_02', 'spine_03', 'upperarm_l', 'upperarm_r',
                        'lowerarm_l', 'lowerarm_r', 'thigh_l', 'thigh_r']
    }
}
RIG_CONFIDENCE_THRESHOLD = 0.6


class AnimationLibraryQueueClient:
    """
    Queue-based client for Animation Library v2 communication

    Communication Method:
    - Desktop app writes "apply_*.json" files to queue directory
    - Blender plugin polls queue and processes requests
    - Plugin deletes files after processing

    Queue Directory:
        Windows: C:\\Users\\{user}\\AppData\\Local\\Temp\\animation_library_queue\\
        Linux/Mac: /tmp/animation_library_queue/

    Queue File Format:
    {
        "status": "pending",
        "animation_id": "uuid-here",
        "animation_name": "Walk Cycle",
        "timestamp": "2024-01-01T12:00:00"
    }
    """

    def __init__(self):
        """Initialize queue client"""
        self.queue_dir = Path(tempfile.gettempdir()) / "animation_library_queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"AnimationLibraryQueueClient initialized. Queue directory: {self.queue_dir}")

    def get_pending_apply_requests(self):
        """
        Get pending apply requests from queue

        Returns:
            list: List of Path objects for pending apply_*.json files,
                  sorted by modification time (newest first)
        """
        try:
            pending_files = list(self.queue_dir.glob("apply_*.json"))
            # Sort by modification time (newest first)
            pending_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            logger.debug(f"Found {len(pending_files)} pending requests")
            return pending_files
        except Exception as e:
            logger.error(f"Error checking queue: {e}")
            return []

    def read_request(self, request_file: Path):
        """
        Read request data from queue file

        Args:
            request_file: Path to queue JSON file

        Returns:
            dict: Request data or None if error

        Note:
            Handles backwards compatibility for older queue format without options.
            If 'options' key is missing, default options are provided.
        """
        try:
            with open(request_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Backwards compatibility: add default options if not present
            if 'options' not in data:
                data['options'] = {
                    "apply_mode": "NEW",
                    "mirror": False,
                    "reverse": False,
                    "selected_bones_only": False,
                    "use_slots": False
                }
                logger.debug("Added default options for backwards compatibility")

            logger.debug(f"Read request: {data.get('animation_name')} ({data.get('animation_id')})")
            logger.debug(f"Options: {data.get('options')}")
            return data
        except Exception as e:
            logger.error(f"Error reading request {request_file}: {e}")
            return None

    def mark_request_completed(self, request_file: Path):
        """
        Mark request as completed by deleting queue file

        Args:
            request_file: Path to queue JSON file

        Returns:
            bool: True if deleted successfully
        """
        try:
            request_file.unlink()
            logger.info(f"Completed request: {request_file.name}")
            return True
        except Exception as e:
            logger.error(f"Error completing request {request_file}: {e}")
            return False

    def detect_rig_type(self, armature):
        """
        Detect rig type from armature bone names

        Args:
            armature: Blender armature object

        Returns:
            tuple: (rig_type: str, confidence: float)
                   rig_type is 'rigify', 'mixamo', 'auto_rig_pro', 'epic_skeleton', or 'unknown'
        """
        if not armature or armature.type != 'ARMATURE':
            logger.warning("Invalid armature object passed to detect_rig_type")
            return 'unknown', 0.0

        bone_names = [bone.name for bone in armature.data.bones]
        bone_set = set(bone_names)
        best_match = 'unknown'
        best_confidence = 0.0

        for rig_type, signature in RIG_SIGNATURES.items():
            score = self.calculate_rig_score(bone_set, signature)
            if score > best_confidence:
                best_confidence = score
                best_match = rig_type

        if best_confidence < RIG_CONFIDENCE_THRESHOLD:
            logger.debug(f"Rig detection below threshold: {best_match} ({best_confidence:.2f})")
            return 'unknown', best_confidence

        logger.info(f"Detected rig type: {best_match} (confidence: {best_confidence:.2f})")
        return best_match, best_confidence

    def calculate_rig_score(self, bone_set, signature):
        """
        Calculate confidence score for a rig type

        Args:
            bone_set: Set of bone names
            signature: Rig signature dict with required_bones, patterns, common_bones

        Returns:
            float: Confidence score (0.0 to 1.0)
        """
        score = 0.0
        total_checks = 0

        # Check required bones (50% weight)
        required_matches = sum(1 for bone in signature['required_bones'] if bone in bone_set)
        if signature['required_bones']:
            score += (required_matches / len(signature['required_bones'])) * 0.5
            total_checks += 0.5

        # Check common bones (30% weight)
        common_matches = sum(1 for bone in signature['common_bones'] if bone in bone_set)
        if signature['common_bones']:
            score += (common_matches / len(signature['common_bones'])) * 0.3
            total_checks += 0.3

        # Check patterns (20% weight)
        if signature['patterns']:
            pattern_matches = 0
            for bone in bone_set:
                if any(pattern in bone for pattern in signature['patterns']):
                    pattern_matches += 1
                    break

            pattern_score = min(1.0, pattern_matches / len(signature['patterns']))
            score += pattern_score * 0.2
            total_checks += 0.2

        return score / total_checks if total_checks > 0 else 0.0


# Global instance
animation_queue_client = AnimationLibraryQueueClient()
