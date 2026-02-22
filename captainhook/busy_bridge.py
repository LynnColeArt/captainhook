"""Busy38 compatibility layer for CaptainHook.

Security-focused compatibility APIs:
- critical hook points are protected from removal without explicit token
- hook/filter callbacks receive immutable copies
- callbacks execute in isolated try/except envelopes
- namespace execution supports explicit action allow-lists
"""

from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Set

_CRITICAL_HOOKS: Set[str] = {
    "busy38.pre_cheatcode_execute",
    "busy38.post_cheatcode_execute",
}

_HOOK_REMOVAL_TOKEN = os.getenv("CAPTAINHOOK_HOOK_REMOVAL_TOKEN", "").strip()


def _validate_identifier(value: str) -> None:
    if not value:
        raise ValueError("Identifier cannot be empty")
    if value.startswith("__") or value.endswith("__"):
        raise ValueError(f"Identifier '{value}' contains forbidden underscore sequence")
    if not (value[0].isalpha() or value[0] == "_"):
        raise ValueError(f"Invalid identifier '{value}'")
    for char in value:
        if not (char.isalnum() or char in {"_", "-", ".", ":"}):
            raise ValueError(f"Invalid identifier '{value}'")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(dict(value))
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, set):
        return frozenset(value)
    if isinstance(value, tuple):
        return tuple(value)
    return value


def _freeze_args(args: tuple, kwargs: Dict[str, Any]) -> tuple:
    safe_args = tuple(_freeze(value) for value in args)
    safe_kwargs = {key: _freeze(value) for key, value in kwargs.items()}
    return safe_args, safe_kwargs


def _ensure_removal_allowed(hook_name: str, allow_critical: bool, removal_token: Optional[str]) -> None:
    if hook_name not in _CRITICAL_HOOKS:
        return
    if not allow_critical:
        raise PermissionError(
            f"critical hook '{hook_name}' cannot be removed without allow_critical=True"
        )
    if not _HOOK_REMOVAL_TOKEN:
        raise PermissionError(
            f"critical hook '{hook_name}' cannot be removed without a configured CAPTAINHOOK_HOOK_REMOVAL_TOKEN"
        )
    if not removal_token or not secrets.compare_digest(removal_token, _HOOK_REMOVAL_TOKEN):
        raise PermissionError(f"critical hook '{hook_name}' requires matching CAPTAINHOOK_HOOK_REMOVAL_TOKEN")


@dataclass(frozen=True)
class _HookEntry:
    callback: Callable
    priority: int
    entry_id: str
    order: int


