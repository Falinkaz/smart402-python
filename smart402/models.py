"""Pydantic models for smart402 API requests and responses."""

from typing import Optional

from pydantic import BaseModel


class CounterpartyDetails(BaseModel):
    """Counterparty intelligence snapshot returned by POST /evaluate."""

    is_contract: Optional[bool] = None
    is_verified_contract: Optional[bool] = None
    wallet_age_days: Optional[int] = None
    times_seen_by_agent: int = 0
    first_time: bool = True


class PaymentRequirementsPayload(BaseModel):
    """Mirrors the payment_requirements field expected by POST /evaluate."""

    amount: str  # Dollar amount as decimal string, e.g. "0.10"
    token: str  # Token symbol or address, e.g. "USDC"
    scheme: Optional[str] = None
    network: str  # CAIP-2 network ID, e.g. "eip155:84532"
    pay_to: str  # Recipient address
    description: Optional[str] = None
    facilitator: Optional[str] = None
    external_id: Optional[str] = None


class EvaluateRequest(BaseModel):
    """Request body for POST /evaluate."""

    agent_id: str
    agent_wallet_address: Optional[str] = None
    wallet_provider: Optional[str] = None
    sdk_version: str = "0.1.0"
    agent_framework: Optional[str] = None
    runtime_region: Optional[str] = None
    is_retry: bool = False
    previous_evaluation_id: Optional[str] = None
    request_url: Optional[str] = None
    payment_requirements: PaymentRequirementsPayload


class EvaluateResponse(BaseModel):
    """Response body from POST /evaluate."""

    decision: str  # "approve" or "deny"
    evaluation_id: str
    evaluated_at: str
    remaining_daily_budget: Optional[str] = None
    rules_checked: int
    triggered_rules: list[str]
    counterparty_risk_score: str = "unknown"  # "low", "medium", "high", or "unknown"
    counterparty_details: Optional[CounterpartyDetails] = None
    latency_ms: int
