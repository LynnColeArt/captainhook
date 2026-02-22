"""Busy-style inference loop demo using CaptainHook.

This script connects to an OpenAI-compatible inference endpoint and runs a
turn-based loop. The model is prompted to emit namespaced tool tags and
`[next /]` as the control-flow tag to continue.

How to read this file:
1. Register tool handlers with `@captainhook.register(...)`.
2. Send a user prompt to a chat-completion endpoint.
3. Parse returned text for CaptainHook tags.
4. Parse tags and execute only tool tags directly (skip `[next /]` as control).
5. Treat selected tool calls as fire-and-forget if your registry marks them with
   `noResponse`.
6. Continue only when `[next /]` appears in that assistant turn.

Example:
  python examples/inference_loop_demo.py \
    --url http://localhost:8000/v1/chat/completions \
    --model gpt-4o-mini \
    --prompt "Run a short 2-step loop using the tools."
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

import captainhook


TOOLS_STATE = {"step": 0}


@captainhook.register("tool:add")
def tool_add(a: str, b: str) -> Dict[str, Any]:
    """Simple math tool that returns the sum."""
    lhs = int(a)
    rhs = int(b)
    result = lhs + rhs
    TOOLS_STATE["step"] += 1
    return {"tool": "add", "a": lhs, "b": rhs, "result": result, "step": TOOLS_STATE["step"]}


@captainhook.register("tool:note")
def tool_note(message: str = "") -> Dict[str, Any]:
    """Simple logging tool."""
    TOOLS_STATE["step"] += 1
    return {"tool": "note", "message": message, "step": TOOLS_STATE["step"]}


def call_inference(
    url: str,
    model: str,
    api_key: str | None,
    messages: List[Dict[str, str]],
    timeout: int = 60,
) -> str:
    """Call an OpenAI-style chat endpoint and return the assistant text."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach inference endpoint: {exc}") from exc

    choices = response_data.get("choices", [])
    if not choices:
        raise RuntimeError("Inference response did not include any choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        raise RuntimeError("Inference response returned an empty content block")

    return content


def build_system_prompt() -> str:
    """Prompt for the model with the exact tag contract."""
    return (
        "You are a tiny planner in a demo loop.\n"
        "When you want the system to do work, emit tags only in this form:\n"
        "  [tool:add <a> <b> /]\n"
        "  [tool:note message=\"text\" /]\n"
        "  [next /]\n"
        "Do not emit [next /] if the loop should end.\n"
    )


def run_demo_loop(args: argparse.Namespace) -> None:
    # State that goes to the model each turn:
    # - system prompt (tool contract)
    # - original user request
    # - assistant text and tool outputs from previous turns
    continue_tag = "[next /]"
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": args.prompt},
    ]

    for turn in range(1, args.max_turns + 1):
        print(f"\n=== Turn {turn} ===")
        model_text = call_inference(
            url=args.url,
            model=args.model,
            api_key=args.api_key,
            messages=messages,
        )
        print(f"LLM output:\n{model_text}\n")

        # Parse tags from the assistant turn. If no tags are present, we can't
        # drive any more tool calls or loop control, so we exit.
        tags = captainhook.parse_all(model_text)
        if not tags:
            print("No tags found in response. Ending loop.")
            break

        # Execute tool tags only. `next` is treated as control, not as an executable tag.
        results_payload = []
        continue_requested = False
        for tag in tags:
            if tag.raw == continue_tag:
                continue_requested = True
                continue

            result = captainhook.execute(tag.raw)
            if tag.namespace and captainhook.get_no_response(tag.namespace, tag.action):
                # Fire-and-forget tool outputs are not appended back into model context.
                continue

            results_payload.append({tag.raw: result})

        print(f"Tool results: {json.dumps(results_payload, indent=2)}")

        # Push both the assistant output and tool results back for the next turn.
        messages.append({"role": "assistant", "content": model_text})
        messages.append(
            {
                "role": "user",
                "content": f"Tool outputs: {json.dumps(results_payload)}",
            }
        )

        if not continue_requested:
            print("No [next /] tag found. Ending loop.")
            break
    else:
        print("Reached max turns. Ending loop.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CaptainHook inference loop demo using [next /] tags."
    )
    parser.add_argument(
        "--url",
        default=os.getenv("INFERENCE_URL", ""),
        help="OpenAI-compatible chat completions URL.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("INFERENCE_MODEL", "gpt-4o-mini"),
        help="Model name to send to the endpoint.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("INFERENCE_API_KEY"),
        help="Bearer token (if endpoint requires auth).",
    )
    parser.add_argument(
        "--prompt",
        default="Run a 2-step loop. Add 2 and 3, then write a note about the sum, and then stop.",
        help="Starting user prompt sent to the model.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=6,
        help="Safety limit for [next /] loops.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.url:
        raise SystemExit("Missing --url (or set INFERENCE_URL in env).")
    run_demo_loop(args)


if __name__ == "__main__":
    main()
