import signal
import sys
import threading
from collections import deque

import db_manager as db_mod
import engine_1 as e1
import log_generator as gen
from router import route_to_cloud_agent

LOG_PATH = "data/live_stream.log"
CONTEXT_WINDOW = 3

_db = None
_recent_safe = deque(maxlen=CONTEXT_WINDOW)


def _handle_anomaly(line: str):
    _db.insert_one(_db.active_threats, {"raw": line})
    route_to_cloud_agent(line, list(_recent_safe))


def _shutdown(sig, frame):
    print("\n[MAIN] Shutting down...")
    if _db:
        _db.close()
    sys.exit(0)


def main():
    global _db

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    _db = db_mod.DatabaseManager()

    print("[MAIN] Training Engine 1 gatekeeper...")
    model, threshold = e1.train_gatekeeper()

    print("[MAIN] Starting log generator in background thread...")
    gen_thread = threading.Thread(target=gen.run, args=(LOG_PATH,), daemon=True)
    gen_thread.start()

    print("[MAIN] Streaming live logs through Engine 1...")
    e1.stream(LOG_PATH, model, threshold, _db, _handle_anomaly)


if __name__ == "__main__":
    main()
