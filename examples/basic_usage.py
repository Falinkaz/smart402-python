"""
Minimal smart402 integration — direct API client.

Run:
    SMART402_API_KEY=ag_live_... python examples/basic_usage.py

Without a valid API key the script will import correctly and fail at the
HTTP call with a 401 error — you can read the code before signing up.
"""

import asyncio
import os

from smart402 import Smart402Client
from smart402.models import EvaluateRequest, PaymentRequirementsPayload


async def main() -> None:
    client = Smart402Client(
        api_key=os.environ.get("SMART402_API_KEY", "ag_live_invalid"),
    )

    result = await client.evaluate(
        EvaluateRequest(
            agent_id="example-agent",
            payment_requirements=PaymentRequirementsPayload(
                amount="0.10",          # Dollar decimal string ($0.10 USDC)
                token="USDC",
                network="eip155:8453",  # Base mainnet (CAIP-2)
                pay_to="0x9dBA414637c611a16BEa6f0796BFcbcBdc410df8",
            ),
        )
    )

    print(f"Decision:      {result.decision}")
    print(f"Risk score:    {result.counterparty_risk_score}")
    print(f"Rules checked: {result.rules_checked}")
    print(f"Latency:       {result.latency_ms}ms")

    if result.triggered_rules:
        print(f"Blocked by:    {', '.join(result.triggered_rules)}")

    if result.remaining_daily_budget is not None:
        print(f"Daily budget remaining: ${result.remaining_daily_budget}")


if __name__ == "__main__":
    asyncio.run(main())
