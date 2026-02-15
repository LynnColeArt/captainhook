"""
Core execution engine for CaptainHook.
"""

import asyncio
from typing import Callable, Dict, Any, Optional
from .parser import Tag, parse_tag
from .hooks import Hooks
from .filters import Filters


class Context:
    """
    Isolated execution context for tags.
    
    Similar to OpenAI's client instances - each context has its own registry.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self.hooks = Hooks()
        self.filters = Filters()
    
    def register(self, tag_pattern: str):
        """
        Decorator to register a handler for a tag pattern.
        
        Args:
            tag_pattern: Pattern like "browser:navigate" or "math:*"
        """
        def decorator(func: Callable):
            self._handlers[tag_pattern] = func
            return func
        return decorator
    
    def execute(self, tag_string: str, **kwargs) -> Any:
        """Execute a tag in this context."""
        tag = parse_tag(tag_string)
        
        # Run before_execute hook
        self.hooks.do_action("before_execute", tag, **kwargs)
        
        # Find handler
        handler = self._find_handler(tag)
        if not handler:
            raise ValueError(f"No handler registered for {tag.namespace}:{tag.action}")
        
        # Execute
        if asyncio.iscoroutinefunction(handler):
            # Async handler in sync context - run it
            result = asyncio.get_event_loop().run_until_complete(
                handler(*tag.params, **kwargs)
            )
        else:
            result = handler(*tag.params, **kwargs)
        
        # Apply filters
        result = self.filters.apply_filters("result", result, tag=tag)
        
        # Run after_execute hook
        self.hooks.do_action("after_execute", tag, result, **kwargs)
        
        return result
    
    async def execute_async(self, tag_string: str, **kwargs) -> Any:
        """Async version of execute."""
        tag = parse_tag(tag_string)
        
        # Run before_execute hook
        self.hooks.do_action("before_execute", tag, **kwargs)
        
        # Find handler
        handler = self._find_handler(tag)
        if not handler:
            raise ValueError(f"No handler registered for {tag.namespace}:{tag.action}")
        
        # Execute
        if asyncio.iscoroutinefunction(handler):
            result = await handler(*tag.params, **kwargs)
        else:
            result = handler(*tag.params, **kwargs)
        
        # Apply filters
        result = self.filters.apply_filters("result", result, tag=tag)
        
        # Run after_execute hook
        self.hooks.do_action("after_execute", tag, result, **kwargs)
        
        return result
    
    def _find_handler(self, tag: Tag) -> Optional[Callable]:
        """Find the best matching handler for a tag."""
        # Exact match
        exact_key = f"{tag.namespace}:{tag.action}"
        if exact_key in self._handlers:
            return self._handlers[exact_key]
        
        # Wildcard match (e.g., "browser:*")
        wildcard_key = f"{tag.namespace}:*"
        if wildcard_key in self._handlers:
            return self._handlers[wildcard_key]
        
        return None


# Global context for module-level functions
_global_context = Context()


def register(tag_pattern: str):
    """Global register decorator."""
    return _global_context.register(tag_pattern)


def execute(tag_string: str, **kwargs) -> Any:
    """Global execute function."""
    return _global_context.execute(tag_string, **kwargs)


async def execute_async(tag_string: str, **kwargs) -> Any:
    """Global async execute function."""
    return await _global_context.execute_async(tag_string, **kwargs)