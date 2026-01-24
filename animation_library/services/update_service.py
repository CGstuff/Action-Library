import json
import logging
import urllib.request
import urllib.error
from typing import Tuple, Optional, Dict, Any

from ..config import Config

logger = logging.getLogger(__name__)

class UpdateService:
    """
    Service to check for application updates.
    """
    
    # GitHub API URL for latest release
    UPDATE_URL = "https://api.github.com/repos/CGstuff/Action-Library/releases/latest"
    
    def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if a new version is available via GitHub API.
        
        Returns:
            Tuple of (update_available, latest_version_str, download_url)
        """
        try:
            req = urllib.request.Request(self.UPDATE_URL)
            # GitHub requires a User-Agent
            req.add_header('User-Agent', f'ActionLibrary/{Config.APP_VERSION}')
            
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status != 200:
                    return False, None, None
                
                data = json.loads(response.read().decode('utf-8'))
                
                # Get version from tag_name (e.g. "v1.4.0")
                tag_name = data.get('tag_name', '')
                download_url = data.get('html_url', '') # Link to release page
                
                if not tag_name:
                    return False, None, None
                
                # Compare versions
                current = self._parse_version(Config.APP_VERSION)
                latest = self._parse_version(tag_name)
                
                if latest > current:
                    return True, tag_name, download_url
                    
        except Exception as e:
            logger.debug(f"Update check failed: {e}")
            return False, None, None
            
        return False, None, None

    def _parse_version(self, v_str: str) -> tuple:
        """Parse '1.2.3' into (1, 2, 3) for comparison"""
        try:
            # Remove v prefix if present
            v_str = v_str.lower().lstrip('v')
            # Split by dot
            parts = v_str.split('.')
            # Convert to int, defaulting to 0
            return tuple(int(p) if p.isdigit() else 0 for p in parts)
        except:
            return (0, 0, 0)
