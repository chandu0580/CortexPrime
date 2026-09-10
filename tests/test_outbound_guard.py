"""Phase 11.1 (ADR-121): the outbound-request guard at the real request boundary.

Judgement is by parsing (the transport fabric's classifier), not by pattern,
and the request itself connects to the judged address with the original Host
and SNI, re-judging every redirect hop. These tests never touch the network:
DNS is a fake resolver, HTTP is an httpx mock transport.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.safety.guardrails_engine import GuardrailDecision, ToolCallGuardrail
from backend.safety.outbound_guard import (
    HTTPS_ONLY,
    OutboundRefused,
    assert_outbound_url,
    guarded_get,
    judge_outbound_url,
)
from backend.safety.rate_limiter import _LIMITS, _classify_endpoint


class _Resolver:
    def __init__(self, table: dict, *, raise_for: tuple = ()) -> None:
        self.table = table
        self.raise_for = raise_for
        self.calls: list = []

    def resolve(self, host: str, port: int, *, timeout_seconds: float) -> tuple:
        self.calls.append((host, port))
        if host in self.raise_for:
            raise OSError("nxdomain")
        return tuple(self.table.get(host, ()))


PRIVATE_LITERALS = [
    "http://localhost/",
    "http://LOCALHOST./",
    "http://ip6-localhost/",
    "http://foo.localhost/",
    "http://127.0.0.1:8080/internal",
    "http://127.1/",
    "http://2130706433/",          # decimal 127.0.0.1
    "http://0x7f000001/",          # hexadecimal
    "http://0177.0.0.1/",          # octal
    "http://0.0.0.0/",
    "http://10.0.0.1/",
    "http://172.16.5.5/",
    "http://192.168.1.100/admin",
    "http://169.254.169.254/latest/meta-data/",   # AWS/GCP/Azure metadata
    "http://169.254.170.2/",                      # ECS task metadata
    "http://100.100.100.200/",                    # Alibaba metadata
    "http://100.64.0.1/",                         # carrier-grade NAT
    "http://224.0.0.1/",                          # multicast
    "http://255.255.255.255/",
    "http://[::1]/",
    "http://[::]/",
    "http://[::ffff:127.0.0.1]/",                 # IPv4-mapped loopback
    "http://[::ffff:10.0.0.1]/",                  # IPv4-mapped private
    "http://[fe80::1]/",                          # link-local
    "http://[fd00::1]/",                          # unique-local
    "http://[fd00:ec2::254]/",                    # AWS IMDSv6
]


class TestLiteralJudgement:
    @pytest.mark.parametrize("url", PRIVATE_LITERALS)
    def test_private_forms_are_refused_without_dns(self, url):
        resolver = _Resolver({})
        j = judge_outbound_url(url, resolver=resolver)
        assert j.allowed is False, url
        assert resolver.calls == [], "a literal must never be resolved"

    @pytest.mark.parametrize("url", [
        "ftp://example.com/x", "file:///etc/passwd", "gopher://example.com/",
        "javascript:alert(1)", "//example.com/x", "example.com", "",
    ])
    def test_unsupported_or_missing_scheme_is_refused(self, url):
        assert judge_outbound_url(url, resolver=_Resolver({})).allowed is False

    def test_https_only_refuses_plaintext(self):
        assert judge_outbound_url("http://example.com/", permitted_schemes=HTTPS_ONLY,
                                  resolver=_Resolver({"example.com": ["93.184.216.34"]})).allowed is False

    def test_credentials_in_url_are_refused(self):
        j = judge_outbound_url("https://user:secret@example.com/", resolver=_Resolver({}))
        assert j.allowed is False and "credential" in j.reason

    def test_control_characters_are_refused(self):
        assert judge_outbound_url("https://example.com/a\r\nX: y", resolver=_Resolver({})).allowed is False

    def test_public_literal_is_allowed_and_pinned(self):
        j = judge_outbound_url("https://93.184.216.34/x", resolver=_Resolver({}))
        assert j.allowed and j.pinned_addresses == ("93.184.216.34",) and j.port == 443


class TestResolutionJudgement:
    def test_public_hostname_is_pinned_to_every_answer(self):
        r = _Resolver({"api.github.com": ["140.82.112.5", "140.82.112.6"]})
        j = judge_outbound_url("https://api.github.com/repos", resolver=r)
        assert j.allowed and j.pinned_addresses == ("140.82.112.5", "140.82.112.6")
        assert r.calls == [("api.github.com", 443)]

    def test_hostname_resolving_to_private_is_refused(self):
        r = _Resolver({"internal.example.com": ["10.1.2.3"]})
        j = judge_outbound_url("https://internal.example.com/", resolver=r)
        assert j.allowed is False and "private" in j.reason

    def test_hostname_resolving_to_metadata_is_refused(self):
        r = _Resolver({"evil.example.com": ["169.254.169.254"]})
        j = judge_outbound_url("https://evil.example.com/", resolver=r)
        assert j.allowed is False and "cloud_metadata" in j.reason

    def test_mixed_public_and_private_answers_are_refused(self):
        # A round-robin rebind: approving on the public answer is the bypass.
        r = _Resolver({"flip.example.com": ["93.184.216.34", "127.0.0.1"]})
        assert judge_outbound_url("https://flip.example.com/", resolver=r).allowed is False

    def test_ipv6_mapped_answer_is_unwrapped_and_refused(self):
        r = _Resolver({"h.example.com": ["::ffff:192.168.0.1"]})
        assert judge_outbound_url("https://h.example.com/", resolver=r).allowed is False

    def test_dns_failure_is_a_refusal(self):
        r = _Resolver({}, raise_for=("gone.example.com",))
        assert judge_outbound_url("https://gone.example.com/", resolver=r).allowed is False
        assert judge_outbound_url("https://empty.example.com/", resolver=_Resolver({})).allowed is False

    def test_allow_list_is_enforced_in_addition(self):
        r = _Resolver({"api.github.com": ["140.82.112.5"], "other.example.com": ["93.184.216.34"]})
        assert judge_outbound_url("https://other.example.com/", resolver=r,
                                  allowed_hosts=frozenset({"api.github.com"})).allowed is False
        assert judge_outbound_url("https://api.github.com/", resolver=r,
                                  allowed_hosts=frozenset({"api.github.com"})).allowed is True

    def test_assert_raises_with_reason(self):
        with pytest.raises(OutboundRefused) as exc:
            assert_outbound_url("http://127.0.0.1/", resolver=_Resolver({}))
        assert "loopback" in exc.value.reason


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


class TestGuardedGet:
    def test_connects_to_pinned_address_with_original_host_and_sni(self):
        seen: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=b"hello", headers={"set-cookie": "a=b", "x": "y"})

        r = _Resolver({"api.github.com": ["140.82.112.5"]})
        resp = _run(guarded_get("https://api.github.com/logs?x=1", headers={"Authorization": "token t"},
                                resolver=r, transport=httpx.MockTransport(handler)))
        assert resp.status_code == 200 and resp.body == b"hello" and resp.truncated is False
        req = seen[0]
        assert req.url.host == "140.82.112.5" and req.url.path == "/logs" and req.url.query == b"x=1"
        assert req.headers["host"] == "api.github.com"
        assert req.extensions.get("sni_hostname") == "api.github.com"
        assert req.headers["authorization"] == "token t"
        assert "set-cookie" not in resp.headers and resp.headers["x"] == "y"

    def test_redirect_to_private_target_is_refused(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

        r = _Resolver({"api.github.com": ["140.82.112.5"]})
        with pytest.raises(OutboundRefused) as exc:
            _run(guarded_get("https://api.github.com/logs", resolver=r, transport=httpx.MockTransport(handler)))
        assert "169.254.169.254" in str(exc.value) or "scheme" in exc.value.reason

    def test_redirect_to_private_hostname_is_refused_by_resolution(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://internal.example.com/"})

        r = _Resolver({"api.github.com": ["140.82.112.5"], "internal.example.com": ["10.0.0.9"]})
        with pytest.raises(OutboundRefused):
            _run(guarded_get("https://api.github.com/logs", resolver=r, transport=httpx.MockTransport(handler)))

    def test_cross_origin_redirect_drops_credentials(self):
        seen: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if request.headers["host"] == "api.github.com":
                return httpx.Response(302, headers={"location": "https://blob.example.com/signed?sig=1"})
            return httpx.Response(200, content=b"log")

        r = _Resolver({"api.github.com": ["140.82.112.5"], "blob.example.com": ["93.184.216.34"]})
        resp = _run(guarded_get("https://api.github.com/logs",
                                headers={"Authorization": "token t", "Accept": "text/plain"},
                                resolver=r, transport=httpx.MockTransport(handler)))
        assert resp.status_code == 200 and len(resp.hops) == 1
        assert "authorization" in seen[0].headers
        assert "authorization" not in seen[1].headers and seen[1].headers["accept"] == "text/plain"
        assert seen[1].url.host == "93.184.216.34" and seen[1].headers["host"] == "blob.example.com"

    def test_redirect_loop_is_bounded(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://api.github.com/again"})

        r = _Resolver({"api.github.com": ["140.82.112.5"]})
        with pytest.raises(OutboundRefused) as exc:
            _run(guarded_get("https://api.github.com/logs", max_hops=2, resolver=r,
                             transport=httpx.MockTransport(handler)))
        assert "hops" in exc.value.reason

    def test_body_is_bounded(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * 5000)

        r = _Resolver({"api.github.com": ["140.82.112.5"]})
        resp = _run(guarded_get("https://api.github.com/logs", max_bytes=1000, resolver=r,
                                transport=httpx.MockTransport(handler)))
        assert len(resp.body) == 1000 and resp.truncated is True

    def test_refused_destination_never_dials(self):
        dialled = []

        def handler(request: httpx.Request) -> httpx.Response:
            dialled.append(request)
            return httpx.Response(200)

        with pytest.raises(OutboundRefused):
            _run(guarded_get("https://127.0.0.1/", resolver=_Resolver({}), transport=httpx.MockTransport(handler)))
        assert dialled == []


class TestGuardrailsCheckExternal:
    """The regex the fabric documented as inadequate is gone; the classifier judges."""

    @pytest.mark.parametrize("url", [
        "http://2130706433/", "http://0x7f000001/", "http://0177.0.0.1/", "http://127.1/",
        "http://[::ffff:127.0.0.1]/", "http://[fe80::1]/", "http://100.64.0.1/",
        "ftp://example.com/", "https://user:pw@example.com/", "http://169.254.169.254/",
    ])
    def test_bypass_forms_are_blocked(self, url):
        assert ToolCallGuardrail().check_external(url).blocked

    def test_public_https_is_allowed(self):
        assert ToolCallGuardrail().check_external("https://api.openai.com/v1/chat").decision == GuardrailDecision.ALLOW


class TestSandboxHttpTool:
    def test_private_url_is_refused_before_any_request(self):
        from backend.execution.sandbox.interfaces import HTTPSandbox

        result = _run(HTTPSandbox().execute("GET", {"url": "http://169.254.169.254/latest/"}))
        assert result.success is False and "refused" in (result.error or "")


class TestWebConnector:
    def test_quarantined_connector_refuses_private_target(self):
        from backend.mcp.connectors.web import WebConnector

        connector = WebConnector(allow_non_production=True)
        _run(connector.authenticate())
        assert connector._client.follow_redirects is False
        out = _run(connector._fetch_url("http://127.0.0.1:8200/v1/sys/health"))
        assert out.success is False and "refused" in (out.error or "")


class TestRateLimitBuckets:
    def test_ingress_buckets_exist_and_classify(self):
        assert _LIMITS["webhook"] > 0 and _LIMITS["ingest"] > 0
        assert _classify_endpoint("/api/github/webhook", "POST") == "webhook"
        assert _classify_endpoint("/api/gitlab/webhook", "POST") == "webhook"
        assert _classify_endpoint("/api/infrastructure/webhook/kubernetes", "POST") == "webhook"
        assert _classify_endpoint("/api/infrastructure/ingest/prometheus", "POST") == "ingest"
        assert _classify_endpoint("/api/infrastructure/otel/v1/traces", "POST") == "ingest"
        assert _classify_endpoint("/api/orchestrate", "POST") == "orchestrate"
