# B&B WhatsApp Concierge (RAG)

Web app di test per un assistente “stile concierge” che risponde **solo** usando la tua knowledge base (Excel) e, prima di rispondere, prova a riconoscere ospite/prenotazione tramite **Ciao Booking** (in alternativa usa un mock locale).

## Avvio locale

1) Crea e attiva un virtualenv, poi installa:

```bash
pip install -r requirements.txt
```

2) Imposta le variabili d’ambiente minime:

```bash
export OPENAI_API_KEY="..."
export ADMIN_API_KEY="una-chiave-a-scelta"
export MOCK_CIAO_BOOKING="true"
```

In alternativa puoi copiare `/.env.example` → `/.env` e compilare i valori (il file `.env` è ignorato da git).

3) (Opzionale) Metti il file Excel della KB in `data/kb.xlsx` (puoi anche caricarlo via UI admin).

4) Avvia:

```bash
uvicorn app.main:app --reload --port 8000
```

Apri `http://localhost:8000`.

## Knowledge base (Excel)

Il file `data/kb.xlsx` deve avere **2 sheet**:

1) Sheet KB con colonne:
`Categoria | Appartamento /stanza | ambito | descrizione | risposta`

2) Sheet “anagrafica” (libero): viene caricato come metadati e reso disponibile al modello.

## Mock Ciao Booking

Per testare senza API reali:

- `MOCK_CIAO_BOOKING=true`
- crea `data/mock_ciaobooking.json` seguendo l’esempio in `data/mock_ciaobooking.example.json`

## Deploy su Render

- Carica questo repository su GitHub
- Su Render crea un “Web Service” e imposta `Start Command` come in `render.yaml`
- Imposta le env vars (almeno `OPENAI_API_KEY`, `ADMIN_API_KEY`)

## Endpoint utili

- UI chat: `GET /`
- Chat API: `POST /api/chat`
- Upload KB (admin): `POST /admin/kb/upload` (Header `X-Admin-Key: ...`)
