"""HTTP client for the smart402 API."""

import logging
from urllib.parse import urlparse

import httpx

from .models import EvaluateRequest, EvaluateResponse, PaymentRequirementsPayload

logger = logging.getLogger("smart402")


class Smart402Client:
    """Async HTTP client that calls the smart402 evaluation API."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        base_url: str = "https://streetsmart-api.fly.dev",
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.base_url = base_url.rstrip("/")
        self._warn_if_insecure()

    def _warn_if_insecure(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme == "http" and parsed.hostname not in (
            "localhost",
            "127.0.0.1",
            "::1",
        ):
            logger.warning(
                "⚠️  smart402 SDK is connecting over HTTP to %s. "
                "API keys sent over HTTP are vulnerable to interception. "
                "Use https:// for non-localhost connections.",
                parsed.hostname,
            )

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        """Call POST /evaluate and return the decision.

        Args:
            request: EvaluateRequest with agent info and payment requirements.

        Returns:
            EvaluateResponse with decision ("approve" or "deny").

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
            httpx.TimeoutException: If request times out.
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{self.base_url}/evaluate",
                json=request.model_dump(),
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return EvaluateResponse(**response.json())

    async def evaluate_payment(
        self,
        amount: str,
        token: str,
        network: str,
        pay_to: str,
    ) -> EvaluateResponse:
        """Convenience wrapper around evaluate() for simple one-payment calls.

        Args:
            amount: Dollar decimal string (e.g. "0.10" for $0.10 USDC).
            token: Token symbol. smart402 accepts "USDC" only.
            network: CAIP-2 network identifier (e.g. "eip155:8453" for Base mainnet).
            pay_to: Recipient wallet address.

        Returns:
            EvaluateResponse with decision ("approve" or "deny").
        """
        return await self.evaluate(
            EvaluateRequest(
                agent_id=self.agent_id,
                payment_requirements=PaymentRequirementsPayload(
                    amount=amount,
                    token=token,
                    network=network,
                    pay_to=pay_to,
                ),
            )
        )
