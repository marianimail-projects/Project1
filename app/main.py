from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, engine
from app.kb import KBStore
from app.service import ChatService


Base.metadata.create_all(bind=engine)

app = FastAPI(title="B&B WhatsApp Concierge (RAG)")

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

kb_store = KBStore()
chat_service = ChatService(kb_store=kb_store)


@app.on_event("startup")
def _startup() -> None:
    Path("data").mkdir(parents=True, exist_ok=True)
    if os.path.exists(settings.kb_excel_path):
        try:
            kb_store.load_from_excel(settings.kb_excel_path)
        except Exception as e:
            # Keep app running even if KB load fails (e.g. missing OPENAI_API_KEY).
            print(f"[startup] KB load failed: {e}")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = static_dir / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def api_chat(payload: dict) -> JSONResponse:
    phone = str(payload.get("phone", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not phone or not message:
        raise HTTPException(status_code=400, detail="Missing 'phone' or 'message'.")

    result = await chat_service.handle_incoming_message(phone_e164=phone, text=message)
    return JSONResponse(content=result)


@app.post("/admin/kb/upload")
async def admin_kb_upload(
    file: UploadFile,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> JSONResponse:
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Please upload an .xlsx file.")

    Path("data").mkdir(parents=True, exist_ok=True)
    target = Path(settings.kb_excel_path)
    target.write_bytes(await file.read())
    kb_store.load_from_excel(str(target))
    return JSONResponse(content={"ok": True, "kb_path": str(target)})


@app.post("/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request) -> HTMLResponse:
    """
    Endpoint pronto per Twilio WhatsApp (fase successiva).
    Twilio invia form-urlencoded con campi tipici: From, Body.
    """
    form = await request.form()
    phone = str(form.get("From", "")).strip()
    body = str(form.get("Body", "")).strip()
    if not phone or not body:
        raise HTTPException(status_code=400, detail="Missing From/Body")

    # Twilio usa formato tipo "whatsapp:+39...." -> normalizziamo
    if phone.startswith("whatsapp:"):
        phone = phone.split(":", 1)[1]

    result = await chat_service.handle_incoming_message(phone_e164=phone, text=body)
    reply = result.get("assistant_message", "")

    # TwiML minimale senza dipendenze
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{_xml_escape(reply)}</Message></Response>'
    return HTMLResponse(content=twiml, media_type="application/xml")


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
