# smart402 — Python SDK

Deterministic policy engine for AI agent payments via [x402](https://x402.org).

No LLM in the decision path. Every approve/deny traces to a rule your team configured — not a model's judgment call. A compromised agent cannot reason or prompt-inject its way past smart402.

> **v0.4.0:** Confirmed on-chain spend tracking. Budgets now reflect payments that actually landed on-chain.

## Install

```bash
pip install smart402
```

For x402 integration extras:

```bash
pip install "smart402[x402]"
```

Python 3.10+ required.

## Before you start

1. Sign up at https://smart402-dashboard.vercel.app
2. Create an agent in the dashboard
3. Configure at least one policy (e.g., daily budget of $10)
4. Create an evaluate-scoped API key in Settings → API Keys
5. Follow the Quick Start below.

## Quick Start

```python
import asyncio
import os
from smart402 import Smart402Client

async def main():
    client = Smart402Client(
        api_key=os.environ["SMART402_AGENT_KEY"],
        agent_id="my-agent-001",
    )

    result = await client.evaluate_payment(
        amount="0.10",          # USDC amount as a decimal string. "0.10" = ten cents. The Python SDK expects pre-converted dollar decimals.
        token="USDC",
        network="eip155:8453",  # Base mainnet (CAIP-2)
        pay_to="0x9dBA414637c611a16BEa6f0796BFcbcBdc410df8",
    )

    print(result.decision)           # "approve" or "deny"
    print(result.triggered_rules)    # [] or ["counterparty_not_on_allowlist", ...]

asyncio.run(main())
```

[Get an API key →](https://smart402-dashboard.vercel.app)

**Synchronous usage:** `asyncio.run()` wraps any async call. A sync API is planned for v0.2.

## x402 Integration

If your agent uses the [x402 Python SDK](https://github.com/coinbase/x402), register smart402 as a lifecycle hook:

```python
from smart402 import smart402_hook
from x402 import x402Client
from x402.mechanisms.evm.exact import register_exact_evm_client
from x402.mechanisms.evm.signers import EthAccountSigner
from eth_account import Account

account = Account.from_key(os.environ["EVM_PRIVATE_KEY"])
signer = EthAccountSigner(account)

client = x402Client()
register_exact_evm_client(client, signer)

# One line to add smart402 protection
client.on_before_payment_creation(
    smart402_hook(
        api_key=os.environ["SMART402_AGENT_KEY"],
        agent_id="my-agent-001",
        agent_wallet_address=signer.address,
    )
)

# Every payment the x402 client makes is now evaluated first
```

The hook fires before each payment is signed. If smart402 denies the payment, `AbortResult` is returned and the payment is not made.

## Advanced Usage

For full control over all request fields, use the Pydantic models directly:

```python
from smart402 import Smart402Client
from smart402.models import EvaluateRequest, PaymentRequirementsPayload

client = Smart402Client(
    api_key=os.environ["SMART402_AGENT_KEY"],
    agent_id="my-agent-001",
)

result = await client.evaluate(
    EvaluateRequest(
        agent_id=client.agent_id,  # set in the constructor above
        agent_wallet_address="0x...",
        payment_requirements=PaymentRequirementsPayload(
            amount="0.10",
            token="USDC",
            network="eip155:8453",
            pay_to="0x9dBA414637c611a16BEa6f0796BFcbcBdc410df8",
        ),
    )
)
```

## Configuration

**`Smart402Client(api_key, agent_id, ...)`**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | required | smart402 API key |
| `agent_id` | required | Agent identifier (from dashboard) |
| `base_url` | `https://streetsmart-api.fly.dev` | API base URL |

**Amount format:** Pass `amount` as a decimal dollar string — `"0.10"` = ten cents. The Python SDK expects pre-converted dollar decimals. If you're reading the amount from an x402 `PaymentRequirements` object (which uses raw USDC units), convert it first: `str(int(raw_amount) / 1_000_000)`.

**`smart402_hook(api_key, agent_id, ...)`**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | required | smart402 API key |
| `agent_id` | required | Agent identifier (from dashboard) |
| `smart402_url` | `https://streetsmart-api.fly.dev` | API base URL |
| `fail_mode` | `"fail_open"` | Behavior when API is unreachable |
| `agent_wallet_address` | `None` | Agent's public EVM address |
| `wallet_provider` | `None` | e.g. `"coinbase"`, `"local_evm"` |
| `agent_framework` | `None` | e.g. `"langchain"`, `"langgraph"` |

## Fail-Open vs Fail-Closed

```python
# fail_open (default): if smart402 is unreachable, payment proceeds
smart402_hook(api_key="...", agent_id="...", fail_mode="fail_open")

# fail_closed: if smart402 is unreachable, payment is blocked
smart402_hook(api_key="...", agent_id="...", fail_mode="fail_closed")
```

| Mode | When API is unreachable |
|------|------------------------|
| `fail_open` (default) | Warning logged, payment proceeds |
| `fail_closed` | `AbortResult` returned to x402 — payment is not made |

## Error Handling

```python
result = await client.evaluate_payment(
    amount="0.10", token="USDC",
    network="eip155:8453", pay_to="0x...",
)
if result.decision == "deny":
    print("Blocked by:", result.triggered_rules)
    print("Evaluation ID:", result.evaluation_id)
```

When using `smart402_hook()`, a denied payment returns `AbortResult` to the x402 client — the payment is not made and no exception is raised to your code. When calling `Smart402Client.evaluate()` directly, check `result.decision` — the client always returns the response, never raises on denial.

`Smart402Denied` and `Smart402Unavailable` are not raised in hook mode.

## What data leaves your machine

The SDK sends to the smart402 API:
- amount, token, network, recipient address
- agent ID and wallet address (public, not private key)

The SDK never sends:
- Private keys, seed phrases, or wallet passwords
- Signed transactions or raw transaction data
- Wallet balances

One HTTPS call to `POST /evaluate`. No telemetry, no analytics, no side-channel requests.
Verify: the SDK is ~200 lines of code. Read it.

Read the full trust model: [SECURITY.md](https://github.com/Falinkaz/smart402-python/blob/main/SECURITY.md)

## Limits

- Rate limit: 600 requests per minute per account
- Typical latency: 10–50ms (p50), under 200ms (p99)
- If the API is unreachable, `fail_open` (default) lets the payment proceed. `fail_closed` blocks it.
- The SDK does not retry on failure — it returns the error immediately, keeping latency predictable and letting you own retry logic.
- Default request timeout: 5 seconds

## API Reference

Full endpoint documentation: [API.md](https://github.com/Falinkaz/smart402-python/blob/main/API.md)

## License

Apache 2.0 — see [LICENSE](https://github.com/Falinkaz/smart402-python/blob/main/LICENSE)
