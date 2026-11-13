# Fraud Link Analysis MVP

A Streamlit-based investigation support tool that connects evidence from multiple sources, identifies potentially related entities, ranks suspicious accounts, and presents an explainable timeline for investigator review.

**Important:** All data used in this project is fully synthetic and generated for demonstration purposes. No real personal, banking, or case data is used.

## Demo Flow

1. Load the synthetic demo case.
2. Review case overview and suspicious account leads.
3. Inspect the transaction and evidence network.
4. Review the chronological event timeline.
5. Open evidence for a selected entity.
6. Accept or reject an investigative lead.

## Project Structure

```text
fraud-mvp/
├── evidence_data/       # Raw synthetic evidence files
├── data/                # Standardized entities, transactions, events, and links
├── engine/              # Entity resolution, scoring, and sequence analysis
├── ui/                  # Streamlit application
├── outputs/             # Generated visual outputs
├── create_sample_evidence.py
└── requirements.txt
```

## How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Generate synthetic evidence:

```bash
python create_sample_evidence.py
```

3. Convert evidence into the standard schema:

```bash
python engine/convert_a_data.py
```

4. Run the Streamlit app:

```bash
streamlit run ui/app.py
```

5. Open the local URL shown in the terminal, usually:

```text
http://localhost:8501
```

## Data Schema

The application uses four standardized CSV files:

- `entities.csv`: people, accounts, UPI IDs, phones, devices, IPs, and groups
- `transactions.csv`: money transfers between accounts
- `events.csv`: complaints, payments, transfers, withdrawals, chats, and device logins
- `links.csv`: evidence-based connections such as shared IP, device, phone, or group

## Key Features

- Entity resolution using fuzzy name matching and shared attributes
- Transparent rule-based mule-account scoring
- Chronological event timeline
- Evidence-linked network view
- Investigator accept/reject workflow
- Audit-style decision logging

## Governance Principle

The system does not make final decisions. It surfaces evidence-backed leads, explains why an entity is suspicious, and allows an investigator to accept or reject the lead. Every result points back to its source document.