import os
import json
import pandas as pd

RAW_DIR = "evidence_data"
OUT_DIR = "data"

os.makedirs(OUT_DIR, exist_ok=True)

NAME_MAP = {
    "Amit S.": "Amit Sharma",
    "Priya": "Priya Patel",
    "amit_s": "Amit Sharma",
    "rkumar": "Rajesh Kumar",
    "ppatel": "Priya Patel"
}

entities = []
transactions = []
events = []
links = []

entity_index = {}


def clean_name(value):
    value = str(value).strip()
    return NAME_MAP.get(value, value)


def get_entity_id(entity_type, value, label=None, source_doc="", role="unknown", location=""):
    key = (entity_type, value)

    if key in entity_index:
        return entity_index[key]

    entity_id = f"E{len(entity_index) + 1:03d}"
    entity_index[key] = entity_id

    entities.append({
        "entity_id": entity_id,
        "type": entity_type,
        "value": value,
        "label": label or value,
        "source_doc": source_doc,
        "role": role,
        "location": location
    })

    return entity_id


# Convert bank/UPI transactions
bank_path = os.path.join(RAW_DIR, "bank_upi_transactions.csv")

if os.path.exists(bank_path):
    bank = pd.read_csv(bank_path)

    for _, row in bank.iterrows():
        sender = clean_name(row["sender_name"])
        receiver = clean_name(row["receiver_name"])

        sender_account_id = get_entity_id(
            "account",
            f"ACCT-{sender.replace(' ', '').upper()}",
            f"{sender} Account",
            "bank_upi_transactions.csv"
        )

        receiver_account_id = get_entity_id(
            "account",
            f"ACCT-{receiver.replace(' ', '').upper()}",
            f"{receiver} Account",
            "bank_upi_transactions.csv"
        )

        txn_id = row["transaction_id"]
        timestamp = str(row["timestamp"])
        amount = float(row["amount"])
        channel = str(row["payment_mode"]).lower()
        status = str(row["status"])

        transactions.append({
            "txn_id": txn_id,
            "from_acct": sender_account_id,
            "to_acct": receiver_account_id,
            "amount": amount,
            "timestamp": timestamp,
            "channel": channel,
            "location": "",
            "source_doc": "bank_upi_transactions.csv"
        })

        events.append({
            "event_id": f"EV-{txn_id}",
            "timestamp": timestamp,
            "type": "payment",
            "entity_id": receiver_account_id,
            "description": f"{sender} sent INR {amount} to {receiver} via {channel}; status {status}",
            "source_doc": "bank_upi_transactions.csv",
            "location": ""
        })

        if status == "FAILED" or sender == "Unknown Sender":
            events.append({
                "event_id": f"EV-{txn_id}-FLAG",
                "timestamp": timestamp,
                "type": "complaint",
                "entity_id": sender_account_id,
                "description": f"Flagged transaction: {status}; sender {sender}",
                "source_doc": "bank_upi_transactions.csv",
                "location": ""
            })


# Convert chat messages
chat_path = os.path.join(RAW_DIR, "chat_export.json")

if os.path.exists(chat_path):
    with open(chat_path, "r", encoding="utf-8") as file:
        chats = json.load(file)

    for i, message in enumerate(chats, start=1):
        sender = clean_name(message["sender"])
        sender_id = get_entity_id(
            "person",
            sender,
            sender,
            "chat_export.json"
        )

        events.append({
            "event_id": f"EV-CHAT-{i:03d}",
            "timestamp": str(message["timestamp"]),
            "type": "chat",
            "entity_id": sender_id,
            "description": message["message"],
            "source_doc": f"chat_export.json#{i}",
            "location": ""
        })


# Convert IP logs
ip_path = os.path.join(RAW_DIR, "ip_logs.csv")

if os.path.exists(ip_path):
    ip_logs = pd.read_csv(ip_path)

    for i, row in ip_logs.iterrows():
        person = clean_name(row["username"])
        ip_value = str(row["ip_address"])
        timestamp = str(row["timestamp"])

        person_id = get_entity_id(
            "person",
            person,
            person,
            "ip_logs.csv"
        )

        ip_id = get_entity_id(
            "ip",
            ip_value,
            ip_value,
            "ip_logs.csv"
        )

        events.append({
            "event_id": f"EV-IP-{i + 1:03d}",
            "timestamp": timestamp,
            "type": "device_login",
            "entity_id": ip_id,
            "description": f"{person} logged in from {ip_value} using {row['device_os']}",
            "source_doc": f"ip_logs.csv#{i + 2}",
            "location": ""
        })

        links.append({
            "link_id": f"L{len(links) + 1:03d}",
            "entity_a": person_id,
            "entity_b": ip_id,
            "link_type": "same_ip",
            "evidence_ref": f"ip_logs.csv#{i + 2}",
            "confidence": 0.95
        })


# Convert CCTV data
cctv_path = os.path.join(RAW_DIR, "cctv_metadata.csv")

if os.path.exists(cctv_path):
    cctv = pd.read_csv(cctv_path)

    for i, row in cctv.iterrows():
        camera_id = str(row["camera_id"])

        camera_id_entity = get_entity_id(
            "device",
            camera_id,
            camera_id,
            "cctv_metadata.csv",
            role="unknown",
            location=str(row["location"])
        )

        events.append({
            "event_id": f"EV-CCTV-{i + 1:03d}",
            "timestamp": str(row["timestamp"]),
            "type": "complaint",
            "entity_id": camera_id_entity,
            "description": (
                f"{row['detected_activity']} at {row['location']} "
                f"(confidence {row['confidence_score']})"
            ),
            "source_doc": f"cctv_metadata.csv#{i + 2}",
            "location": str(row["location"])
        })


# Save the four standard files
pd.DataFrame(entities).to_csv(
    os.path.join(OUT_DIR, "entities.csv"),
    index=False
)

pd.DataFrame(transactions).to_csv(
    os.path.join(OUT_DIR, "transactions.csv"),
    index=False
)

pd.DataFrame(events).to_csv(
    os.path.join(OUT_DIR, "events.csv"),
    index=False
)

pd.DataFrame(links).to_csv(
    os.path.join(OUT_DIR, "links.csv"),
    index=False
)

print("Conversion complete")
print(f"Entities: {len(entities)}")
print(f"Transactions: {len(transactions)}")
print(f"Events: {len(events)}")
print(f"Links: {len(links)}")