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

## Current Progress

* M1 complete: live difficulty, hash vs target verification, inter-block time histogram with exponential baseline, hash rate estimation.
* M2 complete: 80-byte header parsed field by field, SHA256(SHA256(header)) verified with hashlib, bits decoded to 256-bit target, nonce space visualised, merkle root verified.
* M3 complete: difficulty evolution over adjustment periods, real/target block time ratio, % change per period, next adjustment estimate.
* M4 complete: Isolation Forest anomaly detector on inter-block times, 3 features (ibt, log_ibt, ibt_z), statistical z-score baseline, 4 evaluation metrics, 96% agreement with baseline.

## Next Step

* Write final PDF report (2-3 pages).

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

Review time: 2026-04-21 09:19 CEST
Status: Green

Strength:
- Your repository keeps the expected classroom structure.

Improve now:
- The code should connect the API output to theory, especially leading zeros and bits or target.

Next step:
- Add two short code comments that explain leading zeros and the meaning of bits or target.
<!-- student-repo-auditor:teacher-feedback:end -->
