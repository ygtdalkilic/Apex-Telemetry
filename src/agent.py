"""
AI Agent — searches the internet for cybersecurity threat data and dumps
raw findings into MongoDB raw_queue for Engine 1 to process.
"""

import re
import sys
import os
from datetime import datetime, timezone 
import ollama 

from duckduckgo_search import DDGS

sys.path.insert(0, os.path.dirname(__file__))
from db_manager import DatabaseManager

# Topics the agent hunts for on every run
SEARCH_QUERIES = [
    "new CVE vulnerability exploit 2025",
    "active malware campaign IP addresses",
    "SQL injection attack patterns site:github.com",
    "DDoS botnet command control server",
    "web shell backdoor HTTP request pattern",
]

IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
CVE_PATTERN = re.compile(r'CVE-\d{4}-\d+')


def analyze_with_llm(text: str) -> dict:
    prompt = (
        "You are a cybersecurity analyst. Read the following web search result and assess it.\n"
        "Reply in exactly this format:\n"
        "threat_level: low | medium | high\n"
        "reason: one sentence explaining why\n\n"
        f"Search result:\n{text[:1000]}"
    )
    response = ollama.chat(
        model="phi3:mini",
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.message.content
    threat_level = "unknown"
    reason = raw
    for line in raw.splitlines():
        if line.lower().startswith("threat_level:"):
            threat_level = line.split(":", 1)[1].strip()
        elif line.lower().startswith("reason:"):
            reason = line.split(":", 1)[1].strip()
    return {"threat_level": threat_level, "reason": reason}


def _extract_signals(text: str) -> dict:
    return {
        "ips": IP_PATTERN.findall(text),
        "cves": CVE_PATTERN.findall(text),
        "length": len(text),
        "has_exploit": any(w in text.lower() for w in ["exploit", "payload", "shell", "injection", "bypass"]),
    }


def run(max_results_per_query=5):
    db = DatabaseManager()
    total = 0

    with DDGS() as ddgs:
        for query in SEARCH_QUERIES:
            print(f"[AGENT] Searching: {query}")
            try:
                results = list(ddgs.text(query, max_results=max_results_per_query))
            except Exception as e:
                print(f"[AGENT] Search failed for '{query}': {e}")
                continue

            docs = []
            for r in results:
                body = f"{r.get('title', '')} {r.get('body', '')}"
                llm = analyze_with_llm(body)
                print(f"[AGENT] {r.get('title', '')[:60]} → threat_level={llm['threat_level']}")
                docs.append({
                    "source": "duckduckgo",
                    "query": query,
                    "url": r.get("href", ""),
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "signals": _extract_signals(body),
                    "llm_analysis": llm,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "processed": False,
                })

            if docs:
                db.insert_many(db.raw_queue, docs)
                total += len(docs)
                print(f"[AGENT] Dumped {len(docs)} results into raw_queue")

    print(f"[AGENT] Done. Total documents queued: {total}")
    db.close()


if __name__ == "__main__":
    run()
