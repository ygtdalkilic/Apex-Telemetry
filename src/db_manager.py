import os
# pyrefly: ignore [missing-import]
import pymongo


class DatabaseManager:
    def __init__(self):
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        try:
            self.client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.client.server_info()
            db = self.client["apex_telemetry"]
            self.raw_queue = db["raw_queue"]
            self.raw_logs = db["raw_logs"]
            self.safe_traffic = db["safe_traffic"]
            self.active_threats = db["active_threats"]
            print(f"[DB] Connected to {uri}")
        except pymongo.errors.ServerSelectionTimeoutError:
            print(f"[DB] Could not connect to MongoDB at {uri}. Is mongod running?")
            raise

    def insert_one(self, collection, document):
        try:
            collection.insert_one(document)
        except pymongo.errors.PyMongoError as e:
            print(f"[DB] Insert failed: {e}")

    def insert_many(self, collection, documents):
        if not documents:
            return
        try:
            collection.insert_many(documents)
        except pymongo.errors.PyMongoError as e:
            print(f"[DB] Batch insert failed: {e}")

    def close(self):
        self.client.close()
        print("[DB] Connection closed.")
