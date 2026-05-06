# Blockchain Dashboard Project

## Student Information

| Field              | Value                              |
| ------------------ | ---------------------------------- |
| Student Name       | Amaia MartÃ­n Grande                |
| GitHub Username    | amg00005                           |
| Project Title      | CryptoChain Analyzer Dashboard     |
| Chosen AI Approach | Anomaly Detector (Isolation Forest) |

## Module Tracking

| Module | What it should include  | Status |
| ------ | ----------------------- | ------ |
| M1     | Proof of Work Monitor   | Done   |
| M2     | Block Header Analyzer   | Done   |
| M3     | Difficulty History      | Done   |
| M4     | AI Component            | Done   |
| M6     | Security Score          | Done   |

## Current Progress

* M1 complete: live difficulty, hash vs target verification, inter-block time histogram with exponential baseline, hash rate estimation.
* M2 complete: 80-byte header parsed field by field, SHA256(SHA256(header)) verified with hashlib, bits decoded to 256-bit target, nonce space visualised, merkle root verified.
* M3 complete: difficulty evolution over adjustment periods, real/target block time ratio, % change per period, next adjustment estimate.
* M4 complete: Isolation Forest anomaly detector on inter-block times, 3 features, statistical z-score baseline, 4 evaluation metrics, 96% agreement with baseline.
* M6 complete: 51% attack cost estimator using live hash rate, hardware and electricity breakdown, Nakamoto (2008) §11 confirmation depth probability curves.

## Next Step

* Write final PDF report (2-3 pages) and submit repository link before 14 May 2026.


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
|   â””â”€â”€ blockchain_client.py
â””â”€â”€ modules/
    |-- m1_pow_monitor.py
    |-- m2_block_header.py
    |-- m3_difficulty_history.py
    â””â”€â”€ m4_ai_component.py
```

<!-- student-repo-auditor:teacher-feedback:start -->
## Teacher Feedback

### Kick-off Review

Review time: 2026-04-29 20:31 CEST
Status: Green

Strength:
- I can see the dashboard structure integrating the checkpoint modules.

Improve now:
- The checkpoint evidence is strong: the dashboard and core modules are visibly progressing.

Next step:
- Keep building on this checkpoint and prepare the final AI integration.
<!-- student-repo-auditor:teacher-feedback:end -->
