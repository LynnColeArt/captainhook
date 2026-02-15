"""
Core execution engine for CaptainHook.

Reference: Busy38 core/cheatcodes/registry.py
"""

import asyncio
from typing import Callable, Dict, Any, Optional, List
from .parser import Tag, TagType, parse_all, parse_tag
from .hooks import Hooks
from .filters import Filters


class Context:
    """
    Isolated execution context for tags.
    
    Similar to Busy38's NamespaceRegistry - each context has its own handlers.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._container_handlers: Dict[str, Callable] = {}
        self.hooks = Hooks()
        self.filters = Filters()
    
    def register(self, pattern: str):
        """
        Decorator to register a handler.
        
        Patterns:
        - "action" - Self-closing tag [action /]
        - "ns:action" - Cheatcode [ns:action ... /]
        - "tag" (with content param) - Container [tag]content[/tag]
        """
        def decorator(func: Callable):
            if ':' in pattern:
                # Cheatcode: namespace:action
                self._handlers[pattern] = func
            else:
                # Simple tag or container
                self._handlers[pattern] = func
            return func
        return decorator
    
    def register_container(self, tag_name: str):
        """Register a handler for container tags [tag]content[/tag]."""
        def decorator(func: Callable):
            self._container_handlers[tag_name] = func
            return func
        return decorator
    
    def execute_text(self, text: str, **kwargs) -> List[Any]:
        """Execute all tags found in text."""
        tags = parse_all(text)
        results = []
        
        for tag in tags:
            try:
                result = self.execute_tag(tag, **kwargs)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "tag": tag.raw})
        
        return results
    
    def execute_tag(self, tag: Tag, **kwargs) -> Any:
        """Execute a single tag."""
        # Run before_execute hook
        self.hooks.do_action("before_execute", tag, **kwargs)
        
        # Find and execute handler
        if tag.tag_type == TagType.DOUBLE:
            result = self._execute_container(tag, **kwargs)
        elif tag.tag_type == TagType.CHEATCODE:
            result = self._execute_cheatcode(tag, **kwargs)
        else:
            result = self._execute_simple(tag, **kwargs)
        
        # Apply filters
        result = self.filters.apply_filters("result", result, tag=tag)
        
        # Run after_execute hook
        self.hooks.do_action("after_execute", tag, result, **kwargs)
        
        return result
    
    def _execute_container(self, tag: Tag, **kwargs) -> Any:
        """Execute a container tag [tag]content[/tag]."""
        handler = self._container_handlers.get(tag.action)
        if not handler:
            raise ValueError(f"No container handler for '{tag.action}'")
        
        return handler(tag.content, **kwargs)
    
    def _execute_cheatcode(self, tag: Tag, **kwargs) -> Any:
        """Execute a cheatcode [ns:action ... /]."""
        key = f"{tag.namespace}:{tag.action}"
        handler = self._handlers.get(key)
        
        if not handler:
            raise ValueError(f"No handler for cheatcode '{key}'")
        
        # Build arguments
        args = tag.params.copy()
        call_kwargs = {**tag.attributes, **kwargs}
        
        return handler(*args, **call_kwargs)
    
    def _execute_simple(self, tag: Tag, **kwargs) -> Any:
        """Execute a simple self-closing tag [action /]."""
        handler = self._handlers.get(tag.action)
        
        if not handler:
            raise ValueError(f"No handler for tag '{tag.action}'")
        
        return handler(**kwargs)
    
    async def execute_async(self, tag_string: str, **kwargs) -> Any:
        """Async execution."""
        tag = parse_tag(tag_string)
        
        # Run before_execute hook
        self.hooks.do_action("before_execute", tag, **kwargs)
        
        # Find handler
        if tag.tag_type == TagType.DOUBLE:
            handler = self._container_handlers.get(tag.action)
        elif tag.tag_type == TagType.CHEATCODE:
            key = f"{tag.namespace}:{tag.action}"
            handler = self._handlers.get(key)
        else:
            handler = self._handlers.get(tag.action)
        
        if not handler:
            raise ValueError(f"No handler for '{tag.action}'")
        
        # Execute
        if asyncio.iscoroutinefunction(handler):
            if tag.tag_type == TagType.DOUBLE:
                result = await handler(tag.content, **kwargs)
            elif tag.tag_type == TagType.CHEATCODE:
                result = await handler(*tag.params, **tag.attributes, **kwargs)
            else:
                result = await handler(**kwargs)
        else:
            if tag.tag_type == TagType.DOUBLE:
                result = handler(tag.content, **kwargs)
            elif tag.tag_type == TagType.CHEATCODE:
                result = handler(*tag.params, **tag.attributes, **kwargs)
            else:
                result = handler(**kwargs)
        
        # Apply filters
        result = self.filters.apply_filters("result", result, tag=tag)
        
        # Run after_execute hook
        self.hooks.do_action("after_execute", tag, result, **kwargs)
        
        return result


# Global context for module-level functions
_global_context = Context()


def register(pattern: str):
    """Global register decorator."""
    return _global_context.register(pattern)


def register_container(tag_name: str):
    """Global container register decorator."""
    return _global_context.register_container(tag_name)


def execute(tag_string: str, **kwargs) -> Any:
    """Execute a single tag."""
    tag = parse_tag(tag_string)
    return _global_context.execute_tag(tag, **kwargs)


def execute_text(text: str, **kwargs) -> List[Any]:
    """Execute all tags in text."""
    return _global_context.execute_text(text, **kwargs)


async def execute_async(tag_string: str, **kwargs) -> Any:
    """Global async execute."""
    return await _global_context.execute_async(tag_string, **kwargs)