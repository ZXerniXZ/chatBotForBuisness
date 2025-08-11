#!/usr/bin/env python
"""
Chatbot CLI con Gemma 3 4B (Ollama) + memoria lunga.
Salva lo storico su disco e usa riassunti per restare nei limiti di contesto.
"""

import os, json, requests, textwrap, uuid, time
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from dateutil import tz, parser as dtparser

# ---------- Config ----------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = "gemma3:4b"
WINDOW_TOKENS = 4096        # quando superato -> facciamo un riassunto
MEMORY_FILE  = Path("long_memory.jsonl")
SYSTEM_PROMPT = (
    "Sei un assistente virtuale per il customer service. "
    "Rispondi in italiano, con tono amichevole e conciso. "
    "Ricorda i dettagli importanti dell'utente durante la conversazione."
)
# ----------------------------

console = Console()

def call_ollama(prompt: str, temperature: float = 0.7) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["response"].strip()

def num_tokens(text: str) -> int:
    # stima rozza: 1 token ~ 0.75 parole (dipende dal tokenizer)
    return int(len(text.split()) / 0.75)

def summarize(transcript: str) -> str:
    summary_prompt = (
        "Riassumi la seguente conversazione in massimo 8 bullet puntati, "
        "concentrandoti su fatti, preferenze e impegni citati. "
        "Conversazione:\n" + transcript + "\n\nRiassunto:"
    )
    return call_ollama(summary_prompt, temperature=0.3)

def save_long_term(memory: str):
    MEMORY_FILE.write_text("", encoding="utf-8") if not MEMORY_FILE.exists() else None
    MEMORY_FILE.open("a", encoding="utf-8").write(
        json.dumps({"ts": time.time(), "memory": memory}, ensure_ascii=False) + "\n"
    )

def load_long_term() -> str:
    if not MEMORY_FILE.exists():
        return ""
    # prendi gli ultimi 3 riassunti
    lines = MEMORY_FILE.read_text(encoding="utf-8").strip().splitlines()[-3:]
    memories = [json.loads(l)["memory"] for l in lines]
    return "\n".join(memories)

def build_prompt(memory: str, chat_history: str, user: str) -> str:
    now = datetime_now_it()
    return textwrap.dedent(f"""
        ### SYSTEM
        {SYSTEM_PROMPT}

        ### LONG_TERM_MEMORY
        {memory if memory else "(nessun ricordo a lungo termine ancora)"}

        ### CONVERSAZIONE (fino ad ora)
        {chat_history}

        ### DATA/ORA (Europe/Rome)
        {now}

        ### UTENTE
        {user}

        ### ASSISTANT
    """).strip()

def datetime_now_it() -> str:
    return datetime.datetime.now(tz=tz.gettz("Europe/Rome")).strftime("%Y-%m-%d %H:%M")

def main():
    console.print(Markdown("**Gemma3 4B Chatbot (CLI)** – scrivi `exit` per uscire"))
    session_id = str(uuid.uuid4())[:8]
    chat_history: list[tuple[str, str]] = []
    long_memory = load_long_term()

    while True:
        user = console.input("[bold blue]Tu:[/bold blue] ")
        if user.lower() in {"exit", "quit"}:
            console.print("[italic]Ciao! A presto.[/italic]")
            break

        # costruiamo transcript testuale
        transcript = "\n".join(
            f"Utente: {q}\nAssistente: {a}" for q, a in chat_history
        )
        prompt = build_prompt(long_memory, transcript, user)
        answer = call_ollama(prompt)

        chat_history.append((user, answer))
        console.print("[bold green]Bot:[/bold green] " + answer)

        # se superiamo la finestra, riassumiamo e salviamo memoria
        total_tokens = num_tokens(transcript + user + answer)
        if total_tokens > WINDOW_TOKENS:
            summary = summarize(transcript)
            save_long_term(summary)
            long_memory = load_long_term()
            chat_history = []  # reset dello storico breve
            console.print(
                "[grey62][Memoria lunga aggiornata. Contesto compattato.][/grey62]"
            )


if __name__ == "__main__":
    import datetime
    main()