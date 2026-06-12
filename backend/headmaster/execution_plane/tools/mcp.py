"""Minimal MCP stdio transport for registering remote tools in ToolGateway."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from headmaster.execution_plane.models.gateway import ToolSpec
from headmaster.execution_plane.tools.tool_gateway import ToolGateway

MCP_PROTOCOL_VERSION = "2025-06-18"


class McpTransportError(Exception):
    """Raised when an MCP stdio server cannot be reached or returns invalid data."""


class McpToolMapping(BaseModel):
    public_name: str
    remote_name: str
    spec: ToolSpec


class McpStdioServerConfig(BaseModel):
    """Configuration for one stdio MCP server."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    timeout_seconds: float = 10.0
    tool_prefix: str | None = None

    @property
    def public_prefix(self) -> str:
        return sanitize_tool_name(self.tool_prefix or f"mcp_{self.name}")


def sanitize_tool_name(value: str) -> str:
    """Normalize names for model-provider tool-name constraints."""

    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    normalized = normalized.strip("_")
    return normalized or "mcp_tool"


class McpStdioSession:
    """One JSON-RPC session against a stdio MCP server.

    MCP stdio messages are newline-delimited JSON-RPC objects. This session
    supports the lifecycle and tools subset needed by Headmaster.
    """

    def __init__(self, config: McpStdioServerConfig) -> None:
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def __aenter__(self) -> McpStdioSession:
        env = os.environ.copy()
        env.update(self._config.env)
        self._process = await asyncio.create_subprocess_exec(
            self._config.command,
            *self._config.args,
            cwd=self._config.cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        process = self._process
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def initialize(self) -> None:
        await self.request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "headmaster", "version": "0.1.0"},
            },
        )
        await self.notify("notifications/initialized")

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise McpTransportError("MCP tools/list response did not include a tools list")
        return [tool for tool in tools if isinstance(tool, dict)]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        result = await self.request(
            "tools/call", {"name": name, "arguments": dict(arguments)}
        )
        return stringify_mcp_tool_result(result)

    async def notify(self, method: str, params: dict[str, object] | None = None) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def request(self, method: str, params: dict[str, object]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        await self._write(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        return await self._read_result(request_id)

    async def _write(self, message: dict[str, object]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise McpTransportError("MCP server stdin is unavailable")
        process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
        await process.stdin.drain()

    async def _read_result(self, request_id: int) -> dict[str, Any]:
        process = self._require_process()
        if process.stdout is None:
            raise McpTransportError("MCP server stdout is unavailable")
        while True:
            try:
                raw = await asyncio.wait_for(
                    process.stdout.readline(), timeout=self._config.timeout_seconds
                )
            except TimeoutError as exc:
                raise McpTransportError(
                    f"MCP server '{self._config.name}' timed out"
                ) from exc
            if not raw:
                stderr = ""
                if process.stderr is not None:
                    stderr_bytes = await process.stderr.read()
                    stderr = stderr_bytes.decode(errors="replace").strip()
                detail = f": {stderr}" if stderr else ""
                raise McpTransportError(
                    f"MCP server '{self._config.name}' closed stdout{detail}"
                )
            try:
                message = json.loads(raw.decode())
            except json.JSONDecodeError:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise McpTransportError(f"MCP error from '{self._config.name}': {message['error']}")
            result = message.get("result", {})
            if not isinstance(result, dict):
                raise McpTransportError("MCP response result was not an object")
            return result

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise McpTransportError("MCP session is not started")
        return self._process


def stringify_mcp_tool_result(result: dict[str, Any]) -> str:
    """Convert an MCP tools/call result to a model-readable string."""

    content = result.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        if parts:
            return "\n".join(parts)
    if "structuredContent" in result:
        return json.dumps(result["structuredContent"], ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)


def mcp_tool_mapping(config: McpStdioServerConfig, tool: dict[str, Any]) -> McpToolMapping:
    remote_name = str(tool.get("name", "")).strip()
    if not remote_name:
        raise McpTransportError("MCP tool is missing a name")
    public_name = sanitize_tool_name(f"{config.public_prefix}_{remote_name}")
    input_schema = tool.get("inputSchema")
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object"}
    return McpToolMapping(
        public_name=public_name,
        remote_name=remote_name,
        spec=ToolSpec(
            name=public_name,
            description=str(tool.get("description", "")),
            input_schema=input_schema,
        ),
    )


@asynccontextmanager
async def mcp_stdio_session(config: McpStdioServerConfig) -> AsyncIterator[McpStdioSession]:
    async with McpStdioSession(config) as session:
        yield session


async def discover_mcp_stdio_tools(
    config: McpStdioServerConfig,
) -> list[McpToolMapping]:
    """Discover tools from one stdio MCP server."""

    async with mcp_stdio_session(config) as session:
        return [mcp_tool_mapping(config, tool) for tool in await session.list_tools()]


async def register_mcp_stdio_server(
    gateway: ToolGateway, config: McpStdioServerConfig
) -> list[McpToolMapping]:
    """Register an MCP stdio server's tools behind the existing ToolGateway."""

    mappings = await discover_mcp_stdio_tools(config)
    for mapping in mappings:

        async def call_remote(
            arguments: dict[str, object],
            *,
            remote_name: str = mapping.remote_name,
            server_config: McpStdioServerConfig = config,
        ) -> str:
            async with mcp_stdio_session(server_config) as session:
                return await session.call_tool(remote_name, arguments)

        gateway.register(
            mapping.public_name,
            call_remote,
            description=mapping.spec.description,
            input_schema=mapping.spec.input_schema,
        )
    return mappings


def load_mcp_stdio_configs(path: Path) -> list[McpStdioServerConfig]:
    """Load a simple JSON config file containing stdio MCP server definitions."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    servers = raw.get("servers", raw if isinstance(raw, list) else [])
    if not isinstance(servers, list):
        raise McpTransportError("MCP config must be a list or an object with 'servers'")
    return [McpStdioServerConfig.model_validate(server) for server in servers]
