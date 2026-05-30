import os
import re
import time
import tracemalloc
from datetime import datetime, timezone

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from log_generator import _normal_line
from db_manager import DatabaseManager

LOG_PATTERN = re.compile(
    r'(?P<ip>[\d.]+) .+ \[.+\] "(?P<method>\w+) (?P<path>\S+) HTTP/\S+" (?P<status>\d+) (?P<size>\d+)'
)
METHOD_MAP = {"GET": 0, "POST": 1, "PUT": 2, "DELETE": 3, "PATCH": 4, "OPTIONS": 5, "HEAD": 6}

FEATURE_DIM = 6


def _parse(line):
    m = LOG_PATTERN.search(line)
    if not m:
        return None
    ip_parts = m["ip"].split(".")
    ip_norm = sum(int(o) / 255.0 * (1 / (i + 1)) for i, o in enumerate(ip_parts))
    method = METHOD_MAP.get(m["method"], 9) / 9.0
    status = int(m["status"]) / 599.0
    size = min(int(m["size"]), 500_000) / 500_000.0
    path_len = min(len(m["path"]), 500) / 500.0
    has_injection = 1.0 if any(c in m["path"] for c in ["'", "<", ">", "etc", "admin"]) else 0.0
    return [ip_norm, method, status, size, path_len, has_injection]


class Autoencoder(nn.Module):
    def __init__(self, input_dim=FEATURE_DIM):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 4),
        )
        self.decoder = nn.Sequential(
            nn.Linear(4, 8),
            nn.ReLU(),
            nn.Linear(8, 16),
            nn.ReLU(),
            nn.Linear(16, input_dim),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


def train_gatekeeper(n_samples=1000, epochs=50, threshold_percentile=95):
    samples = [_parse(_normal_line()) for _ in range(n_samples)]
    samples = [s for s in samples if s]

    X = torch.tensor(samples, dtype=torch.float32)
    dataset = TensorDataset(X)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    model = Autoencoder()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for (batch,) in loader:
            optimizer.zero_grad()
            reconstructed = model(batch)
            loss = criterion(reconstructed, batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 10 == 0:
            print(f"[E1] Epoch {epoch + 1}/{epochs} — loss: {total_loss / len(loader):.6f}")

    model.eval()
    with torch.no_grad():
        recon = model(X)
        errors = ((recon - X) ** 2).mean(dim=1).numpy()

    threshold = float(torch.tensor(errors).quantile(threshold_percentile / 100))
    print(f"[E1] Autoencoder trained. Anomaly threshold (p{threshold_percentile}): {threshold:.6f}")
    return model, threshold


def stream(log_path, model, threshold, db: DatabaseManager, anomaly_handler):
    tracemalloc.start()
    processed = safe = flagged = 0
    start = time.time()

    model.eval()

    while not os.path.exists(log_path):
        time.sleep(0.1)

    with open(log_path, "r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.05)
                continue

            line = line.strip()
            if not line:
                continue

            features = _parse(line)
            processed += 1

            if features is None:
                continue

            x = torch.tensor([features], dtype=torch.float32)
            with torch.no_grad():
                recon = model(x)
                error = ((recon - x) ** 2).mean().item()

            ts = datetime.now(timezone.utc).isoformat()

            if error <= threshold:
                safe += 1
                db.insert_one(db.safe_traffic, {"raw": line, "recon_error": error, "ts": ts})
            else:
                flagged += 1
                db.insert_one(db.active_threats, {"raw": line, "recon_error": error, "ts": ts})
                anomaly_handler(line)

            if processed % 50 == 0:
                mem_mb = tracemalloc.get_traced_memory()[1] / 1024 / 1024
                elapsed = time.time() - start
                print(f"[E1] processed={processed} safe={safe} flagged={flagged} "
                      f"rate={processed / elapsed:.1f}/s mem_peak={mem_mb:.2f}MB")


def process_queue(model, threshold, db: DatabaseManager, anomaly_handler, batch_size=100):
    """Drain raw_queue documents deposited by the AI agent."""
    model.eval()
    processed = safe = flagged = 0

    while True:
        docs = list(db.raw_queue.find({"processed": False}).limit(batch_size))
        if not docs:
            break

        ids = [d["_id"] for d in docs]

        for doc in docs:
            signals = doc.get("signals", {})
            ip = signals["ips"][0] if signals.get("ips") else "0.0.0.0"
            status = 500 if signals.get("has_exploit") else 200
            size = signals.get("length", 0)
            synthetic_log = f'{ip} - - [agent] "GET {doc.get("url", "/")} HTTP/1.1" {status} {size}'

            features = _parse(synthetic_log)
            processed += 1
            if features is None:
                continue

            x = torch.tensor([features], dtype=torch.float32)
            with torch.no_grad():
                recon = model(x)
                error = ((recon - x) ** 2).mean().item()

            ts = datetime.now(timezone.utc).isoformat()
            record = {"raw": synthetic_log, "source_url": doc.get("url"), "recon_error": error, "ts": ts}

            if error <= threshold:
                safe += 1
                db.insert_one(db.safe_traffic, record)
            else:
                flagged += 1
                db.insert_one(db.active_threats, record)
                anomaly_handler(synthetic_log)

        db.raw_queue.update_many({"_id": {"$in": ids}}, {"$set": {"processed": True}})
        print(f"[E1] Queue batch: processed={processed} safe={safe} flagged={flagged}")

    print(f"[E1] Queue drained. Total={processed} safe={safe} flagged={flagged}")