class HookPointFunc(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ...


class BusyHookRegistry:
    """Minimal compatibility registry used for Busy-style hooks/filters."""

    def __init__(self) -> None:
        self._actions: Dict[str, List[_HookEntry]] = {}
        self._filters: Dict[str, List[_HookEntry]] = {}
        self._lock = threading.RLock()
        self._next_action_id = 0
        self._next_filter_id = 0

    @staticmethod
    def _next_entry_id(counter: int) -> str:
        return f"hook-{counter}"

    def _register(
        self,
        registry: Dict[str, List[_HookEntry]],
        hook_name: str,
        callback: Callable,
        priority: int = 10,
        is_filter: bool = False,
    ) -> str:
        if not callable(callback):
            raise TypeError("hook callback must be callable")
        with self._lock:
            bucket = registry.setdefault(hook_name, [])
            entry_id = self._next_entry_id(
                self._next_filter_id if is_filter else self._next_action_id
            )
            if is_filter:
                self._next_filter_id += 1
            else:
                self._next_action_id += 1
            entry = _HookEntry(callback=callback, priority=priority, entry_id=entry_id, order=len(bucket))
            bucket.append(entry)
            bucket.sort(key=lambda item: (item.priority, item.order))
            return entry.entry_id

    def add_action(self, hook_name: str, callback: Callable, priority: int = 10) -> str:
        _validate_identifier(hook_name)
        return self._register(self._actions, hook_name, callback, priority, is_filter=False)

    def add_filter(self, hook_name: str, callback: Callable, priority: int = 10) -> str:
        _validate_identifier(hook_name)
        return self._register(self._filters, hook_name, callback, priority, is_filter=True)

    def _remove_one(
        self,
        registry: Dict[str, List[_HookEntry]],
        hook_name: str,
        entry_id: str | Callable,
        allow_critical: bool,
        removal_token: Optional[str],
    ) -> bool:
        _ensure_removal_allowed(hook_name, allow_critical, removal_token)
        with self._lock:
            entries = registry.get(hook_name)
            if not entries:
                return False
            before = len(entries)
            if callable(entry_id):
                registry[hook_name] = [entry for entry in entries if entry.callback is not entry_id]
            else:
                registry[hook_name] = [entry for entry in entries if entry.entry_id != entry_id]
            removed = len(registry[hook_name]) != before
            if not registry[hook_name]:
                registry.pop(hook_name, None)
            return removed

    def remove_action(
        self,
        hook_name: str,
        action_id: str | Callable,
        allow_critical: bool = False,
        removal_token: Optional[str] = None,
    ) -> bool:
        return self._remove_one(self._actions, hook_name, action_id, allow_critical, removal_token)

    def remove_filter(
        self,
        hook_name: str,
        filter_id: str | Callable,
        allow_critical: bool = False,
        removal_token: Optional[str] = None,
    ) -> bool:
        return self._remove_one(self._filters, hook_name, filter_id, allow_critical, removal_token)

    def remove_all_actions(
        self,
        hook_name: str,
        allow_critical: bool = False,
        removal_token: Optional[str] = None,
    ) -> bool:
        _ensure_removal_allowed(hook_name, allow_critical, removal_token)
        with self._lock:
            return self._actions.pop(hook_name, None) is not None

    def remove_all_filters(
        self,
        hook_name: str,
        allow_critical: bool = False,
        removal_token: Optional[str] = None,
    ) -> bool:
        _ensure_removal_allowed(hook_name, allow_critical, removal_token)
        with self._lock:
            return self._filters.pop(hook_name, None) is not None

    def do_action(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            callbacks = list(self._actions.get(hook_name, []))
        if not callbacks:
            return
        safe_args, safe_kwargs = _freeze_args(args, dict(kwargs))
        for entry in callbacks:
            try:
                entry.callback(*safe_args, **safe_kwargs)
            except Exception:
                continue

    def apply(self, hook_name: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            callbacks = list(self._filters.get(hook_name, []))
        if not callbacks:
            return value
        safe_args, safe_kwargs = _freeze_args(args, dict(kwargs))
        current = value
        for entry in callbacks:
            try:
                current = entry.callback(current, *safe_args, **safe_kwargs)
            except Exception:
                continue
        return current

    def list_hooks(self) -> List[str]:
        with self._lock:
            hooks = set(self._actions.keys()) | set(self._filters.keys())
        return sorted(hooks)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_actions = sum(len(v) for v in self._actions.values())
            total_filters = sum(len(v) for v in self._filters.values())
        return {
            "total_hooks": total_actions,
            "total_filters": total_filters,
        }


class HookPoints:
    """Busy38-compatible hook points."""

    PRE_AGENT_EXECUTE = "busy38.pre_agent_execute"
    POST_AGENT_EXECUTE = "busy38.post_agent_execute"
    AGENT_SPAWN = "busy38.agent_spawn"
    PRE_LLM_CALL = "busy38.pre_llm_call"
    POST_LLM_CALL = "busy38.post_llm_call"
    LLM_RESPONSE_FILTER = "busy38.llm_response_filter"
    PRE_NOTE_CREATE = "busy38.pre_note_create"
    POST_NOTE_CREATE = "busy38.post_note_create"
    NOTE_CONTENT_FILTER = "busy38.note_content_filter"
    PRE_TOOL_EXECUTE = "busy38.pre_tool_execute"
    POST_TOOL_EXECUTE = "busy38.post_tool_execute"
    TOOL_RESULT_FILTER = "busy38.tool_result_filter"
    PRE_CHEATCODE_EXECUTE = "busy38.pre_cheatcode_execute"
    POST_CHEATCODE_EXECUTE = "busy38.post_cheatcode_execute"
    PRE_WORKSPACE_SAVE = "busy38.pre_workspace_save"
    POST_WORKSPACE_SAVE = "busy38.post_workspace_save"
    PARALLEL_EXECUTE_START = "busy38.parallel_execute_start"
    PARALLEL_EXECUTE_COMPLETE = "busy38.parallel_execute_complete"
    ORCHESTRATION_STATUS = "busy38.orchestration_status"
    HEARTBEAT_REGISTER_JOBS = "busy38.heartbeat.register_jobs"
    HEARTBEAT_TICK_START = "busy38.heartbeat.tick_start"
    HEARTBEAT_TICK_COMPLETE = "busy38.heartbeat.tick_complete"
    HEARTBEAT_JOB_START = "busy38.heartbeat.job_start"
    HEARTBEAT_JOB_COMPLETE = "busy38.heartbeat.job_complete"
    HEARTBEAT_JOB_ERROR = "busy38.heartbeat.job_error"
    HEARTBEAT_LEGACY_CHECK = "busy38.heartbeat.legacy_check"


class NamespaceHandler(Protocol):
    def execute(self, action: str, **kwargs: Any) -> Any:
        ...


class NamespaceRegistry:
    """Thread-safe namespace handler registry."""

    def __init__(self) -> None:
        self._handlers: Dict[str, NamespaceHandler] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _validate_allowed_action_list(namespace: str, values: Any) -> List[str]:
        if values is None:
            return []
        if isinstance(values, tuple):
            values = list(values)
        if not isinstance(values, list):
            raise TypeError(
                f"metadata['allowed_actions'] for namespace '{namespace}' must be a list of action names"
            )
        normalized: List[str] = []
        for value in values:
            if not isinstance(value, str):
                raise TypeError(
                    f"metadata['allowed_actions'] for namespace '{namespace}' must contain strings"
                )
            normalized.append(value)
        return normalized

    def register(
        self,
        namespace: str,
        handler: NamespaceHandler,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        _validate_identifier(namespace)
        with self._lock:
            if namespace in self._handlers:
                raise ValueError(f"Namespace '{namespace}' is already registered")
            self._handlers[namespace] = handler
            self._metadata[namespace] = dict(metadata) if isinstance(metadata, Dict) else {}

    def unregister(self, namespace: str) -> None:
        _validate_identifier(namespace)
        with self._lock:
            if namespace not in self._handlers:
                raise KeyError(f"Namespace '{namespace}' is not registered")
            self._handlers.pop(namespace)
            self._metadata.pop(namespace, None)

    def get(self, namespace: str) -> Optional[NamespaceHandler]:
        _validate_identifier(namespace)
        with self._lock:
            return self._handlers.get(namespace)

    def get_metadata(self, namespace: str) -> Dict[str, Any]:
        _validate_identifier(namespace)
        with self._lock:
            raw = self._metadata.get(namespace, {})
            if isinstance(raw, Dict):
                return dict(raw)
            return {}

    @staticmethod
    def _extract_action_metadata(metadata: Dict[str, Any], action: str) -> Dict[str, Any]:
        if not metadata:
            return {}
        for container_name in ("actions", "action_metadata", "action_metadata_by_name"):
            action_map = metadata.get(container_name)
            if not isinstance(action_map, Dict):
                continue
            if action in action_map and isinstance(action_map[action], Dict):
                candidate = action_map[action]
                return dict(candidate)
            action_lc = action.lower()
            if action_lc in action_map and isinstance(action_map[action_lc], Dict):
                candidate = action_map[action_lc]
                return dict(candidate)
        return {}

    def _allowed_actions(self, namespace_metadata: Dict[str, Any]) -> Optional[Set[str]]:
        if not namespace_metadata:
            return None
        allowed = self._validate_allowed_action_list("namespace", namespace_metadata.get("allowed_actions"))
        return set(allowed) if allowed else None

    def _validate_namespace_action(self, namespace: str, action: str) -> None:
        _validate_identifier(action)
        metadata = self.get_metadata(namespace)
        allowed = self._allowed_actions(metadata)
        if allowed is not None and action not in allowed:
            raise ValueError(f"Action '{action}' is not allowed for namespace '{namespace}'")

    def execute(self, namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
        _validate_identifier(namespace)
        self._validate_namespace_action(namespace, action)
        handler = self.get(namespace)
        if handler is None:
            raise KeyError(f"Namespace '{namespace}' is not registered")
        safe_attrs: Dict[str, Any] = {}
        for key, value in (attributes or {}).items():
            key_str = str(key)
            _validate_identifier(key_str)
            safe_attrs[key_str] = _freeze(value)
        return handler.execute(action, **safe_attrs)

    def is_registered(self, namespace: str) -> bool:
        _validate_identifier(namespace)
        with self._lock:
            return namespace in self._handlers

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
            self._metadata.clear()

    def list_namespaces(self) -> List[str]:
        with self._lock:
            return sorted(self._handlers.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._handlers)

    def __contains__(self, namespace: str) -> bool:
        return self.is_registered(namespace)


busy38_hooks = BusyHookRegistry()
cheatcode_registry = NamespaceRegistry()


def _register_action(hook_name: str, handler: Optional[HookPointFunc] = None, priority: int = 10):
    if handler is None:
        def decorator(fn: HookPointFunc):
            busy38_hooks.add_action(hook_name, fn, priority)
            return fn

        return decorator
    busy38_hooks.add_action(hook_name, handler, priority)
    return handler


def _register_filter(hook_name: str, handler: Optional[HookPointFunc] = None, priority: int = 10):
    if handler is None:
        def decorator(fn: HookPointFunc):
            busy38_hooks.add_filter(hook_name, fn, priority)
            return fn

        return decorator
    busy38_hooks.add_filter(hook_name, handler, priority)
    return handler


def on_pre_agent_execute(handler=None, priority: int = 10):
    return _register_action(HookPoints.PRE_AGENT_EXECUTE, handler, priority)


def on_post_agent_execute(handler=None, priority: int = 10):
    return _register_action(HookPoints.POST_AGENT_EXECUTE, handler, priority)


def on_pre_llm_call(handler=None, priority: int = 10):
    return _register_action(HookPoints.PRE_LLM_CALL, handler, priority)


def on_post_llm_call(handler=None, priority: int = 10):
    return _register_action(HookPoints.POST_LLM_CALL, handler, priority)


def filter_llm_response(handler=None, priority: int = 10):
    return _register_filter(HookPoints.LLM_RESPONSE_FILTER, handler, priority)


def on_pre_note_create(handler=None, priority: int = 10):
    return _register_action(HookPoints.PRE_NOTE_CREATE, handler, priority)


def on_post_note_create(handler=None, priority: int = 10):
    return _register_action(HookPoints.POST_NOTE_CREATE, handler, priority)


def filter_note_content(handler=None, priority: int = 10):
    return _register_filter(HookPoints.NOTE_CONTENT_FILTER, handler, priority)


def on_pre_tool_execute(handler=None, priority: int = 10):
    return _register_action(HookPoints.PRE_TOOL_EXECUTE, handler, priority)


def on_post_tool_execute(handler=None, priority: int = 10):
    return _register_action(HookPoints.POST_TOOL_EXECUTE, handler, priority)


def filter_tool_result(handler=None, priority: int = 10):
    return _register_filter(HookPoints.TOOL_RESULT_FILTER, handler, priority)


def on_pre_cheatcode_execute(handler=None, priority: int = 10):
    return _register_action(HookPoints.PRE_CHEATCODE_EXECUTE, handler, priority)


def on_post_cheatcode_execute(handler=None, priority: int = 10):
    return _register_action(HookPoints.POST_CHEATCODE_EXECUTE, handler, priority)


def on_orchestration_status(handler=None, priority: int = 10):
    return _register_action(HookPoints.ORCHESTRATION_STATUS, handler, priority)


def on_heartbeat_register_jobs(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_REGISTER_JOBS, handler, priority)


def on_heartbeat_tick_start(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_TICK_START, handler, priority)


def on_heartbeat_tick_complete(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_TICK_COMPLETE, handler, priority)


def on_heartbeat_job_start(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_JOB_START, handler, priority)


def on_heartbeat_job_complete(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_JOB_COMPLETE, handler, priority)


def on_heartbeat_job_error(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_JOB_ERROR, handler, priority)


def on_heartbeat_legacy_check(handler=None, priority: int = 10):
    return _register_action(HookPoints.HEARTBEAT_LEGACY_CHECK, handler, priority)


def emit(hook_name: str, *args: Any, context: Optional[Dict[str, Any]] = None) -> None:
    busy38_hooks.do_action(hook_name, *args, context=context)


def apply(hook_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> Any:
    return busy38_hooks.apply(hook_name, value, context=context)


def list_busy38_hooks() -> List[str]:
    return busy38_hooks.list_hooks()


def get_busy38_stats() -> Dict[str, Any]:
    return busy38_hooks.get_stats()


def register_namespace(namespace: str, handler: NamespaceHandler, metadata: Optional[Dict[str, Any]] = None) -> None:
    cheatcode_registry.register(namespace, handler, metadata=metadata)


def unregister_namespace(namespace: str) -> None:
    cheatcode_registry.unregister(namespace)


def get_namespace(namespace: str) -> Optional[NamespaceHandler]:
    return cheatcode_registry.get(namespace)


def get_registry() -> NamespaceRegistry:
    return cheatcode_registry


def execute_cheatcode(namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
    return cheatcode_registry.execute(namespace, action, attributes)


def _as_metadata_dict(metadata: Any) -> Dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, Dict):
        return dict(metadata)
    if hasattr(metadata, "__dict__") and isinstance(metadata.__dict__, Dict):
        return dict(metadata.__dict__)
    if hasattr(metadata, "as_dict"):
        candidate = metadata.as_dict()
        if isinstance(candidate, Dict):
            return dict(candidate)
    return {}


def _extract_action_metadata(metadata: Dict[str, Any], action: str) -> Dict[str, Any]:
    if not metadata:
        return {}
    for container_name in ("actions", "action_metadata", "action_metadata_by_name"):
        actions = metadata.get(container_name)
        if not isinstance(actions, Dict):
            continue
        if action in actions and isinstance(actions[action], Dict):
            return _as_metadata_dict(actions[action])
        action_lc = action.lower()
        if action_lc in actions and isinstance(actions[action_lc], Dict):
            return _as_metadata_dict(actions[action_lc])
    return {}


def validate_action_metadata(namespace: str, action: str, metadata: Optional[Dict[str, Any]]) -> None:
    _validate_identifier(namespace)
    _validate_identifier(action)
    candidate_metadata = metadata or get_namespace_metadata(namespace)
    allowed = candidate_metadata.get("allowed_actions") if isinstance(candidate_metadata, Dict) else None
    if allowed is not None and action not in NamespaceRegistry._validate_allowed_action_list(namespace, allowed):
        raise ValueError(f"Action '{action}' is not allowed for namespace '{namespace}'")

    if isinstance(candidate_metadata, Dict) and candidate_metadata.get("forbid_dangermeta"):
        local = _extract_action_metadata(candidate_metadata, action)
        if local.get("forbid", False):
            raise ValueError(f"Action '{action}' is forbidden in namespace '{namespace}'")


def get_namespace_metadata(namespace: str) -> Dict[str, Any]:
    return cheatcode_registry.get_metadata(namespace)


def should_suppress_cheatcode_response(namespace: str, action: str) -> bool:
    metadata = get_namespace_metadata(namespace)
    if not metadata:
        return False
    for data in (_extract_action_metadata(metadata, action), metadata):
        no_response = data.get("noResponse", data.get("no_response"))
        if isinstance(no_response, bool):
            return bool(no_response)
    return False


def remove_all_actions(hook_name: str, allow_critical: bool = False, removal_token: Optional[str] = None) -> bool:
    return busy38_hooks.remove_all_actions(hook_name, allow_critical=allow_critical, removal_token=removal_token)


def remove_all_filters(hook_name: str, allow_critical: bool = False, removal_token: Optional[str] = None) -> bool:
    return busy38_hooks.remove_all_filters(hook_name, allow_critical=allow_critical, removal_token=removal_token)


def remove_action(
    hook_name: str,
    action_id: str | Callable,
    allow_critical: bool = False,
    removal_token: Optional[str] = None,
) -> bool:
    return busy38_hooks.remove_action(hook_name, action_id, allow_critical=allow_critical, removal_token=removal_token)


def remove_filter(
    hook_name: str,
    filter_id: str | Callable,
    allow_critical: bool = False,
    removal_token: Optional[str] = None,
) -> bool:
    return busy38_hooks.remove_filter(hook_name, filter_id, allow_critical=allow_critical, removal_token=removal_token)


__all__ = [
    "busy38_hooks",
    "cheatcode_registry",
    "HookPoints",
    "BusyHookRegistry",
    "HookPointFunc",
    "NamespaceHandler",
    "NamespaceRegistry",
    "on_pre_agent_execute",
    "on_post_agent_execute",
    "on_pre_llm_call",
    "on_post_llm_call",
    "filter_llm_response",
    "on_pre_note_create",
    "on_post_note_create",
    "filter_note_content",
    "on_pre_tool_execute",
    "on_post_tool_execute",
    "filter_tool_result",
    "on_pre_cheatcode_execute",
    "on_post_cheatcode_execute",
    "on_orchestration_status",
    "on_heartbeat_register_jobs",
    "on_heartbeat_tick_start",
    "on_heartbeat_tick_complete",
    "on_heartbeat_job_start",
    "on_heartbeat_job_complete",
    "on_heartbeat_job_error",
    "on_heartbeat_legacy_check",
    "emit",
    "apply",
    "list_busy38_hooks",
    "get_busy38_stats",
    "register_namespace",
    "unregister_namespace",
    "get_namespace",
    "get_registry",
    "execute_cheatcode",
    "get_namespace_metadata",
    "should_suppress_cheatcode_response",
    "validate_action_metadata",
    "remove_all_actions",
    "remove_all_filters",
    "remove_action",
    "remove_filter",
]
