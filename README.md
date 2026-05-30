# Apex-Telemetry (Still in development)

A real-time server log pipeline with a dual-engine architecture. A local AI agent searches the internet for threat intelligence, a PyTorch autoencoder classifies everything in real time, and anomalies get routed to a cloud LLM for forensic analysis.

---

## How it works

```
GitHub Actions (every 6h)
        │
        ▼
  agent.py — DuckDuckGo search + Phi-3 Mini (local SLM)
        │     reasons about each result: low / medium / high threat
        ▼
  MongoDB: raw_queue        ← Container 1 (raw AI findings)
        │
        ▼
  Engine 1 — PyTorch Autoencoder
  trains on normal traffic, flags by reconstruction error
        │
   ┌────┴────┐
   ▼         ▼
safe_traffic  active_threats  ← Container 2 & 3
                │
                ▼
           router.py ──► Cloud LLM Agent (or pending_analysis.json)

  Parallel: live log stream from log_generator.py
  also feeds Engine 1 in real time via main.py
```

---

## Stack

| Layer | Technology |
|---|---|
| AI Agent | DuckDuckGo Search + Ollama Phi-3 Mini (local) |
| ML Engine | PyTorch Autoencoder (anomaly detection) |
| Database | MongoDB Atlas |
| Automation | GitHub Actions (scheduled + event-driven) |
| Cloud Router | REST POST to cloud LLM agent |

> **Note:** The cloud LLM router (`CLOUD_AGENT_ENDPOINT`) is architected and ready but not active — no budget for a hosted LLM service during development. Phi-3 Mini running locally via Ollama is used in its place for testing. The cloud integration will be wired in once the project moves past the development phase.

---

## What you need

- Python 3.13+
- [Ollama](https://ollama.com) with `phi3:mini` pulled
- MongoDB Atlas free cluster (or local `mongod`)
- `pip install -r requirements.txt`

---

## Getting started

**Clone and install:**
```bash
git clone https://github.com/ygtdalkilic/Apex-Telemetry.git
cd Apex-Telemetry
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Pull the local model:**
```powershell
ollama pull phi3:mini
```

**Set your MongoDB URI:**
```powershell
$env:MONGO_URI = "mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/"
```

**Optionally set a cloud agent endpoint:**
```powershell
$env:CLOUD_AGENT_ENDPOINT = "https://your-agent-url"
```

---

## Run

**Live log pipeline (local):**
```powershell
& "C:\...\python.exe" src\main.py
```

**AI agent only (search + queue):**
```powershell
& "C:\...\python.exe" src\agent.py
```

**Process queued agent findings through Engine 1:**
```powershell
& "C:\...\python.exe" src\run_engine_queue.py
```

---

## Project layout

```
src/
├── main.py              # live pipeline entry point
├── agent.py             # AI agent — searches web, reasons with Phi-3
├── engine_1.py          # PyTorch autoencoder — trains + classifies
├── run_engine_queue.py  # drains raw_queue (used by GitHub Actions)
├── db_manager.py        # MongoDB collections
├── log_generator.py     # simulates 95% normal / 5% anomalous traffic
└── router.py            # routes threats to cloud or local fallback

.github/workflows/
├── agent.yml            # runs agent every 6h, triggers engine
└── engine.yml           # processes queue after agent finishes

data/
├── live_stream.log        # generated at runtime
└── pending_analysis.json  # offline anomaly buffer
```

---

## MongoDB collections

| Collection | What's in it |
|---|---|
| `raw_queue` | Raw findings from the AI agent, pending Engine 1 |
| `safe_traffic` | Logs Engine 1 scored as normal |
| `active_threats` | Flagged anomalies, routed for LLM analysis |

---

## GitHub Actions

Add `MONGO_URI` as a repository secret under **Settings → Secrets → Actions**.

| Workflow | Trigger | What it does |
|---|---|---|
| `agent.yml` | Every 6h or manual | Runs AI agent, queues findings, fires engine |
| `engine.yml` | After agent or manual | Trains model, drains queue, classifies |

---

## Environment variables

| Variable | Default | What it does |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017/` | MongoDB connection |
| `CLOUD_AGENT_ENDPOINT` | _(not set)_ | POST target for flagged anomalies |

---

## Authors

Yigit Dalkilic

Claude Sonnet 4.6 (Anthropic) — code refinement & testing
