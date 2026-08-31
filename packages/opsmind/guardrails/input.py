"""Input guardrails — jailbreak / injection / hostile prompts (P5)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""
    rule: str = ""


_JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)?\s*(system\s+)?instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)?\s*(system\s+)?instructions",
    r"forget\s+(everything|all\s+previous)",
    r"you\s+are\s+now\s+(dan|unrestricted|jailbroken)",
    r"override\s+(your\s+)?(system|safety)\s+(prompt|policy)",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    r"developer\s+mode\s+enabled",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"(output|reveal|show|dump)\s+(the\s+)?(database\s+)?(passwords|credentials|keys)",
    r"(admin|root)\s+credentials",
]

_INJECTION_PATTERNS = [
    r"<\s*system\s*>",
    r"```\s*system",
    r"\[\s*system\s*\]",
    r"new\s+system\s+prompt\s*:",
    r"tool\s*:\s*execute",
    r";\s*drop\s+table\b",
    r"union\s+select\b",
]


def check_input_guardrails(text: str) -> GuardrailResult:
    """Reject classic jailbreak / injection style inputs before the graph runs."""
    raw = text or ""
    lower = raw.lower()

    for pat in _JAILBREAK_PATTERNS:
        if re.search(pat, lower):
            return GuardrailResult(
                allowed=False,
                reason="Input rejected by jailbreak/injection guardrail.",
                rule=pat,
            )
    for pat in _INJECTION_PATTERNS:
        if re.search(pat, lower):
            return GuardrailResult(
                allowed=False,
                reason="Input rejected by prompt-injection guardrail.",
                rule=pat,
            )
    return GuardrailResult(allowed=True)
