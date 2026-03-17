# smart402 API Reference

Base URL: `https://streetsmart-api.fly.dev`

---

## Authentication

All endpoints except `/health` require a Bearer token:

```
Authorization: Bearer ag_live_xxxxxxxxxxxxxxxx
```

API keys are generated when you sign up at [smart402-dashboard.vercel.app](https://smart402-dashboard.vercel.app). You can rotate your key from the Settings page.

---

## Core Endpoint

### POST /evaluate

Evaluate a payment against your agent's policies. Call this before signing any payment.

**Amount format:** Dollar decimal string, e.g. `"0.10"` for $0.10 USDC. The Python SDK's `smart402_hook` converts from x402's smallest-unit format automatically. If calling the API directly, pass dollar amounts.

**Request:**

```json
{
  "agent_id": "my-agent-001",
  "agent_wallet_address": "0xABCD...",
  "agent_framework": "langchain",
  "wallet_provider": "local_evm",
  "sdk_version": "0.1.0",
  "payment_requirements": {
    "amount": "0.10",
    "token": "USDC",
    "network": "eip155:8453",
    "pay_to": "0x9dBA414637c611a16BEa6f0796BFcbcBdc410df8",
    "scheme": "exact",
    "description": "Weather data — 1 request",
    "facilitator": "https://facilitator.coinbase.com"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | yes | Agent identifier (from dashboard or `external_id`) |
| `payment_requirements.amount` | string | yes | Dollar decimal string, e.g. `"0.10"` |
| `payment_requirements.token` | string | yes | Token symbol, e.g. `"USDC"` |
| `payment_requirements.network` | string | yes | CAIP-2 chain ID, e.g. `"eip155:8453"` |
| `payment_requirements.pay_to` | string | yes | Recipient address |
| `agent_wallet_address` | string | no | Sender address (for audit trail) |
| `agent_framework` | string | no | e.g. `"langchain"`, `"langgraph"` |
| `wallet_provider` | string | no | e.g. `"coinbase"`, `"local_evm"` |

**Response (approve):**

```json
{
  "decision": "approve",
  "evaluation_id": "3f7a1b2c-...",
  "evaluated_at": "2026-03-06T12:00:00Z",
  "counterparty_risk_score": "low",
  "counterparty_details": {
    "is_contract": false,
    "wallet_age_days": 142,
    "times_seen_by_agent": 8,
    "first_time": false
  },
  "rules_checked": 10,
  "triggered_rules": [],
  "remaining_daily_budget": "0.90",
  "latency_ms": 12
}
```

**Response (deny):**

```json
{
  "decision": "deny",
  "evaluation_id": "9c4d2e1f-...",
  "evaluated_at": "2026-03-06T12:00:01Z",
  "counterparty_risk_score": "medium",
  "rules_checked": 10,
  "triggered_rules": ["counterparty_not_on_allowlist"],
  "remaining_daily_budget": "1.00",
  "latency_ms": 8
}
```

**curl:**

```bash
curl -X POST https://streetsmart-api.fly.dev/evaluate \
  -H "Authorization: Bearer ag_live_xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent-001",
    "payment_requirements": {
      "amount": "0.10",
      "token": "USDC",
      "network": "eip155:8453",
      "pay_to": "0x9dBA414637c611a16BEa6f0796BFcbcBdc410df8"
    }
  }'
```

**Errors:**

| Code | Meaning |
|------|---------|
| 401 | Invalid or missing API key |
| 404 | Agent not found (check `agent_id`) |
| 422 | Validation error (check request body) |
| 429 | Rate limit exceeded |

---

## Agents

### GET /agents

List all agents for your account.

```bash
curl https://streetsmart-api.fly.dev/agents \
  -H "Authorization: Bearer ag_live_xxxxxxxx"
```

**Response:**

```json
[
  {
    "id": "uuid",
    "external_id": "my-agent-001",
    "name": "Weather Agent",
    "status": "active",
    "agent_framework": "langchain",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-03-06T00:00:00Z"
  }
]
```

---

### POST /agents

Create a new agent.

```bash
curl -X POST https://streetsmart-api.fly.dev/agents \
  -H "Authorization: Bearer ag_live_xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Agent", "external_id": "my-agent-001"}'
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Human-readable label |
| `external_id` | no | Your own identifier (used in `/evaluate`) |
| `agent_framework` | no | e.g. `"langchain"` |

---

### GET /agents/{id}

Get a single agent by UUID or `external_id`.

---

### PATCH /agents/{id}

Update agent name or status.

```bash
curl -X PATCH https://streetsmart-api.fly.dev/agents/uuid \
  -H "Authorization: Bearer ag_live_xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Name", "status": "paused"}'
```

Status values: `active`, `paused`, `disabled`

---

