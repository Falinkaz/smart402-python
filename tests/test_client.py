"""Unit tests for smart402.client — the smart402 API HTTP client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from smart402.client import Smart402Client
from smart402.models import EvaluateRequest, EvaluateResponse, PaymentRequirementsPayload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**kwargs) -> Smart402Client:
    defaults = dict(api_key="test-key", agent_id="test-agent")
    defaults.update(kwargs)
    return Smart402Client(**defaults)


def _make_request(**kwargs) -> EvaluateRequest:
    defaults = dict(
        agent_id="weather-agent-001",
        payment_requirements=PaymentRequirementsPayload(
            amount="0.10",
            token="USDC",
            scheme="exact",
            network="eip155:84532",
            pay_to="0xSellerAddress",
        ),
    )
    defaults.update(kwargs)
    return EvaluateRequest(**defaults)


def _make_approve_response_body() -> dict:
    return {
        "decision": "approve",
        "evaluation_id": "eval-abc123",
        "evaluated_at": "2026-01-01T00:00:00Z",
        "remaining_daily_budget": "0.90",
        "rules_checked": 5,
        "triggered_rules": [],
        "counterparty_risk_score": "low",
        "counterparty_details": None,
        "latency_ms": 8,
    }


def _make_deny_response_body() -> dict:
    return {
        "decision": "deny",
        "evaluation_id": "eval-def456",
        "evaluated_at": "2026-01-01T00:00:00Z",
        "remaining_daily_budget": "0.00",
        "rules_checked": 5,
        "triggered_rules": ["daily_budget_exceeded"],
        "counterparty_risk_score": "medium",
        "counterparty_details": None,
        "latency_ms": 6,
    }


def _mock_httpx(mock_class, response_body: dict):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = response_body
    mock_response.raise_for_status = MagicMock()

    instance = AsyncMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.post = AsyncMock(return_value=mock_response)
    mock_class.return_value = instance
    return mock_response


# ---------------------------------------------------------------------------
# Tests — evaluate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_approve():
    """Client parses approve response correctly."""
    client = _make_client()

    with patch("httpx.AsyncClient") as MockHttpx:
        _mock_httpx(MockHttpx, _make_approve_response_body())
        result = await client.evaluate(_make_request())

    assert isinstance(result, EvaluateResponse)
    assert result.decision == "approve"
    assert result.evaluation_id == "eval-abc123"
    assert result.triggered_rules == []
    assert result.latency_ms == 8


@pytest.mark.asyncio
async def test_evaluate_deny():
    """Client parses deny response with triggered_rules."""
    client = _make_client()

    with patch("httpx.AsyncClient") as MockHttpx:
        _mock_httpx(MockHttpx, _make_deny_response_body())
        result = await client.evaluate(_make_request())

    assert result.decision == "deny"
    assert "daily_budget_exceeded" in result.triggered_rules


@pytest.mark.asyncio
async def test_evaluate_timeout():
    """Client raises TimeoutException on timeout."""
    client = _make_client()

    with patch("httpx.AsyncClient") as MockHttpx:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        MockHttpx.return_value = instance

        with pytest.raises(httpx.TimeoutException):
            await client.evaluate(_make_request())


@pytest.mark.asyncio
async def test_evaluate_401():
    """Client raises HTTPStatusError on 401 Unauthorized."""
    client = _make_client(api_key="bad-key")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
    )

    with patch("httpx.AsyncClient") as MockHttpx:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(return_value=mock_response)
        MockHttpx.return_value = instance

        with pytest.raises(httpx.HTTPStatusError):
            await client.evaluate(_make_request())


@pytest.mark.asyncio
async def test_evaluate_sends_correct_headers():
    """Client sends Authorization Bearer header."""
    client = _make_client(api_key="ag_live_secret123")
    captured_kwargs = {}

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = _make_approve_response_body()
    mock_response.raise_for_status = MagicMock()

    async def fake_post(url, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_response

    with patch("httpx.AsyncClient") as MockHttpx:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = fake_post
        MockHttpx.return_value = instance

        await client.evaluate(_make_request())

    assert "headers" in captured_kwargs
    assert captured_kwargs["headers"]["Authorization"] == "Bearer ag_live_secret123"


# ---------------------------------------------------------------------------
# Tests — evaluate_payment()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_payment_approve():
    """evaluate_payment() returns approve response."""
    client = _make_client(agent_id="my-agent-001")

    with patch("httpx.AsyncClient") as MockHttpx:
        _mock_httpx(MockHttpx, _make_approve_response_body())
        result = await client.evaluate_payment(
            amount="0.10",
            token="USDC",
            network="eip155:8453",
            pay_to="0xRecipient",
        )

    assert result.decision == "approve"


@pytest.mark.asyncio
async def test_evaluate_payment_builds_correct_request():
    """evaluate_payment() uses the client's agent_id and passes all payment fields."""
    client = _make_client(agent_id="my-agent-001")
    captured = {}

    async def fake_post(url, **kwargs):
        captured["body"] = kwargs.get("json", {})
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_approve_response_body()
        return mock_response

    with patch("httpx.AsyncClient") as MockHttpx:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = fake_post
        MockHttpx.return_value = instance

        await client.evaluate_payment(
            amount="0.50",
            token="USDC",
            network="eip155:8453",
            pay_to="0xSellerAddress",
        )

    assert captured["body"]["agent_id"] == "my-agent-001"
    pr = captured["body"]["payment_requirements"]
    assert pr["amount"] == "0.50"
    assert pr["token"] == "USDC"
    assert pr["network"] == "eip155:8453"
    assert pr["pay_to"] == "0xSellerAddress"
