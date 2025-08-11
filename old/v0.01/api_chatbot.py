# app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from sentence_transformers import SentenceTransformer, util
import requests
from datetime import datetime
import pytz
import uvicorn
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# ──────────────────────── FastAPI & CORS ───────────────────────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringi se necessario
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────── Orari di apertura ─────────────────────
WEEKDAY_OPEN = os.getenv("WEEKDAY_OPEN", "00:00")
WEEKDAY_CLOSE = os.getenv("WEEKDAY_CLOSE", "00:00")
WEEKEND_OPEN = os.getenv("WEEKEND_OPEN", "00:00")
WEEKEND_CLOSE = os.getenv("WEEKEND_CLOSE", "00:00")

HOURS: Dict[str, tuple[str, str]] = {
    "weekday": (WEEKDAY_OPEN, WEEKDAY_CLOSE),
    "weekend": (WEEKEND_OPEN, WEEKEND_CLOSE),
}

def get_open_status(tz: str = "Europe/Rome") -> tuple[str, bool, str]:
    """Ritorna (timestamp, open_now_bool, fascia_oraria_oggi)."""
    now_dt = datetime.now(pytz.timezone(tz))
    key = "weekend" if now_dt.weekday() >= 5 else "weekday"
    open_t, close_t = HOURS[key]
    open_now = open_t <= now_dt.strftime("%H:%M") < close_t
    return now_dt.strftime("%Y-%m-%d %H:%M"), open_now, f"{open_t}–{close_t}"

# ───────────────────────── FAQ & Embeddings ─────────────────────
# ───────────────────────── FAQ & Embeddings ─────────────────────
with open("faq.jsonl", encoding="utf-8") as f:
    faqs = [json.loads(line) for line in f]

questions = [faq["question"] for faq in faqs]

# Configurazione RAG
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# Switch via .env  →  EMB_MODEL=minilm | jina
EMB_MODEL = os.getenv("EMB_MODEL", "minilm").lower()

try:
    if EMB_MODEL == "jina":
        # Jina Embeddings v4 da Hugging Face (niente index esterno)
        from sentence_transformers import SentenceTransformer
        import torch

        print(f"Caricamento modello Jina embeddings...")
        embedder = SentenceTransformer(
            "jinaai/jina-embeddings-v2-base-en",
            device="cuda" if torch.cuda.is_available() else "cpu"
        )
        question_embs = embedder.encode(
            questions, convert_to_tensor=True, normalize_embeddings=True
        )

        def get_embedding(text: str):
            return embedder.encode(
                [text], convert_to_tensor=True, normalize_embeddings=True
            )

        def cosine_sim(q_vec, doc_mat):
            # vettori normalizzati  →  dot product = cosine
            return (q_vec @ doc_mat.T).squeeze(0)
        
        print(f"✅ Modello Jina caricato con successo!")

    else:  # MiniLM-L6  (default)
        from sentence_transformers import SentenceTransformer, util

        print(f"Caricamento modello MiniLM-L6...")
        embedder = SentenceTransformer("all-MiniLM-L6-v2")
        question_embs = embedder.encode(questions, convert_to_tensor=True)

        def get_embedding(text: str):
            return embedder.encode([text], convert_to_tensor=True)

        def cosine_sim(q_vec, doc_mat):
            return util.pytorch_cos_sim(q_vec, doc_mat)[0]
        
        print(f"✅ Modello MiniLM-L6 caricato con successo!")

except Exception as e:
    print(f"❌ Errore nel caricamento del modello {EMB_MODEL}: {e}")
    print("🔄 Fallback su MiniLM-L6...")
    
    # Fallback su MiniLM
    from sentence_transformers import SentenceTransformer, util
    
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    question_embs = embedder.encode(questions, convert_to_tensor=True)

    def get_embedding(text: str):
        return embedder.encode([text], convert_to_tensor=True)

    def cosine_sim(q_vec, doc_mat):
        return util.pytorch_cos_sim(q_vec, doc_mat)[0]
    
    print("✅ Fallback MiniLM-L6 completato!")


