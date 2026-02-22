"""
Tests for CaptainHook core execution.
"""

import sys
sys.path.insert(0, '..')

import pytest
from captainhook import Context, register, register_container, execute, execute_text


class TestCore:
    """Test core execution."""
    
    def test_context_register_and_execute(self):
        """Test registering and executing a handler."""
        ctx = Context()
        
        @ctx.register("test:action")
        def test_action(param):
            return f"Executed with {param}"
        
        result = ctx.execute("[test:action hello /]")
        assert result == "Executed with hello"

    def test_execute_rejects_parameter_smuggling(self):
        """Overlapping param keys must be rejected between attrs and runtime kwargs."""
        ctx = Context()

        @ctx.register("safe:set")
        def set_value(value):
            return value

        with pytest.raises(ValueError):
            ctx.execute('[safe:set value="from_tag" /]', value="from_runtime")
    
    def test_container_handler(self):
        """Test container tag execution."""
        ctx = Context()
        
        @ctx.register_container("code")
        def handle_code(content):
            return f"Code: {content}"
        
        result = ctx.execute("[code]print('hello')[/code]")
        assert result == "Code: print('hello')"
    
    def test_global_register(self):
        """Test global registration."""
        @register("global:test")
        def global_test():
            return "global executed"
        
        result = execute("[global:test /]")
        assert result == "global executed"
    
    def test_execute_text_multiple(self):
        """Test executing multiple tags from text."""
        ctx = Context()
        
        @ctx.register("math:add")
        def add(a, b):
            return int(a) + int(b)
        
        @ctx.register_container("echo")
        def echo(content):
            return content.upper()
        
        text = """
        [math:add 5 3 /]
        [echo]hello[/echo]
        """
        results = ctx.execute_text(text)
        
        assert len(results) == 2
        assert results[0] == 8
        assert results[1] == "HELLO"
    
    def test_hooks_execution(self):
        """Test that hooks are called."""
        ctx = Context()
        calls = []
        
        @ctx.register("hooked:action")
        def hooked_action():
            calls.append("handler")
            return "done"
        
        ctx.hooks.add_action("before_execute", lambda tag: calls.append("before"))
        ctx.hooks.add_action("after_execute", lambda tag, result: calls.append("after"))
        
        ctx.execute("[hooked:action /]")
        
        assert calls == ["before", "handler", "after"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
