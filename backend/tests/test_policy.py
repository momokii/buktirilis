"""Target policy and OpenAPI sanitisation tests."""

from __future__ import annotations

import pytest

from app.services.policy import (
    PolicyError,
    TargetPolicy,
    load_openapi_document,
    parse_origin,
    sanitise_openapi,
)


def policy(**overrides) -> TargetPolicy:
    values = {
        "base_url": "https://staging.example.test",
        "allowed_origins": ("https://staging.example.test",),
        "path_prefixes": ("/api",),
        "allow_loopback": False,
    }
    values.update(overrides)
    return TargetPolicy(**values)


def test_origin_requires_http_scheme_and_no_path():
    with pytest.raises(PolicyError):
        parse_origin("ftp://staging.example.test")
    with pytest.raises(PolicyError):
        parse_origin("https://staging.example.test/api")
    with pytest.raises(PolicyError):
        parse_origin("https://user:pass@staging.example.test")


def test_metadata_host_is_rejected():
    with pytest.raises(PolicyError):
        parse_origin("http://metadata.google.internal")


def test_destination_outside_allowlist_is_denied():
    with pytest.raises(PolicyError) as exc:
        policy().check("https://other.example.test/api/invoices")
    assert exc.value.code == "origin_denied"


def test_path_restriction_denied():
    with pytest.raises(PolicyError) as exc:
        policy().check("https://staging.example.test/admin/settings")
    assert exc.value.code == "path_denied"
    policy().check("https://staging.example.test/api/invoices")


def test_loopback_disabled_by_default():
    local = policy(
        base_url="http://127.0.0.1:8099",
        allowed_origins=("http://127.0.0.1:8099",),
        allow_loopback=False,
    )
    with pytest.raises(PolicyError) as exc:
        local.check("http://127.0.0.1:8099/api/me")
    assert exc.value.code == "loopback_denied"
    allowed = policy(
        base_url="http://127.0.0.1:8099",
        allowed_origins=("http://127.0.0.1:8099",),
        allow_loopback=True,
    )
    assert allowed.check("http://127.0.0.1:8099/api/me").host == "127.0.0.1"


def test_redirect_outside_scope_is_denied():
    with pytest.raises(PolicyError):
        policy().check_redirect(
            "https://evil.example.test/steal", from_url="https://staging.example.test/api/x"
        )


def test_terminal_slash_and_ports_are_normalised():
    destination = policy().check("https://staging.example.test:443/api/invoices")
    assert destination.origin == "https://staging.example.test:443"


def _spec(servers=None, path_servers=None, operation_servers=None):
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test", "version": "1"},
        "servers": servers or [{"url": "https://staging.example.test"}],
        "paths": {
            "/api/invoices": {
                "servers": path_servers or [],
                "get": {
                    "operationId": "listInvoices",
                    "servers": operation_servers or [],
                    "responses": {"200": {"description": "ok"}},
                },
            }
        },
    }


def test_openapi_accepts_approved_server_and_sanitises():
    sanitised, declared, operations = sanitise_openapi(_spec(), policy())
    assert declared == ["https://staging.example.test"]
    assert sanitised["servers"] == [{"url": "https://staging.example.test"}]
    assert operations[0]["path"] == "/api/invoices"
    assert "servers" not in sanitised["paths"]["/api/invoices"]["get"]


def test_openapi_root_server_override_fails_closed():
    with pytest.raises(PolicyError) as exc:
        sanitise_openapi(_spec(servers=[{"url": "https://evil.example.test"}]), policy())
    assert exc.value.code == "openapi_server_denied"


def test_openapi_path_level_override_fails_closed():
    with pytest.raises(PolicyError):
        sanitise_openapi(_spec(path_servers=[{"url": "https://evil.example.test"}]), policy())


def test_openapi_operation_level_override_fails_closed():
    with pytest.raises(PolicyError):
        sanitise_openapi(_spec(operation_servers=[{"url": "https://evil.example.test"}]), policy())


def test_swagger_host_override_fails_closed():
    document = {
        "swagger": "2.0",
        "info": {"title": "Legacy", "version": "1"},
        "host": "evil.example.test",
        "basePath": "/api",
        "schemes": ["https"],
        "paths": {"/api/invoices": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }
    with pytest.raises(PolicyError):
        sanitise_openapi(document, policy())


def test_openapi_rejects_external_refs():
    document = _spec()
    document["paths"]["/api/invoices"]["get"]["responses"] = {
        "200": {"$ref": "https://evil.example.test/schema.json"}
    }
    with pytest.raises(Exception):  # noqa: B017 - UnsupportedReference is a ValueError
        sanitise_openapi(document, policy())


def test_openapi_parsing_requires_supported_extension_and_shape():
    with pytest.raises(PolicyError):
        load_openapi_document(b"{}", "spec.txt")
    with pytest.raises(PolicyError):
        load_openapi_document(b"{}", "spec.json")
    document = load_openapi_document(
        b'{"openapi":"3.0.3","info":{"title":"t","version":"1"},"paths":{}}', "spec.json"
    )
    assert document["openapi"] == "3.0.3"
