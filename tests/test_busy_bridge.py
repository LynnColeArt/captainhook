"""
Tests for Busy38 compatibility hooks and namespace registry.
"""

import asyncio
import os

import pytest

from captainhook import (
    Context,
    busy38_hooks,
    HookPoints,
    register_namespace,
    get_no_response,
    unregister_namespace,
    get_namespace,
    execute_cheatcode,
    list_busy38_hooks,
    get_busy38_stats,
    should_suppress_cheatcode_response,
)


class TestBusyBridgeNamespace:
    """Validate namespace registry behavior."""

    def test_register_execute_and_unregister_namespace(self):
        calls = []

        class DemoHandler:
            def execute(self, action, **kwargs):
                calls.append((action, kwargs))
                return {"action": action, **kwargs}

        handler = DemoHandler()
        register_namespace("demo", handler)

        try:
            result = execute_cheatcode("demo", "ping", {"value": "ok"})
            assert result == {"action": "ping", "value": "ok"}
            assert calls == [("ping", {"value": "ok"})]
            assert get_namespace("demo") is handler
        finally:
            unregister_namespace("demo")

    def test_context_falls_back_to_global_namespace(self):
        class Probe:
            def __init__(self):
                self.calls = []

            def execute(self, action, **kwargs):
                self.calls.append((action, kwargs))
                return {"ok": True, "action": action, **kwargs}

        handler = Probe()
        register_namespace("ctxprobe", handler)
        ctx = Context()

        try:
            result = ctx.execute('[ctxprobe:status value="alive" /]')
            assert result == {"ok": True, "action": "status", "value": "alive"}
            assert handler.calls == [("status", {"value": "alive"})]
        finally:
            unregister_namespace("ctxprobe")

    def test_action_allowlist_blocks_unknown_action(self):
        class Probe:
            def execute(self, action, **kwargs):
                return {"ok": True, "action": action, **kwargs}

        register_namespace("strict", Probe(), metadata={"allowed_actions": ["ping"]})
        try:
            with pytest.raises(ValueError):
                execute_cheatcode("strict", "pong", {"value": "x"})
        finally:
            unregister_namespace("strict")

    def test_async_namespace_execution_from_execute_async(self):
        class AsyncProbe:
            async def execute(self, action, **kwargs):
                await asyncio.sleep(0)
                return {"ok": True, "action": action, **kwargs}

        register_namespace("asyncprobe", AsyncProbe())
        ctx = Context()

        try:
            result = asyncio.run(ctx.execute_async('[asyncprobe:check value="x" /]'))
            assert result == {"ok": True, "action": "check", "value": "x"}
        finally:
            unregister_namespace("asyncprobe")

    def test_namespace_level_no_response_metadata(self):
        class Probe:
            def execute(self, action, **kwargs):
                return {"ok": True, "action": action, **kwargs}

        register_namespace("noreply", Probe(), metadata={"noResponse": True})
        try:
            assert get_no_response("noreply", "anything") is True
        finally:
            unregister_namespace("noreply")

    def test_namespace_level_no_response_uses_snake_case_key(self):
        class Probe:
            def execute(self, action, **kwargs):
                return {"ok": True, "action": action, **kwargs}

        register_namespace("snakecase", Probe(), metadata={"no_response": True})
        try:
            assert should_suppress_cheatcode_response("snakecase", "anything") is True
            assert get_no_response("snakecase", "anything") is True
        finally:
            unregister_namespace("snakecase")

    def test_action_level_no_response_overrides_namespace_default(self):
        class Probe:
            def execute(self, action, **kwargs):
                return {"ok": True, "action": action, **kwargs}

        register_namespace(
            "actionreply",
            Probe(),
            metadata={
                "noResponse": False,
                "actions": {
                    "silent": {"noResponse": True},
                    "loud": {"noResponse": False},
                },
            },
        )
        try:
            assert get_no_response("actionreply", "silent") is True
            assert get_no_response("actionreply", "loud") is False
            assert get_no_response("actionreply", "unknown") is False
        finally:
            unregister_namespace("actionreply")

        register_namespace(
            "actionreply2",
            Probe(),
            metadata={"noResponse": True, "actions": {"silent": {"noResponse": False}}},
        )
        try:
            assert get_no_response("actionreply2", "silent") is False
        finally:
            unregister_namespace("actionreply2")


class TestBusyBridgeHooks:
    """Validate busy-style hook points."""

    def test_hook_emit_order_and_context(self):
        events = []

        def pre(namespace, action, attrs, context=None):
            events.append(("pre", namespace, action, context.get("phase")))

        def post(namespace, action, result, context=None):
            events.append(("post", namespace, action, context.get("phase")))

        pre_id = busy38_hooks.add_action(HookPoints.PRE_TOOL_EXECUTE, pre, priority=10)
        post_id = busy38_hooks.add_action(HookPoints.POST_TOOL_EXECUTE, post, priority=10)

        try:
            busy38_hooks.do_action(
                HookPoints.PRE_TOOL_EXECUTE,
                "n1",
                "a1",
                {"value": "1"},
                context={"phase": "before"},
            )
            busy38_hooks.do_action(
                HookPoints.POST_TOOL_EXECUTE,
                "n1",
                "a1",
                {"ok": True},
                context={"phase": "after"},
            )

            assert events == [("pre", "n1", "a1", "before"), ("post", "n1", "a1", "after")]
        finally:
            busy38_hooks.remove_action(HookPoints.PRE_TOOL_EXECUTE, pre_id)
            busy38_hooks.remove_action(HookPoints.POST_TOOL_EXECUTE, post_id)

    def test_hook_registry_introspection(self):
        action_id = busy38_hooks.add_action("bridge:inspect", lambda value: value)
        try:
            hooks = list_busy38_hooks()
            assert "bridge:inspect" in hooks

            stats = get_busy38_stats()
            assert "total_hooks" in stats
            assert "total_filters" in stats
        finally:
            busy38_hooks.remove_action("bridge:inspect", action_id)

    def test_critical_hook_removal_requires_token(self):
        event = []

        def _blocked(*_args, **_kwargs):
            event.append("blocked")

        action_id = busy38_hooks.add_action(HookPoints.PRE_CHEATCODE_EXECUTE, _blocked, priority=10)
        try:
            with pytest.raises(PermissionError):
                busy38_hooks.remove_action(HookPoints.PRE_CHEATCODE_EXECUTE, action_id)
        finally:
            # If env token not set, critical hooks are intentionally immutable.
            token = os.getenv("CAPTAINHOOK_HOOK_REMOVAL_TOKEN", "").strip()
            if token:
                assert busy38_hooks.remove_action(
                    HookPoints.PRE_CHEATCODE_EXECUTE,
                    action_id,
                    allow_critical=True,
                    removal_token=token,
                )
            else:
                assert event == []
