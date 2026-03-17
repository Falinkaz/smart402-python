# Security and Trust Model

smart402 is a risk evaluation service for AI agent payments. This document explains exactly what the SDK sees, what it sends, and what it cannot do — so you can verify these claims by reading the source.

---

## What the SDK sends to smart402

When your agent encounters an x402 payment requirement, the SDK calls `POST /evaluate` with this data:

```json
{
  "agent_id": "your-agent-id",
  "agent_wallet_address": "0x...",
  "agent_framework": "langchain",
  "wallet_provider": "local_evm",
  "sdk_version": "0.1.0",
  "payment_requirements": {
    "amount": "0.10",
    "token": "USDC",
    "network": "eip155:8453",
    "pay_to": "0x9dBA414637c611a16BEa6f0796BFcbcBdc410df8",
    "scheme": "exact",
    "description": "Weather data — 1 request"
  }
}
```

**All of these fields are visible to the counterparty or the x402 protocol anyway.** The `pay_to` address is public. The `amount` and `token` are in the payment requirement served by the seller. The `agent_wallet_address` is the public key, not the private key.

---

## What the SDK does NOT send

- **Private keys** — the SDK never asks for them, never touches them
- **Wallet seed phrases** — same
- **Signed transactions** — signing happens after smart402 approves, in your wallet/signer
- **Raw transaction data** — smart402 evaluates payment *requirements*, not signed transactions
- **Wallet balances** — not requested, not sent
- **Other agent state** — only the fields above

You can verify this by reading the source:

- Python: [`smart402/client.py`](smart402/client.py) — the only outbound HTTP call
- Python: [`smart402/guard.py`](smart402/guard.py) — what gets extracted from x402 requirements
- Python: [`smart402/models.py`](smart402/models.py) — the exact request schema

Or proxy the SDK's HTTP calls with mitmproxy and inspect what goes over the wire.

---

## What smart402 can do

- Return `approve` or `deny` for a payment
- Log the evaluation: amount, token, counterparty address, decision, latency
- Update your agent's spend counters for budget enforcement
- Cache counterparty metadata (contract type, wallet age) from public Etherscan data

---

## What smart402 cannot do

- Sign transactions — it has no access to your private key
- Initiate payments — it responds to your evaluation requests, never initiates
- Modify payment parameters — it returns an approve/deny decision; your code decides what to do next
- Redirect payments to a different address — the SDK does not modify `pay_to`
- Access your wallet funds — no key, no access

---

## The SDK trust boundary

The SDK is a thin HTTP client. The Python SDK is ~300 lines across 4 files. It does two things:

1. Converts the x402 `PaymentRequirements` object to the smart402 request format
2. Calls `POST /evaluate` and returns the response

It does not hook into wallet signing. It does not intercept or modify transactions. It does not hold state between calls beyond configuration. Your agent code decides what to do with the `approve`/`deny` response — the SDK does not enforce anything.

**Zero network calls beyond the single `POST /evaluate`.** No telemetry, no analytics, no side-channel requests.

---

## Fail modes

You control what happens when smart402 is unreachable:

| Mode | Behavior |
|------|----------|
| `fail_open` (default) | SDK returns a synthetic `approve` — payment proceeds. You lose risk protection but keep functionality. |
| `fail_closed` | SDK raises `Smart402Unavailable` — payment is blocked until the API recovers. |

Set `fail_mode="fail_closed"` for high-value agents where safety is more important than uptime.

---

## Data stored by the hosted service

When you use the hosted API at `https://streetsmart-api.fly.dev`:

**Stored per evaluation:**
- Amount, token, network, counterparty address (`pay_to`)
- Decision (`approve`/`deny`) and triggered rules
- Latency and timestamp
- Agent ID and account ID (your account, not your private key)

**Counterparty cache** (shared across accounts for efficiency):
- Whether `pay_to` is a contract or EOA
- Wallet age in days (derived from first transaction, via Etherscan)
- Whether the contract is verified on Etherscan

**Never stored:**
- Private keys
- Signed transactions
- Wallet balances
- Any data not listed above

**Isolation:** All evaluation data is scoped to your account. Other accounts cannot see your evaluations, agents, or policies. Dashboard access is authenticated via Clerk.

---

## How to verify these claims

1. **Read the SDK source** — it's ~300 lines of Python. The entire outbound request is in `client.py`.
2. **Proxy the SDK** — use mitmproxy or Charles and inspect the actual HTTP call.
3. **Check the request schema** — `models.py` defines exactly what gets serialized.
4. **Run the tests** — `pytest tests/` — they use mock HTTP and confirm no unexpected calls are made.
