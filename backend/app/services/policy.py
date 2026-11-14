"""Target policy, destination resolution, and OpenAPI sanitisation.

A spec-supplied host can never authorize a destination: uploads are validated against
the project policy and rejected when any declared server falls outside it.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import yaml


class PolicyError(ValueError):
    """Raised when a destination or document violates the approved scope."""

    def __init__(self, message: str, *, code: str = "policy_violation") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Destination:
    scheme: str
    host: str
    port: int
    origin: str
    path: str
    url: str

    @property
    def host_header(self) -> str:
        default_port = 443 if self.scheme == "https" else 80
        return self.host if self.port == default_port else f"{self.host}:{self.port}"


def _normalise_origin(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{host}:{port}"


def parse_origin(origin: str) -> tuple[str, str, int]:
    raw = (origin or "").strip()
    if not raw:
        raise PolicyError("Origin is required")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"}:
        raise PolicyError("Only http and https destinations are approved")
    if not parts.hostname:
        raise PolicyError("Origin must include a hostname")
    if parts.username or parts.password:
        raise PolicyError("Credentials must not be embedded in a URL")
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        raise PolicyError("An approved origin must not include a path, query, or fragment")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    host = parts.hostname.lower()
    if _is_blocked_host(host):
        raise PolicyError("Host is not an approved destination for this installation")
    return parts.scheme, host, port


def parse_destination(url: str) -> Destination:
    parts = urlsplit((url or "").strip())
    if parts.scheme not in {"http", "https"}:
        raise PolicyError("Only http and https destinations are approved", code="scheme_denied")
    if not parts.hostname:
        raise PolicyError("Destination must include a hostname", code="host_missing")
    if parts.username or parts.password:
        raise PolicyError("Credentials must not be embedded in a URL", code="userinfo_denied")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    host = parts.hostname.lower()
    path = parts.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    origin = _normalise_origin(parts.scheme, host, port)
    return Destination(
        scheme=parts.scheme,
        host=host,
        port=port,
        origin=origin,
        path=path,
        url=urlunsplit((parts.scheme, parts.netloc, path, parts.query, "")),
    )


def _is_blocked_host(host: str) -> bool:
    """Reject metadata endpoints and control-plane style hosts by default.

    Loopback is policy-controlled because the bundled lab is a loopback target; the
    caller decides that with ``allow_loopback``.
    """
    lowered = host.strip("[]").lower()
    if lowered in {"metadata.google.internal", "metadata", "instance-data"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return address.is_link_local or address.is_multicast or address.is_reserved


@dataclass(frozen=True)
class TargetPolicy:
    base_url: str
    allowed_origins: tuple[str, ...]
    path_prefixes: tuple[str, ...]
    allow_loopback: bool
    environment_label: str = "staging"

    @classmethod
    def from_config(cls, config, *, allow_loopback: bool) -> TargetPolicy:
        origins = tuple(str(o).strip() for o in (config.allowed_origins or []))
        if not origins:
            origins = (config.base_url,)
        prefixes = tuple(
            _normalise_prefix(p) for p in (config.path_prefixes or []) if str(p).strip()
        )
        return cls(
            base_url=config.base_url,
            allowed_origins=origins,
            path_prefixes=prefixes,
            allow_loopback=allow_loopback,
            environment_label=config.environment_label,
        )

    def check(self, url: str, *, enforce_prefix: bool = True) -> Destination:
        destination = parse_destination(url)
        allowed = False
        for origin in self.allowed_origins:
            scheme, host, port = parse_origin(origin)
            if (
                destination.scheme == scheme
                and destination.host == host
                and destination.port == port
            ):
                allowed = True
                break
        if not allowed:
            raise PolicyError(
                "Destination is outside the approved origin allowlist",
                code="origin_denied",
            )
        if _is_loopback(destination) and not self.allow_loopback:
            raise PolicyError(
                "Loopback destinations are disabled for this deployment",
                code="loopback_denied",
            )
        if enforce_prefix and self.path_prefixes:
            normalised = _normalise_prefix(destination.path)
            if not any(
                normalised == prefix or normalised.startswith(prefix.rstrip("/") + "/")
                for prefix in self.path_prefixes
            ):
                raise PolicyError(
                    "Destination path is outside the approved path restrictions",
                    code="path_denied",
                )
        return destination

    def check_redirect(self, location: str, *, from_url: str) -> Destination:
        """Redirects are re-validated against the same policy; none are followed."""
        from urllib.parse import urljoin

        target = urljoin(from_url, location)
        return self.check(target)

    def resolve(self, base_url: str, path_template: str) -> Destination:
        """Resolve a relative replay path against the selected build's base URL."""
        if "://" in path_template or path_template.startswith("//"):
            raise PolicyError("Replay recipes may only use relative paths", code="absolute_path")
        if ".." in path_template.split("?")[0].split("/"):
            raise PolicyError("Replay paths may not traverse directories", code="path_traversal")
        joined = base_url.rstrip("/") + "/" + path_template.lstrip("/")
        return self.check(joined)

    def origins_signature(self) -> str:
        return "|".join(sorted(self.allowed_origins)) + "::" + "|".join(self.path_prefixes)


def _is_loopback(destination: Destination) -> bool:
    host = destination.host
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _normalise_prefix(prefix: str) -> str:
    value = str(prefix or "").strip()
    if not value:
        return "/"
    if not value.startswith("/"):
        value = "/" + value
    if ".." in value.split("/"):
        raise PolicyError("Path restrictions may not traverse directories")
    return value.rstrip("/") or "/"


