"""
Basic CaptainHook Example

Demonstrates singles, doubles, and cheatcodes.
"""

import sys
sys.path.insert(0, '..')

import captainhook

# Register a simple self-closing tag
@captainhook.register("hello")
def hello():
    return "Hello, World!"

# Register a cheatcode
@captainhook.register("math:add")
def add(a, b):
    return int(a) + int(b)

# Register a container tag
@captainhook.register_container("echo")
def echo(content):
    return f"ECHO: {content}"

# Execute examples
def main():
    print("=== CaptainHook Basic Example ===\n")
    
    # Single (self-closing)
    print("1. Self-closing tag [hello /]:")
    result = captainhook.execute("[hello /]")
    print(f"   Result: {result}\n")
    
    # Cheatcode
    print("2. Cheatcode [math:add 5 3 /]:")
    result = captainhook.execute("[math:add 5 3 /]")
    print(f"   Result: {result}\n")
    
    # Container
    print("3. Container [echo]Hello World[/echo]:")
    result = captainhook.execute("[echo]Hello World[/echo]")
    print(f"   Result: {result}\n")
    
    # Execute multiple from text
    print("4. Multiple tags in text:")
    text = """
    [hello /]
    [math:add 10 20 /]
    [echo]Nested content here[/echo]
    """
    results = captainhook.execute_text(text)
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result}")

if __name__ == "__main__":
    main()