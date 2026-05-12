"""
Dialogs package
"""

from .icon_picker_dialog import IconPickerDialog
from .tag_input_dialog import TagInputDialog
from .gradient_picker_dialog import GradientPickerDialog
from .version_history_dialog import VersionHistoryDialog
from .identity_wizard import IdentityWizard

__all__ = [
    'IconPickerDialog',
    'TagInputDialog',
    'GradientPickerDialog',
    'VersionHistoryDialog',
    'IdentityWizard',
]
