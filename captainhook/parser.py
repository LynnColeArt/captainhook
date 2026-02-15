"""
Tag parser for cheatcode syntax.

Supports: [namespace:action param1 param2 ...]
"""

import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Tag:
    """Represents a parsed cheatcode tag."""
    namespace: str
    action: str
    params: List[str]
    raw: str
    
    def __repr__(self):
        return f"Tag({self.namespace}:{self.action} {' '.join(self.params)})"


def parse_tag(tag_string: str) -> Tag:
    """
    Parse a cheatcode tag string.
    
    Args:
        tag_string: String like "[browser:navigate https://example.com /]"
        
    Returns:
        Tag object with namespace, action, and params
        
    Raises:
        ValueError: If tag format is invalid
    """
    # Strip brackets - supports both [/] and ] endings for flexibility
    match = re.match(r'^\[(.+?)(?:\s*/\]|\])$', tag_string.strip())
    if not match:
        raise ValueError(f"Invalid tag format: {tag_string}. Expected [namespace:action ... /]")
    
    content = match.group(1)
    
    # Split by whitespace to get parts
    parts = content.split()
    if not parts:
        raise ValueError(f"Empty tag: {tag_string}")
    
    # First part should be namespace:action
    action_part = parts[0]
    if ':' not in action_part:
        raise ValueError(f"Invalid action format: {action_part}. Expected namespace:action")
    
    namespace, action = action_part.split(':', 1)
    
    # Remaining parts are parameters
    params = parts[1:] if len(parts) > 1 else []
    
    return Tag(
        namespace=namespace,
        action=action,
        params=params,
        raw=tag_string
    )


def is_valid_tag(tag_string: str) -> bool:
    """Check if a string is a valid cheatcode format."""
    try:
        parse_tag(tag_string)
        return True
    except ValueError:
        return False