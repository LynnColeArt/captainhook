"""
Flask Integration Example

Shows how to use CaptainHook in a Flask web app.
"""

from flask import Flask, request, jsonify
import sys
sys.path.insert(0, '..')

import captainhook

app = Flask(__name__)

# Register some handlers
@captainhook.register("browser:navigate")
def navigate(url):
    return {"action": "navigate", "url": url}

@captainhook.register("data:fetch")
def fetch_data(endpoint, method="GET"):
    return {"action": "fetch", "endpoint": endpoint, "method": method}

@app.route("/execute", methods=["POST"])
def execute():
    """Execute a cheatcode via HTTP."""
    data = request.get_json()
    tag = data.get("tag")
    
    if not tag:
        return jsonify({"error": "No tag provided"}), 400
    
    try:
        result = captainhook.execute(tag)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/execute-batch", methods=["POST"])
def execute_batch():
    """Execute multiple cheatcodes from text."""
    data = request.get_json()
    text = data.get("text")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    results = captainhook.execute_text(text)
    return jsonify({"results": results})

if __name__ == "__main__":
    print("Starting Flask app on http://localhost:5000")
    print("Try: curl -X POST http://localhost:5000/execute -H 'Content-Type: application/json' -d '{\"tag\": \"[browser:navigate https://example.com /]\"}'")
    app.run(debug=True)