### DELETE /agents/{id}

Delete an agent and all its policies.

---

## Policies

### GET /agents/{id}/policies

List all policies for an agent.

```bash
curl https://streetsmart-api.fly.dev/agents/uuid/policies \
  -H "Authorization: Bearer ag_live_xxxxxxxx"
```

---

### POST /agents/{id}/policies

Create a policy.

```bash
curl -X POST https://streetsmart-api.fly.dev/agents/uuid/policies \
  -H "Authorization: Bearer ag_live_xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "policy_type": "daily_budget",
    "parameters": {"max_daily": "10.00", "token": "USDC"},
    "priority": 10
  }'
```

**Policy types:**

| Policy type | Parameters | Description |
|-------------|------------|-------------|
| `max_transaction_amount` | `max_amount`, `token` | Max per-transaction amount |
| `daily_budget` | `max_daily`, `token` | Max daily spend |
| `weekly_budget` | `max_weekly`, `token` | Max weekly spend |
| `monthly_budget` | `max_monthly`, `token` | Max monthly spend |
| `allowed_tokens` | `tokens` (list) | Whitelist of allowed token symbols |
| `allowed_chains` | `chains` (list) | Whitelist of allowed CAIP-2 networks |
| `counterparty_allowlist` | `addresses` (list) | Only pay these addresses |
| `counterparty_blocklist` | `addresses` (list) | Never pay these addresses |
| `time_restriction` | `allowed_hours_utc` (list of `[start, end]`) | Restrict payments to time windows |
| `contract_restriction` | `allow_contracts` (bool), `require_verified` (bool) | Contract interaction rules |
| `counterparty_familiarity` | `require_seen_before` (bool), `max_amount_first_time` | Familiarity-based limits |
| `wallet_age_restriction` | `min_age_days` | Minimum counterparty wallet age |
| `counterparty_risk_threshold` | `max_risk_score` (`"low"`, `"medium"`, `"high"`) | Block by risk score |

---

### PATCH /agents/{id}/policies/{policy_id}

Update a policy's parameters or priority.

---

### DELETE /agents/{id}/policies/{policy_id}

Delete a policy.

---

## Evaluations

### GET /agents/{id}/evaluations

List recent evaluations (paginated).

```bash
curl "https://streetsmart-api.fly.dev/agents/uuid/evaluations?limit=20" \
  -H "Authorization: Bearer ag_live_xxxxxxxx"
```

Query params: `limit` (default 20, max 100), `after` (cursor — `evaluation_id` for pagination)

---

### GET /agents/{id}/stats

Spend statistics for an agent.

```bash
curl https://streetsmart-api.fly.dev/agents/uuid/stats \
  -H "Authorization: Bearer ag_live_xxxxxxxx"
```

**Response:**

```json
{
  "daily_spend": "0.50",
  "weekly_spend": "2.30",
  "monthly_spend": "8.10",
  "total_evaluations": 47,
  "approve_count": 44,
  "deny_count": 3
}
```

---

## Account

### GET /account/info

Your account details.

```bash
curl https://streetsmart-api.fly.dev/account/info \
  -H "Authorization: Bearer ag_live_xxxxxxxx"
```

**Response:**

```json
{
  "id": "uuid",
  "email": "you@example.com",
  "display_name": "Your Name",
  "api_key_prefix": "ag_live_xxxx",
  "plan": "free",
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

### POST /account/keys/rotate

> **Deprecated — returns 410 Gone.** Use `POST /account/keys/{id}/rotate` with a specific key ID instead. Find key IDs via `GET /account/keys`.

Rotate a specific API key. Returns the new key once — store it immediately.

```bash
curl -X POST https://streetsmart-api.fly.dev/account/keys/{id}/rotate \
  -H "Authorization: Bearer ag_live_xxxxxxxx"
```

**Response:**

```json
{
  "id": "uuid",
  "name": "My agent key",
  "scope": "evaluate",
  "key": "ag_live_newkeyxxxxxxxxxxxxxxxx",
  "key_prefix": "ag_live_newk",
  "message": "Key rotated. The old key is no longer valid."
}
```

The old key is invalidated immediately.

---

### GET /account/audit

Audit log of account actions (key rotations, policy changes).

---

## Health

### GET /health

No auth required.

```bash
curl https://streetsmart-api.fly.dev/health
```

```json
{"status": "ok", "version": "0.1.0"}
```

---

## Error format

All errors return:

```json
{
  "detail": "Human-readable error message"
}
```

| Code | Meaning |
|------|---------|
| 400 | Bad request |
| 401 | Unauthorized — invalid or missing API key |
| 404 | Not found |
| 409 | Conflict |
| 422 | Validation error — check request body |
| 429 | Rate limit exceeded — back off and retry |
| 500 | Internal server error |
