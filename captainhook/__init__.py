"""
CaptainHook - Cheatcode-style hooks, filters, and tags for Python
"""

from .core import execute, execute_async, register, Context
from .hooks import Hooks
from .filters import Filters
from .parser import Tag, parse_tag

__version__ = "0.1.0"
__all__ = [
    "execute",
    "execute_async", 
    "register",
    "Context",
    "Hooks",
    "Filters",
    "Tag",
    "parse_tag",
    "hooks",
    "filters",
]

# Global instances
hooks = Hooks()
filters = Filters()


def execute(tag_string: str, **kwargs):
    """
    Execute a cheatcode tag.
    
    Args:
        tag_string: The tag to execute (e.g., "[browser:navigate https://example.com]")
        **kwargs: Additional context
        
    Returns:
        The result of the execution
    """
    tag = parse_tag(tag_string)
    return _execute_tag(tag, **kwargs)


async def execute_async(tag_string: str, **kwargs):
    """Async version of execute."""
    tag = parse_tag(tag_string)
    return await _execute_tag_async(tag, **kwargs)


# Internal execution functions (to be implemented)
def _execute_tag(tag, **kwargs):
    raise NotImplementedError("Core execution not yet implemented")


async def _execute_tag_async(tag, **kwargs):
    raise NotImplementedError("Async execution not yet implemented")