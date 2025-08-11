#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import json
import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3:latest")

# Endpoint del client MCP persistente
MCP_CLIENT_URL = os.environ.get("MCP_CLIENT_URL", "http://127.0.0.1:8000")

# TTL per il refresh automatico dei tool (in secondi)
MCP_TOOL_TTL = int(os.environ.get("MCP_TOOL_TTL", "60"))

TOOL_BLOCK_RE = re.compile(r"```mcp\s*(\{.*?\})\s*```", re.DOTALL)

# Cache strumenti
_cached_tools = []
_last_refresh = 0.0

# Cache risorse
_cached_resources = []
_last_res_refresh = 0.0

def discover_tools(force: bool = False):
    """Scarica la lista tool dal client MCP HTTP con caching/TTL."""
    global _cached_tools, _last_refresh
    now = time.time()
    if not force and _cached_tools and (now - _last_refresh) < MCP_TOOL_TTL:
        return _cached_tools
    try:
        r = requests.get(f"{MCP_CLIENT_URL}/tools", timeout=10)
        r.raise_for_status()
        data = r.json()
        tools = data.get("tools", [])
        # Normalizza a lista di nomi (accetta sia [{"name":...},...] che ["echo",...])
        if tools and isinstance(tools[0], dict):
            names = [t.get("name") for t in tools if t.get("name")]
        else:
            names = [str(t) for t in tools]
        _cached_tools = sorted(set(names))
        _last_refresh = now
    except Exception:
        # mantieni la cache precedente in caso di errore
        pass
    return _cached_tools

def discover_resources(force: bool = False):
    """Scarica la lista risorse dal client MCP HTTP con caching/TTL."""
    global _cached_resources, _last_res_refresh
    now = time.time()
    if not force and _cached_resources and (now - _last_res_refresh) < MCP_TOOL_TTL:
        return _cached_resources
    try:
        r = requests.get(f"{MCP_CLIENT_URL}/resources", timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("resources", [])
        # Teniamo solo le URI per semplicità
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
        "Sei un assistente utile e conciso. Rispondi in italiano salvo diversa richiesta.\n"
    )
    if tools:
        # Elenca gli strumenti rilevati
        elenco = ", ".join(tools)
        resources = discover_resources(force=False)
        elenco_res = ", ".join(resources) if resources else "(nessuna risorsa)"
        howto = (
            "Strumenti MCP disponibili: " + elenco + ".\n"
            "Risorse MCP disponibili: " + elenco_res + ".\n"
            "Se devi LEGGERE una risorsa, emetti SOLO un blocco come questo e nient'altro testo:\n"
            "```mcp\n"
            '{"resource":"<URI_COMPLETA>"}\n'
            "```\n"
            "Se devi ESEGUIRE un tool, usa il formato tool come indicato sotto e attendi il risultato."
        )
        return base + howto
    else:
        return base + (
            "Al momento non ci sono strumenti MCP disponibili. Non generare blocchi ```mcp```."
        )

def stream_chat(messages, temperature=0.7):
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {"model": MODEL, "messages": messages, "stream": True, "options": {"temperature": temperature}}
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
    m = TOOL_BLOCK_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        tool = data.get("tool")
        arguments = data.get("arguments", {})
        if isinstance(tool, str) and isinstance(arguments, dict):
            return {"tool": tool, "arguments": arguments}
    except Exception:
        return None
    return None

