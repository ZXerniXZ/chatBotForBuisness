#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Performance Tips:
# 1. Use a smaller model: export OLLAMA_MODEL=qwen2.5:3b
# 2. Use fast mode: ./run_fast_bot.sh
# 3. Adjust settings: export OLLAMA_NUM_CTX=1024
# 4. For maximum speed: export OLLAMA_MODEL=llama3.2:1b

import os
import sys
import re
import time
import json
import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")

# Performance optimization settings
NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "2048"))
NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "512"))
TOP_K = int(os.environ.get("OLLAMA_TOP_K", "10"))
TOP_P = float(os.environ.get("OLLAMA_TOP_P", "0.9"))
REPEAT_PENALTY = float(os.environ.get("OLLAMA_REPEAT_PENALTY", "1.1"))
NUM_THREAD = int(os.environ.get("OLLAMA_NUM_THREAD", "4"))
NUM_GPU = int(os.environ.get("OLLAMA_NUM_GPU", "1"))
TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.7"))

# Persistent MCP client endpoint
MCP_CLIENT_URL = os.environ.get("MCP_CLIENT_URL", "http://127.0.0.1:8000")

# TTL for automatic tool refresh (in seconds)
MCP_TOOL_TTL = int(os.environ.get("MCP_TOOL_TTL", "60"))

TOOL_BLOCK_RE = re.compile(r"```mcp\s*(\{.*?\})\s*```", re.DOTALL)

# Tools cache
_cached_tools = []
_last_refresh = 0.0

# Resources cache
_cached_resources = []
_last_res_refresh = 0.0

def discover_tools(force: bool = False):
    """Downloads the tool list from the MCP HTTP client with caching/TTL."""
    global _cached_tools, _last_refresh
    now = time.time()
    if not force and _cached_tools and (now - _last_refresh) < MCP_TOOL_TTL:
        return _cached_tools
    try:
        r = requests.get(f"{MCP_CLIENT_URL}/tools", timeout=10)
        r.raise_for_status()
        data = r.json()
        tools = data.get("tools", [])
        # Normalize to name list (accepts both [{"name":...},...] and ["echo",...])
        if tools and isinstance(tools[0], dict):
            names = [t.get("name") for t in tools if t.get("name")]
        else:
            names = [str(t) for t in tools]
        _cached_tools = sorted(set(names))
        _last_refresh = now
    except Exception:
        # keep previous cache in case of error
        pass
    return _cached_tools

def discover_resources(force: bool = False):
    """Downloads the resource list from the MCP HTTP client with caching/TTL."""
    global _cached_resources, _last_res_refresh
    now = time.time()
    if not force and _cached_resources and (now - _last_res_refresh) < MCP_TOOL_TTL:
        return _cached_resources
    try:
        r = requests.get(f"{MCP_CLIENT_URL}/resources", timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("resources", [])
        # Keep only URIs for simplicity
        uris = []
        for it in items:
            uri = it.get("uri")
            if uri:
                uris.append(uri)
        _cached_resources = sorted(set(uris))
        _last_res_refresh = now
    except Exception:
        pass
    return _cached_resources

def build_system_prompt(tools: list[str]) -> str:
    base = (
        "You are a helpful and concise assistant. Respond in English unless specifically requested otherwise. do not allucinate, if you don't know the answer, say so or use the tools to find the answer. do not pass the turn to the user if you didn't end your response. \n"
    )

    if tools:
        elenco = ", ".join(tools)
        resources = discover_resources(force=False)
        elenco_res = ", ".join(resources) if resources else "(no resources)"

        howto = (
            "if you decide to use tools, do as follows:\n"
            f"You are connected to a set of external tools via the MCP protocol.\n"
            f"Available MCP tools: {elenco}.\n"
            f"Available MCP resources: {elenco_res}.\n\n"
            "You have complete autonomy to decide whether to:\n"
            "- Call one or more of the available tools to gather or process information.\n"
            "- Read a resource.\n"
            "- Or answer directly without using any tools.\n\n"
            "When calling tools or reading resources:\n"
            "1. Respond with one or more valid MCP blocks in the exact JSON format shown below.\n"
            "2. You can include multiple MCP blocks in sequence if needed.\n"
            "3. Wrap each block in triple backticks like this:\n\n"
            "Tool call:\n"
            "```mcp\n"
            '{"tool":"<TOOL_NAME>","arguments":{"<PARAMETER>":"<VALUE>"}}\n'
            "```\n\n"
            "Resource read:\n"
            "```mcp\n"
            '{"resource":"<COMPLETE_URI>"}\n'
            "```\n\n"
            "Rules:\n"
            "- Pick the most relevant tools for the user's request. You can use multiple tools if needed.\n"
            "- If you use tools, do not explain the calls — just output the MCP blocks.\n"
            "- You can chain multiple tool calls in sequence to accomplish complex tasks.\n"
            "- If no tools are needed, respond normally in English.\n\n"
            "Example multiple tool calls:\n"
            "```mcp\n"
            '{"tool":"rag_search","arguments":{"query":"restaurant menu"}}\n'
            "```\n"
            "```mcp\n"
            '{"tool":"file_search","arguments":{"query":"menu.txt"}}\n'
            "```\n\n"
            "Example resource read:\n"
            "```mcp\n"
            '{"resource":"restaurant://menu/today"}\n'
            "```\n"
        )

        return base + howto

    else:
        return base + (
            "Currently no MCP tools are available. Do not generate ```mcp``` blocks."
        )


def stream_chat(messages, temperature=TEMPERATURE):
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": MODEL, 
        "messages": messages, 
        "stream": True, 
        "options": {
            "temperature": temperature,
            "num_ctx": NUM_CTX,  # Reduce context window for faster processing
            "num_predict": NUM_PREDICT,  # Limit response length
            "top_k": TOP_K,  # Reduce top-k for faster token selection
            "top_p": TOP_P,  # Slightly reduce top-p
            "repeat_penalty": REPEAT_PENALTY,  # Reduce repetition penalty
            "num_thread": NUM_THREAD,  # Use more CPU threads
            "num_gpu": NUM_GPU,  # Use GPU if available
        }
    }
    with requests.post(url, json=payload, stream=True) as r:
        r.raise_for_status()
        full_text = []
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = chunk.get("message", {})
            delta = msg.get("content", "")
            if delta:
                full_text.append(delta)
                print(delta, end="", flush=True)
            if chunk.get("done"):
                break
        print()
        return "".join(full_text)

