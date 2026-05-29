# Apex-Telemetry

A real-time server log pipeline that uses machine learning to separate the noise from actual threats — then ships the weird stuff off to a cloud LLM to figure out what went wrong and why.

The idea: most log anomaly tools either drown you in false positives or miss the subtle ones. This one runs a fast Scikit-Learn filter first (cheap, instant), and only escalates the genuinely suspicious lines to a cloud AI agent for deep analysis. Two engines, one pipeline.

---

## How it works

```
Live Log Stream
      │
      ▼
┌─────────────┐
│  Engine 1   │  IsolationForest scores every line as it comes in
│ (Gatekeeper)│
└──────┬──────┘
       │
  ┌────┴─────┐
  │          │
Normal     Anomaly
  │          │
  ▼          ▼
MongoDB   router.py ──► Cloud LLM Agent
safe_      active_           │
traffic    threats            └─► pending_analysis.json (if offline)
```

Engine 1 trains on a sample of healthy traffic on startup, then watches the live log file line by line. Anything that looks statistically out of place gets flagged and sent to the router. The router packages the anomaly alongside the 3 preceding normal logs for context, then POSTs it to your cloud agent — or dumps it locally if there's no endpoint configured.

---

## What you need

- Python 3.13+
- MongoDB — either running locally or a free Atlas cluster
- `pip install -r requirements.txt`

---

## Getting started

**Clone and install:**
```bash
git clone https://github.com/ygtdalkilic/Apex-Telemetry.git
cd Apex-Telemetry
pip install -r requirements.txt
```

**MongoDB — pick one:**

Local: download the Community Server from [mongodb.com/try/download/community](https://www.mongodb.com/try/download/community), install it as a Windows service and you're done.

Atlas (easier, no install): spin up a free M0 cluster at [cloud.mongodb.com](https://cloud.mongodb.com), grab your connection string, then:
```powershell
$env:MONGO_URI = "mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/"
```

**Optionally point it at your cloud agent:**
```powershell
$env:CLOUD_AGENT_ENDPOINT = "https://your-agent-url"
```
If you skip this, flagged anomalies just pile up in `data/pending_analysis.json` — useful for debugging locally.

---

## Run it

```powershell
cd src
python main.py
```

It'll train the model, spin up the log generator in the background, and start classifying. You'll see something like:

```
[DB] Connected to mongodb://localhost:27017/
[E1] Model trained on 500 normal samples.
[GEN] Writing logs to data/live_stream.log — Ctrl+C to stop
[E1] processed=50 safe=48 flagged=2 rate=9.8/s mem_peak=0.14MB
[ROUTER] CLOUD_AGENT_ENDPOINT not set — writing to pending file.
```

Hit `Ctrl+C` to stop — it shuts down cleanly.

---

## Project layout

```
src/
├── main.py           # start here — wires everything together
├── db_manager.py     # MongoDB connection + insert helpers
├── log_generator.py  # fake Nginx traffic (95% normal, 5% nasty)
├── engine_1.py       # IsolationForest training + live stream classifier
└── router.py         # sends anomalies to cloud or saves them locally

data/
├── live_stream.log        # generated while running
└── pending_analysis.json  # anomaly buffer when cloud is unreachable
```

---

## MongoDB collections

| Collection | What's in it |
|---|---|
| `safe_traffic` | Every log line Engine 1 cleared as normal |
| `active_threats` | Lines flagged as anomalies, waiting on LLM analysis |
| `raw_logs` | Reserved for future raw capture |

---

## Environment variables

| Variable | Default | What it does |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017/` | Where to connect for storage |
| `CLOUD_AGENT_ENDPOINT` | _(not set)_ | Where to POST anomalies for LLM analysis |

---

## Authors

Yigit — [ygtdalkilic@gmail.com](mailto:ygtdalkilic@gmail.com)

Claude Sonnet 4.6 (Anthropic) — code refinement & testing
