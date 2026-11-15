import json
import os
import csv
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
from pyvis.network import Network
from datetime import datetime
from engine.graph_correlation import run_network_correlation_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

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
AUDIT_FILE = "outputs/audit_log.csv"


os.makedirs(OUTPUT_DIR, exist_ok=True)


st.sidebar.title("Case controls")


role = st.sidebar.selectbox(
    "Select role",
    ["Investigator", "Supervisor", "Auditor"]
)


if st.sidebar.button("Load demo case"):
    st.session_state["loaded"] = True
    st.sidebar.success("Demo case loaded. You can now review transactions and analyze the network.")    


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
page = st.sidebar.radio(
    "Navigation",
    [
        "Transaction Review",
        "Network Correlation Analysis"
    ],
    key="main_navigation"
)


if data is None:
    data = {
        "entities": pd.DataFrame(),
        "transactions": pd.DataFrame(),
        "events": pd.DataFrame(),
        "links": pd.DataFrame()
    }
def render_transaction_review_page():
    entities = data["entities"]
    transactions = data["transactions"]
    events = data["events"]
    links = data["links"]

    if (
        entities.empty
        or "type" not in entities.columns
        or transactions.empty
    ):
        st.info(
            "Click **Load demo case** in the left sidebar or upload "
            "the required CSV files to view transaction review."
        )
        return

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
            source = str(transaction["from_acct"])
            target = str(transaction["to_acct"])

            for node_id in [source, target]:
                if node_id not in graph.get_nodes():
                    graph.add_node(
                        node_id,
                        label=node_id,
                        color="#8993A4",
                        title=(
                            f"Type: account<br>"
                            f"Value: {node_id}<br>"
                            f"Role: unknown"
                        )
                    )

            graph.add_edge(
                source,
                target,
                title=(
                    f"Amount: INR {transaction['amount']}<br>"
                    f"Channel: {transaction['channel']}<br>"
                    f"Time: {transaction['timestamp']}"
                ),
                color="#FF5630"
            )


        for _, link in links.iterrows():
            entity_a = str(link["entity_a"])
            entity_b = str(link["entity_b"])

            for node_id in [entity_a, entity_b]:
                if node_id not in graph.get_nodes():
                    graph.add_node(
                        node_id,
                        label=node_id,
                        color="#8993A4",
                        title=(
                            f"Type: entity<br>"
                            f"Value: {node_id}<br>"
                            f"Role: unknown"
                        )
                    )

            graph.add_edge(
                entity_a,
                entity_b,
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
            audit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


            st.session_state["audit_log"].append({
                "time": audit_time,
                "user": role,
                "action": "Accepted lead",
                "entity": selected
            })


            with open(AUDIT_FILE, "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)


                if not os.path.exists(AUDIT_FILE) or os.path.getsize(AUDIT_FILE) == 0:
                    writer.writerow(["time", "user", "action", "entity"])


                writer.writerow([
                    audit_time,
                    role,
                    "Accepted lead",
                    selected
                ])


            st.success("Lead accepted and audit entry recorded.")


        if reject_column.button("Reject lead"):
            audit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


            st.session_state["audit_log"].append({
                "time": audit_time,
                "user": role,
                "action": "Rejected lead",
                "entity": selected
            })


            with open(AUDIT_FILE, "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)


                if not os.path.exists(AUDIT_FILE) or os.path.getsize(AUDIT_FILE) == 0:
                    writer.writerow(["time", "user", "action", "entity"])


                writer.writerow([
                    audit_time,
                    role,
                    "Rejected lead",
                    selected
                ])


            st.warning("Lead rejected and audit entry recorded.")


        if st.session_state["audit_log"]:
            st.write("### Audit log")


            st.dataframe(
                pd.DataFrame(st.session_state["audit_log"]),
                use_container_width=True
            )

def run_network_analysis():
    try:
        from engine.graph_correlation import (
            run_network_correlation_analysis
        )

        with st.spinner("Analyzing transaction network..."):
            result = run_network_correlation_analysis()

        st.success("Network correlation analysis completed.")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Nodes",
            result["graph"].number_of_nodes()
        )

        col2.metric(
            "Edges",
            result["graph"].number_of_edges()
        )

        col3.metric(
            "Communities",
            len(result["network_communities"])
        )

    except FileNotFoundError as error:
        st.error(
            "Required data file is missing. "
            "Please check the data folder."
        )
        st.exception(error)

    except Exception as error:
        st.error("Network correlation analysis failed.")
        st.exception(error)



    
def render_network_correlation_page():
    st.title("Network Correlation Analysis")
    st.write(
        "Analyze transaction and digital-footprint connections to identify "
        "high-risk account communities, network controllers, and fund-flow paths."
    )

    output_dir = "outputs"

    communities_file = os.path.join(
        output_dir,
        "network_communities.json"
    )

    controller_file = os.path.join(
        output_dir,
        "network_controller_candidates.json"
    )

    fund_paths_file = os.path.join(
        output_dir,
        "fund_flow_analysis.json"
    )

    if st.button("Run network correlation analysis"):
        run_network_analysis()

    st.divider()

    st.subheader("Account communities")

    if os.path.exists(communities_file):
        with open(communities_file, "r", encoding="utf-8") as file:
            communities = json.load(file)

        connected_communities = [
            community
            for community in communities
            if community["size"] > 1
        ]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Connected communities",
            len(connected_communities)
        )

        col2.metric(
            "Total communities",
            len(communities)
        )

        col3.metric(
            "High-risk communities",
            sum(
                1
                for community in communities
                if community["risk_level"] == "high"
            )
        )

        if connected_communities:
            st.dataframe(
                pd.DataFrame(connected_communities),
                use_container_width=True
            )
        else:
            st.info(
                "No connected account communities were detected."
            )
    else:
        st.warning(
            "Network community results are not available. "
            "Run the analysis first."
        )

    st.divider()

    st.subheader("Potential network controllers")

    if os.path.exists(controller_file):
        with open(controller_file, "r", encoding="utf-8") as file:
            controllers = json.load(file)

        if controllers:
            controller_rows = []

            for controller in controllers[:10]:
                controller_rows.append({
                    "Entity ID": controller.get("entity_id"),
                    "Label": controller.get("label"),
                    "Role": controller.get("role"),
                    "Controller score": controller.get(
                        "controller_score"
                    ),
                    "High-risk connections": controller.get(
                        "connected_high_risk_accounts"
                    ),
                    "Digital links": controller.get(
                        "digital_link_count"
                    ),
                    "Betweenness": controller.get(
                        "betweenness"
                    ),
                    "PageRank": controller.get(
                        "pagerank"
                    )
                })

            st.dataframe(
                pd.DataFrame(controller_rows),
                use_container_width=True
            )
        else:
            st.info(
                "No potential network controllers were identified."
            )
    else:
        st.warning(
            "Network controller results are not available. "
            "Run the analysis first."
        )

    st.divider()

    st.subheader("Fund-flow paths")

    if os.path.exists(fund_paths_file):
        with open(fund_paths_file, "r", encoding="utf-8") as file:
            fund_analysis = json.load(file)

        fund_paths = fund_analysis.get("fund_flow_paths", [])
        circular_flows = fund_analysis.get(
            "circular_fund_flows",
            []
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Fund-flow paths",
            len(fund_paths)
        )

        col2.metric(
            "Circular fund flows",
            len(circular_flows)
        )

        if fund_paths:
            path_rows = []

            for path in fund_paths:
                path_rows.append({
                    "Source": path.get("source"),
                    "Target": path.get("target"),
                    "Transfer hops": path.get(
                        "transfer_hops"
                    ),
                    "Total amount": path.get(
                        "total_amount"
                    ),
                    "Layering risk": path.get(
                        "layering_risk"
                    ),
                    "Path": " -> ".join(
                        path.get("path", [])
                    )
                })

            st.dataframe(
                pd.DataFrame(path_rows),
                use_container_width=True
            )
        else:
            st.info(
                "No multi-hop fund-flow paths were detected."
            )
    else:
        st.warning(
            "Fund-flow analysis results are not available. "
            "Run the analysis first."
        )

if page == "Transaction Review":
    render_transaction_review_page()

elif page == "Network Correlation Analysis":
    render_network_correlation_page() 