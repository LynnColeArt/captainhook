"""Hooks system - WordPress-style action hooks."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Dict, List


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


@dataclass(frozen=True)
class _HookRegistration:
    callback: Callable
    priority: int
    action: str


class Hooks:
    """WordPress-style action hooks."""

    def __init__(self) -> None:
        self._hooks: Dict[str, List[_HookRegistration]] = {}

    def add_action(self, hook_name: str, callback: Callable, priority: int = 10):
        """
        Add an action hook.

        Args:
            hook_name: Name of the hook
            callback: Function to call
            priority: Lower = earlier execution (default: 10)
        """
        entry = _HookRegistration(callback=callback, priority=priority, action=hook_name)
        self._hooks.setdefault(hook_name, []).append(entry)
        self._hooks[hook_name].sort(key=lambda item: item.priority)

    def do_action(self, hook_name: str, *args, **kwargs):
        """
        Execute all callbacks for a hook.

        Args:
            hook_name: Name of the hook to execute
            *args: Positional arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
        """
        callbacks = list(self._hooks.get(hook_name, []))
        if not callbacks:
            return

        safe_args = tuple(_freeze(value) for value in args)
        safe_kwargs: Dict[str, Any] = {key: _freeze(value) for key, value in kwargs.items()}
        for hook in callbacks:
            try:
                hook.callback(*safe_args, **safe_kwargs)
            except Exception:
                continue

    def remove_action(self, hook_name: str, callback: Callable):
        """Remove a specific action."""
        hooks = self._hooks.get(hook_name)
        if not hooks:
            return
        self._hooks[hook_name] = [h for h in hooks if h.callback is not callback]

    def has_action(self, hook_name: str) -> bool:
        """Check if a hook has any actions."""
        return hook_name in self._hooks and len(self._hooks[hook_name]) > 0
