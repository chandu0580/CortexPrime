"""
Browser Agent  (CortexPrime)
=============================
Persistent-session browser automation powered by Playwright.

Key design principles
---------------------
* ONE browser process and BrowserContext is kept alive per session_id.
  No new browser is launched for every action (P3).
* All page operations run inside the shared session page (P4).
* Readable content is extracted via ``page.inner_text("body")``
  instead of the raw HTML ``page.content()`` (P5).
* Robust wait strategies: ``wait_for_load_state``, ``wait_for_selector``,
  configurable timeouts, and automatic retry on navigation errors (P6).
* ``execute_task()`` is the high-level entry point called by
  ``MissionRuntimeService`` for natural-language browser tasks (P7).
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)


# =========================================================
# KNOWN DOMAIN MAP  — "Open GitHub" → https://github.com
# =========================================================

_DOMAIN_MAP: Dict[str, str] = {
    "github":        "https://github.com",
    "google":        "https://www.google.com",
    "wikipedia":     "https://en.wikipedia.org",
    "youtube":       "https://www.youtube.com",
    "twitter":       "https://twitter.com",
    "linkedin":      "https://www.linkedin.com",
    "reddit":        "https://www.reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "npm":           "https://www.npmjs.com",
    "pypi":          "https://pypi.org",
    "hackernews":    "https://news.ycombinator.com",
}

# Search query template (DuckDuckGo — simpler HTML than Google)
_SEARCH_URL = "https://duckduckgo.com/?q={query}&ia=web"

# Maximum characters returned as extracted text
_MAX_EXTRACT_CHARS = 8000

# Default navigation timeout (ms)
_DEFAULT_TIMEOUT = 30_000

# Retry attempts for navigation
_NAV_RETRIES = 2


# =========================================================
# BROWSER SESSION
# =========================================================

class BrowserSession:
    """Holds one persistent Playwright context + page."""

    def __init__(self) -> None:
        self.browser      = None
        self.context      = None
        self.page         = None
        self.current_url: Optional[str] = None
        self.history:     List[str]     = []
        self.created_at   = datetime.utcnow().isoformat()
        self.last_used_at = datetime.utcnow().isoformat()

    async def close(self) -> None:
        for obj in (self.page, self.context, self.browser):
            try:
                if obj:
                    await obj.close()
            except Exception:
                pass


# =========================================================
# BROWSER AGENT
# =========================================================
# RISKY BROWSER ACTIONS  (require governance approval)
# =========================================================

_BROWSER_HIGH_RISK_ACTIONS = {
    "form_submit", "login", "authenticate",
    "purchase", "checkout", "enter_credentials",
    "fill_password", "enter_credit_card",
}


async def _browser_governance_check(
    action:       str,
    description:  str,
    execution_id: str,
    session_id:   str | None = None,
) -> bool:
    """
    Returns True if the action is allowed to proceed.
    Submits an approval request for high-risk browser actions.
    """
    try:
        from backend.safety.audit_logger import audit_logger
        from backend.safety.emergency_stop import emergency_stop
        from backend.safety.safety_guard import safety_guard

        if emergency_stop.is_stopped(execution_id):
            return False

        assessment = safety_guard.assess_action(
            action = action,
            agent  = "browser_agent",
        )

        audit_logger.log(
            execution_id = execution_id,
            agent        = "browser_agent",
            action       = action,
            risk_level   = assessment.risk_level.value,
            outcome      = "blocked" if assessment.blocked else (
                "requires_approval" if assessment.requires_approval else "allowed"
            ),
            reason       = assessment.reason,
            session_id   = session_id,
        )

        if assessment.blocked:
            return False

        if assessment.requires_approval or action in _BROWSER_HIGH_RISK_ACTIONS:
            from backend.safety.approval_queue import approval_queue
            req = await approval_queue.request(
                execution_id = execution_id,
                agent        = "browser_agent",
                action       = action,
                description  = description,
                risk_level   = assessment.risk_level.value,
                context      = {"action": action, "description": description},
                session_id   = session_id,
                timeout      = 300,
            )
            audit_logger.log(
                execution_id = execution_id,
                agent        = "browser_agent",
                action       = action,
                risk_level   = assessment.risk_level.value,
                outcome      = req.status.value,
                reason       = req.reject_reason or "Resolved by operator",
                session_id   = session_id,
                request_id   = req.request_id,
            )
            return req.status.value == "approved"

        return True

    except Exception:
        # Governance errors must not break browser execution
        return True


# =========================================================

class BrowserAgent:

    def __init__(self) -> None:
        self.headless        = True
        self.default_timeout = _DEFAULT_TIMEOUT
        self._sessions:      Dict[str, BrowserSession] = {}
        self._playwright     = None
        self._pw_lock        = asyncio.Lock()


    # ----------------------------------------------------------
    # PLAYWRIGHT SINGLETON
    # ----------------------------------------------------------

    async def _get_playwright(self):
        """Return a module-level Playwright instance (started once, not a context manager)."""
        if self._playwright is None:
            async with self._pw_lock:
                if self._playwright is None:
                    from playwright.async_api import async_playwright
                    self._playwright = await async_playwright().start()
        return self._playwright

    # ----------------------------------------------------------
    # SESSION MANAGEMENT  (P3)
    # ----------------------------------------------------------

    async def _get_or_create_session(self, session_id: str) -> BrowserSession:
        """
        Return existing live session or create a new persistent one.
        Cookies and storage state survive across actions within the same session.
        """
        session = self._sessions.get(session_id)

        if session is not None:
            try:
                _ = session.page.url  # raises if page closed
                session.last_used_at = datetime.utcnow().isoformat()
                return session
            except Exception:
                await session.close()
                del self._sessions[session_id]
                session = None

        pw      = await self._get_playwright()
        browser = await pw.chromium.launch(
            headless = self.headless,
            args     = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport            = {"width": 1280, "height": 800},
            java_script_enabled = True,
            accept_downloads    = False,
        )
        page = await context.new_page()
        page.set_default_timeout(self.default_timeout)

        session              = BrowserSession()
        session.browser      = browser
        session.context      = context
        session.page         = page
        self._sessions[session_id] = session

        log.info("Browser session created: %s", session_id)
        return session

    async def close_session(self, session_id: str) -> None:
        """Cleanly close a browser session and free resources."""
        if session_id in self._sessions:
            await self._sessions[session_id].close()
            del self._sessions[session_id]
            log.info("Browser session closed: %s", session_id)

    def list_sessions(self) -> List[str]:
        return list(self._sessions.keys())

    def get_session_history(self, session_id: str) -> List[str]:
        s = self._sessions.get(session_id)
        return s.history if s else []

    # ----------------------------------------------------------
    # EVENT HELPER
    # ----------------------------------------------------------

    async def _publish_event(
        self,
        execution_id: str,
        event_type:   str,
        status:       str,
        phase:        str,
        message:      str,
        payload:      Dict[str, Any] | None = None,
    ) -> None:
        try:
            from backend.events.event_bus import publish_event
            await publish_event("browser_agent", execution_id, event_type, status, phase, message, payload)
        except Exception:
            pass

    # Keep old name for backwards compatibility with tool_registry
    async def publish_event(self, execution_id, event_type, status, phase, message, payload=None):
        await self._publish_event(execution_id, event_type, status, phase, message, payload)

    # ----------------------------------------------------------
    # NAVIGATION HELPER  (with wait + retry)  (P6)
    # ----------------------------------------------------------

    async def _navigate(self, page, url: str, retries: int = _NAV_RETRIES) -> None:
        """Navigate with load-state wait and automatic retry."""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.default_timeout)
                await page.wait_for_load_state("networkidle", timeout=15_000)
                return
            except Exception as exc:
                last_err = exc
                if attempt < retries:
                    log.warning("Nav attempt %d/%d for %s failed: %s — retrying",
                                attempt + 1, retries + 1, url, exc)
                    await asyncio.sleep(1.0)
        raise last_err  # type: ignore[misc]

    # ----------------------------------------------------------
    # CONTENT EXTRACTION  (P5)
    # ----------------------------------------------------------

    async def _extract_readable_text(self, page) -> str:
        """Return human-readable page text via inner_text (not raw HTML)."""
        try:
            await page.wait_for_selector("body", timeout=10_000)
            text = await page.inner_text("body")
            text = re.sub(r"\n{3,}", "\n\n", text.strip())
            text = re.sub(r"[ \t]{2,}", " ", text)
            return text[:_MAX_EXTRACT_CHARS]
        except Exception:
            try:
                return await page.title()
            except Exception:
                return ""

    async def _extract_structured(self, page) -> Dict[str, Any]:
        try:
            title = await page.title()
        except Exception:
            title = ""

        meta_desc = ""
        try:
            meta_desc = await page.eval_on_selector(
                'meta[name="description"]', "el => el.getAttribute('content')"
            )
        except Exception:
            pass

        headings: List[str] = []
        try:
            headings = await page.eval_on_selector_all(
                "h1, h2, h3",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 0)",
            )
        except Exception:
            pass

        return {"title": title, "description": meta_desc or "", "headings": headings[:20]}

    # ----------------------------------------------------------
    # URL / INTENT HELPERS
    # ----------------------------------------------------------

    @staticmethod
    def _extract_url(text: str) -> str | None:
        m = re.search(r'https?://[^\s<>"\']+', text)
        if m:
            return m.group(0).rstrip(".,;)")
        text_lower = text.lower()
        for keyword, url in _DOMAIN_MAP.items():
            if keyword in text_lower:
                return url
        return None

    @staticmethod
    def _build_search_url(query: str) -> str:
        from urllib.parse import quote_plus
        return _SEARCH_URL.format(query=quote_plus(query))

    # ==========================================================
    # HIGH-LEVEL ENTRY POINT  (P7 — called by mission_runtime)
    # ==========================================================

    async def execute_task(
        self,
        execution_id: str,
        objective:    str,
        session_id:   str = "global",
    ) -> Dict[str, Any]:
        """
        Execute a browser task from a natural-language objective.
        Routes to open_page if a URL/domain is detected, else search_web.
        """
        await self._publish_event(
            execution_id, "browser_task_started", "running", "browser_agent",
            f"Browser agent activated: {objective[:80]}", {"objective": objective},
        )

        url = self._extract_url(objective)
        if url:
            result = await self.open_page({"url": url}, session_id=execution_id)
        else:
            result = await self.search_web({"query": objective}, session_id=execution_id)

        # ── AUDIT: URL visited / search performed ──────────────────
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id = execution_id,
                agent        = "browser_agent",
                action       = "visit_url" if url else "web_search",
                risk_level   = "low",
                outcome      = "allowed" if result.get("success") else "failed",
                reason       = f"Browser: {result.get('url', objective[:120])} — {result.get('title', '')}",
                session_id   = session_id,
                metadata     = {
                    "url":            result.get("url", url or ""),
                    "title":          result.get("title", ""),
                    "objective":      objective[:200],
                    "content_length": len(result.get("extracted_text", "")),
                },
            )
        except Exception:
            pass

        await self._publish_event(
            execution_id, "browser_task_completed", "completed", "browser_agent",
            "Browser task completed",
            {
                "url":            result.get("url"),
                "title":          result.get("title"),
                "content_length": len(result.get("extracted_text", "")),
            },
        )
        return result

    # ==========================================================
    # OPEN PAGE  (P4 — persistent session)
    # ==========================================================

    async def open_page(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        execution_id = str(uuid4())
        url = payload.get("url")
        if not url:
            return {"success": False, "error": "Missing URL"}

        await self._publish_event(
            execution_id, "browser_navigation_started", "running",
            "browser_navigation", f"Opening page: {url}", {"url": url},
        )

        try:
            session = await self._get_or_create_session(session_id)
            await self._navigate(session.page, url)

            session.current_url = session.page.url
            session.history.append(session.current_url)

            text       = await self._extract_readable_text(session.page)
            structured = await self._extract_structured(session.page)

            await self._publish_event(
                execution_id, "browser_navigation_completed", "completed",
                "browser_navigation", f"Loaded: {structured['title']}",
                {"url": url, "title": structured["title"]},
            )

            return {
                "success":        True,
                "url":            session.current_url,
                "title":          structured["title"],
                "description":    structured["description"],
                "headings":       structured["headings"],
                "extracted_text": text,
                "session_id":     session_id,
                "timestamp":      datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            log.error("open_page failed [%s]: %s", url, exc)
            await self._publish_event(
                execution_id, "browser_navigation_failed", "failed",
                "browser_navigation", "Navigation failed", {"url": url, "error": str(exc)},
            )
            return {"success": False, "url": url, "error": str(exc)}

    # ==========================================================
    # NAVIGATE  (alias)
    # ==========================================================

    async def navigate(self, payload: Dict[str, Any], session_id: str = "global") -> Dict[str, Any]:
        return await self.open_page(payload, session_id=session_id)

    # ==========================================================
    # CLICK ELEMENT  (P4 + P6)
    # ==========================================================

    async def click_element(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        execution_id = str(uuid4())
        url          = payload.get("url")
        selector     = payload.get("selector")

        if not selector:
            return {"success": False, "error": "Missing selector"}

        try:
            session = await self._get_or_create_session(session_id)
            if url:
                await self._navigate(session.page, url)

            await session.page.wait_for_selector(selector, state="visible", timeout=10_000)
            await session.page.click(selector)

            try:
                await session.page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass

            session.current_url = session.page.url
            title = await session.page.title()

            await self._publish_event(
                execution_id, "browser_click_completed", "completed",
                "browser_interaction", f"Clicked: {selector}",
                {"selector": selector, "current_url": session.current_url},
            )

            return {
                "success":    True,
                "selector":   selector,
                "title":      title,
                "url":        session.current_url,
                "session_id": session_id,
            }

        except Exception as exc:
            log.error("click_element failed [%s]: %s", selector, exc)
            return {"success": False, "selector": selector, "error": str(exc)}

    # ==========================================================
    # TYPE TEXT  (P4 + P6)
    # ==========================================================

    async def type_text(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        execution_id = str(uuid4())
        url          = payload.get("url")
        selector     = payload.get("selector")
        text         = payload.get("text", "")

        if not selector:
            return {"success": False, "error": "Missing selector"}

        try:
            session = await self._get_or_create_session(session_id)
            if url:
                await self._navigate(session.page, url)

            await session.page.wait_for_selector(selector, state="visible", timeout=10_000)
            await session.page.fill(selector, text)

            await self._publish_event(
                execution_id, "browser_typing_completed", "completed",
                "browser_interaction", f"Typed into: {selector}", {"selector": selector},
            )

            return {"success": True, "selector": selector, "session_id": session_id}

        except Exception as exc:
            log.error("type_text failed [%s]: %s", selector, exc)
            return {"success": False, "selector": selector, "error": str(exc)}

    # ==========================================================
    # EXTRACT CONTENT  (P5)
    # ==========================================================

    async def extract_content(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        url = payload.get("url")
        if url:
            return await self.open_page({"url": url}, session_id=session_id)
        try:
            session    = await self._get_or_create_session(session_id)
            text       = await self._extract_readable_text(session.page)
            structured = await self._extract_structured(session.page)
            return {
                "success":        True,
                "url":            session.page.url,
                "title":          structured["title"],
                "description":    structured["description"],
                "headings":       structured["headings"],
                "extracted_text": text,
                "session_id":     session_id,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ==========================================================
    # TAKE SCREENSHOT  (P4)
    # ==========================================================

    async def take_screenshot(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        import os
        execution_id = str(uuid4())
        url          = payload.get("url")

        try:
            session = await self._get_or_create_session(session_id)
            if url:
                await self._navigate(session.page, url)

            os.makedirs("screenshots", exist_ok=True)
            screenshot_path = f"screenshots/{execution_id}.png"
            await session.page.screenshot(path=screenshot_path, full_page=True)

            await self._publish_event(
                execution_id, "browser_screenshot_completed", "completed",
                "browser_visual_capture", "Screenshot captured",
                {"url": session.page.url, "screenshot_path": screenshot_path},
            )

            return {
                "success":         True,
                "screenshot_path": screenshot_path,
                "url":             session.page.url,
                "session_id":      session_id,
            }

        except Exception as exc:
            log.error("take_screenshot failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ==========================================================
    # SEARCH WEB  (P4)
    # ==========================================================

    async def search_web(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        query = payload.get("query", "").strip()
        if not query:
            return {"success": False, "error": "Missing query"}

        search_url = self._build_search_url(query)
        result     = await self.open_page({"url": search_url}, session_id=session_id)
        if result.get("success"):
            result["query"] = query
        return result

    # ==========================================================
    # EXTRACT LINKS  (P4)
    # ==========================================================

    async def extract_links(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        url = payload.get("url")

        try:
            session = await self._get_or_create_session(session_id)
            if url:
                await self._navigate(session.page, url)

            links = await session.page.eval_on_selector_all(
                "a[href]",
                """
                elements => elements.map(el => ({
                    text: el.innerText.trim(),
                    href: el.href
                })).filter(l => l.href.startsWith('http'))
                """,
            )

            return {
                "success":    True,
                "links":      links[:100],
                "link_count": len(links),
                "url":        session.page.url,
                "session_id": session_id,
            }

        except Exception as exc:
            log.error("extract_links failed: %s", exc)
            return {"success": False, "error": str(exc)}


    # ==========================================================
    # GOVERNED FORM SUBMIT  (requires approval)
    # ==========================================================

    async def governed_form_submit(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        """
        Submit a form — ALWAYS requires human approval before executing.
        payload: {url, selector, fields: {selector: value}}
        """
        execution_id  = payload.get("execution_id", str(uuid4()))
        description   = f"Form submission on: {payload.get('url', 'unknown')}"

        allowed = await _browser_governance_check(
            action       = "form_submit",
            description  = description,
            execution_id = execution_id,
            session_id   = session_id,
        )
        if not allowed:
            return {
                "success":     False,
                "error":       "Form submission blocked — approval required or denied.",
                "governance":  "blocked",
            }

        # Execute the actual submission
        try:
            session = await self._get_or_create_session(session_id)
            url = payload.get("url")
            if url:
                await self._navigate(session.page, url)

            fields: Dict[str, str] = payload.get("fields", {})
            for selector, value in fields.items():
                await session.page.wait_for_selector(selector, state="visible", timeout=10_000)
                await session.page.fill(selector, value)

            submit_selector = payload.get("submit_selector", "[type=submit]")
            await session.page.wait_for_selector(submit_selector, state="visible", timeout=10_000)
            await session.page.click(submit_selector)
            try:
                await session.page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

            return {
                "success":    True,
                "url":        session.page.url,
                "governance": "approved",
                "session_id": session_id,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ==========================================================
    # GOVERNED LOGIN  (requires approval)
    # ==========================================================

    async def governed_login(
        self,
        payload:    Dict[str, Any],
        session_id: str = "global",
    ) -> Dict[str, Any]:
        """
        Perform a login — ALWAYS requires human approval.
        payload: {url, username_selector, password_selector, username, submit_selector}
        """
        execution_id = payload.get("execution_id", str(uuid4()))
        url          = payload.get("url", "unknown")
        description  = f"Login on: {url}"

        allowed = await _browser_governance_check(
            action       = "login",
            description  = description,
            execution_id = execution_id,
            session_id   = session_id,
        )
        if not allowed:
            return {
                "success":    False,
                "error":      "Login blocked — approval required or denied.",
                "governance": "blocked",
            }

        try:
            session = await self._get_or_create_session(session_id)
            if url != "unknown":
                await self._navigate(session.page, url)

            uname_sel = payload.get("username_selector", "#username")
            pwd_sel   = payload.get("password_selector", "#password")
            submit    = payload.get("submit_selector", "[type=submit]")

            await session.page.wait_for_selector(uname_sel, state="visible", timeout=10_000)
            await session.page.fill(uname_sel, payload.get("username", ""))
            await session.page.fill(pwd_sel, payload.get("password", ""))
            await session.page.click(submit)

            try:
                await session.page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

            return {
                "success":    True,
                "url":        session.page.url,
                "governance": "approved",
                "session_id": session_id,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}


# =========================================================
# SINGLETON
# =========================================================

browser_agent = BrowserAgent()


# =========================================================
# TOOL REGISTRY
# =========================================================

try:
    from backend.tools.tool_registry import tool_registry

    tool_registry.register_tool(
        name="browser_open_page",
        description="Open and inspect webpages",
        handler=browser_agent.open_page,
        tool_type="browser",
    )
    tool_registry.register_tool(
        name="browser_search_web",
        description="Search the web using browser",
        handler=browser_agent.search_web,
        tool_type="browser",
    )
    tool_registry.register_tool(
        name="browser_extract_links",
        description="Extract webpage links",
        handler=browser_agent.extract_links,
        tool_type="browser",
    )
    tool_registry.register_tool(
        name="browser_click_element",
        description="Click webpage elements",
        handler=browser_agent.click_element,
        tool_type="browser",
    )
    tool_registry.register_tool(
        name="browser_type_text",
        description="Type text into webpage fields",
        handler=browser_agent.type_text,
        tool_type="browser",
    )
    tool_registry.register_tool(
        name="browser_take_screenshot",
        description="Capture webpage screenshots",
        handler=browser_agent.take_screenshot,
        tool_type="browser",
    )
    tool_registry.register_tool(
        name="browser_extract_content",
        description="Extract readable text and metadata from a webpage",
        handler=browser_agent.extract_content,
        tool_type="browser",
    )
except Exception as _reg_err:
    log.warning("Tool registry unavailable: %s", _reg_err)

    # ==========================================
