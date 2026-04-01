"""smart402 SDK — deterministic risk engine for AI agent payments via x402."""

from .client import Smart402Client
from .guard import Smart402Guard, smart402_hook

__version__ = "0.4.0"

__all__ = [
    "smart402_hook",
    "Smart402Guard",
    "Smart402Client",
]