# ---------------------------------------------------------------------------
# OpenAPI parsing


MAX_REF_DEPTH = 32
_SUPPORTED_DOC_PREFIXES = ("#/",)


class UnsupportedReference(ValueError):
    pass


def load_openapi_document(raw: bytes, filename: str) -> dict:
    if not raw:
        raise PolicyError("The uploaded document is empty")
    text = raw.decode("utf-8-sig", errors="strict")
    lowered = filename.lower()
    if lowered.endswith((".yaml", ".yml")):
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PolicyError(
                f"OpenAPI YAML could not be parsed: {exc.__class__.__name__}"
            ) from exc
    elif lowered.endswith(".json"):
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PolicyError("OpenAPI JSON could not be parsed") from exc
    else:
        raise PolicyError("Only .json, .yaml, and .yml OpenAPI documents are accepted")
    if not isinstance(document, dict):
        raise PolicyError("OpenAPI document must be a JSON/YAML object")
    if not (document.get("openapi") or document.get("swagger")):
        raise PolicyError("Document is not an OpenAPI or Swagger definition")
    if not isinstance(document.get("paths"), dict):
        raise PolicyError("OpenAPI document has no paths object")
    return document


def _iter_server_urls(document: dict):
    """Yield (location, url) for every server declaration, including overrides."""
    if isinstance(document.get("servers"), list):
        for index, server in enumerate(document["servers"]):
            if isinstance(server, dict) and isinstance(server.get("url"), str):
                yield f"servers[{index}]", server["url"]
    base_path = document.get("basePath")
    host = document.get("host")
    if isinstance(base_path, str) and isinstance(host, str):
        scheme = "https"
        schemes = document.get("schemes")
        if isinstance(schemes, list) and schemes and isinstance(schemes[0], str):
            scheme = schemes[0]
        yield "host/basePath", f"{scheme}://{host}{base_path}"
    paths = document.get("paths")
    if not isinstance(paths, dict):
        return
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for index, server in enumerate(item.get("servers") or []):
            if isinstance(server, dict) and isinstance(server.get("url"), str):
                yield f"paths[{path}].servers[{index}]", server["url"]
        for method, operation in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(operation, dict):
                continue
            for index, server in enumerate(operation.get("servers") or []):
                if isinstance(server, dict) and isinstance(server["url"], str):
                    yield f"paths[{path}].{method}.servers[{index}]", server["url"]


def _resolve_local_ref(document: dict, ref: str, depth: int = 0):
    if depth > MAX_REF_DEPTH:
        raise UnsupportedReference("reference chain too deep")
    if not ref.startswith(_SUPPORTED_DOC_PREFIXES):
        raise UnsupportedReference(f"external reference is not supported: {ref[:120]}")
    node: object = document
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise UnsupportedReference(f"unresolvable local reference: {ref[:120]}")
        node = node[part]
    if isinstance(node, dict) and isinstance(node.get("$ref"), str):
        return _resolve_local_ref(document, node["$ref"], depth + 1)
    return node


def _sanitise_node(node, document: dict, *, depth: int = 0):
    if depth > MAX_REF_DEPTH:
        raise UnsupportedReference("reference chain too deep")
    if isinstance(node, dict):
        if "$ref" in node:
            resolved = _resolve_local_ref(document, str(node["$ref"]), depth + 1)
            return _sanitise_node(resolved, document, depth=depth + 1)
        return {
            key: _sanitise_node(value, document, depth=depth + 1)
            for key, value in node.items()
            if key not in {"servers", "host", "basePath", "schemes"}
        }
    if isinstance(node, list):
        return [_sanitise_node(item, document, depth=depth + 1) for item in node]
    return node


def sanitise_openapi(document: dict, policy: TargetPolicy) -> tuple[dict, list[str], list[dict]]:
    """Validate every declared server, then return a sanitised doc and its operations.

    Raises ``PolicyError`` when any server declaration (root, path, operation, or
    Swagger host/basePath) is outside the project's approved origin and prefixes.
    """
    declared_urls: list[tuple[str, str]] = list(_iter_server_urls(document))
    for location, url in declared_urls:
        try:
            # Origin only: path restrictions apply to executed requests, not to a
            # document's declared server base.
            policy.check(url, enforce_prefix=False)
        except PolicyError as exc:
            raise PolicyError(
                f"{location} declares an unapproved server ({_safe_url(url)}): {exc}",
                code="openapi_server_denied",
            ) from exc

    operations: list[dict] = []
    paths = document.get("paths") or {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            lowered = method.lower()
            if lowered not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(operation, dict):
                continue
            operations.append(
                {
                    "path": str(path),
                    "method": lowered.upper(),
                    "operation_id": str(operation.get("operationId") or "")[:120],
                    "summary": str(operation.get("summary") or "")[:200],
                }
            )

    sanitised = _sanitise_node(document, document)
    if not isinstance(sanitised, dict):
        raise PolicyError("OpenAPI document could not be sanitised")
    sanitised["servers"] = [{"url": policy.base_url}]
    declared = sorted({url for _, url in declared_urls})
    operations.sort(key=lambda item: (item["path"], item["method"]))
    return sanitised, declared, operations


def _safe_url(url: str) -> str:
    try:
        destination = parse_destination(url)
        return destination.origin + destination.path
    except PolicyError:
        return "[invalid url]"
