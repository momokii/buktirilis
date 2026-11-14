"""Redaction and output-safe formatting shared by evidence, logs, and exports."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
        "x-xsrf-token",
        "x-session-token",
        "api-key",
    }
)

SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "client_secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "session",
        "session_id",
        "credential",
        "private_key",
        "bearer",
    }
)

REDACTED = "[REDACTED]"

_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}")
_BASIC_RE = re.compile(r"(?i)\b(basic)\s+[A-Za-z0-9+/=]{8,}")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:token|access_token|api_key|apikey|password|secret|sig|signature)=)[^&#\s]+"
)
_HEADER_LINE_RE = re.compile(
    r"(?im)^((?:authorization|cookie|set-cookie|x-api-key|x-auth-token)\s*:\s*).+$"
)


def redact_text(value: str) -> str:
    value = _BEARER_RE.sub(r"\1 [REDACTED]", value)
    value = _BASIC_RE.sub(r"\1 [REDACTED]", value)
    value = _JWT_RE.sub(REDACTED, value)
    value = _QUERY_SECRET_RE.sub(r"\1[REDACTED]", value)
    return _HEADER_LINE_RE.sub(r"\1[REDACTED]", value)


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    cleaned: dict[str, str] = {}
    for name, value in headers.items():
        key = name.lower()
        if key in SENSITIVE_HEADERS:
            cleaned[name] = REDACTED
        else:
            cleaned[name] = redact_text(str(value))
    return cleaned


def redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if (
        lowered in SENSITIVE_FIELD_NAMES
        or lowered in SENSITIVE_HEADERS
        or any(part in lowered for part in ("password", "secret", "token", "credential"))
    ):
        return REDACTED
    if isinstance(value, dict):
        return redact_payload(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(k): redact_value(str(k), v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, str):
        return redact_text(payload)
    return payload


def truncate(value: str, limit: int = 8000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n[truncated {len(value) - limit} characters]"


def csv_cell(value: Any) -> str:
    """Neutralise spreadsheet formula triggers (CWE-1236), then stringify."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def looks_secret_like(value: str) -> bool:
    """True when a value carries a credential-shaped string (tests, guards)."""
    if _BEARER_RE.search(value) or _JWT_RE.search(value) or _BASIC_RE.search(value):
        return True
    lowered = value.lower()
    return any(
        marker in lowered for marker in ("password=", "authorization:", "cookie:", "api_key=")
    )
