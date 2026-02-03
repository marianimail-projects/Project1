from __future__ import annotations

import json
from typing import Any

import httpx
from sqlalchemy import select

from app.ciaobooking import CiaoBookingClient
from app.config import settings
from app.db import SessionLocal
from app.kb import KBStore
from app.llm import chat_completion
from app.models import ChatMessage, ChatSession, HandoffRequest


AGENT_SYSTEM_PROMPT = """Sei un assistente virtuale altamente qualificato che lavora per una struttura alberghiera di lusso. Il tuo ruolo è fornire supporto agli ospiti prima, durante e dopo il soggiorno, con lo stesso tono, precisione e livello di servizio di un concierge 5 stelle.

Il tuo comportamento deve sempre essere professionale, cortese, proattivo e attento ai dettagli.

Hai piena conoscenza di:
- Servizi e comfort offerti dalla struttura (spa, ristorante, palestra, piscina, room service, tipologie di camere, orari di check-in/check-out)
- Servizi extra (transfer privato, navetta aeroportuale, baby-sitting, pet-friendly)
- Attrazioni locali, eventi, ristoranti e attività esperienziali nella zona
- Politiche della struttura (cancellazioni, pagamenti, fumo, animali, accessi)
- Richieste speciali (compleanni, anniversari, lune di miele)
- Gestione di upgrade, modifiche prenotazioni, esigenze dietetiche e preferenze personali
- Richieste urgenti (manutenzione, pulizie, late check-out)

Il tuo tono:
- È sempre elegante, formale e caloroso, come in un hotel 5 stelle.
- Mantieni sempre un approccio orientato alla soluzione.
- Sei capace di rispondere in più lingue, ma utilizzi l’italiano come lingua predefinita (o quella utilizzata dall’ospite).
- Sei attento nel personalizzare le risposte in base al contesto.

Regole speciali:
- Rivolgiti sempre al cliente come “Sig./Sig.ra/Mx. [Cognome]” quando noto.
- Non dichiarare mai di essere un assistente virtuale o un'intelligenza artificiale.
- Non condividere mai processi interni o dati sensibili.
- Se non comprendi esattamente la richiesta, fai domande di chiarimento in modo gentile.
- Se il cliente sta festeggiando un evento speciale, proponi proattivamente un gesto di benvenuto (es. upgrade, omaggio in camera), se previsto dalla policy.

Inizia ogni conversazione riconoscendo la richiesta del cliente e offrendo supporto in modo naturale.
"""


def _handoff_message(last_name: str | None) -> str:
    if last_name:
        return (
            f"Grazie, Sig./Sig.ra/Mx. {last_name}. "
            "Per offrirLe una risposta precisa la metto subito in contatto con Niccolò, "
            "che La ricontatterà al più presto."
        )
    return (
        "Grazie per il messaggio. Per offrirLe una risposta precisa la metto subito in contatto con Niccolò, "
        "che La ricontatterà al più presto."
    )


