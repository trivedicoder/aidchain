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
from fastapi.responses import FileResponse, HTMLResponse

from backend import inference, ledger
from backend.models import AidClaim, ClaimDecision

FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'

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


@app.get('/', response_class=HTMLResponse)
def dashboard():
    """Serve the live operator dashboard."""
    index = FRONTEND_DIR / 'index.html'
    if not index.exists():
        return HTMLResponse(
            '<h1>Dashboard not found</h1>'
            '<p>frontend/index.html is missing. API is still available at <a href="/api">/api</a>.</p>',
            status_code=404,
        )
    return FileResponse(index)


@app.get('/api')
def api_root():
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


@app.get('/audit')
def audit_recent(limit: int = 50):
    return {'entries': ledger.get_all(limit=limit)}


# /audit/verify must come BEFORE /audit/{claim_id} or FastAPI matches "verify" as a claim_id.
@app.get('/audit/verify')
def audit_verify():
    return ledger.verify_chain()


@app.get('/audit/{claim_id}')
def audit_claim(claim_id: str):
    entry = ledger.get_by_claim(claim_id)
    if not entry:
        raise HTTPException(404, f'No audit entry for claim {claim_id}')
    return entry


@app.get('/stats')
def stats():
    return ledger.stats()


@app.post('/maria')
async def submit_maria():
    """Inject Maria Rodriguez's claim — Hurricane Maria, San Juan, age 67, displaced.

    Demo-only endpoint that ties our Devpost narrative to the live dashboard.
    Maria's profile is engineered to score very high on PriorityCare so the
    high-priority card always lights up on stage.
    """
    import time as _t
    maria = {
        'claim_id': f'MARIA-{int(_t.time())}',
        'age': 67,
        'disability': 1,
        'dependents': 3,
        'income_proxy': 8000.0,
        'displaced': 1,
        'in_affected_zone': 1,
        'prior_claims_count': 0,
        'amount_requested': 2500.0,
        'days_since_disaster': 1.0,
        'claimant_name': 'Maria Rodriguez',
    }
    result = inference.score(maria)
    ledger.append(
        claim_id=maria['claim_id'],
        decision=result['decision'],
        fraud_score=result['fraud_score'],
        vulnerability_score=result['vulnerability_score'],
        amount_approved=result['amount_approved'],
    )
    payload = {
        'type': 'decision',
        'claim_id': maria['claim_id'],
        'claimant_name': 'Maria Rodriguez',
        'location': 'San Juan, Puerto Rico',
        'maria_scenario': True,
        'age': maria['age'],
        'disability': maria['disability'],
        'dependents': maria['dependents'],
        **result,
    }
    await manager.broadcast(payload)
    return payload


@app.post('/admin/tamper')
def tamper_demo():
    """DEMO ONLY: tamper with a random ledger entry to prove the chain catches it.

    Modifies the payload column for a random row WITHOUT recomputing the hash,
    so verify_chain will detect the inconsistency. Used by the dashboard's
    "Demonstrate Tamper" button.
    """
    import json
    import sqlite3

    conn = sqlite3.connect(ledger.LEDGER_DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT sequence, payload FROM ledger ORDER BY RANDOM() LIMIT 1')
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(400, 'Ledger is empty — run a simulation first.')

    seq, payload_json = row
    payload = json.loads(payload_json)
    original_amount = payload['amount_approved']
    payload['amount_approved'] = 9999999.99  # forge!

    cur.execute(
        'UPDATE ledger SET amount_approved = ?, payload = ? WHERE sequence = ?',
        (9999999.99, json.dumps(payload), seq),
    )
    conn.commit()
    conn.close()

    return {
        'tampered_sequence': seq,
        'original_amount': original_amount,
        'forged_amount': 9999999.99,
        'message': f'Sequence {seq} forged. Run /audit/verify to see the chain catch it.',
    }


@app.websocket('/live')
async def live_feed(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        manager.disconnect(ws)
