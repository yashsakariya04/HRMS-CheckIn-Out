"""
app/ai/handlers/chat_handler.py — Chat & Ambiguous Handler
===========================================================
Handles CHAT (greetings, general questions) and AMBIGUOUS intents.
Uses Groq to generate a natural response grounded in user context.
"""

import json

from groq import Groq

from app.core.config import settings

_client = Groq(api_key=settings.GROQ_API_KEY)

_SYSTEM = """You are an AI assistant embedded in an HRMS (HR Management System).
You help employees manage their attendance, leave, and tasks through conversation.

You can help with:
- Checking in and out of work
- Applying for leave, WFH, comp-off, or missing time correction
- Viewing leave balance and request status
- Answering questions about how to use the system

Keep responses concise and friendly. If the user's intent is unclear, ask one
clarifying question. Never make up data — only use what's in the user context.
"""


def handle_chat(message: str, context: dict, history: list) -> dict:
    """
    Generate a conversational response for CHAT or AMBIGUOUS intents.
    Returns {"response": str, "api_call": None, "needs_followup": bool}
    """
    ctx_str = json.dumps(context, indent=2)
    messages = [
        {"role": "system", "content": f"{_SYSTEM}\n\nUser context:\n{ctx_str}"},
        *history,
        {"role": "user", "content": message},
    ]

    try:
        resp = _client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        return {"response": text, "api_call": None, "needs_followup": False}
    except Exception:
        return {
            "response": "I'm having trouble connecting right now. Please try again in a moment.",
            "api_call": None,
            "needs_followup": False,
        }
