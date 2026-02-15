# CaptainHook 🪝

> Cheatcode-style hooks, filters, and tags for Python - with an OpenAI-style API

## Installation

```bash
pip install captainhook
```

## Quick Start

```python
import captainhook

# Execute a cheatcode
result = captainhook.execute("[browser:navigate https://example.com]")
print(result)
```

## Register Custom Handlers

```python
import captainhook

@captainhook.register("browser:navigate")
async def navigate(url: str):
    print(f"Navigating to {url}")
    return {"status": "success", "url": url}

# Execute
result = captainhook.execute("[browser:navigate https://example.com]")
```

## Context-Based Execution

```python
import captainhook

# Create isolated context
ctx = captainhook.Context()

# Register handlers in this context only
@ctx.register("math:add")
def add(a: int, b: int):
    return int(a) + int(b)

# Execute within context
result = ctx.execute("[math:add 5 3]")
print(result)  # 8
```

## Async Support

```python
import captainhook
import asyncio

@captainhook.register("fetch:data")
async def fetch_data(url: str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# Async execution
result = await captainhook.execute_async("[fetch:data https://api.example.com/data]")
```

## Hooks and Filters

```python
import captainhook

# Add action hook
captainhook.hooks.add_action("before_execute", lambda tag: print(f"Executing: {tag}"))

# Add filter
captainhook.filters.add_filter("result", lambda r: r.upper())

# Execute - hooks and filters run automatically
result = captainhook.execute("[echo hello]")
```

## Integration Examples

### Flask Integration

```python
from flask import Flask
import captainhook

app = Flask(__name__)

@app.route("/execute", methods=["POST"])
def execute():
    tag = request.json.get("tag")
    result = captainhook.execute(tag)
    return jsonify(result)
```

### FastAPI Integration

```python
from fastapi import FastAPI
import captainhook

app = FastAPI()

@app.post("/execute")
async def execute(tag: str):
    result = await captainhook.execute_async(tag)
    return {"result": result}
```

### CLI Tool

```python
import captainhook
import sys

# cli.py
if __name__ == "__main__":
    tag = sys.argv[1]
    result = captainhook.execute(tag)
    print(result)
```

```bash
$ python cli.py "[browser:screenshot https://example.com]"
```

## Advanced Usage

### Custom Parsers

```python
import captainhook

@captainhook.parser
def parse_custom_syntax(tag: str):
    # Custom parsing logic
    if tag.startswith("!"):
        return captainhook.Tag("custom", tag[1:])
    return None
```

### Middleware

```python
import captainhook

@captainhook.middleware
async def log_execution(tag, next):
    print(f"Before: {tag}")
    result = await next(tag)
    print(f"After: {result}")
    return result
```

## License

GPL-3.0-only