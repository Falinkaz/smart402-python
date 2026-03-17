"""Core smart402 integration: x402 lifecycle hook and Smart402Guard wrapper."""

import logging

from .client import Smart402Client
from .models import EvaluateRequest, PaymentRequirementsPayload

logger = logging.getLogger("smart402")

# USDC decimals (6) — used to convert x402's smallest-unit amounts to dollar strings
_USDC_DECIMALS = 6

# Known USDC contract addresses (lowercase) for supported chains.
# Used as a reliable fallback when x402's NETWORK_CONFIGS doesn't include the chain.
_KNOWN_USDC_ADDRESSES = frozenset({
    "0x036cbd53842c5426634e7929541ec2318f3dcf7e",  # USDC — Base Sepolia
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC — Base Mainnet
})


def _extract_amount_dollars(requirements) -> str:
    """Convert x402 PaymentRequirements amount to dollar decimal string.

    x402 V2 PaymentRequirements.amount is in smallest units (e.g., 100000 for $0.10 USDC).
    We convert to a dollar string for the smart402 API.

    Args:
        requirements: x402 PaymentRequirements object.

    Returns:
        Dollar amount as decimal string, e.g. "0.1".
    """
    try:
        from x402.mechanisms.evm.utils import format_amount, get_asset_info

        network = str(requirements.network)
        asset = str(requirements.asset)
        amount_int = int(requirements.amount)

        try:
            asset_info = get_asset_info(network, asset)
            decimals = asset_info.get("decimals", _USDC_DECIMALS)
        except (ValueError, KeyError):
            decimals = _USDC_DECIMALS

        return format_amount(amount_int, decimals)
    except Exception:
        # Fallback: return raw amount string
        return str(requirements.amount)


def _extract_token(requirements) -> str:
    """Extract token symbol from x402 PaymentRequirements.

    x402 V2 uses requirements.asset as the contract address.
    We look up the known symbol from the asset info, falling back to "USDC".

    Args:
        requirements: x402 PaymentRequirements object.

    Returns:
        Token symbol string, e.g. "USDC".
    """
    try:
        from x402.mechanisms.evm.constants import NETWORK_CONFIGS

        network = str(requirements.network)
        asset = str(requirements.asset)

        # Normalize to canonical CAIP-2 if needed
        try:
            from x402.mechanisms.evm.utils import get_network_config

            config = get_network_config(network)
            for symbol, info in config["supported_assets"].items():
                if info["address"].lower() == asset.lower():
                    return symbol
        except (ValueError, KeyError):
            pass

        # Static fallback for known USDC contract addresses
        if asset.lower() in _KNOWN_USDC_ADDRESSES:
            return "USDC"
        # Asset not found in any lookup — return address as-is
        return asset
    except Exception:
        return "USDC"


