"""
AidChain — Cryptographically-signed audit ledger.

Every decision the AI makes is appended to an HMAC-chained ledger backed by
SQLite. Each entry includes the hash of the previous entry, creating a
tamper-evident chain (similar to a blockchain, lighter to run).

Why this matters for the demo: when judges ask "How do we know your AI is
fair?" — every decision is signed and the full audit trail is queryable and
verifiable. On real IBM Z, the HMAC key would live in the Z hardware
security module, making the chain cryptographically anchored to the box.
"""

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

# In production this would be a Z hardware-protected key.
LEDGER_SECRET = os.environ.get(
    'AIDCHAIN_LEDGER_SECRET', 'demo-secret-key-replace-in-prod'
).encode()
LEDGER_DB_PATH = os.environ.get('AIDCHAIN_LEDGER_DB', 'ledger.db')

GENESIS_HASH = '0' * 64


def _init_db():
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            fraud_score REAL NOT NULL,
            vulnerability_score REAL NOT NULL,
            amount_approved REAL NOT NULL,
            timestamp TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def _compute_hash(payload: dict, previous_hash: str) -> str:
    """HMAC-SHA256 over the previous hash + canonical payload."""
    msg = previous_hash + json.dumps(payload, sort_keys=True)
    return hmac.new(LEDGER_SECRET, msg.encode(), hashlib.sha256).hexdigest()


def append(claim_id: str, decision: str, fraud_score: float,
           vulnerability_score: float, amount_approved: float) -> Dict:
    """Append a decision to the ledger and return the entry."""
    _init_db()
    timestamp = datetime.utcnow().isoformat()

    conn = sqlite3.connect(LEDGER_DB_PATH)
    cur = conn.cursor()

    cur.execute('SELECT entry_hash FROM ledger ORDER BY sequence DESC LIMIT 1')
    row = cur.fetchone()
    previous_hash = row[0] if row else GENESIS_HASH

    payload = {
        'claim_id': claim_id,
        'decision': decision,
        'fraud_score': fraud_score,
        'vulnerability_score': vulnerability_score,
        'amount_approved': amount_approved,
        'timestamp': timestamp,
    }
    entry_hash = _compute_hash(payload, previous_hash)

    cur.execute('''
        INSERT INTO ledger (claim_id, decision, fraud_score, vulnerability_score,
                            amount_approved, timestamp, previous_hash, entry_hash, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (claim_id, decision, fraud_score, vulnerability_score, amount_approved,
          timestamp, previous_hash, entry_hash, json.dumps(payload)))

    seq = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        'sequence': seq,
        **payload,
        'previous_hash': previous_hash,
        'entry_hash': entry_hash,
    }


def get_by_claim(claim_id: str) -> Optional[Dict]:
    _init_db()
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        'SELECT * FROM ledger WHERE claim_id = ? ORDER BY sequence DESC LIMIT 1',
        (claim_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all(limit: int = 100) -> List[Dict]:
    _init_db()
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM ledger ORDER BY sequence DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def verify_chain() -> Dict:
    """Verify the integrity of the entire ledger chain.

    Returns:
        {'valid': bool, 'entries_checked': int, 'first_invalid': Optional[int]}
    """
    _init_db()
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM ledger ORDER BY sequence ASC')
    rows = cur.fetchall()
    conn.close()

    previous_hash = GENESIS_HASH
    for row in rows:
        payload = json.loads(row['payload'])
        expected = _compute_hash(payload, previous_hash)
        if expected != row['entry_hash'] or row['previous_hash'] != previous_hash:
            return {
                'valid': False,
                'entries_checked': row['sequence'],
                'first_invalid': row['sequence'],
            }
        previous_hash = row['entry_hash']

    return {'valid': True, 'entries_checked': len(rows), 'first_invalid': None}


def stats() -> Dict:
    _init_db()
    conn = sqlite3.connect(LEDGER_DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT decision, COUNT(*), SUM(amount_approved)
        FROM ledger GROUP BY decision
    ''')
    rows = cur.fetchall()
    cur.execute('SELECT COUNT(*), SUM(amount_approved) FROM ledger')
    total_count, total_amount = cur.fetchone()
    conn.close()

    return {
        'total_decisions': total_count or 0,
        'total_amount_approved': float(total_amount or 0),
        'by_decision': {
            r[0]: {'count': r[1], 'amount': float(r[2] or 0)} for r in rows
        },
    }
