import os
import pandas as pd
import streamlit as st
import plotly.express as px
from pyvis.network import Network
from datetime import datetime


st.set_page_config(
    page_title="Fraud Link Analysis MVP",
    layout="wide"
)


st.title("Fraud Link Analysis MVP")
st.caption("Synthetic data. The system suggests; the investigator decides.")

st.warning(
    "All data shown is fully synthetic and generated for demonstration purposes. "
    "No real personal, banking, or case data is used."
)


DATA_DIR = "data"
OUTPUT_DIR = "outputs"

os.makedirs(OUTPUT_DIR, exist_ok=True)


st.sidebar.title("Case controls")

role = st.sidebar.selectbox(
    "Select role",
    ["Investigator", "Supervisor", "Auditor"]
)

if st.sidebar.button("Load demo case"):
    st.session_state["loaded"] = True


uploaded_files = st.sidebar.file_uploader(
    "Upload CSV files",
    accept_multiple_files=True,
    type=["csv"]
)


def load_data():
    if uploaded_files:
        data = {}

        for uploaded_file in uploaded_files:
            name = uploaded_file.name.lower()

            if "entities" in name:
                data["entities"] = pd.read_csv(uploaded_file)

            elif "transactions" in name:
                data["transactions"] = pd.read_csv(uploaded_file)

            elif "events" in name:
                data["events"] = pd.read_csv(uploaded_file)

            elif "links" in name:
                data["links"] = pd.read_csv(uploaded_file)

        return data

    if st.session_state.get("loaded"):
        return {
            "entities": pd.read_csv(f"{DATA_DIR}/entities.csv"),
            "transactions": pd.read_csv(f"{DATA_DIR}/transactions.csv"),
            "events": pd.read_csv(f"{DATA_DIR}/events.csv"),
            "links": pd.read_csv(f"{DATA_DIR}/links.csv")
        }

    return None


data = load_data()

if data is None:
    st.info("Click **Load demo case** in the left sidebar.")
    st.stop()


entities = data["entities"]
transactions = data["transactions"]
events = data["events"]
links = data["links"]


tab1, tab2, tab3, tab4 = st.tabs([
    "Overview",
    "Network",
    "Timeline",
    "Evidence"
])


with tab1:
    st.subheader("Case overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Entities", len(entities))
    col2.metric("Transactions", len(transactions))
    col3.metric("Events", len(events))
    col4.metric("Evidence links", len(links))

    st.subheader("Suspicious account leads")

    account_entities = entities[entities["type"] == "account"]
    results = []

    for _, account in account_entities.iterrows():
        account_id = account["entity_id"]

        incoming = transactions[transactions["to_acct"] == account_id]
        outgoing = transactions[transactions["from_acct"] == account_id]

        inflow = incoming["amount"].sum()
        outflow = outgoing["amount"].sum()

        unique_senders = incoming["from_acct"].nunique()

        score = (
            min(unique_senders / 2, 1) * 0.40
            + min(outflow / inflow if inflow else 0, 1) * 0.30
            + min(len(incoming) / 2, 1) * 0.30
        )

        reasons = []

        if unique_senders:
            reasons.append(
                f"Received from {unique_senders} sender(s)"
            )

        if inflow:
            reasons.append(
                f"Pass-through ratio: {outflow / inflow:.0%}"
            )

        results.append({
            "Account": account["label"],
            "Mule score": round(score, 2),
            "Money received": inflow,
            "Money sent": outflow,
            "Reasons": "; ".join(reasons)
        })

    scores = pd.DataFrame(results).sort_values(
        "Mule score",
        ascending=False
    )

    st.dataframe(scores, use_container_width=True)

    if not scores.empty:
        top_lead = scores.iloc[0]

        st.markdown("### Top investigative lead")

        st.metric(
            label=top_lead["Account"],
            value=top_lead["Mule score"],
            help="Transparent rule-based suspicion score"
        )

        st.info(top_lead["Reasons"])


with tab2:
    st.subheader("Transaction network")

    colors = {
        "victim": "#4C9AFF",
        "mule": "#FF5630",
        "recruiter": "#FFAB00",
        "onward": "#36B37E",
        "atm": "#6554C0",
        "unknown": "#8993A4"
    }

    graph = Network(
        height="600px",
        directed=True,
        bgcolor="#ffffff"
    )

    graph.barnes_hut()

    for _, entity in entities.iterrows():
        graph.add_node(
            entity["entity_id"],
            label=entity["label"],
            color=colors.get(entity["role"], "#8993A4"),
            title=(
                f"Type: {entity['type']}<br>"
                f"Value: {entity['value']}<br>"
                f"Role: {entity['role']}"
            )
        )

    for _, transaction in transactions.iterrows():
        graph.add_edge(
            transaction["from_acct"],
            transaction["to_acct"],
            title=(
                f"Amount: INR {transaction['amount']}<br>"
                f"Channel: {transaction['channel']}<br>"
                f"Time: {transaction['timestamp']}"
            ),
            color="#FF5630"
        )

    for _, link in links.iterrows():
        graph.add_edge(
            link["entity_a"],
            link["entity_b"],
            title=(
                f"Link type: {link['link_type']}<br>"
                f"Evidence: {link['evidence_ref']}"
            ),
            color="#4C9AFF",
            dashes=True
        )

    graph.save_graph(f"{OUTPUT_DIR}/network.html")

    with open(
        f"{OUTPUT_DIR}/network.html",
        "r",
        encoding="utf-8"
    ) as file:
        graph_html = file.read()

    st.components.v1.html(graph_html, height=620)


with tab3:
    st.subheader("Event timeline")

    timeline = events.copy()
    timeline["timestamp"] = pd.to_datetime(
        timeline["timestamp"],
        errors="coerce"
    )

    timeline = timeline.dropna(subset=["timestamp"])
    timeline = timeline.sort_values("timestamp")

    fig = px.scatter(
        timeline,
        x="timestamp",
        y="entity_id",
        color="type",
        hover_data=["description", "source_doc", "location"],
        title="Events over time"
    )

    st.plotly_chart(fig, use_container_width=True)


with tab4:
    st.subheader("Evidence and decision")

    selected = st.selectbox(
        "Select entity",
        entities["entity_id"].tolist(),
        format_func=lambda entity_id: entities[
            entities["entity_id"] == entity_id
        ]["label"].iloc[0]
    )

    entity_events = events[
        events["entity_id"] == selected
    ]

    entity_links = links[
        (links["entity_a"] == selected)
        | (links["entity_b"] == selected)
    ]

    st.write("### Events")
    st.dataframe(entity_events, use_container_width=True)

    st.write("### Evidence links")
    st.dataframe(entity_links, use_container_width=True)

    if "audit_log" not in st.session_state:
        st.session_state["audit_log"] = []

    accept_column, reject_column = st.columns(2)

    if accept_column.button("Accept lead"):
        st.session_state["audit_log"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": role,
            "action": "Accepted lead",
            "entity": selected
        })

        st.success("Lead accepted and audit entry recorded.")

    if reject_column.button("Reject lead"):
        st.session_state["audit_log"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": role,
            "action": "Rejected lead",
            "entity": selected
        })

        st.warning("Lead rejected and audit entry recorded.")

    if st.session_state["audit_log"]:
        st.write("### Audit log")

        st.dataframe(
            pd.DataFrame(st.session_state["audit_log"]),
            use_container_width=True
        )