class ChatService:
    def __init__(self, *, kb_store: KBStore) -> None:
        self._kb = kb_store
        self._ciao = CiaoBookingClient()

    async def handle_incoming_message(self, *, phone_e164: str, text: str) -> dict[str, Any]:
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.phone_e164 == phone_e164))
            if not session:
                session = ChatSession(phone_e164=phone_e164)
                db.add(session)
                db.commit()
                db.refresh(session)

            # Always store user message
            db.add(ChatMessage(session_id=session.id, role="user", content=text))
            db.commit()

        # Ensure booking context exists
        booking_ctx = self._ciao.get_booking_by_phone(phone_e164)
        if not booking_ctx:
            await self._create_handoff(phone_e164, None, None, None, text, reason="no_booking")
            assistant = _handoff_message(None)
            self._store_assistant(phone_e164, assistant)
            return {
                "status": "handoff",
                "assistant_message": assistant,
                "booking_found": False,
            }

        # Persist booking context into session
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.phone_e164 == phone_e164))
            if session:
                session.booking_id = booking_ctx.booking_id
                session.property_id = booking_ctx.property_id
                session.guest_last_name = booking_ctx.guest_last_name
                db.commit()

        # Retrieve from KB filtered by property_id
        retrieved = self._kb.retrieve(text, property_hint=booking_ctx.property_id)
        best_score = retrieved[0].score if retrieved else 0.0
        if not retrieved or best_score < settings.kb_min_score:
            await self._create_handoff(
                phone_e164,
                booking_ctx.guest_last_name,
                booking_ctx.property_id,
                booking_ctx.booking_id,
                text,
                reason="no_kb_answer",
            )
            assistant = _handoff_message(booking_ctx.guest_last_name)
            self._store_assistant(phone_e164, assistant)
            return {
                "status": "handoff",
                "assistant_message": assistant,
                "booking_found": True,
                "kb_used": False,
                "kb_best_score": best_score,
            }

        # Compose LLM prompt with RAG context
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.phone_e164 == phone_e164))
            memory_summary = session.memory_summary if session else None
            history_messages: list[ChatMessage] = []
            if session:
                msgs = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.session_id == session.id)
                    .order_by(ChatMessage.id.desc())
                    .limit(16)
                    .all()
                )
                history_messages = list(reversed(msgs))

        # Remove the current user message from history (we add it explicitly at the end)
        if history_messages and history_messages[-1].role == "user" and history_messages[-1].content == text:
            history_messages = history_messages[:-1]

        registry = self._kb.property_registry.get(booking_ctx.property_id, {})
        guest_name_line = (
            f"Cognome ospite: {booking_ctx.guest_last_name}" if booking_ctx.guest_last_name else ""
        )
        registry_line = f"Anagrafica struttura (property_id={booking_ctx.property_id}): {json.dumps(registry, ensure_ascii=False)}"

        rag_context_lines = []
        for i, r in enumerate(retrieved, start=1):
            rag_context_lines.append(
                f"[KB {i} | score={r.score:.3f} | unit={r.unit or 'N/A'} | ambito={r.scope or 'N/A'}]\n"
                f"Descrizione: {r.description or ''}\n"
                f"Risposta: {r.answer}\n"
            )
        rag_context = "\n".join(rag_context_lines)

        guardrails = (
            "REGOLE VINCOLANTI:\n"
            "- Rispondi usando SOLO le informazioni presenti in 'CONTESTO KB' e nell'anagrafica struttura.\n"
            "- Se il contesto non contiene la risposta specifica, NON inventare: rispondi esattamente con '[[HANDOFF_NICCOLO]]'.\n"
            "- Non menzionare la knowledge base, retrieval, punteggi o sistemi interni.\n"
            "- Mantieni il tono 5 stelle.\n"
            "- Usa la lingua del cliente (default italiano).\n"
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "system", "content": guardrails},
            {
                "role": "system",
                "content": f"{guest_name_line}\nBooking ID: {booking_ctx.booking_id}\n{registry_line}".strip(),
            },
        ]
        if memory_summary:
            messages.append({"role": "system", "content": f"Memoria conversazione: {memory_summary}"})

        for m in history_messages:
            if m.role in {"user", "assistant"}:
                messages.append({"role": m.role, "content": m.content})

        messages.append(
            {
                "role": "system",
                "content": f"CONTESTO KB:\n{rag_context}".strip(),
            }
        )
        messages.append({"role": "user", "content": text})

        assistant = chat_completion(messages).strip()
        if assistant == "[[HANDOFF_NICCOLO]]" or assistant.strip().upper().find("HANDOFF_NICCOLO") != -1:
            await self._create_handoff(
                phone_e164,
                booking_ctx.guest_last_name,
                booking_ctx.property_id,
                booking_ctx.booking_id,
                text,
                reason="model_handoff",
            )
            assistant = _handoff_message(booking_ctx.guest_last_name)

        self._store_assistant(phone_e164, assistant)
        await self._maybe_update_memory(phone_e164)
        return {
            "status": "ok",
            "assistant_message": assistant,
            "booking_found": True,
            "kb_used": True,
            "kb_best_score": best_score,
        }

    def _store_assistant(self, phone_e164: str, assistant_text: str) -> None:
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.phone_e164 == phone_e164))
            if not session:
                return
            db.add(ChatMessage(session_id=session.id, role="assistant", content=assistant_text))
            db.commit()

    async def _maybe_update_memory(self, phone_e164: str) -> None:
        # Lightweight: create/update a short summary every few turns (here: always after assistant reply).
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.phone_e164 == phone_e164))
            if not session:
                return
            msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.id.desc())
                .limit(20)
                .all()
            )
            msgs = list(reversed(msgs))
            prior = session.memory_summary or ""

        conv = "\n".join([f"{m.role}: {m.content}" for m in msgs if m.role in {"user", "assistant"}])
        prompt = [
            {
                "role": "system",
                "content": (
                    "Aggiorna una memoria sintetica della conversazione in italiano. "
                    "Deve contenere solo fatti utili (preferenze, richieste, dettagli soggiorno) "
                    "senza dati sensibili non necessari. Massimo 6 bullet."
                ),
            },
            {"role": "system", "content": f"Memoria precedente:\n{prior}".strip()},
            {"role": "user", "content": f"Conversazione recente:\n{conv}".strip()},
        ]
        updated = chat_completion(prompt).strip()
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.phone_e164 == phone_e164))
            if not session:
                return
            session.memory_summary = updated
            db.commit()

    async def _create_handoff(
        self,
        phone_e164: str,
        last_name: str | None,
        property_id: str | None,
        booking_id: str | None,
        user_message: str,
        *,
        reason: str,
    ) -> None:
        with SessionLocal() as db:
            db.add(
                HandoffRequest(
                    phone_e164=phone_e164,
                    guest_last_name=last_name,
                    property_id=property_id,
                    booking_id=booking_id,
                    user_message=user_message,
                    reason=reason,
                )
            )
            db.commit()

        if settings.niccolo_notify_webhook_url:
            payload = {
                "phone_e164": phone_e164,
                "guest_last_name": last_name,
                "property_id": property_id,
                "booking_id": booking_id,
                "reason": reason,
                "message": user_message,
            }
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    await client.post(settings.niccolo_notify_webhook_url, json=payload)
            except Exception:
                # Silent fail: non blocchiamo la risposta al cliente
                pass
