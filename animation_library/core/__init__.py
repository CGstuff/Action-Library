"""Core business logic for Animation Library v2"""

from .metadata_extractor import MetadataExtractor
from .thumbnail_generator import ThumbnailGenerator
from .animation_scanner import AnimationScanner

__all__ = ['MetadataExtractor', 'ThumbnailGenerator', 'AnimationScanner']
