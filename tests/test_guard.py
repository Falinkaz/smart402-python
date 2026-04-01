"""Unit tests for smart402.guard — the x402 lifecycle hook logic."""

import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smart402.guard import smart402_hook, _extract_token, _extract_amount_dollars
from smart402.models import EvaluateResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_requirements(
    amount="100000",
    asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    network="eip155:84532",
    pay_to="0xDeadBeef00000000000000000000000000000001",
    scheme="exact",
):
    """Create a minimal mock PaymentRequirements object."""
    req = MagicMock()
    req.amount = amount
    req.asset = asset
    req.network = network
    req.pay_to = pay_to
    req.scheme = scheme
    # Set optional attributes to None so Pydantic accepts them
    req.description = None
    req.facilitator_url = None
    req.external_id = None
    return req


def _make_context(requirements=None):
    """Create a mock x402 hook context."""
    ctx = MagicMock()
    ctx.selected_requirements = requirements or _make_requirements()
    return ctx


def _make_approve_response(**kwargs):
    return EvaluateResponse(
        decision="approve",
        evaluation_id="eval-001",
        evaluated_at="2026-01-01T00:00:00Z",
        remaining_daily_budget="0.90",
        rules_checked=5,
        triggered_rules=[],
        latency_ms=12,
        **kwargs,
    )


def _make_deny_response(triggered_rules=None):
    return EvaluateResponse(
        decision="deny",
        evaluation_id="eval-002",
        evaluated_at="2026-01-01T00:00:00Z",
        remaining_daily_budget="0.00",
        rules_checked=5,
        triggered_rules=triggered_rules or ["daily_budget_exceeded"],
        latency_ms=10,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hook_approve():
    """Hook returns None when smart402 approves."""
    hook = smart402_hook(api_key="test-key", agent_id="test-agent")
    ctx = _make_context()

    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = AsyncMock(return_value=_make_approve_response())
        MockClient.return_value = instance

        hook = smart402_hook(api_key="test-key", agent_id="test-agent")
        result = await hook(ctx)

    assert result is None


@pytest.mark.asyncio
async def test_hook_deny():
    """Hook returns AbortResult when smart402 denies."""
    from x402 import AbortResult

    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = AsyncMock(
            return_value=_make_deny_response(triggered_rules=["daily_budget_exceeded"])
        )
        MockClient.return_value = instance

        hook = smart402_hook(api_key="test-key", agent_id="test-agent")
        ctx = _make_context()
        result = await hook(ctx)

    assert isinstance(result, AbortResult)
    assert "daily_budget_exceeded" in result.reason


@pytest.mark.asyncio
async def test_hook_fail_open():
    """Hook returns None on API error when fail_mode is 'fail_open'."""
    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = AsyncMock(side_effect=ConnectionError("refused"))
        MockClient.return_value = instance

        hook = smart402_hook(
            api_key="test-key", agent_id="test-agent", fail_mode="fail_open"
        )
        ctx = _make_context()
        result = await hook(ctx)

    assert result is None


@pytest.mark.asyncio
async def test_hook_fail_closed():
    """Hook returns AbortResult on API error when fail_mode is 'fail_closed'."""
    from x402 import AbortResult

    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = AsyncMock(side_effect=ConnectionError("refused"))
        MockClient.return_value = instance

        hook = smart402_hook(
            api_key="test-key", agent_id="test-agent", fail_mode="fail_closed"
        )
        ctx = _make_context()
        result = await hook(ctx)

    assert isinstance(result, AbortResult)
    assert "smart402 unavailable" in result.reason


@pytest.mark.asyncio
async def test_hook_extracts_payment_requirements():
    """Hook builds EvaluateRequest with correct fields from x402 PaymentRequirements."""
    captured = {}

    async def fake_evaluate(request):
        captured["request"] = request
        return _make_approve_response()

    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = fake_evaluate
        MockClient.return_value = instance

        hook = smart402_hook(
            api_key="test-key",
            agent_id="weather-agent-001",
            agent_wallet_address="0xAgentAddress",
        )
        req = _make_requirements(
            amount="100000",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            network="eip155:84532",
            pay_to="0xSellerAddress",
            scheme="exact",
        )
        ctx = _make_context(req)
        await hook(ctx)

    assert "request" in captured
    pr = captured["request"].payment_requirements
    assert pr.network == "eip155:84532"
    assert pr.pay_to == "0xSellerAddress"
    assert pr.scheme == "exact"
    assert captured["request"].agent_id == "weather-agent-001"
    assert captured["request"].agent_wallet_address == "0xAgentAddress"
    # Amount should be a decimal string (converted from smallest units)
    float(pr.amount)  # must be parseable as a number


@pytest.mark.asyncio
async def test_hook_logs_approve(caplog):
    """Hook logs an INFO message on approve."""
    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = AsyncMock(return_value=_make_approve_response())
        MockClient.return_value = instance

        hook = smart402_hook(api_key="test-key", agent_id="test-agent")
        ctx = _make_context()
        with caplog.at_level(logging.INFO, logger="smart402"):
            await hook(ctx)

    assert any("APPROVED" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_hook_rejects_non_usdc():
    """Hook raises ValueError immediately for non-USDC tokens."""
    hook = smart402_hook(api_key="test-key", agent_id="test-agent")
    # Unknown contract address → _extract_token falls back to raw address → not "USDC"
    req = _make_requirements(asset="0xdeadbeef00000000000000000000000000000001")
    ctx = _make_context(req)
    with pytest.raises(ValueError, match="smart402 supports USDC only"):
        await hook(ctx)


@pytest.mark.asyncio
async def test_hook_logs_deny(caplog):
    """Hook logs a WARNING message on deny."""
    with patch("smart402.guard.Smart402Client") as MockClient:
        instance = AsyncMock()
        instance.evaluate = AsyncMock(
            return_value=_make_deny_response(triggered_rules=["max_transaction_amount"])
        )
        MockClient.return_value = instance

        hook = smart402_hook(api_key="test-key", agent_id="test-agent")
        ctx = _make_context()
        with caplog.at_level(logging.WARNING, logger="smart402"):
            await hook(ctx)

    assert any("DENIED" in r.message for r in caplog.records)
