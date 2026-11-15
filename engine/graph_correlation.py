"""
Network correlation and risk analysis module.

Builds a directed financial and digital-footprint graph, identifies
high-risk account communities, traces multi-hop fund-flow paths,
and ranks potential network controllers using graph centrality,
PageRank, connectivity, and shared digital attributes.
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone


import networkx as nx
import pandas as pd

DATA_DIR = "data"
OUTPUT_DIR = "outputs"

ENTITIES_FILE = os.path.join(DATA_DIR, "entities.csv")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.csv")
LINKS_FILE = os.path.join(DATA_DIR, "links.csv")

GRAPH_JSON_FILE = os.path.join(OUTPUT_DIR, "network_graph.json")
NETWORK_COMMUNITIES_FILE = os.path.join(OUTPUT_DIR, "network_communities.json")
SUSPECTS_FILE = os.path.join(OUTPUT_DIR, "network_controller_candidates.json")
FUND_PATHS_FILE = os.path.join(OUTPUT_DIR, "fund_flow_analysis.json")

def load_inputs():
    entities = pd.read_csv(ENTITIES_FILE)
    transactions = pd.read_csv(TRANSACTIONS_FILE)
    links = pd.read_csv(LINKS_FILE)

    return entities, transactions, links

def create_analysis_metadata(graph, transactions, links):
    return {
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "transaction_count": len(transactions),
        "digital_link_count": len(links),
        "method": "Graph-based network correlation and risk analysis"
    }


def normalize_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip().lower()


def parse_timestamp(value):
    timestamp = pd.to_datetime(value, errors="coerce", utc=True)

    if pd.isna(timestamp):
        return None

    return timestamp


def build_graph(entities, transactions, links):
    graph = nx.DiGraph()

    for _, entity in entities.iterrows():
        entity_id = str(entity["entity_id"])

        graph.add_node(
            entity_id,
            label=str(entity.get("label", entity_id)),
            type=normalize_text(entity.get("type", "unknown")),
            role=normalize_text(entity.get("role", "unknown")),
            value=str(entity.get("value", "")),
            node_kind="entity"
        )

    for _, transaction in transactions.iterrows():
        source = str(transaction["from_acct"])
        target = str(transaction["to_acct"])
        amount = float(transaction.get("amount", 0) or 0)
        timestamp = parse_timestamp(transaction.get("timestamp"))

        for account in [source, target]:
            if account not in graph:
                graph.add_node(
                    account,
                    label=account,
                    type="account",
                    role="unknown",
                    value=account,
                    node_kind="entity"
                )

        edge_data = {
            "edge_kind": "TRANSFERRED",
            "amount": amount,
            "transaction_count": 1,
            "timestamps": [timestamp.isoformat() if timestamp else ""],
            "channel": str(transaction.get("channel", "")),
            "evidence_refs": [str(transaction.get("transaction_id", ""))]
        }

        if graph.has_edge(source, target):
            existing = graph[source][target]
            existing["amount"] += amount
            existing["transaction_count"] += 1
            existing["timestamps"].append(
                timestamp.isoformat() if timestamp else ""
            )
            existing["evidence_refs"].extend(
                edge_data["evidence_refs"]
            )
        else:
            graph.add_edge(source, target, **edge_data)

    for _, link in links.iterrows():
        entity_a = str(link["entity_a"])
        entity_b = str(link["entity_b"])
        link_type = normalize_text(link.get("link_type", "linked"))
        evidence_ref = str(link.get("evidence_ref", ""))

        for entity in [entity_a, entity_b]:
            if entity not in graph:
                graph.add_node(
                    entity,
                    label=entity,
                    type="entity",
                    role="unknown",
                    value=entity,
                    node_kind="entity"
                )

        if graph.has_edge(entity_a, entity_b):
            existing = graph[entity_a][entity_b]

            if link_type not in existing.get("link_types", []):
                existing.setdefault("link_types", []).append(link_type)

            existing["evidence_refs"].append(evidence_ref)
        else:
            graph.add_edge(
                entity_a,
                entity_b,
                edge_kind="DIGITAL_LINK",
                link_types=[link_type],
                evidence_refs=[evidence_ref],
                amount=0,
                transaction_count=0,
                timestamps=[]
            )

    return graph


def calculate_financial_metrics(graph, transactions):
    inflow = defaultdict(float)
    outflow = defaultdict(float)
    incoming_count = defaultdict(int)
    outgoing_count = defaultdict(int)
    unique_senders = defaultdict(set)
    unique_receivers = defaultdict(set)

    for _, transaction in transactions.iterrows():
        source = str(transaction["from_acct"])
        target = str(transaction["to_acct"])
        amount = float(transaction.get("amount", 0) or 0)

        outflow[source] += amount
        inflow[target] += amount

        incoming_count[target] += 1
        outgoing_count[source] += 1

        unique_senders[target].add(source)
        unique_receivers[source].add(target)

    metrics = {}

    for node in graph.nodes:
        node_inflow = inflow[node]
        node_outflow = outflow[node]

        pass_through_ratio = (
            node_outflow / node_inflow
            if node_inflow > 0
            else 0
        )

        metrics[node] = {
            "inflow": round(node_inflow, 2),
            "outflow": round(node_outflow, 2),
            "pass_through_ratio": round(pass_through_ratio, 4),
            "incoming_count": incoming_count[node],
            "outgoing_count": outgoing_count[node],
            "unique_senders": len(unique_senders[node]),
            "unique_receivers": len(unique_receivers[node])
        }

    return metrics


def calculate_velocity(graph, transactions, window_minutes=30):
    account_transactions = defaultdict(list)

    for _, transaction in transactions.iterrows():
        timestamp = parse_timestamp(transaction.get("timestamp"))

        if timestamp is None:
            continue

        source = str(transaction["from_acct"])
        target = str(transaction["to_acct"])
        amount = float(transaction.get("amount", 0) or 0)

        account_transactions[source].append({
            "timestamp": timestamp,
            "direction": "out",
            "amount": amount,
            "counterparty": target
        })

        account_transactions[target].append({
            "timestamp": timestamp,
            "direction": "in",
            "amount": amount,
            "counterparty": source
        })

    velocity_results = {}

    for account, records in account_transactions.items():
        records.sort(key=lambda record: record["timestamp"])

        rapid_transfers = 0
        rapid_amount = 0.0

        for index, incoming in enumerate(records):
            if incoming["direction"] != "in":
                continue

            for outgoing in records[index + 1:]:
                time_difference = (
                    outgoing["timestamp"] - incoming["timestamp"]
                ).total_seconds() / 60

                if time_difference < 0:
                    continue

                if time_difference <= window_minutes:
                    rapid_transfers += 1
                    rapid_amount += outgoing["amount"]

        velocity_results[account] = {
            "rapid_outgoing_transfers": rapid_transfers,
            "rapid_outgoing_amount": round(rapid_amount, 2),
            "velocity_window_minutes": window_minutes
        }

    return velocity_results


def calculate_account_risk_score(metrics, velocity_results):
    scores = {}
    reasons = {}

    for node, values in metrics.items():
        velocity = velocity_results.get(node, {})

        unique_sender_score = min(values["unique_senders"] / 3, 1)
        transaction_count_score = min(values["incoming_count"] / 3, 1)
        pass_through_score = min(values["pass_through_ratio"], 1)
        velocity_score = min(
            velocity.get("rapid_outgoing_transfers", 0) / 3,
            1
        )

        score = (
            unique_sender_score * 0.30
            + transaction_count_score * 0.20
            + pass_through_score * 0.30
            + velocity_score * 0.20
        )

        node_reasons = []

        if values["unique_senders"] >= 2:
            node_reasons.append(
                f"Received funds from {values['unique_senders']} unique senders"
            )

        if values["pass_through_ratio"] >= 0.8:
            node_reasons.append(
                f"High pass-through ratio: {values['pass_through_ratio']:.0%}"
            )

        if velocity.get("rapid_outgoing_transfers", 0) >= 1:
            node_reasons.append(
                "Rapid onward transfer detected within "
                f"{velocity['velocity_window_minutes']} minutes"
            )

        if values["incoming_count"] >= 2:
            node_reasons.append(
                f"Received {values['incoming_count']} incoming transactions"
            )

        scores[node] = round(score, 4)
        reasons[node] = node_reasons

    return scores, reasons


def calculate_network_controller_score(graph, account_risk_scores, metrics, velocity_results):
    betweenness = nx.betweenness_centrality(graph)
    pagerank = nx.pagerank(graph, alpha=0.85)

    network_controller_scores = {}
    network_controller_reasons = {}

    for node in graph.nodes:
        connected_high_risk_accounts = 0

        for neighbor in graph.neighbors(node):
            if account_risk_scores.get(neighbor, 0) >= 0.6:
                connected_high_risk_accounts += 1

        digital_link_count = 0
        digital_link_types = set()

        for _, _, data in graph.edges(node, data=True):
            if data.get("edge_kind") == "DIGITAL_LINK":
                digital_link_count += 1
                digital_link_types.update(data.get("link_types", []))

        score = (
            min(connected_high_risk_accounts / 3, 1) * 0.35
            + min(digital_link_count / 4, 1) * 0.25
            + min(betweenness.get(node, 0) * 10, 1) * 0.20
            + min(pagerank.get(node, 0) * 20, 1) * 0.20
        )

        reasons = []

        if connected_high_risk_accounts >= 2:
            reasons.append(
                f"Connected to {connected_high_risk_accounts} high-risk accounts"
            )

        if digital_link_count >= 2:
            reasons.append(
                f"Linked through {digital_link_count} digital-footprint connections"
            )

        if betweenness.get(node, 0) >= 0.1:
            reasons.append(
                "Acts as a bridge between different parts of the network"
            )

        if pagerank.get(node, 0) >= 0.05:
            reasons.append(
                "Has high influence in the transaction network"
            )

        network_controller_scores[node] = {
            "controller_score": round(score, 4),
            "connected_high_risk_accounts": connected_high_risk_accounts,
            "digital_link_count": digital_link_count,
            "digital_link_types": sorted(digital_link_types),
            "betweenness": round(betweenness.get(node, 0), 4),
            "pagerank": round(pagerank.get(node, 0), 4),
            "account_risk_score": account_risk_scores.get(node, 0),
            "financial_metrics": metrics.get(node, {}),
            "velocity_metrics": velocity_results.get(node, {}),
            "score_components": {
                "high_risk_connection_component": round(
                    min(connected_high_risk_accounts / 3, 1) * 0.35,
                    4
                ),
                "digital_link_component": round(
                    min(digital_link_count / 4, 1) * 0.25,
                    4
                ),
                "betweenness_component": round(
                    min(betweenness.get(node, 0) * 10, 1) * 0.20,
                    4
                ),
                "pagerank_component": round(
                    min(pagerank.get(node, 0) * 20, 1) * 0.20,
                    4
                )
            }        
        }

        network_controller_reasons[node] = reasons

    return network_controller_scores, network_controller_reasons


def detect_network_communities(graph, account_risk_scores):
    undirected_graph = graph.to_undirected()

    communities = nx.community.louvain_communities(
        undirected_graph,
        resolution=1.0,
        seed=42
    )

    network_communities = []
    isolated_accounts = []

    for cluster_id, members in enumerate(communities):
        member_list = sorted(members)

        if len(member_list) <= 1:
            isolated_accounts.extend(member_list)
            continue

        cluster_scores = [
            account_risk_scores.get(member, 0)
            for member in member_list
        ]

        average_score = (
            sum(cluster_scores) / len(cluster_scores)
            if cluster_scores
            else 0
        )

        high_risk_members = [
            member
            for member in member_list
            if account_risk_scores.get(member, 0) >= 0.6
        ]

        digital_links = 0

        for member in member_list:
            for _, _, edge_data in graph.edges(member, data=True):
                if edge_data.get("edge_kind") == "DIGITAL_LINK":
                    digital_links += 1

        network_communities.append({
            "cluster_id": cluster_id,
            "members": member_list,
            "size": len(member_list),
            "average_account_risk_score": round(average_score, 4),
            "high_risk_members": high_risk_members,
            "digital_link_count": digital_links,
            "risk_level": (
                "high"
                if average_score >= 0.6
                else "medium"
                if average_score >= 0.35
                else "low"
            )
        })

    network_communities.sort(
        key=lambda community: community["average_account_risk_score"],
        reverse=True
    )

    return {
        "network_communities": network_communities,
        "isolated_accounts": isolated_accounts
    }

def detect_circular_fund_flows(graph):
    cycles = []

    try:
        found_cycles = list(nx.simple_cycles(graph))

        for cycle in found_cycles:
            if 2 <= len(cycle) <= 8:
                total_amount = 0

                for index in range(len(cycle)):
                    source = cycle[index]
                    target = cycle[(index + 1) % len(cycle)]

                    if graph.has_edge(source, target):
                        total_amount += graph[source][target].get(
                            "amount", 0
                        )

                cycles.append({
                    "cycle": cycle,
                    "hops": len(cycle),
                    "total_amount": round(total_amount, 2),
                    "layering_risk": (
                        "high"
                        if len(cycle) >= 3
                        else "medium"
                    )
                })

    except Exception:
        cycles = []

    cycles.sort(key=lambda cycle: cycle["hops"], reverse=True)

    return cycles[:10]

def trace_fund_flow_paths(graph, source_account, target_account, max_hops=8):
    if source_account not in graph or target_account not in graph:
        return []

    paths = []

    try:
        simple_paths = nx.all_simple_paths(
            graph,
            source=source_account,
            target=target_account,
            cutoff=max_hops
        )

        for path in simple_paths:
            total_amount = 0
            transfer_hops = 0
            hop_details = []

            for index in range(len(path) - 1):
                edge = graph[path[index]][path[index + 1]]


                if edge.get("edge_kind") == "TRANSFERRED":
                    transfer_hops += 1
                    total_amount += edge.get("amount", 0)


                    hop_details.append({
                        "from_account": path[index],
                        "to_account": path[index + 1],
                        "amount": edge.get("amount", 0),
                        "transaction_count": edge.get("transaction_count", 0),
                        "timestamps": edge.get("timestamps", []),
                        "channel": edge.get("channel", ""),
                        "evidence_refs": edge.get("evidence_refs", [])
                    })

            if transfer_hops == 0:
                continue

            paths.append({
                "source": source_account,
                "target": target_account,
                "path": path,
                "transfer_hops": transfer_hops,
                "total_amount": round(total_amount, 2),
                "hop_details": hop_details,
                "layering_risk": (
                    "high"
                    if transfer_hops >= 4
                    else "medium"
                    if transfer_hops >= 2
                    else "low"
                )
            })

    except nx.NetworkXNoPath:
        return []

    paths.sort(key=lambda path: path["transfer_hops"], reverse=True)

    return paths[:10]


def identify_priority_fund_flow_paths(graph, transactions, max_paths=10):
    account_amounts = defaultdict(float)

    for _, transaction in transactions.iterrows():
        source = str(transaction["from_acct"])
        amount = float(transaction.get("amount", 0) or 0)

        account_amounts[source] += amount

    top_sources = sorted(
        account_amounts.items(),
        key=lambda item: item[1],
        reverse=True
    )[:5]

    top_targets = sorted(
        account_amounts.items(),
        key=lambda item: item[1],
        reverse=True
    )[:5]

    paths = []

    for source, _ in top_sources:
        for target, _ in top_targets:
            if source == target:
                continue

            paths.extend(
                trace_fund_flow_paths(
                    graph,
                    source,
                    target,
                    max_hops=8
                )
            )

    paths.sort(
        key=lambda path: (
            path["transfer_hops"],
            path["total_amount"]
        ),
        reverse=True
    )

    return paths[:max_paths]


def export_results(
    graph,
    account_risk_scores,
    account_risk_reasons,
    network_controller_scores,
    network_controller_reasons,
    network_communities,
    circular_fund_flows,
    fund_paths,
    analysis_metadata
):
    nodes = []

    for node, data in graph.nodes(data=True):
        cluster_id = next(
            (
                cluster["cluster_id"]
                for cluster in network_communities
                if node in cluster["members"]
            ),
            None
        )

        nodes.append({
            "id": node,
            "label": data.get("label", node),
            "type": data.get("type", "unknown"),
            "role": data.get("role", "unknown"),
            "value": data.get("value", ""),
            "account_risk_score": account_risk_scores.get(node, 0),
            "account_risk_reasons": account_risk_reasons.get(node, []),
            "controller_score": network_controller_scores.get(node, {}).get(
                "controller_score", 0
            ),
            "network_controller_reasons": network_controller_reasons.get(node, []),
            "cluster_id": cluster_id
        })

    edges = []

    for source, target, data in graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "edge_kind": data.get("edge_kind", "LINK"),
            "amount": data.get("amount", 0),
            "transaction_count": data.get("transaction_count", 0),
            "link_types": data.get("link_types", []),
            "evidence_refs": data.get("evidence_refs", [])
        })

    graph_output = {
    "analysis_metadata": analysis_metadata,
    "nodes": nodes,
    "edges": edges
}

    with open(GRAPH_JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(graph_output, file, indent=2)

    with open(NETWORK_COMMUNITIES_FILE, "w", encoding="utf-8") as file:
        json.dump(network_communities, file, indent=2)
   
    controller_candidates = sorted(
        network_controller_scores.items(),
        key=lambda item: item[1]["controller_score"],
        reverse=True
    )

    controller_candidates_output = []

    for node, values in controller_candidates:
        controller_candidates_output.append({
            "entity_id": node,
            "label": graph.nodes[node].get("label", node),
            "role": graph.nodes[node].get("role", "unknown"),
            **values,
            "network_controller_reasons": network_controller_reasons.get(node, [])
        })

    with open(SUSPECTS_FILE, "w", encoding="utf-8") as file:
        json.dump(controller_candidates_output, file, indent=2)

    with open(FUND_PATHS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {
                "circular_fund_flows": circular_fund_flows,
                "fund_flow_paths": fund_paths
            },
            file,
            indent=2
        )

def run_network_correlation_analysis():
    entities, transactions, links = load_inputs()

    graph = build_graph(entities, transactions, links)

    analysis_metadata = create_analysis_metadata(
        graph,
        transactions,
        links
    )

    metrics = calculate_financial_metrics(graph, transactions)
    velocity_results = calculate_velocity(graph, transactions)

    account_risk_scores, account_risk_reasons = calculate_account_risk_score(
        metrics,
        velocity_results
    )

    network_controller_scores, network_controller_reasons = calculate_network_controller_score(
        graph,
        account_risk_scores,
        metrics,
        velocity_results
    )
    community_results = detect_network_communities(
        graph,
        account_risk_scores
    )

    network_communities = community_results["network_communities"]
    isolated_accounts = community_results["isolated_accounts"]

    circular_fund_flows = detect_circular_fund_flows(graph)
    fund_paths = identify_priority_fund_flow_paths(graph, transactions)

    export_results(
        graph,
        account_risk_scores,
        account_risk_reasons,
        network_controller_scores,
        network_controller_reasons,
        network_communities,
        circular_fund_flows,
        fund_paths,
        analysis_metadata
    )

    return {
    "graph": graph,
    "account_risk_scores": account_risk_scores,
    "account_risk_reasons": account_risk_reasons,
    "network_controller_scores": network_controller_scores,
    "network_controller_reasons": network_controller_reasons,
    "network_communities": network_communities,
    "isolated_accounts": isolated_accounts,
    "circular_fund_flows": circular_fund_flows,
    "fund_paths": fund_paths
}


if __name__ == "__main__":
    result = run_network_correlation_analysis()

    print("Network correlation analysis completed.")
    print(f"Nodes: {result['graph'].number_of_nodes()}")
    print(f"Edges: {result['graph'].number_of_edges()}")
    print(f"Communities: {len(result['network_communities'])}")
    print(f"Circular fund flows: {len(result['circular_fund_flows'])}")
    print(f"Fund-flow paths: {len(result['fund_paths'])}")
    print(f"Graph export: {GRAPH_JSON_FILE}")
    print(f"Community export: {NETWORK_COMMUNITIES_FILE}")
    print(f"Controller ranking: {SUSPECTS_FILE}")
    print(f"Fund-flow analysis: {FUND_PATHS_FILE}")