def parse_tool_call(text):
    """Parse all tool calls from the text and return a list of tool specifications."""
    matches = TOOL_BLOCK_RE.findall(text)
    tool_calls = []
    for match in matches:
        try:
            data = json.loads(match)
            tool = data.get("tool")
            arguments = data.get("arguments", {})
            if isinstance(tool, str) and isinstance(arguments, dict):
                tool_calls.append({"tool": tool, "arguments": arguments})
        except Exception:
            continue
    return tool_calls

def parse_resource_read(text):
    """Parse all resource reads from the text and return a list of resource URIs."""
    matches = TOOL_BLOCK_RE.findall(text)
    resource_reads = []
    for match in matches:
        try:
            data = json.loads(match)
            uri = data.get("resource")
            if isinstance(uri, str) and uri.startswith("restaurant://"):
                resource_reads.append({"uri": uri})
        except Exception:
            continue
    return resource_reads

def call_client_http(tool: str, arguments: dict) -> dict:
    try:
        resp = requests.post(
            f"{MCP_CLIENT_URL}/call_tool",
            json={"tool": tool, "arguments": arguments},
            timeout=30,
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def read_client_resource(uri: str) -> dict:
    try:
        resp = requests.post(
            f"{MCP_CLIENT_URL}/read_resource",
            json={"uri": uri},
            timeout=30,
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def main():
    print(f"🤖 Chat CLI with Ollama + MCP HTTP client – model: {MODEL}")
    print(f"(MCP Client: {MCP_CLIENT_URL})")
    print("Type 'exit' to quit.\n")

    # 1) Initial discovery
    tool_names = discover_tools(force=True)
    _ = discover_resources(force=True)
    system_prompt = build_system_prompt(tool_names)
    history = [{"role": "system", "content": system_prompt}]

    try:
        while True:
            # 2) Periodic refresh (TTL) or on-the-fly
            new_tools = discover_tools(force=False)
            if set(new_tools) != set(tool_names):
                tool_names = new_tools
                history.append({
                    "role": "system",
                    "content": "Updated available MCP tools: " +
                               (", ".join(tool_names) if tool_names else "(none)") +
                               ". Use only these names in MCP blocks."
                })

            try:
                user_input = input("You ▸ ").strip()
            except EOFError:
                print("\nGoodbye!"); break

            if user_input.lower() in {"exit", "quit", ":q"}:
                print("Goodbye!"); break
            if user_input == ":refresh-tools":
                tool_names = discover_tools(force=True)
                history.append({
                    "role": "system",
                    "content": "Manual tool update: " +
                               (", ".join(tool_names) if tool_names else "(none)")
                })
                continue
            if not user_input:
                continue

            history.append({"role": "user", "content": user_input})

            # 3) First model response
            print("AI ▸ ", end="", flush=True)
            assistant_text = stream_chat(history)
            history.append({"role": "assistant", "content": assistant_text})

            # 4) Handle multiple tool-calls and resource reads per turn, then finalize
            resource_specs = parse_resource_read(assistant_text)
            tool_specs = parse_tool_call(assistant_text)
            
            # Process all resource reads first
            resource_results = []
            for res_spec in resource_specs:
                result = read_client_resource(res_spec["uri"])
                if not result.get("ok"):
                    msg = f"Error reading MCP resource '{res_spec['uri']}': {result.get('error')}"
                else:
                    payload = result.get("result", {})
                    text = payload.get("text")
                    msg = f"Resource content {res_spec['uri']}:\n{text}"
                resource_results.append(msg)
            
            # Process all tool calls
            tool_results = []
            for spec in tool_specs:
                if spec["tool"] not in tool_names:
                    tool_msg = (f"Error: tool '{spec['tool']}' not available. "
                                f"Valid tools: {', '.join(tool_names) if tool_names else '(none)'}")
                else:
                    result = call_client_http(spec["tool"], spec["arguments"])
                    if not result.get("ok"):
                        tool_msg = f"Error executing MCP tool '{spec['tool']}': {result.get('error')}"
                    else:
                        tool_msg = (f"MCP tool result '{spec['tool']}': "
                                    f"{json.dumps(result['result'], ensure_ascii=False)}")
                tool_results.append(tool_msg)
            
            # If any tools or resources were used, provide results and get final response
            if resource_results or tool_results:
                all_results = resource_results + tool_results
                results_text = "\n\n".join(all_results)
                
                # Finalization prompt: no further MCP blocks
                history.append({"role": "user",
                                "content": results_text + "\n\nNow provide the final response for the user, in English, without ```mcp``` blocks."})
                print("AI ▸ ", end="", flush=True)
                assistant_text = stream_chat(history)
                # Filter any remaining MCP blocks in output (not in memory)
                assistant_text_clean = re.sub(TOOL_BLOCK_RE, "", assistant_text).strip()
                if assistant_text_clean != assistant_text:
                    print("\rAI ▸ " + assistant_text_clean)  # re-print clean (optional)
                history.append({"role": "assistant", "content": assistant_text})

    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
