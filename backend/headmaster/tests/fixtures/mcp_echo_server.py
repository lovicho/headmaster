"""Tiny newline-delimited JSON-RPC MCP server for transport tests."""

import json
import sys


def write(message: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


TOOLS = [
    {
        "name": "echo",
        "description": "Echo a message",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    }
]


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        continue
    if method == "initialize":
        write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "echo", "version": "0.1.0"},
                },
            }
        )
    elif method == "tools/list":
        write({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params = request.get("params", {})
        arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
        text = str(arguments.get("message", "")) if isinstance(arguments, dict) else ""
        write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"echo: {text}"}]},
            }
        )
    else:
        write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"unknown method {method}"},
            }
        )