def retrieve_context(q: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Top-k FAQ più simili, con punteggio di similarità."""
    q_vec  = get_embedding(q)
    scores = cosine_sim(q_vec, question_embs)           # tensor shape (N,)
    vals, idx = scores.topk(top_k)
    retrieved_docs = []
    for i, s in zip(idx.tolist(), vals.tolist()):
        doc = faqs[i].copy()
        doc["similarity_score"] = float(s)
        retrieved_docs.append(doc)
    return retrieved_docs


# ─────────────────────────  Ollama LLM  ─────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma3:4b")

def ask_ollama(prompt: str) -> str:
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()
    return r.json()["response"].strip()

# ─────────────────────── Intent classificazione ─────────────────
INTENTS = [
    "greeting",
    "info_request",
    "escalation_request",
    "confirm_escalation",
    "bot_question",
    "offensive",
    "other",
]

INTENTS_EXAMPLES = [
    "greeting: (saluti generali) ciao, come va, come butta, che mi dici, buon giorno...",
    "info_request: (domande sul locale, le sue attività e le sue caratteristiche) cosa offrite oggi?, cosa posso mangiare?, siete aperti?...",
    "escalation_request: (richieste di parlare con un umano)posso parlare con un umano?, mi passi un operatore?, voglio parlare con il tuo capo...",
    "confirm_escalation: si voglio parlare con l'operatore, ok, certo...",
    "bot_question: (domande sull'assistente virtuale) chi sei?, cosa sei?, sei un umano? cosa puoi fare?...",
    "offensive: messaggi volgari o offensivi di qualsiasi natura...",
    "other: tutto il resto...",
]



# ───────────────────────────── State ────────────────────────────
session_states = {}

def get_default_state() -> Dict[str, Any]:
    return {"greeted": False, "pending_escalation": False, "offensive": False}

def update_state(state: Dict[str, Any], intent: str) -> Dict[str, Any]:
    if intent == "greeting":
        state["greeted"] = True
    elif intent == "escalation_request":
        state["pending_escalation"] = True
    elif intent == "confirm_escalation" and state.get("pending_escalation"):
        state["pending_escalation"] = False
    elif intent == "offensive":
        state["offensive"] = True
    return state

# ───────────── Riformulazione (makes question standalone) ───────
def rewrite_question(history: List[List[str]], user_msg: str) -> tuple[str, str]:
    hist_str = "\n".join(f"Utente: {q}\nBot: {a}" for q, a in history)
    prompt = (

        f"""##################################################################
            #            PROMPT - "Rephrase to Stand-Alone Question"         #
            ##################################################################

            ╭─ 👔  RUOLO
            │  Sei un *rewriter*: converte l'ultima domanda dell'utente in una
            │  forma completa e indipendente, usando la chat history solo per
            │  colmare i riferimenti impliciti mantieni pure contenuti di natura sessuale e/o volgare, saranno filtrati successivamente.
            ╰─────────────────────────────────────────────────────────────────

            ╭─ 🎯  OBIETTIVI
            │  1. **Autosufficienza** – La domanda risultante deve essere
            │     comprensibile da sola, senza bisogno di consultare il dialogo
            │     precedente.
            │  2. **Fedeltà** – Mantieni
            │        • persona grammaticale
            │        • tempo verbale
            │        • contenuto semantico
            │     Non introdurre né rimuovere informazioni.
            │  3. **Nessun richiamo storico** – Niente "come detto prima", "nel
            │     messaggio precedente" o simili.
            │  4. **Pulizia** – Rispondi con UNA sola domanda (o le minime frasi
            │     interrogative necessarie), senza meta-commenti o spiegazioni.
            ╰─────────────────────────────────────────────────────────────────

            ╭─ ⚙️  INPUT
            │  CHAT_HISTORY =
            │  «{hist_str}»
            │
            │  USER_LAST_QUESTION =
            │  «{user_msg}»
            ╰─────────────────────────────────────────────────────────────────

            ╭─ 📝  ISTRUZIONI OPERATIVE
            │  • Leggi la HISTORY per capire a chi/cosa si riferiscono pronomi
            │    o locuzioni ("qui", "lì", "questo", "quella data", ecc.).
            │  • Integra i riferimenti mancanti direttamente nel testo.
            │  • Se la domanda originale è già autonoma, copiala invariata.
            │  • NON modificare persona o tempo; NON aggiungere giudizi.
            │  • Restituisci **solo** la domanda riformulata.
            ╰─────────────────────────────────────────────────────────────────

            ╭─ ✅  OUTPUT ATTESO
            │  DOMANDA_RIFORMULATA =
            │  (un'unica domanda autosufficiente, senza prefissi o note)
            ╰─────────────────────────────────────────────────────────────────
        """
    )
    rewritten = ask_ollama(prompt)
    return prompt, rewritten

# ───────────────────────── Prompt builder ───────────────────────
def build_prompt(history: List[List[str]],
                 rewritten_question: str,
                 context_docs: List[Dict[str, Any]],
                 state: Dict[str, Any],
                 intent: str) -> str:
    history_str = "\n".join(f"Utente: {q}\nBot: {a}" for q, a in history)
    now, open_now, today_open = get_open_status()
    
    # Combina i contenuti dei documenti recuperati
    ctx_blocks = []
    for i, doc in enumerate(context_docs, 1):
        score = doc.get('similarity_score', 0.0)
        ctx_blocks.append(f"DOCUMENTO {i} (rilevanza: {score:.3f}):\n{doc['answer']}")
    
    ctx_text = "\n\n".join(ctx_blocks)

    prompt = f"""

#############################
#  SYSTEM                   #
#############################
Sei l'assistente virtuale di **Officina Panarari** (café-bistrò a Treviglio).
Tono: amichevole, conciso, italiano naturale, conversazionale rispondi in prima persona direttamente all'utente.
Lunghezza: 2-4 frasi; elenchi puntati solo se servono davvero.
Fonti: usa **solo** le informazioni nei blocchi «CONTEXT».
Non inventare dati (zero "hallucinations") piuttosto Se le informazioni mancano o non sono affidabili →  
«Purtroppo non posso fornirti una risposta precisa. Vuoi che ti metta in contatto con lo staff?».

IMPORTANTE: Rispondi direttamente alla domanda senza ripeterla o citarla nel testo della risposta.

Proponi, quando opportuno, un *fatto utile* (es.: "alle 18 serviamo l'aperitivo con drink stagionali") purché derivato da CONTEXT.

#############################
#  STATE (sessione)         #
#############################
greeted = {state["greeted"]}               # Bool – hai già salutato?
pending_escalation = {state["pending_escalation"]}   # Bool – attendi conferma?
offensive_flag = {state["offensive"]}      # Bool – messaggio volgare precedente?

#############################
#  INTENT (detect → codice) #
#############################
{intent}  

#############################
#  DOMANDA UTENTE           #
#############################
{rewritten_question}

#############################
#  TIME (Europe/Rome)       #
#############################
{now}
OPEN_NOW = {open_now}  TODAY_OPEN = {today_open}   # calcolati nel back-end

#############################
#  CONTEXT (fonti RAG)      #
#############################
#di seguito troverai {RAG_TOP_K} dispense riconducibili alla domanda che ti è stata posta considerale tutta ma non citare quelle ovviamente fuori contesto
{ctx_text}

#############################
#  RULES                    #
#############################
A. ***Gestione intent***  
   A1. INFO_REQUEST → passa alle regole di risposta (sez. B).  
   A2. BOT_QUESTION → rispondi alle domande su di te usando il CONTEXT se disponibile, altrimenti rispondi in prima persona in modo conciso (max 2 frasi).
   A3. ESCALATION_REQUEST → chiedi conferma ("Vuoi che ti metta in contatto con lo staff?") → pending_escalation = True.  
   A4. CONFIRM_ESCALATION  
       • Se pending_escalation == True e conferma ("sì / ok / certo"/lo stato della richiesta è escalation_request) → **fornisci SOLO** telefono 338 1355 700 e mail officinapanarari@gmail.com, poi pending_escalation = False.  
       • Se rifiuta ("no") → "Va bene, rimango a disposizione!" → pending_escalation = False.  
   A5. OTHER → se non comprendi → "Non sono sicuro di aver capito, potresti riformulare?"

B. ***Costruzione risposta INFO_REQUEST***  
   B1. a meno che greeted == false non salutare
   B2. Ignora parti dei CONTEXT non pertinenti alla domanda.    
   B3. Se la risposta dipende dall'orario, per esempio una domanda sullo stato attuale di apertura del locale:  
       • Se OPEN_NOW == True → indica che il locale è aperto; se utile, mostra l'orario di chiusura.  
       • Se OPEN_NOW == False → "Io locale è chiuso; riapriamo alle {today_open.split('–')[0]}."  
   B4. Per prenotazioni/eventi: spiega i passaggi chiave ("clicca su Prenota" / "scrivi a ..." ) e offri escalation solo se necessario.  
   B5. Per richieste personali (es. cani, allergie): rispondi e, se opportuno, aggiungi frase rassicurante.  
   B6. Se context insufficiente → usa messaggio di fallback standard + gestisci eventuale escalation (come in A3).

C. ***Netiquette e coerenza***  
    ▪ Non ripetere presentazioni o saluti inutili all'inizio delle frasi a meno che non sia il messaggio iniziale.  
    ▪ Rispondi direttamente alla domanda senza ripeterla o citarla
    ▪ Non iniziare con "Potresti descrivere..." o frasi simili che ripetono la domanda 

#############################
#  ASSISTANT                #
#############################
(Genera qui la risposta finale seguendo le sezioni SYSTEM + RULES)
####################################################################################

"""
    return prompt

# ────────────────────────── Logger JSON ─────────────────────
def log_chat(user_msg: str, bot_msg: str, intent: str, intent_prompt: str = None, intent_response: str = None, rewrite_prompt: str = None, rewritten_question: str = None, final_prompt: str = None, greeting_prompt: str = None, bot_prompt: str = None, offensive_prompt: str = None, context_docs: List[Dict[str, Any]] = None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepara i documenti RAG per il JSON
    rag_docs = []
    if context_docs:
        for i, doc in enumerate(context_docs, 1):
            rag_docs.append({
                "document_id": i,
                "similarity_score": doc.get('similarity_score', 0.0),
                "question": doc.get('question', 'N/A'),
                "answer": doc.get('answer', 'N/A')
            })
    
    # Crea l'oggetto log
    log_entry = {
        "timestamp": ts,
        "intent": intent,
        "user_message": user_msg,
        "bot_message": bot_msg,
        "prompts": {
            "intent_classification": {
                "prompt": intent_prompt,
                "response": intent_response
            },
            "question_rewriting": {
                "prompt": rewrite_prompt,
                "response": rewritten_question
            },
            "final_generation": {
                "prompt": final_prompt
            },
            "greeting": {
                "prompt": greeting_prompt
            },
            "bot_question": {
                "prompt": bot_prompt
            },
            "offensive": {
                "prompt": offensive_prompt
            }
        },
        "rag_documents": rag_docs
    }
    
    # Salva in formato JSON
    with open("chat_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def read_chat_logs(limit: int = None) -> List[Dict[str, Any]]:
    """Legge i log delle chat dal file JSONL."""
    logs = []
    try:
        with open("chat_log.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
                    if limit and len(logs) >= limit:
                        break
    except FileNotFoundError:
        pass
    return logs

def get_chat_stats() -> Dict[str, Any]:
    """Calcola statistiche sui log delle chat."""
    logs = read_chat_logs()
    if not logs:
        return {"total_conversations": 0}
    
    intents = [log["intent"] for log in logs]
    intent_counts = {}
    for intent in intents:
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    
    return {
        "total_conversations": len(logs),
        "intent_distribution": intent_counts,
        "first_conversation": logs[0]["timestamp"] if logs else None,
        "last_conversation": logs[-1]["timestamp"] if logs else None
    }

# ───────────────────────── Schemi Pydantic ──────────────────────
class ChatRequest(BaseModel):
    user_message: str
    history: Optional[List[List[str]]] = []
    debug: Optional[bool] = False
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    answer: str
    history: List[List[str]]
    debug_info: Optional[str] = None
    state: Dict[str, Any]

class ResetRequest(BaseModel):
    session_id: Optional[str] = "default"

class ResetResponse(BaseModel):
    message: str
    session_id: str

class StatsResponse(BaseModel):
    total_conversations: int
    intent_distribution: Dict[str, int]
    first_conversation: Optional[str]
    last_conversation: Optional[str]

# ──────────────────────────── Endpoint ──────────────────────────
@app.post("/reset", response_model=ResetResponse)
def reset_session(req: ResetRequest):
    # Reset dello stato per questa sessione
    session_states[req.session_id] = get_default_state()
    return ResetResponse(
        message="Chat history e stato resettati per questa sessione",
        session_id=req.session_id
    )

@app.get("/stats", response_model=StatsResponse)
def get_stats():
    """Endpoint per ottenere statistiche sui log delle chat."""
    return get_chat_stats()

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    history = req.history or []
    
    # Gestione dello stato per sessione
    if req.session_id not in session_states:
        session_states[req.session_id] = get_default_state()
    
    state = session_states[req.session_id].copy()

    # 1) Riformula la domanda
    rewrite_prompt, rewritten_question = rewrite_question(history[-3:], req.user_message)

    # 2) Intent classification sulla domanda riformulata
    intent_prompt = (
        "Classifica l'intento scegliendo UNA sola tra:\n"
        f"{', '.join(INTENTS)}\n"
        "Rispondi solo con la categoria.\n"
        "Ecco alcuni esempi:\n"
        f"{chr(10).join(INTENTS_EXAMPLES)}\n"
        f"Domanda utente: {rewritten_question}"
    )
    intent_response = ask_ollama(intent_prompt)
    intent = intent_response.lower()
    intent = intent if intent in INTENTS else "other"

    # 3) Filtro volgarità immediato
    if intent == "offensive":
        offensive_prompt = f"""
Sei l'assistente virtuale di Officina Panarari.
Rispondi educatamente chiedendo di usare un linguaggio rispettoso.
Non essere aggressivo, mantieni un tono professionale.

Utente: {req.user_message}

Risposta:"""
        answer = ask_ollama(offensive_prompt)
        # Aggiorna stato per messaggi offensivi
        state = update_state(state, intent)
        session_states[req.session_id] = state
        history.append([req.user_message, answer])
        log_chat(req.user_message, answer, intent, intent_prompt, intent_response, offensive_prompt=offensive_prompt)
        return ChatResponse(answer=answer, history=history, state=state)

    # 4) Gestione saluti senza RAG
    if intent == "greeting":
        greeting_prompt = f"""
Sei l'assistente virtuale di Officina Panarari (café-bistrò a Treviglio).
Tono: amichevole, conciso, italiano naturale.

Stato: greeted = {state["greeted"]}

Se greeted == False: saluta in modo cordiale e presentati brevemente (2-3 frasi)
Se greeted == True: rispondi con un saluto breve (max 5 parole)

Utente: {req.user_message}

Risposta:"""
        answer = ask_ollama(greeting_prompt)
        # Aggiorna stato per i saluti
        state = update_state(state, intent)
        session_states[req.session_id] = state
        history.append([req.user_message, answer])
        log_chat(req.user_message, answer, intent, intent_prompt, intent_response, greeting_prompt)
        return ChatResponse(answer=answer, history=history, state=state)

    # 5) RAG (per tutti gli intent che richiedono informazioni, incluso bot_question)
    context_docs = retrieve_context(rewritten_question, top_k=RAG_TOP_K)

    # 6) Prompt & risposta (con stato NON aggiornato)
    final_prompt = build_prompt(history[-3:], rewritten_question, context_docs, state, intent)
    answer = ask_ollama(final_prompt)

    # 7) Aggiorna stato DOPO aver generato la risposta
    state = update_state(state, intent)
    
    # 8) Aggiorna lo stato della sessione
    session_states[req.session_id] = state
    
    # 9) Log & risposta
    history.append([req.user_message, answer])
    log_chat(req.user_message, answer, intent, intent_prompt, intent_response, rewrite_prompt, rewritten_question, final_prompt, context_docs=context_docs)

    debug_info = final_prompt if req.debug else None
    return ChatResponse(answer=answer, history=history, debug_info=debug_info, state=state)

# ──────────────────────────── Main ──────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
