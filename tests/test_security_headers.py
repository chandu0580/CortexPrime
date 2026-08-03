from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_CONF = REPO_ROOT / "infra" / "nginx" / "conf.d" / "cortex.conf"
FRONTEND_MIDDLEWARE = REPO_ROOT / "frontend" / "proxy.ts"
FRONTEND_LAYOUT = REPO_ROOT / "frontend" / "app" / "layout.tsx"


def test_nginx_emits_required_security_headers() -> None:
    config = NGINX_CONF.read_text(encoding="utf-8")

    assert 'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;' in config
    assert 'add_header X-Frame-Options "DENY" always;' in config
    assert 'add_header X-Content-Type-Options "nosniff" always;' in config
    assert 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' in config
    assert 'add_header Permissions-Policy "camera=(), microphone=(self), geolocation=(), payment=()" always;' in config


def test_nginx_backend_routes_emit_locked_down_csp() -> None:
    config = NGINX_CONF.read_text(encoding="utf-8")
    locked_down_csp = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none';"

    assert config.count(f'add_header Content-Security-Policy "{locked_down_csp}" always;') >= 6
    assert "location /api/ {" in config
    assert "location /health {" in config
    assert "location = /metrics {" in config
    assert "location = /ws {" in config


def test_nginx_csp_no_longer_allows_unsafe_inline_or_eval() -> None:
    config = NGINX_CONF.read_text(encoding="utf-8")

    assert "unsafe-inline" not in config
    assert "unsafe-eval" not in config


def test_frontend_middleware_uses_nonce_based_script_csp() -> None:
    middleware_source = FRONTEND_MIDDLEWARE.read_text(encoding="utf-8")

    assert "const NONCE_HEADER = \"x-nonce\"" in middleware_source
    assert "script-src 'self' 'nonce-${nonce}' 'strict-dynamic'" in middleware_source
    assert 'style-src-attr \'unsafe-inline\'' in middleware_source
    assert 'IS_DEVELOPMENT ? " \'unsafe-eval\'" : ""' in middleware_source


def test_root_layout_forces_request_aware_rendering_for_nonce_injection() -> None:
    layout_source = FRONTEND_LAYOUT.read_text(encoding="utf-8")

    assert 'import { headers } from "next/headers"' in layout_source
    assert "export default async function RootLayout" in layout_source
    assert "await headers()" in layout_source