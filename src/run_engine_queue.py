"""
Entry point for GitHub Actions — trains Engine 1 and drains raw_queue.
Does not run the live log stream (that's main.py for local use).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import db_manager as db_mod
import engine_1 as e1
from router import route_to_cloud_agent

_db = None
_recent = []


def _handle_anomaly(line: str):
    route_to_cloud_agent(line, _recent[-3:])


def main():
    global _db
    _db = db_mod.DatabaseManager()

    pending = _db.raw_queue.count_documents({"processed": False})
    print(f"[QUEUE] {pending} unprocessed documents in raw_queue")

    if pending == 0:
        print("[QUEUE] Nothing to process. Exiting.")
        _db.close()
        return

    print("[QUEUE] Training Engine 1...")
    model, threshold = e1.train_gatekeeper()

    print("[QUEUE] Processing queue...")
    e1.process_queue(model, threshold, _db, _handle_anomaly)

    _db.close()


if __name__ == "__main__":
    main()
