import pandas as pd


def build_sequence(events, entity_id):
    entity_events = events[events["entity_id"] == entity_id].copy()
    entity_events["timestamp"] = pd.to_datetime(entity_events["timestamp"])

    return entity_events.sort_values("timestamp")


def detect_impossible_sequences(events):
    events = events.copy()
    events["timestamp"] = pd.to_datetime(events["timestamp"])
    events = events.sort_values("timestamp")

    problems = []

    for entity_id, group in events.groupby("entity_id"):
        withdrawals = group[group["type"] == "withdrawal"]
        transfers = group[group["type"] == "transfer"]

        for _, withdrawal in withdrawals.iterrows():
            earlier_transfers = transfers[
                transfers["timestamp"] < withdrawal["timestamp"]
            ]

            if earlier_transfers.empty:
                problems.append({
                    "entity_id": entity_id,
                    "timestamp": withdrawal["timestamp"],
                    "issue": "Withdrawal happened before any transfer",
                    "evidence_ref": withdrawal["source_doc"]
                })

    return pd.DataFrame(problems)