def parse_resource_read(text):
    m = TOOL_BLOCK_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        uri = data.get("resource")
        if isinstance(uri, str) and uri.startswith("restaurant://"):
            return {"uri": uri}
    except Exception:
        return None
    return None

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
    print(f"🤖 Chat CLI con Ollama + client MCP HTTP – modello: {MODEL}")
    print(f"(Client MCP: {MCP_CLIENT_URL})")
    print("Digita 'exit' per uscire.\n")

    # 1) Discovery iniziale
    tool_names = discover_tools(force=True)
    _ = discover_resources(force=True)
    system_prompt = build_system_prompt(tool_names)
    history = [{"role": "system", "content": system_prompt}]

    try:
        while True:
            # 2) Refresh periodico (TTL) o on-the-fly
            new_tools = discover_tools(force=False)
            if set(new_tools) != set(tool_names):
                tool_names = new_tools
                history.append({
                    "role": "system",
                    "content": "Aggiornamento strumenti MCP disponibili: " +
                               (", ".join(tool_names) if tool_names else "(nessuno)") +
                               ". Usa solo questi nomi nei blocchi MCP."
                })

            try:
                user_input = input("Tu ▸ ").strip()
            except EOFError:
                print("\nCiao!"); break

            if user_input.lower() in {"exit", "quit", ":q"}:
                print("Ciao!"); break
            if user_input == ":refresh-tools":
                tool_names = discover_tools(force=True)
                history.append({
                    "role": "system",
                    "content": "Aggiornamento manuale strumenti: " +
                               (", ".join(tool_names) if tool_names else "(nessuno)")
                })
                continue
            if not user_input:
                continue

            history.append({"role": "user", "content": user_input})

            # 3) Prima risposta del modello
            print("AI ▸ ", end="", flush=True)
            assistant_text = stream_chat(history)
            history.append({"role": "assistant", "content": assistant_text})

            # 4) UNA sola tool-call per turno, poi finalizza
            res_spec = parse_resource_read(assistant_text)
            if res_spec:
                result = read_client_resource(res_spec["uri"])
                if not result.get("ok"):
                    msg = f"Errore leggendo risorsa MCP '{res_spec['uri']}': {result.get('error')}"
                else:
                    payload = result.get("result", {})
                    text = payload.get("text")
                    msg = f"Contenuto risorsa {res_spec['uri']}:\n{text}"

                history.append({
                    "role": "user",
                    "content": msg + "\n\nOra fornisci la risposta finale per l’utente, in italiano, senza blocchi ```mcp```."
                })
                print("AI ▸ ", end="", flush=True)
                assistant_text = stream_chat(history)
                assistant_text_clean = re.sub(TOOL_BLOCK_RE, "", assistant_text).strip()
                if assistant_text_clean != assistant_text:
                    print("\rAI ▸ " + assistant_text_clean)
                history.append({"role": "assistant", "content": assistant_text})
                continue

            spec = parse_tool_call(assistant_text)
            if spec:
                if spec["tool"] not in tool_names:
                    tool_msg = (f"Errore: tool '{spec['tool']}' non disponibile. "
                                f"Tool validi: {', '.join(tool_names) if tool_names else '(nessuno)'}")
                else:
                    result = call_client_http(spec["tool"], spec["arguments"])
                    if not result.get("ok"):
                        tool_msg = f"Errore eseguendo tool MCP '{spec['tool']}': {result.get('error')}"
                    else:
                        tool_msg = (f"Risultato tool MCP '{spec['tool']}': "
                                    f"{json.dumps(result['result'], ensure_ascii=False)}")

                # Prompt di finalizzazione: niente ulteriori blocchi MCP
                history.append({"role": "user",
                                "content": tool_msg + "\n\nOra fornisci la risposta finale per l’utente, "
                                                       "in italiano, senza blocchi ```mcp```."})
                print("AI ▸ ", end="", flush=True)
                assistant_text = stream_chat(history)
                # Filtra eventuali blocchi MCP residui in stampa (non nella memoria)
                assistant_text_clean = re.sub(TOOL_BLOCK_RE, "", assistant_text).strip()
                if assistant_text_clean != assistant_text:
                    print("\rAI ▸ " + assistant_text_clean)  # re-stampa pulita (opzionale)
                history.append({"role": "assistant", "content": assistant_text})

    except KeyboardInterrupt:
        print("\nInterrotto. Ciao!")
        sys.exit(0)

if __name__ == "__main__":
    main()
