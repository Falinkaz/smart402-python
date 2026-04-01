# Changelog

## 0.3.0

- `_raw_usdc_to_decimal()`: `evaluate_payment()` now accepts raw USDC units (e.g. `"100000"`) matching the TypeScript SDK; raises `ValueError` on invalid input
- `Smart402Client` now reuses a single `httpx.AsyncClient` across calls (lower latency at high throughput); add `aclose()` / async context manager support

## 0.2.0

- `Smart402Guard`: class-based interface that separates evaluation from signing; works with eth_account, CDP wallets (AgentKit), Privy, and any signing mechanism
- `wallet_address` parameter on guard and hook for counterparty familiarity checks

## 0.1.0 — Initial release

- `Smart402Client` — async HTTP client for `POST /evaluate`
- `smart402_hook` — x402 `on_before_payment_creation` lifecycle hook
- `Smart402Guard` — convenience wrapper for x402Client with smart402 protection
- `fail_open` / `fail_closed` modes
- Pydantic v2 models for request/response
