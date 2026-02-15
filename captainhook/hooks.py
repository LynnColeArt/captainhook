"""
Hooks system - WordPress-style action hooks.
"""

from typing import Callable, List, Any


class Hooks:
    """WordPress-style action hooks."""
    
    def __init__(self):
        self._hooks: dict = {}
    
    def add_action(self, hook_name: str, callback: Callable, priority: int = 10):
        """
        Add an action hook.
        
        Args:
            hook_name: Name of the hook
            callback: Function to call
            priority: Lower = earlier execution (default: 10)
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        
        self._hooks[hook_name].append({
            'callback': callback,
            'priority': priority
        })
        
        # Sort by priority
        self._hooks[hook_name].sort(key=lambda x: x['priority'])
    
    def do_action(self, hook_name: str, *args, **kwargs):
        """
        Execute all callbacks for a hook.
        
        Args:
            hook_name: Name of the hook to execute
            *args: Positional arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
        """
        if hook_name not in self._hooks:
            return
        
        for hook in self._hooks[hook_name]:
            hook['callback'](*args, **kwargs)
    
    def remove_action(self, hook_name: str, callback: Callable):
        """Remove a specific action."""
        if hook_name not in self._hooks:
            return
        
        self._hooks[hook_name] = [
            h for h in self._hooks[hook_name] 
            if h['callback'] != callback
        ]
    
    def has_action(self, hook_name: str) -> bool:
        """Check if a hook has any actions."""
        return hook_name in self._hooks and len(self._hooks[hook_name]) > 0