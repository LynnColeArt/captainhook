"""
CaptainHook - Cheatcode-style extensibility for Python

Reference: Busy38 cheatcode system
"""

from .core import (
    Context,
    register,
    register_container,
    execute_async,
    execute,
    execute_text,
    register_namespace,
    unregister_namespace,
    execute_cheatcode,
    get_no_response,
)
from .parser import (
    Tag,
    TagType,
    parse_tag,
    parse_all,
    is_valid_tag,
    remove_tags,
)
from .hooks import Hooks
from .filters import Filters
from .busy_bridge import (
    busy38_hooks,
    cheatcode_registry,
    HookPoints,
    NamespaceHandler,
    NamespaceRegistry,
    get_namespace_metadata,
    on_pre_agent_execute,
    on_post_agent_execute,
    on_pre_llm_call,
    on_post_llm_call,
    filter_llm_response,
    on_pre_note_create,
    on_post_note_create,
    filter_note_content,
    on_pre_tool_execute,
    on_post_tool_execute,
    filter_tool_result,
    on_pre_cheatcode_execute,
    on_post_cheatcode_execute,
    on_orchestration_status,
    on_heartbeat_register_jobs,
    on_heartbeat_tick_start,
    on_heartbeat_tick_complete,
    on_heartbeat_job_start,
    on_heartbeat_job_complete,
    on_heartbeat_job_error,
    on_heartbeat_legacy_check,
    emit,
    apply,
    list_busy38_hooks,
    get_busy38_stats,
    get_namespace,
    should_suppress_cheatcode_response,
)

__version__ = "0.1.0"
__license__ = "GPL-3.0-only"

__all__ = [
    # Core
    "Context",
    "register",
    "register_container",
    "execute",
    "execute_text",
    "execute_async",
    "register_namespace",
    "unregister_namespace",
    "execute_cheatcode",
    "get_no_response",
    # Parser
    "Tag",
    "TagType",
    "parse_tag",
    "parse_all",
    "is_valid_tag",
    "remove_tags",
    # Hooks/Filters
    "Hooks",
    "Filters",
    # Busy-compatible hook points/registry
    "busy38_hooks",
    "cheatcode_registry",
    "HookPoints",
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
    "get_namespace",
    "get_namespace_metadata",
    "should_suppress_cheatcode_response",
]
