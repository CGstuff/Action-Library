FFmpeg Binary Directory
=======================

This directory contains the FFmpeg executable used for video preview generation.

For Windows:
  - Download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/
  - Get the "ffmpeg-release-essentials.zip" build
  - Extract and copy ffmpeg.exe to this directory

For Linux:
  - Copy the ffmpeg binary to this directory
  - Or install via package manager (apt install ffmpeg)

For macOS:
  - Copy the ffmpeg binary to this directory
  - Or install via Homebrew (brew install ffmpeg)

The Animation Library Blender plugin will automatically detect and use ffmpeg
from this directory if it's not found in your system PATH.
