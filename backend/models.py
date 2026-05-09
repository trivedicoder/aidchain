"""
AidChain — Pydantic schemas for API contracts.
"""

from typing import Optional

from pydantic import BaseModel, Field


class AidClaim(BaseModel):
    """Incoming disaster aid claim."""
    claim_id: str = Field(..., description='Unique claim identifier')
    age: int = Field(..., ge=0, le=120)
    disability: int = Field(..., ge=0, le=1)
    dependents: int = Field(..., ge=0)
    income_proxy: float = Field(..., ge=0)
    displaced: int = Field(..., ge=0, le=1)
    in_affected_zone: int = Field(..., ge=0, le=1)
    prior_claims_count: int = Field(..., ge=0)
    amount_requested: float = Field(..., ge=0)
    days_since_disaster: float = Field(..., ge=0)
    claimant_name: Optional[str] = None  # for human-readable demo


class ClaimDecision(BaseModel):
    """AidChain decision after running both AIs."""
    claim_id: str
    fraud_score: float = Field(..., ge=0, le=1)
    vulnerability_score: float = Field(..., ge=0, le=1)
    decision: str = Field(..., description='approved | rejected | prioritized')
    reasoning: str
    amount_approved: float
    decision_timestamp: str
    inference_time_ms: float
