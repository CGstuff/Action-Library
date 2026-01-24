"""
Annotated Export Service - Export video with burned-in annotations

Extracts video frames, composites annotation overlays, and encodes to MP4.
"""

import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Callable, Tuple, List

import cv2
import numpy as np

from .drawover_storage import get_drawover_storage


def find_ffmpeg() -> Optional[Path]:
    """
    Find FFmpeg executable.

    Checks:
    1. System PATH
    2. Common installation locations

    Returns:
        Path to ffmpeg executable, or None if not found
    """
    # Check system PATH first
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return Path(ffmpeg_path)

    # Check common Windows locations
    if sys.platform == 'win32':
        common_paths = [
            Path(r'C:\ffmpeg\bin\ffmpeg.exe'),
            Path(r'C:\Program Files\ffmpeg\bin\ffmpeg.exe'),
            Path(r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe'),
            Path.home() / 'ffmpeg' / 'bin' / 'ffmpeg.exe',
        ]
        for path in common_paths:
            if path.exists():
                return path

    return None


def get_reviews_folder() -> Path:
    """
    Get the reviews export folder.

    Location: {exe_directory}/reviews/
    Auto-creates if it doesn't exist.

    Returns:
        Path to reviews folder
    """
    # Get directory of the running executable/script
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = Path(sys.executable).parent
    else:
        # Running as script - use cwd or a sensible default
        base_dir = Path.cwd()

    reviews_folder = base_dir / 'reviews'
    reviews_folder.mkdir(parents=True, exist_ok=True)
    return reviews_folder


def export_with_annotations(
    video_path: str,
    output_path: str,
    animation_uuid: str,
    version_label: str,
    fps: int = 24,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None
) -> Tuple[bool, str]:
    """
    Export video with annotations burned in.

    Args:
        video_path: Path to source video
        output_path: Path for output MP4
        animation_uuid: UUID of the animation
        version_label: Version label (e.g., 'v001')
        fps: Video frame rate
        progress_callback: Optional callback(current, total, message)
        cancelled_check: Optional callable returning True if cancelled

    Returns:
        Tuple of (success: bool, message: str)
    """
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        return False, "FFmpeg not found. Please install FFmpeg from https://ffmpeg.org/download.html and add it to your system PATH."

    if not Path(video_path).exists():
        return False, f"Video file not found: {video_path}"

    # Create temp directory for frame sequence
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix='annotated_export_'))

        # Extract and composite frames
        success, msg = _extract_and_composite_frames(
            video_path=video_path,
            temp_dir=temp_dir,
            animation_uuid=animation_uuid,
            version_label=version_label,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check
        )

        if not success:
            return False, msg

        # Check if cancelled before encoding
        if cancelled_check and cancelled_check():
            return False, "Export cancelled"

        # Encode to MP4
        if progress_callback:
            progress_callback(0, 0, "Encoding video...")

        success, msg = _encode_to_mp4(
            frame_dir=temp_dir,
            output_path=output_path,
            fps=fps,
            ffmpeg_path=ffmpeg_path
        )

        return success, msg

    except Exception as e:
        return False, f"Export failed: {str(e)}"

    finally:
        # Clean up temp directory
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def _extract_and_composite_frames(
    video_path: str,
    temp_dir: Path,
    animation_uuid: str,
    version_label: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None
) -> Tuple[bool, str]:
    """
    Extract video frames and composite annotations.

    Saves composited frames as PNG sequence in temp_dir.

    Returns:
        Tuple of (success: bool, message: str)
    """
    storage = get_drawover_storage()

    # Get list of frames with annotations
    annotated_frames = set(storage.list_frames_with_drawovers(animation_uuid, version_label))

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False, f"Could not open video: {video_path}"

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if total_frames <= 0:
            return False, "Could not determine video frame count"

        for frame_num in range(total_frames):
            # Check for cancellation
            if cancelled_check and cancelled_check():
                return False, "Export cancelled"

            # Update progress
            if progress_callback:
                progress_callback(frame_num + 1, total_frames, f"Processing frame {frame_num + 1}/{total_frames}")

            # Read frame
            ret, frame = cap.read()
            if not ret:
                # End of video
                break

            # Check if this frame has annotations
            if frame_num in annotated_frames:
                # Render annotation to PNG
                png_path = storage.render_to_png(
                    animation_uuid,
                    version_label,
                    frame_num,
                    (width, height)
                )

                if png_path and png_path.exists():
                    # Composite annotation onto frame
                    frame = _composite_frame_with_annotation(frame, str(png_path))

            # Save frame as PNG
            output_frame_path = temp_dir / f'frame_{frame_num:06d}.png'
            cv2.imwrite(str(output_frame_path), frame)

        return True, "Frames processed successfully"

    finally:
        cap.release()