def smart402_hook(
    api_key: str,
    agent_id: str,
    smart402_url: str = "https://streetsmart-api.fly.dev",
    agent_wallet_address: str | None = None,
    wallet_provider: str | None = None,
    agent_framework: str | None = None,
    fail_mode: str = "fail_open",
):
    """Return an async callback for x402's on_before_payment_creation hook.

    On approve: returns None (payment proceeds).
    On deny: returns AbortResult with reason (payment aborted).
    On API error:
      - fail_open: returns None (payment proceeds, logs warning)
      - fail_closed: returns AbortResult (payment blocked)

    Args:
        api_key: smart402 API key (Bearer token).
        agent_id: Agent identifier registered in smart402.
        smart402_url: Base URL of the smart402 API.
        agent_wallet_address: Agent's EVM wallet address (optional metadata).
        wallet_provider: Wallet provider name (optional metadata).
        agent_framework: Agent framework name (optional metadata).
        fail_mode: "fail_open" (allow on error) or "fail_closed" (block on error).

    Returns:
        Async hook function to pass to client.on_before_payment_creation().
    """
    try:
        from x402 import AbortResult
    except ImportError:
        raise ImportError(
            "x402 is required to use smart402_hook(). "
            "Install it with: pip install 'smart402[x402]'"
        ) from None

    ss_client = Smart402Client(api_key=api_key, agent_id=agent_id, base_url=smart402_url)

    async def hook(ctx):
        req = ctx.selected_requirements

        # Validate and convert outside the try/except so these errors propagate
        # immediately rather than being silently fail_open'd.
        amount = _extract_amount_dollars(req)
        token = _extract_token(req)
        if token != "USDC":
            raise ValueError(f"smart402 v0.1 supports USDC only. Got: {token}")

        try:
            eval_request = EvaluateRequest(
                agent_id=agent_id,
                agent_wallet_address=agent_wallet_address,
                wallet_provider=wallet_provider,
                agent_framework=agent_framework,
                payment_requirements=PaymentRequirementsPayload(
                    amount=amount,
                    token=token,
                    scheme=req.scheme,
                    network=str(req.network),
                    pay_to=req.pay_to,
                    description=getattr(req, "description", None),
                    facilitator=getattr(req, "facilitator_url", None),
                    external_id=getattr(req, "external_id", None),
                ),
            )

            result = await ss_client.evaluate(eval_request)

            if result.decision == "approve":
                logger.info(
                    "APPROVED | %s %s -> %s... | eval_id=%s | %dms",
                    amount,
                    token,
                    req.pay_to[:10],
                    result.evaluation_id,
                    result.latency_ms,
                )
                return None  # Let payment proceed

            else:
                reason = f"smart402 denied: {', '.join(result.triggered_rules)}"
                logger.warning(
                    "DENIED | %s %s | rules: %s",
                    amount,
                    token,
                    result.triggered_rules,
                )
                return AbortResult(reason=reason)

        except Exception as e:
            if fail_mode == "fail_closed":
                logger.error("FAIL_CLOSED | smart402 unreachable: %s", e)
                return AbortResult(reason=f"smart402 unavailable: {e}")
            else:
                logger.warning(
                    "FAIL_OPEN | smart402 unreachable: %s — allowing payment", e
                )
                return None

    return hook


class Smart402Guard:
    """Convenience wrapper: creates a pre-configured x402Client with smart402.

    Registers the smart402 lifecycle hook on the x402Client so that every
    payment is evaluated before it is signed.

    NOTE: Smart402Guard.httpx_client() creates an httpx client backed by the
    x402 transport (which fires registered hooks). Use the sequential pattern in
    demo tools instead for guaranteed hook invocation.
    """

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        signer,
        smart402_url: str = "https://streetsmart-api.fly.dev",
        network: str = "eip155:84532",
        fail_mode: str = "fail_open",
        wallet_provider: str | None = None,
        agent_framework: str | None = None,
    ):
        """Initialize Smart402Guard.

        Args:
            api_key: smart402 API key.
            agent_id: Agent identifier in smart402.
            signer: eth_account LocalAccount (from Account.from_key()).
            smart402_url: smart402 API base URL.
            network: Default EVM network (CAIP-2 format).
            fail_mode: "fail_open" or "fail_closed".
            wallet_provider: Optional wallet provider label.
            agent_framework: Optional agent framework label.
        """
        from x402 import x402Client
        from x402.mechanisms.evm.exact import register_exact_evm_client
        from x402.mechanisms.evm.signers import EthAccountSigner

        evm_signer = EthAccountSigner(signer)

        self.client = x402Client()
        register_exact_evm_client(self.client, evm_signer)

        self.client.on_before_payment_creation(
            smart402_hook(
                api_key=api_key,
                agent_id=agent_id,
                smart402_url=smart402_url,
                agent_wallet_address=evm_signer.address,
                wallet_provider=wallet_provider,
                agent_framework=agent_framework,
                fail_mode=fail_mode,
            )
        )

        self._signer = evm_signer
        self._network = network

    def httpx_client(self, base_url: str | None = None):
        """Not yet implemented — hook chaining between x402 and smart402 is broken.

        Use the sequential pattern instead:
          1. Make a plain httpx request to the seller
          2. On 402, parse the PaymentRequirements from the response
          3. Call Smart402Client.evaluate() directly
          4. If approved, sign payment via x402 and retry with payment headers

        See demo/agent/tools.py for a working example.
        """
        raise NotImplementedError(
            "Smart402Guard.httpx_client() is disabled because it bypasses smart402 "
            "protection. Use the sequential pattern (plain request → evaluate → sign) instead. "
            "See demo/agent/tools.py for a working example."
        )
