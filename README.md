# CaptainHook 🪝

> Cheatcode-style extensibility for Python - like Busy38

## Installation

```bash
pip install captainhook
```

## Quick Start

```python
import captainhook

# Register a cheatcode
@captainhook.register("browser:navigate")
def navigate(url):
    print(f"Navigating to {url}")
    return {"status": "success", "url": url}

# Execute
result = captainhook.execute("[browser:navigate https://example.com /]")
```

## Tag Types

CaptainHook supports both **singles** and **doubles** (like XML):

### Singles (Self-Closing)
```python
[action /]                    # Simple tag
[namespace:action params /]   # Cheatcode with params
[next /]                      # Control flow
```

### Doubles (Container)
```python
[mission]Spawn sub-agent[/mission]
[tool]Execute code[/tool]
[echo]Content to process[/echo]
```

## Examples

### Basic Usage

```python
import captainhook

# Self-closing tag
@captainhook.register("hello")
def hello():
    return "Hello, World!"

result = captainhook.execute("[hello /]")

# Cheatcode with parameters
@captainhook.register("math:add")
def add(a, b):
    return int(a) + int(b)

result = captainhook.execute("[math:add 5 3 /]")

# Container tag
@captainhook.register_container("echo")
def echo(content):
    return f"ECHO: {content}"

result = captainhook.execute("[echo]Hello World[/echo]")
```

### Context-Based Execution

```python
import captainhook

# Create isolated context
ctx = captainhook.Context()

@ctx.register("math:add")
def add(a, b):
    return int(a) + int(b)

@ctx.register_container("code")
def run_code(code):
    return eval(code)

# Execute multiple tags
text = """
[math:add 10 20 /]
[code]2 + 2[/code]
"""
results = ctx.execute_text(text)
```

### Async Support

```python
import captainhook
import asyncio

@captainhook.register("fetch:data")
async def fetch_data(url):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# Async execution
result = await captainhook.execute_async("[fetch:data https://api.example.com /]")
```

### Hooks and Filters

```python
import captainhook

ctx = captainhook.Context()

# Add hooks
ctx.hooks.add_action("before_execute", lambda tag: print(f"Before: {tag}"))
ctx.hooks.add_action("after_execute", lambda tag, result: print(f"After: {result}"))

# Add filters
ctx.filters.add_filter("result", lambda r: r.upper())

@ctx.register("echo")
def echo():
    return "hello"

result = ctx.execute("[echo /]")  # Returns "HELLO"
```

## Busy38-compatible SDK API

CaptainHook includes a compatibility layer so external systems can use Busy-style
hook and namespace-extension APIs without depending on the full Busy runtime.

```python
from captainhook import (
    on_pre_cheatcode_execute,
    on_post_cheatcode_execute,
    HookPoints,
    busy38_hooks,
    register_namespace,
    execute_cheatcode,
)


@on_pre_cheatcode_execute
def pre_hook(namespace, action, attrs, context=None):
    print("pre", namespace, action, attrs)


class DemoHandler:
    def execute(self, action, **kwargs):
        return {"action": action, "kwargs": kwargs}


register_namespace("demo", DemoHandler())
result = execute_cheatcode("demo", "status", {"mode": "active"})
print(result)

print(HookPoints.PRE_CHEATCODE_EXECUTE)
print("registry", busy38_hooks.list_hooks())
```

## Flask Integration

```python
from flask import Flask, request, jsonify
import captainhook

app = Flask(__name__)

@captainhook.register("browser:navigate")
def navigate(url):
    return {"action": "navigate", "url": url}

@app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json()
    tag = data.get("tag")
    result = captainhook.execute(tag)
    return jsonify({"result": result})
```

## Testing

```bash
cd tests
pytest -v
```

## AI-Generated / Automated Contributions

Automated and AI-assisted contributions are welcome, provided they meet the same production standards as human-written code.

For production code, placeholders are not acceptable.

- Unit tests may use mocks and stubs.
- Runtime code must be functional and complete before merge.
- New functionality must include unit tests (or updates to existing tests) that cover the new behavior.
- Failure states are telemetry and should remain visible; do not introduce graceful-fallback behavior that hides runtime failures.
- All relevant tests must pass before merge.

Before submitting generated changes, verify:

- No production file contains temporary placeholders (`TODO`, `FIXME`, `NotImplementedError`, `return None` placeholders).
- Mock/stub logic is limited to tests and test fixtures.
- Edge cases and failure paths are explicit, not hidden behind placeholders.

## License

GPL-3.0-only
