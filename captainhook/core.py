"""Core execution engine for CaptainHook."""

from __future__ import annotations

import asyncio
import inspect
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional

from .parser import ParseError, Tag, TagType, parse_all, parse_tag
from .hooks import Hooks
from .filters import Filters


def _freeze_kwargs(values: Dict[str, Any]) -> Dict[str, Any]:
    return dict(MappingProxyType(dict(values)))


def _validate_identifier(value: str) -> None:
    if not value:
        raise ValueError("Empty identifier is not allowed")
    if value.startswith("__") or value.endswith("__"):
        raise ValueError(f"Invalid identifier '{value}'")
    if not (value[0].isalpha() or value[0] == "_"):
        raise ValueError(f"Invalid identifier '{value}'")
    for char in value:
        if not (char.isalnum() or char in {"_", "-"}):
            raise ValueError(f"Invalid identifier '{value}'")


def _merge_call_kwargs(tag_attrs: Dict[str, str], runtime_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    overlap = set(tag_attrs) & set(runtime_kwargs)
    if overlap:
        raise ValueError(f"Tag data overlaps runtime keys: {sorted(overlap)}")
    merged = dict(runtime_kwargs)
    merged.update(tag_attrs)
    return _freeze_kwargs(merged)


def _validate_tag_values(tag: Tag) -> None:
    _validate_identifier(tag.action)
    if tag.namespace is not None:
        _validate_identifier(tag.namespace)
    for key in tag.attributes:
        _validate_identifier(key)


class Context:
    """
    Isolated execution context for CaptainHook control tags.
    """

    def __init__(self, apply_filters: bool = False):
        self._handlers: Dict[str, Callable] = {}
        self._namespace_handlers: Dict[str, Any] = {}
        self._namespace_metadata: Dict[str, Dict[str, Any]] = {}
        self._container_handlers: Dict[str, Callable] = {}
        self._apply_filters = apply_filters
        self.hooks = Hooks()
        self.filters = Filters()

    def register(self, pattern: str):
        if ":" in pattern:
            namespace, action = pattern.split(":", 1)
            _validate_identifier(namespace)
            _validate_identifier(action)
        else:
            _validate_identifier(pattern)

        def decorator(func: Callable):
            self._handlers[pattern] = func
            return func

        return decorator

    def register_namespace(self, namespace: str, handler: Any, metadata: Optional[Dict[str, Any]] = None):
        _validate_identifier(namespace)
        if namespace in self._namespace_handlers:
            raise ValueError(f"Namespace '{namespace}' is already registered")
        self._namespace_handlers[namespace] = handler
        self._namespace_metadata[namespace] = dict(metadata) if isinstance(metadata, Dict) else {}
        return handler

    def _resolve_namespace_handler(self, namespace: str):
        handler = self._namespace_handlers.get(namespace)
        if handler is not None:
            return handler
        try:
            from .busy_bridge import get_namespace

            return get_namespace(namespace)
        except Exception:
            return None

    def _resolve_namespace_metadata(self, namespace: str) -> Dict[str, Any]:
        local_metadata = self._namespace_metadata.get(namespace)
        local_payload = dict(local_metadata) if isinstance(local_metadata, Dict) else {}
        try:
            from .busy_bridge import get_namespace_metadata

            bridge_metadata = get_namespace_metadata(namespace)
            local_payload.update(bridge_metadata or {})
            return local_payload
        except Exception:
            return local_payload

    def get_no_response(self, namespace: str, action: str) -> bool:
        metadata = self._resolve_namespace_metadata(namespace)
        if not metadata:
            return False
        for data in (self._extract_action_metadata(metadata, action), metadata):
            value = data.get("noResponse", data.get("no_response"))
            if isinstance(value, bool):
                return value
        return False

    @staticmethod
    def _extract_action_metadata(metadata: Dict[str, Any], action: str) -> Dict[str, Any]:
        if not metadata:
            return {}
        action_name = str(action or "").strip()
        action_name_lc = action_name.lower()
        for container_name in ("actions", "action_metadata", "action_metadata_by_name"):
            actions = metadata.get(container_name)
            if not isinstance(actions, Dict):
                continue
            if action_name in actions and isinstance(actions[action_name], Dict):
                return dict(actions[action_name])
            if action_name_lc in actions and isinstance(actions[action_name_lc], Dict):
                return dict(actions[action_name_lc])
        return {}

    def unregister_namespace(self, namespace: str) -> None:
        if namespace not in self._namespace_handlers:
            raise KeyError(f"Namespace '{namespace}' is not registered")
        del self._namespace_handlers[namespace]
        self._namespace_metadata.pop(namespace, None)

    def execute_cheatcode(self, namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None):
        _validate_identifier(namespace)
        _validate_identifier(action)
        handler = self._resolve_namespace_handler(namespace)
        if handler is None:
            raise KeyError(f"Namespace '{namespace}' is not registered")
        if not hasattr(handler, "execute"):
            raise TypeError(f"Namespace handler for '{namespace}' is missing execute(action, **kwargs)")
        attrs = dict(attributes or {})
        for key in attrs:
            _validate_identifier(key)
        return handler.execute(action, **_freeze_kwargs(attrs))

    def register_container(self, tag_name: str):
        _validate_identifier(tag_name)

        def decorator(func: Callable):
            self._container_handlers[tag_name] = func
            return func

        return decorator

    def execute_text(self, text: str, **kwargs) -> List[Any]:
        tags = parse_all(text)
        results = []
        for tag in tags:
            try:
                results.append(self.execute_tag(tag, **kwargs))
            except Exception as exc:
                results.append({"error": str(exc), "tag": tag.raw})
        return results

    def execute(self, tag_string: str, **kwargs) -> Any:
        tag = parse_tag(tag_string)
        return self.execute_tag(tag, **kwargs)

    def execute_tag(self, tag: Tag, **kwargs) -> Any:
        _validate_tag_values(tag)
        safe_kwargs = _freeze_kwargs(kwargs)
        self.hooks.do_action("before_execute", tag, **safe_kwargs)
        if tag.tag_type == TagType.DOUBLE:
            result = self._execute_container(tag, **kwargs)
        elif tag.tag_type == TagType.CHEATCODE:
            result = self._execute_cheatcode(tag, **kwargs)
        else:
            result = self._execute_simple(tag, **kwargs)
        if self._apply_filters:
            result = self.filters.apply_filters("result", result, tag, **safe_kwargs)
        self.hooks.do_action("after_execute", tag, result, **safe_kwargs)
        return result

    def _execute_container(self, tag: Tag, **kwargs) -> Any:
        handler = self._container_handlers.get(tag.action)
        if not handler:
            raise ValueError(f"No container handler for '{tag.action}'")
        return handler(tag.content, **_freeze_kwargs(kwargs))

    def _execute_cheatcode(self, tag: Tag, **kwargs) -> Any:
        key = f"{tag.namespace}:{tag.action}"
        local_handler = self._handlers.get(key)

        safe_kwargs = _freeze_kwargs(kwargs)
        call_context = {"tag": tag, "namespace": tag.namespace, "action": tag.action}
        call_context.update(safe_kwargs)

        try:
            from .busy_bridge import emit as emit_compat, HookPoints

            emit_compat(
                HookPoints.PRE_CHEATCODE_EXECUTE,
                tag.namespace,
                tag.action,
                tag.attributes,
                context=call_context,
            )
        except Exception:
            pass

        if local_handler is None:
            namespace = str(tag.namespace)
            ns_handler = self._resolve_namespace_handler(namespace)
            if ns_handler is None:
                raise ValueError(f"No handler for cheatcode '{key}'")
            if not hasattr(ns_handler, "execute"):
                raise ValueError(f"Namespace handler for '{namespace}' has no execute() method")
            from .busy_bridge import validate_action_metadata

            validate_action_metadata(namespace, tag.action, self._resolve_namespace_metadata(namespace))
            result = ns_handler.execute(tag.action, **_merge_call_kwargs(tag.attributes, safe_kwargs))
        else:
            args = tag.params.copy()
            result = local_handler(*args, **_merge_call_kwargs(tag.attributes, safe_kwargs))

        try:
            from .busy_bridge import emit as emit_compat, HookPoints

            emit_compat(
                HookPoints.POST_CHEATCODE_EXECUTE,
                tag.namespace,
                tag.action,
                result,
                context=call_context,
            )
        except Exception:
            pass

        return result

    def _execute_simple(self, tag: Tag, **kwargs) -> Any:
        handler = self._handlers.get(tag.action)
        if not handler:
            raise ValueError(f"No handler for tag '{tag.action}'")
        return handler(**_freeze_kwargs(kwargs))

    async def execute_async(self, tag_string: str, **kwargs) -> Any:
        tag = parse_tag(tag_string)
        safe_kwargs = _freeze_kwargs(kwargs)
        self.hooks.do_action("before_execute", tag, **safe_kwargs)

        if tag.tag_type == TagType.DOUBLE:
            handler = self._container_handlers.get(tag.action)
            if not handler:
                raise ValueError(f"No handler for '{tag.action}'")
            result = handler(tag.content, **safe_kwargs)
        elif tag.tag_type == TagType.CHEATCODE:
            key = f"{tag.namespace}:{tag.action}"
            handler = self._handlers.get(key)
            if handler is None:
                ns_handler = self._resolve_namespace_handler(str(tag.namespace))
                if ns_handler is None:
                    raise ValueError(f"No handler for '{tag.namespace}:{tag.action}'")
                if not hasattr(ns_handler, "execute"):
                    raise ValueError(f"Namespace handler for '{tag.namespace}' has no execute() method")
                metadata = self._resolve_namespace_metadata(str(tag.namespace))
                from .busy_bridge import validate_action_metadata

                validate_action_metadata(str(tag.namespace), tag.action, metadata)
                result = ns_handler.execute(tag.action, **_merge_call_kwargs(tag.attributes, safe_kwargs))
            else:
                result = handler(*tag.params, **_merge_call_kwargs(tag.attributes, safe_kwargs))
        else:
            handler = self._handlers.get(tag.action)
            if not handler:
                raise ValueError(f"No handler for '{tag.action}'")
            result = handler(**safe_kwargs)

        if inspect.isawaitable(result):
            result = await result
        if self._apply_filters:
            result = self.filters.apply_filters("result", result, tag, **safe_kwargs)
        self.hooks.do_action("after_execute", tag, result, **safe_kwargs)
        return result


_global_context = Context()


def register(pattern: str):
    return _global_context.register(pattern)


def register_container(tag_name: str):
    return _global_context.register_container(tag_name)


def execute(tag_string: str, **kwargs) -> Any:
    tag = parse_tag(tag_string)
    return _global_context.execute_tag(tag, **kwargs)


def execute_text(text: str, **kwargs) -> List[Any]:
    return _global_context.execute_text(text, **kwargs)


def register_namespace(namespace: str, handler: Any, metadata: Optional[Dict[str, Any]] = None):
    try:
        from .busy_bridge import register_namespace as register_bridge_namespace

        register_bridge_namespace(namespace, handler, metadata=metadata)
    except (ImportError, ModuleNotFoundError):
        _global_context.register_namespace(namespace, handler, metadata=metadata)
    return handler


def unregister_namespace(namespace: str) -> None:
    try:
        from .busy_bridge import unregister_namespace as unregister_bridge_namespace

        unregister_bridge_namespace(namespace)
    except (ImportError, ModuleNotFoundError):
        _global_context.unregister_namespace(namespace)


def execute_cheatcode(namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None):
    try:
        from .busy_bridge import execute_cheatcode as execute_bridge_cheatcode

        return execute_bridge_cheatcode(namespace, action, attributes)
    except (ImportError, ModuleNotFoundError):
        return _global_context.execute_cheatcode(namespace, action, attributes)


def get_no_response(namespace: str, action: str) -> bool:
    return _global_context.get_no_response(namespace, action)


async def execute_async(tag_string: str, **kwargs) -> Any:
    return await _global_context.execute_async(tag_string, **kwargs)
