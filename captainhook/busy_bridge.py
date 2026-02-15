"""Busy38 compatibility layer for CaptainHook.

This module mirrors Busy38's public extension API for hooks and namespace
registry usage so external integrations can plug in with a familiar contract.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol


def _make_id(counter: int) -> str:
    return f"hook-{counter}"


class HookPointFunc(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ...


@dataclass
class _HookEntry:
    callback: Callable
    priority: int
    entry_id: str
    order: int


class BusyHookRegistry:
    """Minimal compatibility registry used for Busy-style hooks/filters."""

    def __init__(self) -> None:
        self._actions: Dict[str, List[_HookEntry]] = {}
        self._filters: Dict[str, List[_HookEntry]] = {}
        self._lock = threading.RLock()
        self._next_action_id = 0
        self._next_filter_id = 0

    def _next_id(self, is_filter: bool = False) -> str:
        if is_filter:
            self._next_filter_id += 1
            return _make_id(self._next_filter_id)
        self._next_action_id += 1
        return _make_id(self._next_action_id)

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
            entry = _HookEntry(callback=callback, priority=priority, entry_id=self._next_id(is_filter), order=len(bucket))
            bucket.append(entry)
            bucket.sort(key=lambda item: (item.priority, item.order))
            return entry.entry_id

    def add_action(self, hook_name: str, callback: Callable, priority: int = 10) -> str:
        return self._register(self._actions, hook_name, callback, priority, is_filter=False)

    def add_filter(self, hook_name: str, callback: Callable, priority: int = 10) -> str:
        return self._register(self._filters, hook_name, callback, priority, is_filter=True)

    def _remove_one(
        self,
        registry: Dict[str, List[_HookEntry]],
        hook_name: str,
        entry_id: str | Callable,
    ) -> bool:
        with self._lock:
            entries = registry.get(hook_name)
            if not entries:
                return False
            before = len(entries)
            if callable(entry_id):
                registry[hook_name] = [
                    entry
                    for entry in entries
                    if entry.callback is not entry_id
                ]
            else:
                registry[hook_name] = [
                    entry
                    for entry in entries
                    if entry.entry_id != entry_id
                ]
            removed = len(registry[hook_name]) != before
            if not registry[hook_name]:
                registry.pop(hook_name, None)
            return removed

    def remove_action(self, hook_name: str, action_id: str) -> bool:
        return self._remove_one(self._actions, hook_name, action_id)

    def remove_filter(self, hook_name: str, filter_id: str) -> bool:
        return self._remove_one(self._filters, hook_name, filter_id)

    def remove_all_actions(self, hook_name: str) -> bool:
        with self._lock:
            return self._actions.pop(hook_name, None) is not None

    def remove_all_filters(self, hook_name: str) -> bool:
        with self._lock:
            return self._filters.pop(hook_name, None) is not None

    def do_action(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            callbacks = list(self._actions.get(hook_name, []))
        for entry in callbacks:
            entry.callback(*args, **kwargs)

    def apply(self, hook_name: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            callbacks = list(self._filters.get(hook_name, []))
        for entry in callbacks:
            value = entry.callback(value, *args, **kwargs)
        return value

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

    # Agent lifecycle
    PRE_AGENT_EXECUTE = "busy38.pre_agent_execute"
    POST_AGENT_EXECUTE = "busy38.post_agent_execute"
    AGENT_SPAWN = "busy38.agent_spawn"

    # LLM interaction
    PRE_LLM_CALL = "busy38.pre_llm_call"
    POST_LLM_CALL = "busy38.post_llm_call"
    LLM_RESPONSE_FILTER = "busy38.llm_response_filter"

    # Memory/notes
    PRE_NOTE_CREATE = "busy38.pre_note_create"
    POST_NOTE_CREATE = "busy38.post_note_create"
    NOTE_CONTENT_FILTER = "busy38.note_content_filter"

    # Tools
    PRE_TOOL_EXECUTE = "busy38.pre_tool_execute"
    POST_TOOL_EXECUTE = "busy38.post_tool_execute"
    TOOL_RESULT_FILTER = "busy38.tool_result_filter"

    # Cheatcodes
    PRE_CHEATCODE_EXECUTE = "busy38.pre_cheatcode_execute"
    POST_CHEATCODE_EXECUTE = "busy38.post_cheatcode_execute"

    # Workspace
    PRE_WORKSPACE_SAVE = "busy38.pre_workspace_save"
    POST_WORKSPACE_SAVE = "busy38.post_workspace_save"

    # Orchestration
    PARALLEL_EXECUTE_START = "busy38.parallel_execute_start"
    PARALLEL_EXECUTE_COMPLETE = "busy38.parallel_execute_complete"
    ORCHESTRATION_STATUS = "busy38.orchestration_status"

    # Heartbeat automation
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
        self._lock = threading.RLock()

    def register(self, namespace: str, handler: NamespaceHandler) -> None:
        with self._lock:
            if namespace in self._handlers:
                raise ValueError(f"Namespace '{namespace}' is already registered")
            self._handlers[namespace] = handler

    def unregister(self, namespace: str) -> None:
        with self._lock:
            if namespace not in self._handlers:
                raise KeyError(f"Namespace '{namespace}' is not registered")
            self._handlers.pop(namespace)

    def get(self, namespace: str) -> Optional[NamespaceHandler]:
        with self._lock:
            return self._handlers.get(namespace)

    def execute(self, namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
        handler = self.get(namespace)
        if handler is None:
            raise KeyError(f"Namespace '{namespace}' is not registered")
        attributes = attributes or {}
        return handler.execute(action, **attributes)

    def is_registered(self, namespace: str) -> bool:
        with self._lock:
            return namespace in self._handlers

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()

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


def register_namespace(namespace: str, handler: NamespaceHandler) -> None:
    cheatcode_registry.register(namespace, handler)


def unregister_namespace(namespace: str) -> None:
    cheatcode_registry.unregister(namespace)


def get_namespace(namespace: str) -> Optional[NamespaceHandler]:
    return cheatcode_registry.get(namespace)


def get_registry() -> NamespaceRegistry:
    return cheatcode_registry


def execute_cheatcode(namespace: str, action: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
    return cheatcode_registry.execute(namespace, action, attributes)


def remove_all_actions(hook_name: str) -> bool:
    return busy38_hooks.remove_all_actions(hook_name)


def remove_all_filters(hook_name: str) -> bool:
    return busy38_hooks.remove_all_filters(hook_name)


def remove_action(hook_name: str, action_id: str) -> bool:
    return busy38_hooks.remove_action(hook_name, action_id)


def remove_filter(hook_name: str, filter_id: str) -> bool:
    return busy38_hooks.remove_filter(hook_name, filter_id)


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
    "remove_all_actions",
    "remove_all_filters",
    "remove_action",
    "remove_filter",
]
