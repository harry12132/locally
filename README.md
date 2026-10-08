# Local Enterprise AI Agent

A local-first agent backend for privacy-sensitive business workflows. The first
vertical slice routes accounting and legal questions to specialist agents and
reads firm records from SQLite. Ollama hosts the model; prompts and business
records are not sent to a cloud service.

## Requirements

- Python 3.14
- Ollama with `qwen2.5:3b` pulled locally

## Run the backend

```bash
ollama pull qwen2.5:3b
python3 -m venv .venv
source .venv/bin/activate
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The database is created and seeded on first startup at
`backend/firm_data.db`. Set `FIRM_DB_PATH` to use a different local SQLite
file. The API binds to loopback by default; do not expose it to a network
without adding authentication and deployment security controls.

`POST /api/chat` accepts `{"message":"..."}` and streams newline-delimited
SSE events. `GET /health` reports service availability. You can run the data
layer checks without installing the AI dependencies with:

```bash
python3 -m unittest discover -s backend/tests -v
```

The seed records are demonstration data. Replace them with a controlled import
and access policy before using real client or financial information.

## Run the frontend

In a second terminal, start the Next.js client:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The backend must be running separately at
`http://127.0.0.1:8000`. Set `NEXT_PUBLIC_AGENT_API_URL` before starting the
frontend if the local API uses another address.

## Email approvals

Email drafting is available through the chat, but sending is disabled unless a
loopback SMTP relay is configured. Set `LOCAL_SMTP_FROM` to the approved sender
address; `LOCAL_SMTP_HOST` is restricted to loopback, and `LOCAL_SMTP_PORT`
defaults to `1025`. Each send pauses for explicit approval in the UI. Configure
and secure the relay separately; never expose this backend to an untrusted
network.