"""
AidChain — FastAPI transaction service.

Endpoints:
    POST /claim                Submit a single aid claim (returns decision)
    POST /simulate             Simulate a disaster (streams N claims)
    GET  /audit/{claim_id}     Retrieve audit entry for a single claim
    GET  /audit                Get latest N audit entries
    GET  /audit/verify         Verify integrity of the entire audit chain
    GET  /stats                Dashboard stats (total deployed, by decision)
    WS   /live                 Live WebSocket feed of incoming decisions

Run:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import sys
from pathlib import Path

# Make sibling modules importable when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend import inference, ledger
from backend.models import AidClaim, ClaimDecision

app = FastAPI(
    title='AidChain',
    description='Real-time disaster aid distribution on IBM Z',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)


class ConnectionManager:
    """Manages WebSocket connections for the live dashboard."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.get('/')
def root():
    return {
        'service': 'AidChain',
        'version': '0.1.0',
        'description': 'Real-time disaster aid distribution on IBM Z',
        'endpoints': ['/claim', '/simulate', '/audit', '/stats', '/live (ws)'],
    }


@app.post('/claim', response_model=ClaimDecision)
async def submit_claim(claim: AidClaim):
    """Process a single aid claim through both AIs and append to ledger."""
    result = inference.score(claim.model_dump())

    entry = ledger.append(
        claim_id=claim.claim_id,
        decision=result['decision'],
        fraud_score=result['fraud_score'],
        vulnerability_score=result['vulnerability_score'],
        amount_approved=result['amount_approved'],
    )

    decision = ClaimDecision(
        claim_id=claim.claim_id,
        fraud_score=result['fraud_score'],
        vulnerability_score=result['vulnerability_score'],
        decision=result['decision'],
        reasoning=result['reasoning'],
        amount_approved=result['amount_approved'],
        decision_timestamp=entry['timestamp'],
        inference_time_ms=result['inference_time_ms'],
    )

    await manager.broadcast({
        'type': 'decision',
        'claimant_name': claim.claimant_name,
        **decision.model_dump(),
    })

    return decision


@app.post('/simulate')
async def simulate_disaster(n: int = 1000, fraud_rate: float = 0.08):
    """Kick off a disaster simulation. Generates N claims and processes them."""
    from ml.generate_data import generate_claims

    df = generate_claims(n=n, fraud_rate=fraud_rate)
    asyncio.create_task(_run_simulation(df))

    return {
        'status': 'started',
        'claims_queued': n,
        'message': f'Disaster simulation processing {n:,} claims through AidChain.',
    }


async def _run_simulation(df):
    """Process a batch of claims, broadcasting each decision to dashboards."""
    for _, row in df.iterrows():
        claim_dict = row.to_dict()
        try:
            result = inference.score(claim_dict)
            ledger.append(
                claim_id=claim_dict['claim_id'],
                decision=result['decision'],
                fraud_score=result['fraud_score'],
                vulnerability_score=result['vulnerability_score'],
                amount_approved=result['amount_approved'],
            )
            await manager.broadcast({
                'type': 'decision',
                'claim_id': claim_dict['claim_id'],
                'age': int(claim_dict['age']),
                'disability': int(claim_dict['disability']),
                'dependents': int(claim_dict['dependents']),
                **result,
            })
            await asyncio.sleep(0.005)  # ~200/sec, visible streaming for demo
        except Exception as e:
            print(f"Error processing {claim_dict.get('claim_id')}: {e}")


@app.get('/audit/{claim_id}')
def audit_claim(claim_id: str):
    entry = ledger.get_by_claim(claim_id)
    if not entry:
        raise HTTPException(404, f'No audit entry for claim {claim_id}')
    return entry


@app.get('/audit')
def audit_recent(limit: int = 50):
    return {'entries': ledger.get_all(limit=limit)}


@app.get('/audit/verify')
def audit_verify():
    return ledger.verify_chain()


@app.get('/stats')
def stats():
    return ledger.stats()


@app.websocket('/live')
async def live_feed(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        manager.disconnect(ws)
