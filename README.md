# Blockchain Dashboard Project

## Student Information

| Field              | Value                              |
| ------------------ | ---------------------------------- |
| Student Name       | Amaia Martín Grande                |
| GitHub Username    | amg00005                           |
| Project Title      | CryptoChain Analyzer Dashboard     |
| Chosen AI Approach | Anomaly Detector (Isolation Forest) |

## Module Tracking

| Module | What it should include  | Status      |
| ------ | ----------------------- | ----------- |
| M1     | Proof of Work Monitor   | Done        |
| M2     | Block Header Analyzer   | In progress |
| M3     | Difficulty History      | In progress |
| M4     | AI Component            | In progress |

## Current Progress

* M1 complete: live difficulty, hash vs target verification, inter-block time histogram with exponential baseline, hash rate estimation.
* First API call working: connects to Blockstream and prints block height, hash, difficulty, nonce, bits, and tx count.
* Dashboard running locally with Streamlit (`streamlit run app.py`).
* Modules M2, M3 and M4 scaffolded and partially implemented.

## Next Step

* Test and fix M2 (Block Header Analyzer) — verify SHA256(SHA256(header)) locally with hashlib.

## Main Problem or Blocker

* No blockers for now.

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```text
blockchain-dashboard-amg00005/
|-- README.md
|-- requirements.txt
|-- app.py
|-- api/
|   └── blockchain_client.py
└── modules/
    |-- m1_pow_monitor.py
    |-- m2_block_header.py
    |-- m3_difficulty_history.py
    └── m4_ai_component.py
```