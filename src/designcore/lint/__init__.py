"""Deterministic diagram checks. Nothing here calls a model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # "error" | "warning"
    message: str
    subject: str = ""


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity == "error" for f in findings)
