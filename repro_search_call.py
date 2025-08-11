#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import sys
import dataclasses
from typing import Any

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _to_jsonable(obj: Any) -> Any:
    """Best-effort conversion of arbitrary objects to JSON-serializable structures."""
    # Dataclasses
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Pydantic v1
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict()
        except Exception:
            pass
    # Common containers
    if isinstance(obj, (list, tuple, set)):
        return list(obj)
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return obj
    # Fallback to __dict__ or str
    if hasattr(obj, "__dict__"):
        try:
            return {k: _to_jsonable(v) for k, v in obj.__dict__.items()}
        except Exception:
            return str(obj)
    return str(obj)


async def main() -> None:
    """Connects to an MCP server over Streamable HTTP and calls the 'search' tool.

    Usage:
      python3 repro_search_call.py "query text" [count] [api_key]

    Env:
      MCP_SERVER_URL: defaults to http://127.0.0.1:8001/mcp
      BRAVE_API_KEY: used if provided and api_key arg not passed
    """
    load_dotenv()

    mcp_url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")
    query: str = sys.argv[1] if len(sys.argv) > 1 else "abitanti Calcio BG"
    count: int | None = int(sys.argv[2]) if len(sys.argv) > 2 else None
    api_key_arg: str | None = sys.argv[3] if len(sys.argv) > 3 else None
    api_key_env: str | None = os.environ.get("BRAVE_API_KEY")
    api_key: str | None = api_key_arg or api_key_env

    print(f"Connecting to MCP: {mcp_url}")

    http_cm = streamablehttp_client(mcp_url)
    streams: Any = await http_cm.__aenter__()
    try:
        if isinstance(streams, tuple) and len(streams) >= 2:
            read_stream, write_stream = streams[0], streams[1]
        else:
            read_stream, write_stream = streams

        session_cm = ClientSession(read_stream, write_stream)
        session = await session_cm.__aenter__()
        try:
            await session.initialize()

            # List tools to ensure 'search' exists
            tools_resp = await session.list_tools()
            tool_names = [getattr(t, "name", None) for t in tools_resp.tools]
            print("Available tools:", tool_names)
            if "search" not in tool_names:
                raise RuntimeError("Tool 'search' non trovato nel server MCP")

            # Prepare arguments
            args: dict[str, Any] = {"message": query}
            if count is not None:
                args["count"] = count
            if api_key:
                args["api_key"] = api_key

            print("Calling tool 'search' with:", json.dumps(args, ensure_ascii=False))
            result = await session.call_tool("search", args)
            print(f"Result type: {type(result).__name__}")
            print("Raw tool result (JSON):")
            print(json.dumps(result, ensure_ascii=False, indent=2, default=_to_jsonable))
        finally:
            await session_cm.__aexit__(None, None, None)
    finally:
        await http_cm.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main()) 