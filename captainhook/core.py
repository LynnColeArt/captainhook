"""
Core execution engine for CaptainHook.

Reference: Busy38 core/cheatcodes/registry.py
"""

import asyncio
import inspect
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
        self._namespace_handlers: Dict[str, Any] = {}
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

    def register_namespace(self, namespace: str, handler: Any):
        """Register a Busy-style namespace handler for `[namespace:action /]`."""
        if namespace in self._namespace_handlers:
            raise ValueError(f"Namespace '{namespace}' is already registered")
        self._namespace_handlers[namespace] = handler
        return handler

    def _resolve_namespace_handler(self, namespace: str):
        """Resolve a namespace handler from local or global registry."""
        handler = self._namespace_handlers.get(namespace)
        if handler is not None:
            return handler

        try:
            from .busy_bridge import get_namespace
            return get_namespace(namespace)
        except Exception:
            return None

    def unregister_namespace(self, namespace: str) -> None:
        """Unregister a namespace handler."""
        if namespace not in self._namespace_handlers:
            raise KeyError(f"Namespace '{namespace}' is not registered")
        del self._namespace_handlers[namespace]

    def execute_cheatcode(self, namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None):
        """Execute a namespace handler directly."""
        handler = self._resolve_namespace_handler(namespace)
        if handler is None:
            raise KeyError(f"Namespace '{namespace}' is not registered")
        if not hasattr(handler, "execute"):
            raise TypeError(f"Namespace handler for '{namespace}' is missing execute(action, **kwargs)")
        return handler.execute(action, **(attributes or {}))
    
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

    def execute(self, tag_string: str, **kwargs) -> Any:
        """Execute a single tag string."""
        tag = parse_tag(tag_string)
        return self.execute_tag(tag, **kwargs)
    
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
        result = self.filters.apply_filters("result", result, tag)
        
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
        ns_handler = None

        try:
            from .busy_bridge import emit as emit_compat, HookPoints
            emit_compat(
                HookPoints.PRE_CHEATCODE_EXECUTE,
                tag.namespace,
                tag.action,
                tag.attributes,
                context={"tag": tag, "namespace": tag.namespace, "action": tag.action, **kwargs},
            )
        except Exception:
            pass
        
        if not handler:
            ns = str(tag.namespace)
            ns_handler = self._resolve_namespace_handler(ns)
            if not ns_handler:
                raise ValueError(f"No handler for cheatcode '{key}'")
            if not hasattr(ns_handler, "execute"):
                raise ValueError(f"Namespace handler for '{ns}' has no execute() method")
            result = ns_handler.execute(tag.action, **{**tag.attributes, **kwargs})
        else:
            # Build arguments
            args = tag.params.copy()
            call_kwargs = {**tag.attributes, **kwargs}
            result = handler(*args, **call_kwargs)

        try:
            from .busy_bridge import emit as emit_compat, HookPoints
            emit_compat(
                HookPoints.POST_CHEATCODE_EXECUTE,
                tag.namespace,
                tag.action,
                result,
                context={"tag": tag, "namespace": tag.namespace, "action": tag.action, **kwargs},
            )
        except Exception:
            pass

        return result
    
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
            if not handler:
                handler = None
        else:
            handler = self._handlers.get(tag.action)
        
        if not handler and tag.tag_type != TagType.CHEATCODE:
            raise ValueError(f"No handler for '{tag.action}'")

        # Execute
        if tag.tag_type == TagType.DOUBLE:
            result = handler(tag.content, **kwargs)
        elif tag.tag_type == TagType.CHEATCODE:
            ns_handler = self._resolve_namespace_handler(str(tag.namespace))
            if ns_handler:
                if not hasattr(ns_handler, "execute"):
                    raise ValueError(f"Namespace handler for '{tag.namespace}' has no execute() method")
                result = ns_handler.execute(tag.action, **{**tag.attributes, **kwargs})
            else:
                if handler is None:
                    raise ValueError(f"No handler for cheatcode '{tag.namespace}:{tag.action}'")
                result = handler(*tag.params, **{**tag.attributes, **kwargs})
        else:
            result = handler(**kwargs)

        if inspect.isawaitable(result):
            result = await result
        
        # Apply filters
        result = self.filters.apply_filters("result", result, tag)
        
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


def register_namespace(namespace: str, handler: Any):
    """Register a Busy-compatible namespace handler."""
    try:
        from .busy_bridge import register_namespace as register_bridge_namespace
        register_bridge_namespace(namespace, handler)
    except Exception:
        _global_context.register_namespace(namespace, handler)
    return handler


def unregister_namespace(namespace: str) -> None:
    """Unregister a Busy-compatible namespace handler."""
    try:
        from .busy_bridge import unregister_namespace as unregister_bridge_namespace
        unregister_bridge_namespace(namespace)
    except Exception:
        _global_context.unregister_namespace(namespace)


def execute_cheatcode(namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None):
    """Execute a namespace handler directly."""
    try:
        from .busy_bridge import execute_cheatcode as execute_bridge_cheatcode
        return execute_bridge_cheatcode(namespace, action, attributes)
    except Exception:
        return _global_context.execute_cheatcode(namespace, action, attributes)


async def execute_async(tag_string: str, **kwargs) -> Any:
    """Global async execute."""
    return await _global_context.execute_async(tag_string, **kwargs)
