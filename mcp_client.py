#!/usr/bin/env python3
# mcp_client_server.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client  # 👈 HTTP client

# Load variables from .env if present
load_dotenv()

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")

app = FastAPI(title="MCP Client Server (HTTP)")

class ToolCall(BaseModel):
    tool: str
    arguments: dict | None = None

# Connection state (lazy)
app.state._http_cm = None
app.state._session_cm = None
app.state.session = None

async def ensure_session():
    if app.state.session is not None:
        return
    try:
        app.state._http_cm = streamablehttp_client(MCP_SERVER_URL)
        streams = await app.state._http_cm.__aenter__()
        # streamablehttp_client may return a tuple with more than two items in newer versions.
        if isinstance(streams, tuple) and len(streams) >= 2:
            read_stream, write_stream = streams[0], streams[1]
        else:
            read_stream, write_stream = streams
        app.state._session_cm = ClientSession(read_stream, write_stream)
        app.state.session = await app.state._session_cm.__aenter__()
        await app.state.session.initialize()
    except Exception as e:
        # partial cleanup in case of error
        if app.state._session_cm:
            try:
                await app.state._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
            app.state._session_cm = None
        if app.state._http_cm:
            try:
                await app.state._http_cm.__aexit__(None, None, None)
            except Exception:
                pass
            app.state._http_cm = None
        app.state.session = None
        raise HTTPException(502, f"MCP connection failed to {MCP_SERVER_URL}: {e}")

@app.on_event("shutdown")
async def shutdown():
    if getattr(app.state, "_session_cm", None):
        try:
            await app.state._session_cm.__aexit__(None, None, None)
        except Exception:
            pass
        app.state._session_cm = None
        app.state.session = None
    if getattr(app.state, "_http_cm", None):
        try:
            await app.state._http_cm.__aexit__(None, None, None)
        except Exception:
            pass
        app.state._http_cm = None

@app.get("/health")
async def health():
    return {"ok": True, "connected": app.state.session is not None}

@app.get("/tools")
async def tools():
    """
    Ritorna l’elenco tool. Include anche descrizione e schema se disponibili.
    Output: {"ok": true, "tools": [{"name":"echo","description":"...", "input_schema": {...}}, ...]}
    """
    await ensure_session()
    try:
        res = await app.state.session.list_tools()
        items = []
        for t in res.tools:
            item = {"name": getattr(t, "name", None)}
            desc = getattr(t, "description", None) or getattr(t, "descriptions", None)
            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
            if desc:
                item["description"] = desc
            if schema:
                item["input_schema"] = schema
            items.append(item)
        return {"ok": True, "tools": items}
    except Exception as e:
        raise HTTPException(500, f"Error in list_tools: {e}")


# --- New endpoints for MCP Resources ---
@app.get("/resources")
async def resources():
    """Lists available resources from the MCP server."""
    await ensure_session()
    try:
        items = []
        # Material resources
        res = await app.state.session.list_resources()
        resources_list = getattr(res, "resources", []) or []
        for r in resources_list:
            items.append({
                "uri": getattr(r, "uri", None) or getattr(r, "uri_template", None),
                "name": getattr(r, "name", None),
                "description": getattr(r, "description", None),
                "type": "resource",
            })
        # Resource templates (e.g. restaurant://menu/{date})
        tmpl = await app.state.session.list_resource_templates()
        templates_list = getattr(tmpl, "templates", None)
        if templates_list is None:
            templates_list = getattr(tmpl, "resource_templates", []) or []
        for t in templates_list:
            items.append({
                "uri": getattr(t, "uri", None) or getattr(t, "uri_template", None),
                "name": getattr(t, "name", None),
                "description": getattr(t, "description", None),
                "type": "template",
            })
        # De-dup
        seen = set()
        deduped = []
        for it in items:
            key = (it.get("uri"), it.get("type"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(it)
        return {"ok": True, "resources": deduped}
    except Exception as e:
        raise HTTPException(500, f"Error in list_resources: {e}")


class ReadResourceBody(BaseModel):
    uri: str

@app.post("/read_resource")
async def read_resource(body: ReadResourceBody):
    """Reads an MCP resource given its complete URI."""
    await ensure_session()
    try:
        result = await app.state.session.read_resource(body.uri)
        # Some clients return an object with fields like uri, mimeType, text, blob
        payload = {
            "uri": getattr(result, "uri", body.uri),
            "mime_type": getattr(result, "mime_type", None) or getattr(result, "mimeType", None),
            "text": getattr(result, "text", None),
        }
        return {"ok": True, "result": payload}
    except Exception as e:
        raise HTTPException(500, f"Error in read_resource: {e}")


@app.post("/call_tool")
async def call_tool(body: ToolCall):
    await ensure_session()
    try:
        result = await app.state.session.call_tool(body.tool, body.arguments or {})
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(500, f"Error in call_tool: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
