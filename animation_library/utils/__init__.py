"""Utility functions for Animation Library v2"""

from .gradient_utils import composite_image_on_gradient_colors, create_vertical_gradient
from .image_utils import load_image_as_pixmap, get_image_size
from .color_utils import hex_to_rgb, rgb_to_hex, hsl_to_rgb, rgb_to_hsl
from .icon_loader import IconLoader
from .icon_utils import colorize_white_svg
from .color_presets import GRADIENT_PRESETS, get_preset_by_name, get_preset_gradient
from .dialog_helper import DialogHelper
from .layout_utils import clear_layout, clear_grid, add_grid_row, set_layout_margins, set_layout_spacing

# String utilities
from .string_utils import (
    sanitize_filename,
    sanitize_for_path,
    strip_version_suffix,
    format_version_label,
    parse_version_label,
)

# JSON utilities
from .json_utils import (
    safe_json_load,
    safe_json_save,
    safe_json_update,
    is_valid_json_file,
)

# File utilities
from .file_utils import (
    transactional_move,
    atomic_write,
    safe_remove_tree,
    ensure_parent_exists,
    get_unique_path,
)

__all__ = [
    'composite_image_on_gradient_colors',
    'create_vertical_gradient',
    'load_image_as_pixmap',
    'get_image_size',
    'hex_to_rgb',
    'rgb_to_hex',
    'hsl_to_rgb',
    'rgb_to_hsl',
    'IconLoader',
    'colorize_white_svg',
    'GRADIENT_PRESETS',
    'get_preset_by_name',
    'get_preset_gradient',
    # Dialog utilities
    'DialogHelper',
    # Layout utilities
    'clear_layout',
    'clear_grid',
    'add_grid_row',
    'set_layout_margins',
    'set_layout_spacing',
    # String utilities
    'sanitize_filename',
    'sanitize_for_path',
    'strip_version_suffix',
    'format_version_label',
    'parse_version_label',
    # JSON utilities
    'safe_json_load',
    'safe_json_save',
    'safe_json_update',
    'is_valid_json_file',
    # File utilities
    'transactional_move',
    'atomic_write',
    'safe_remove_tree',
    'ensure_parent_exists',
    'get_unique_path',
]