def _composite_frame_with_annotation(
    frame: np.ndarray,
    annotation_png_path: str
) -> np.ndarray:
    """
    Composite annotation PNG onto video frame using alpha blending.

    Args:
        frame: Video frame (BGR, uint8)
        annotation_png_path: Path to annotation PNG with alpha channel

    Returns:
        Composited frame (BGR, uint8)
    """
    # Load annotation with alpha channel
    overlay = cv2.imread(annotation_png_path, cv2.IMREAD_UNCHANGED)

    if overlay is None:
        return frame

    # Handle size mismatch
    if overlay.shape[:2] != frame.shape[:2]:
        overlay = cv2.resize(overlay, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_AREA)

    # Check if overlay has alpha channel
    if overlay.shape[2] == 4:
        # Extract alpha channel and normalize to 0-1
        alpha = overlay[:, :, 3] / 255.0
        alpha = alpha[:, :, np.newaxis]  # Add dimension for broadcasting

        # Extract BGR channels from overlay (convert from BGRA)
        overlay_bgr = overlay[:, :, :3]

        # Alpha blend: result = overlay * alpha + frame * (1 - alpha)
        result = (overlay_bgr * alpha + frame * (1 - alpha)).astype(np.uint8)
        return result
    else:
        # No alpha channel - just return original frame
        return frame


def _encode_to_mp4(
    frame_dir: Path,
    output_path: str,
    fps: int,
    ffmpeg_path: Path
) -> Tuple[bool, str]:
    """
    Encode PNG sequence to MP4 using FFmpeg.

    Args:
        frame_dir: Directory containing frame_XXXXXX.png files
        output_path: Path for output MP4
        fps: Frame rate
        ffmpeg_path: Path to ffmpeg executable

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg command
    input_pattern = str(frame_dir / 'frame_%06d.png')

    cmd = [
        str(ffmpeg_path),
        '-y',  # Overwrite output
        '-framerate', str(fps),
        '-i', input_pattern,
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-crf', '23',
        '-movflags', '+faststart',
        output_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            # Extract useful error info
            error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
            return False, f"FFmpeg encoding failed:\n{error_msg}"

        # Verify output exists
        if not Path(output_path).exists():
            return False, "Output file was not created"

        return True, f"Export completed: {output_path}"

    except subprocess.TimeoutExpired:
        return False, "FFmpeg encoding timed out"
    except Exception as e:
        return False, f"FFmpeg execution failed: {str(e)}"


def generate_export_filename(
    animation_name: str,
    version_label: str,
    existing_check: bool = True
) -> str:
    """
    Generate a unique filename for the export.

    Format: {animation_name}_{version}_annotated.mp4
    If file exists, adds timestamp.

    Args:
        animation_name: Name of the animation
        version_label: Version label (e.g., 'v001')
        existing_check: Check for existing files and add timestamp if needed

    Returns:
        Filename (not full path)
    """
    import re
    from datetime import datetime

    # Clean the animation name for filename use
    clean_name = re.sub(r'[<>:"/\\|?*]', '_', animation_name)
    clean_name = clean_name.strip()[:50]  # Limit length

    base_name = f"{clean_name}_{version_label}_annotated"
    filename = f"{base_name}.mp4"

    if existing_check:
        reviews_folder = get_reviews_folder()
        if (reviews_folder / filename).exists():
            # Add timestamp to make unique
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{base_name}_{timestamp}.mp4"

    return filename


__all__ = [
    'find_ffmpeg',
    'get_reviews_folder',
    'export_with_annotations',
    'generate_export_filename'
]
