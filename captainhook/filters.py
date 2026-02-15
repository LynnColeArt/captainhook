"""
Filters system - WordPress-style filter hooks.
"""

from typing import Callable, List, Any


class Filters:
    """WordPress-style filter hooks."""
    
    def __init__(self):
        self._filters: dict = {}
    
    def add_filter(self, tag: str, callback: Callable, priority: int = 10):
        """
        Add a filter.
        
        Args:
            tag: Filter name
            callback: Function to call (should accept and return value)
            priority: Lower = earlier execution (default: 10)
        """
        if tag not in self._filters:
            self._filters[tag] = []
        
        self._filters[tag].append({
            'callback': callback,
            'priority': priority
        })
        
        # Sort by priority
        self._filters[tag].sort(key=lambda x: x['priority'])
    
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
        if tag not in self._filters:
            return value
        
        for filter_item in self._filters[tag]:
            value = filter_item['callback'](value, *args, **kwargs)
        
        return value
    
    def remove_filter(self, tag: str, callback: Callable):
        """Remove a specific filter."""
        if tag not in self._filters:
            return
        
        self._filters[tag] = [
            f for f in self._filters[tag] 
            if f['callback'] != callback
        ]
    
    def has_filter(self, tag: str) -> bool:
        """Check if a filter exists."""
        return tag in self._filters and len(self._filters[tag]) > 0