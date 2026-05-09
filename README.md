# AidChain

> Real-time disaster aid distribution on IBM Z, where two AIs work in parallel: one blocks fraudsters, one prioritizes the most vulnerable.

Built for the **IBM Z Sheridan x UNSA Sheridan Hackathon 2026** (UN SDG track).

## The Problem

When disasters strike, billions in aid flow through banks and NGOs. Three things go wrong every time:

1. **Fraud eats 20–30% of every dollar.** Fake claims, duplicate identities, inflated damages.
2. **Real victims wait weeks.** Hurricane Maria (2017) took an average of 47 days for aid to land.
3. **The most vulnerable get left behind.** Elderly, disabled, single mothers — the people who need help most are the ones least able to fight through paperwork.

## The Idea

AidChain runs every aid claim through **two AIs at once**, on the IBM Z mainframe, in the transaction path itself:

- **FraudGuard** — Random Forest classifier that blocks fraudulent claims (target: catch >95% of fraud, false positive rate <5%).
- **PriorityCare** — Gradient Boosting regressor that ranks claimants by vulnerability and routes the most vulnerable to the front of the queue.

> AI in finance has spent 20 years deciding *who to keep out*. AidChain uses it to decide *who to let in first.*

Every decision is appended to an **HMAC-signed audit ledger** so fairness is provable, claim-by-claim.

## Why IBM Z

The whole point of IBM Z's Telum chip is on-chip AI inference inside the transaction itself, in microseconds. That's not a marketing line — it's the only architecture that can run two ML models on every aid claim, at disaster scale (50K+ claims/sec), without latency tanking.

On AWS, this is minutes. On Z, it's microseconds.

## Architecture

```
┌─────────────┐     ┌──────────────────────────────┐     ┌──────────────┐
│  Aid Claim  │────▶│        FastAPI Service       │────▶│   Decision   │
│ (REST/JSON) │     │       (LinuxONE / Z)         │     │ approved /   │
└─────────────┘     │                              │     │ rejected /   │
                    │  ┌────────────┐              │     │ prioritized  │
                    │  │ FraudGuard │ Telum AI     │     └──────┬───────┘
                    │  │   Random   │ on-chip      │            │
                    │  │   Forest   │ inference    │            │
                    │  └────────────┘              │     ┌──────▼───────┐
                    │  ┌────────────┐              │     │ Audit Ledger │
                    │  │ Priority-  │              │────▶│  HMAC chain  │
                    │  │   Care     │              │     │   (SQLite)   │
                    │  │  Gradient  │              │     └──────────────┘
                    │  │  Boosting  │              │
                    │  └────────────┘              │
                    └──────────────────────────────┘
                                  │
                                  ▼  WebSocket
                       Live Operator Dashboard
```

## Project Structure

```
aidchain/
├── backend/                # FastAPI transaction service
│   ├── main.py             # API endpoints + WebSocket
│   ├── inference.py        # Two-AI inference pipeline
│   ├── ledger.py           # HMAC-chained audit ledger
│   └── models.py           # Pydantic schemas
├── ml/                     # Machine learning
│   ├── generate_data.py    # Synthetic disaster claim generator
│   ├── train_fraud.py      # Train FraudGuard
│   ├── train_vulnerability.py  # Train PriorityCare
│   ├── data/               # Generated datasets (gitignored)
│   └── models/             # Trained .pkl models (gitignored)
├── frontend/               # React dashboard (coming soon)
├── scripts/
│   ├── setup_server.sh     # One-time venv + deps install
│   └── run_server.sh       # Start the backend
├── requirements.txt
└── README.md
```

## Quick Start (on LinuxONE or local)

```bash
# 1. Clone
git clone https://github.com/trivedicoder/aidchain.git
cd aidchain

# 2. Set up venv + install deps
bash scripts/setup_server.sh

# 3. Run the backend (auto-trains models on first run)
bash scripts/run_server.sh
```

Then in another terminal:

```bash
# Verify it's alive
curl http://localhost:8000/

# Submit a single claim
curl -X POST http://localhost:8000/claim \
  -H 'Content-Type: application/json' \
  -d '{
    "claim_id": "TEST-0001",
    "age": 67,
    "disability": 1,
    "dependents": 0,
    "income_proxy": 18000,
    "displaced": 1,
    "in_affected_zone": 1,
    "prior_claims_count": 0,
    "amount_requested": 1500,
    "days_since_disaster": 1.2,
    "claimant_name": "Maria"
  }'

# Run a 1000-claim disaster simulation
curl -X POST 'http://localhost:8000/simulate?n=1000'

# Check stats
curl http://localhost:8000/stats

# Verify the audit chain
curl http://localhost:8000/audit/verify
```

## API Reference

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/claim` | Process one aid claim through both AIs |
| `POST` | `/simulate?n=1000` | Stream N synthetic claims through the system |
| `GET` | `/audit/{claim_id}` | Audit entry for a single claim |
| `GET` | `/audit?limit=50` | Recent audit entries |
| `GET` | `/audit/verify` | Cryptographically verify the entire chain |
| `GET` | `/stats` | Dashboard stats (totals, by decision) |
| `WS` | `/live` | Live feed of decisions (for dashboard) |

## Team

- **Arya Trivedi** — IBM Z deployment, demo lead
- **[Teammate]** — TBD
- **Claude** — coding teammate

## License

MIT
