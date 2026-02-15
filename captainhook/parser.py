"""
Tag parser for cheatcode syntax.

Supports both singles and doubles (like XML):
- Singles (self-closing): [namespace:action params /]
- Doubles (container): [tag]content[/tag]

Reference: Busy38 core/parser/tags.py
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TagType(Enum):
    """Types of tags supported."""
    SINGLE = "single"  # Self-closing: [action /]
    DOUBLE = "double"  # Container: [tag]content[/tag]
    CHEATCODE = "cheatcode"  # [ns:action attr="value" /]


@dataclass
class Tag:
    """Represents a parsed tag."""
    tag_type: TagType
    namespace: Optional[str]
    action: str
    params: List[str]
    attributes: Dict[str, str]
    content: Optional[str]  # For doubles
    raw: str


# Container tag pattern: [tag]content[/tag]
CONTAINER_PATTERN = r"\[(\w+)\](.*?)\[/\1\]"

# Self-closing pattern: [action /] or [action/]
SELF_CLOSING_PATTERN = r"\[(\w+)\s*/\]"

# Cheatcode pattern: [namespace:action attr="value" key=value /]
CHEATCODE_PATTERN = r"\[(\w+):(\w+)\s+([^\]]*?)/\]"

# Attribute pattern: key="value" or key=value
ATTR_PATTERN = r'(\w+)=(?:"([^"]*)"|([^\s\]]*))'


def parse_container_tags(text: str) -> List[Tag]:
    """Parse container tags [tag]content[/tag]."""
    tags = []
    
    for match in re.finditer(CONTAINER_PATTERN, text, re.DOTALL):
        tag_name = match.group(1)
        content = match.group(2).strip()
        
        tag = Tag(
            tag_type=TagType.DOUBLE,
            namespace=None,
            action=tag_name,
            params=[],
            attributes={},
            content=content,
            raw=match.group(0)
        )
        tags.append(tag)
    
    return tags


def parse_self_closing(text: str) -> List[Tag]:
    """Parse self-closing tags [action /]."""
    tags = []
    
    for match in re.finditer(SELF_CLOSING_PATTERN, text):
        action = match.group(1)
        
        tag = Tag(
            tag_type=TagType.SINGLE,
            namespace=None,
            action=action,
            params=[],
            attributes={},
            content=None,
            raw=match.group(0)
        )
        tags.append(tag)
    
    return tags


def parse_cheatcodes(text: str) -> List[Tag]:
    """Parse cheatcode tags [ns:action attr="value" /]."""
    tags = []
    
    for match in re.finditer(CHEATCODE_PATTERN, text):
        namespace = match.group(1)
        action = match.group(2)
        attr_text = match.group(3)
        
        # Parse attributes
        attributes = {}
        for attr_match in re.finditer(ATTR_PATTERN, attr_text):
            key = attr_match.group(1)
            value = attr_match.group(2) if attr_match.group(2) is not None else attr_match.group(3)
            attributes[key] = value
        
        # Params are remaining non-key=value parts
        params = []
        for part in attr_text.split():
            if '=' not in part:
                params.append(part.strip('"'))
        
        tag = Tag(
            tag_type=TagType.CHEATCODE,
            namespace=namespace,
            action=action,
            params=params,
            attributes=attributes,
            content=None,
            raw=match.group(0)
        )
        tags.append(tag)
    
    return tags


def parse_all(text: str) -> List[Tag]:
    """Parse all tag types from text."""
    tags = []
    
    # Parse each type
    tags.extend(parse_container_tags(text))
    tags.extend(parse_cheatcodes(text))
    tags.extend(parse_self_closing(text))
    
    # Sort by position in text (using raw string to estimate position)
    def get_position(tag):
        return text.find(tag.raw)
    
    tags.sort(key=get_position)
    
    return tags


def parse_tag(tag_string: str) -> Tag:
    """
    Parse a single tag string.
    
    Supports:
    - [action /] - Self-closing
    - [ns:action params /] - Cheatcode
    - [tag]content[/tag] - Container (if content provided)
    """
    # Try cheatcode first
    if ":" in tag_string and re.fullmatch(CHEATCODE_PATTERN, tag_string.strip(), re.DOTALL):
        tags = parse_cheatcodes(tag_string)
        if tags:
            return tags[0]
    
    # Try self-closing
    if re.fullmatch(SELF_CLOSING_PATTERN, tag_string.strip()):
        tags = parse_self_closing(tag_string)
        if tags:
            return tags[0]
    
    # Try container
    if re.fullmatch(CONTAINER_PATTERN, tag_string.strip(), re.DOTALL):
        tags = parse_container_tags(tag_string)
        if tags:
            return tags[0]
    
    raise ValueError(f"Invalid tag format: {tag_string}")


def is_valid_tag(tag_string: str) -> bool:
    """Check if a string is a valid tag format."""
    try:
        parse_tag(tag_string)
        return True
    except ValueError:
        return False


def remove_tags(text: str) -> str:
    """Remove all tags from text, returning clean content."""
    tags = parse_all(text)
    if not tags:
        return text
    
    # Remove from end to start to preserve positions
    result = text
    for tag in reversed(tags):
        result = result.replace(tag.raw, '', 1)
    
    return result.strip()
