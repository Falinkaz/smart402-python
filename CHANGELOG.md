# Changelog

## 0.1.0 — Initial release

- `Smart402Client` — async HTTP client for `POST /evaluate`
- `smart402_hook` — x402 `on_before_payment_creation` lifecycle hook
- `Smart402Guard` — convenience wrapper for x402Client with smart402 protection
- `fail_open` / `fail_closed` modes
- Pydantic v2 models for request/response
