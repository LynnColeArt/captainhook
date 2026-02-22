"""
Structured parser for CaptainHook control tags.

Replaces regex-based parsing with a deterministic stack parser.
Malformed markup fails closed via ParseError.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TagType(Enum):
    """Types of tags supported."""

    SINGLE = "single"  # Self-closing: [action /]
    DOUBLE = "double"  # Container: [tag]content[/tag]
    CHEATCODE = "cheatcode"  # [ns:action attr="value" /]


class ParseError(ValueError):
    """Raised when tag parsing fails."""


@dataclass
class Tag:
    """Represents a parsed tag."""

    tag_type: TagType
    namespace: Optional[str]
    action: str
    params: List[str]
    attributes: Dict[str, str]
    content: Optional[str]
    raw: str


def _read_identifier(text: str, start: int) -> Tuple[Optional[str], int]:
    if start >= len(text):
        return None, start
    if not (text[start].isalpha() or text[start] == "_"):
        return None, start

    end = start + 1
    while end < len(text) and (text[end].isalnum() or text[end] in {"_", "-"}):
        end += 1
    return text[start:end], end


def _parse_arg_tokens(arg_text: str, base_offset: int = 0) -> Tuple[Dict[str, str], List[str]]:
    if not arg_text:
        return {}, []
    try:
        tokens = shlex.split(arg_text, posix=True)
    except ValueError as exc:
        raise ParseError(f"Malformed argument quoting near index {base_offset}: {exc}") from exc

    attributes: Dict[str, str] = {}
    params: List[str] = []
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            if not key:
                raise ParseError(f"Invalid attribute token '{token}'")
            key_name, _ = _read_identifier(key, 0)
            if key_name != key:
                raise ParseError(f"Invalid attribute key '{key}'")
            attributes[key] = value
        else:
            params.append(token)
    return attributes, params


def _find_cheatcode_close(text: str, start: int) -> int:
    """
    Find the start of a closing ` /]` sequence for a cheatcode, honoring quotes.
    Returns index of '/' or raises ParseError.
    """
    i = start
    quote: Optional[str] = None
    escaped = False
    while i < len(text) - 1:
        ch = text[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if quote is not None:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
            i += 1
            continue
        if ch == "/" and text[i + 1] == "]":
            return i
        i += 1
    raise ParseError("Malformed cheatcode: missing '/]'")


def _read_tag_token(text: str, start: int) -> Tuple[Optional[Dict[str, Any]], int]:
    if start >= len(text) or text[start] != "[":
        return None, start
    if start + 1 >= len(text):
        return None, start

    # Closing tag.
    if text[start + 1] == "/":
        cursor = start + 2
        name, cursor = _read_identifier(text, cursor)
        if not name:
            raise ParseError(f"Invalid close tag at index {start}")
        if cursor >= len(text) or text[cursor] != "]":
            raise ParseError(f"Malformed close tag for '{name}' at index {start}")
        return {
            "kind": "close",
            "name": name,
            "raw": text[start : cursor + 1],
        }, cursor + 1

    # Open, cheatcode, or malformed.
    cursor = start + 1
    namespace, cursor = _read_identifier(text, cursor)
    if not namespace:
        raise ParseError(f"Invalid tag name at index {start}")

    # namespace:action /]
    if cursor < len(text) and text[cursor] == ":":
        cursor += 1
        action, cursor = _read_identifier(text, cursor)
        if not action:
            raise ParseError(f"Invalid cheatcode action at index {start}")
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1

        close_at = _find_cheatcode_close(text, cursor)
        arg_text = text[cursor:close_at].strip()
        attrs, params = _parse_arg_tokens(arg_text, base_offset=cursor)
        raw = text[start : close_at + 2]
        return {
            "kind": "cheatcode",
            "namespace": namespace,
            "action": action,
            "raw": raw,
            "attributes": attrs,
            "params": params,
        }, close_at + 2

    # Ignore any whitespace before closing.
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    if cursor >= len(text):
        raise ParseError(f"Unterminated token at index {start}")

    if text[cursor] == "/":
        if cursor + 1 >= len(text) or text[cursor + 1] != "]":
            raise ParseError(f"Malformed self-closing tag '[{namespace}' at index {start}")
        return {
            "kind": "single",
            "name": namespace,
            "raw": text[start : cursor + 2],
        }, cursor + 2

    if text[cursor] != "]":
        raise ParseError(f"Malformed token after '{namespace}' at index {start}")
    return {
        "kind": "open",
        "name": namespace,
        "content_start": cursor + 1,
        "raw_start": start,
        "raw": text[start : cursor + 1],
    }, cursor + 1


def parse_all(text: str, include_nested: bool = False) -> List[Tag]:
    """Parse all tags from text in source order."""
    tags: List[Tag] = []
    container_stack: List[Dict[str, Any]] = []
    cursor = 0

    while cursor < len(text):
        if text[cursor] != "[":
            cursor += 1
            continue

        parsed, next_cursor = _read_tag_token(text, cursor)
        if parsed is None:
            cursor += 1
            continue

        kind = parsed["kind"]
        if kind == "open":
            container_stack.append(parsed)
            cursor = next_cursor
            continue

        if kind == "close":
            if not container_stack:
                raise ParseError(f"Unexpected close tag '[/{parsed['name']}]' at index {cursor}")
            open_tag = container_stack.pop()
            if parsed["name"] != open_tag["name"]:
                raise ParseError(
                    f"Unbalanced container. expected '[/{open_tag['name']}]' before '[/{parsed['name']}]'"
                )
            if not container_stack:
                content = text[open_tag["content_start"] : cursor]
                raw = text[open_tag["raw_start"] : next_cursor]
                tags.append(
                    Tag(
                        tag_type=TagType.DOUBLE,
                        namespace=None,
                        action=open_tag["name"],
                        params=[],
                        attributes={},
                        content=content,
                        raw=raw,
                    )
                )
            cursor = next_cursor
            continue

        depth = len(container_stack)
        if not include_nested and depth > 0:
            cursor = next_cursor
            continue

        if kind == "single":
            tags.append(
                Tag(
                    tag_type=TagType.SINGLE,
                    namespace=None,
                    action=parsed["name"],
                    params=[],
                    attributes={},
                    content=None,
                    raw=parsed["raw"],
                )
            )
        else:
            tags.append(
                Tag(
                    tag_type=TagType.CHEATCODE,
                    namespace=parsed["namespace"],
                    action=parsed["action"],
                    params=parsed["params"],
                    attributes=parsed["attributes"],
                    content=None,
                    raw=parsed["raw"],
                )
            )
        cursor = next_cursor

    if container_stack:
        unclosed = container_stack[-1]["name"]
        raise ParseError(f"Unterminated container tag '[{unclosed}]'")

    return tags


def parse_container_tags(text: str) -> List[Tag]:
    return [tag for tag in parse_all(text, include_nested=True) if tag.tag_type == TagType.DOUBLE]


def parse_self_closing(text: str) -> List[Tag]:
    return [tag for tag in parse_all(text) if tag.tag_type == TagType.SINGLE]


def parse_cheatcodes(text: str) -> List[Tag]:
    return [tag for tag in parse_all(text, include_nested=True) if tag.tag_type == TagType.CHEATCODE]


def parse_tag(tag_string: str) -> Tag:
    """Parse a single tag string."""
    text = tag_string.strip()
    if not text.startswith("[") or not text.endswith("]"):
        raise ParseError(f"Invalid tag format: {tag_string}")
    tags = parse_all(text, include_nested=True)
    if len(tags) != 1:
        raise ParseError(f"Tag must contain exactly one control tag: {tag_string}")
    return tags[0]


def is_valid_tag(tag_string: str) -> bool:
    """Check if a string is a valid tag format."""
    try:
        parse_tag(tag_string)
        return True
    except ParseError:
        return False


def remove_tags(text: str) -> str:
    """Remove all tags from text, returning clean content."""
    tags = parse_all(text)
    if not tags:
        return text
    result = text
    for tag in reversed(tags):
        result = result.replace(tag.raw, "", 1)
    return result.strip()
