"""
CaptainHook - Cheatcode-style extensibility for Python

Reference: Busy38 cheatcode system
"""

from .core import (
    Context,
    register,
    register_container,
    execute,
    execute_text,
    execute_async,
)
from .parser import (
    Tag,
    TagType,
    parse_tag,
    parse_all,
    is_valid_tag,
    remove_tags,
)
from .hooks import Hooks
from .filters import Filters

__version__ = "0.1.0"
__license__ = "GPL-3.0-only"

__all__ = [
    # Core
    "Context",
    "register",
    "register_container",
    "execute",
    "execute_text",
    "execute_async",
    # Parser
    "Tag",
    "TagType",
    "parse_tag",
    "parse_all",
    "is_valid_tag",
    "remove_tags",
    # Hooks/Filters
    "Hooks",
    "Filters",
]