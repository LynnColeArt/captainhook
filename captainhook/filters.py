"""Filters system - WordPress-style filter hooks."""

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
class _FilterRegistration:
    callback: Callable
    priority: int


class Filters:
    """Filters system - WordPress-style filter hooks."""

    def __init__(self) -> None:
        self._filters: Dict[str, List[_FilterRegistration]] = {}

    def add_filter(self, tag: str, callback: Callable, priority: int = 10):
        """
        Add a filter.

        Args:
            tag: Filter name
            callback: Callback to execute (should accept and return value)
            priority: Lower = earlier execution (default: 10)
        """
        self._filters.setdefault(tag, []).append(_FilterRegistration(callback=callback, priority=priority))
        self._filters[tag].sort(key=lambda item: item.priority)

    def apply_filters(self, tag: str, value: Any, *args, **kwargs) -> Any:
        """
        Apply all filters to a value.

        Args:
            tag: Filter name
            value: Initial value
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Filtered value
        """
        callbacks = list(self._filters.get(tag, []))
        if not callbacks:
            return value

        safe_args = tuple(_freeze(value) for value in args)
        safe_kwargs: Dict[str, Any] = {key: _freeze(value) for key, value in kwargs.items()}
        current = _freeze(value)
        for filter_registration in callbacks:
            try:
                current = filter_registration.callback(current, *safe_args, **safe_kwargs)
            except Exception:
                continue
        return current

    def remove_filter(self, tag: str, callback: Callable):
        """Remove a specific filter."""
        callbacks = self._filters.get(tag)
        if not callbacks:
            return
        self._filters[tag] = [f for f in callbacks if f.callback is not callback]

    def has_filter(self, tag: str) -> bool:
        """Check if a filter exists."""
        return tag in self._filters and len(self._filters[tag]) > 0
