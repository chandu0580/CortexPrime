"""The gateway's rate limiter: token buckets at the one invocation choke point.

Why here, and only here
-------------------------
Every governed provider call -- reads, writes, watch windows, health probes --
is admitted by ``SecureCapabilityInvocationGateway`` and nowhere else. Its rate
stage has always existed (``RateLimiter`` protocol) and has always been empty:
no composition passed a limiter (connector reality audit, finding S-3). A
limiter wired at the gateway cannot be bypassed by an alternate route because
there is no alternate route to a provider; a second limiter anywhere else would
be a second rule that could disagree with this one.

Three budgets, all of which must have room
--------------------------------------------
* **tenant + capability** -- one tenant's investigation loop cannot starve that
  tenant's other capabilities;
* **tenant** -- one tenant cannot consume the platform's whole budget;
* **provider** (every tenant) -- the provider itself is protected. A Kubernetes
  API server applies its own API Priority and Fairness and answers 429 when
  flooded; the platform should run out of budget before the cluster does.

A request consumes one token from each budget, atomically: if any budget is
empty nothing is consumed, so a refused request never drains the others.

Scope and honesty
-------------------
Buckets live in the process. That is correct for this runtime because the
governed runtime dispatches from one process per store (the scheduler and
audit-writer roles are leader-elected singletons, ADR-122); a multi-dispatcher
deployment would need a shared store and is not claimed here.

A limiter is a *resource* control, not an authority control: a refusal is
retryable and names the budget that ran out, never the tenant's data.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "RateLimitPolicy",
    "TokenBucketRateLimiter",
    "build_rate_limiter",
    "RATE_LIMIT_METRIC",
]

#: Counter incremented once per refused request, labelled by the budget scope.
RATE_LIMIT_METRIC = "gateway.rate_limited"

_ENV_PREFIX = "CORTEX_RATE_LIMIT_"


@dataclass(frozen=True)
class RateLimitPolicy:
    """Budgets in requests per minute, with a burst capacity each.

    Defaults are sized for the governed read loops of one namespace (a watch
    window every ~20 s, an investigation burst of ~10 reads, a health probe per
    minute) with headroom, and well under a default API server's fairness limits.
    """

    capability_per_minute: int = 120
    capability_burst: int = 40
    tenant_per_minute: int = 600
    tenant_burst: int = 150
    provider_per_minute: int = 1200
    provider_burst: int = 300

    def __post_init__(self) -> None:
        for name in ("capability_per_minute", "capability_burst", "tenant_per_minute",
                     "tenant_burst", "provider_per_minute", "provider_burst"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ContractViolation(
                    f"rate limit {name} must be a positive integer; a budget of zero "
                    "is an outage, and 'unlimited' is not a value this policy takes")
        if self.capability_per_minute > self.tenant_per_minute:
            raise ContractViolation(
                "a per-capability budget larger than the tenant budget is unreachable "
                "and hides a misconfiguration")

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "RateLimitPolicy":
        """``CORTEX_RATE_LIMIT_<FIELD>`` overrides; anything unparseable refuses."""
        env = os.environ if environ is None else environ
        values: dict = {}
        for field_name in cls.__dataclass_fields__:
            raw = (env.get(_ENV_PREFIX + field_name.upper()) or "").strip()
            if not raw:
                continue
            try:
                values[field_name] = int(raw)
            except ValueError as exc:
                raise ContractViolation(
                    f"{_ENV_PREFIX}{field_name.upper()} must be an integer") from exc
        return cls(**values)


class _Bucket:
    __slots__ = ("capacity", "rate", "tokens", "updated")

    def __init__(self, capacity: int, per_minute: int, now: float) -> None:
        self.capacity = float(capacity)
        self.rate = per_minute / 60.0
        self.tokens = float(capacity)
        self.updated = now

    def refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.updated)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.updated = now

    def seconds_until_token(self) -> float:
        return 0.0 if self.tokens >= 1.0 else (1.0 - self.tokens) / self.rate


class TokenBucketRateLimiter:
    """Implements the gateway's ``RateLimiter`` protocol."""

    #: Idle, full buckets beyond this many are forgotten (a forgotten bucket
    #: re-creates full, which is exactly the state it was in).
    MAX_BUCKETS = 10_000

    def __init__(
        self,
        policy: Optional[RateLimitPolicy] = None,
        *,
        clock: Optional[Callable[[], float]] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        self._policy = policy or RateLimitPolicy()
        self._clock = clock or time.monotonic
        self._metrics = metrics
        self._buckets: dict = {}
        self._lock = threading.Lock()

    @property
    def policy(self) -> RateLimitPolicy:
        return self._policy

    def check(self, context: Any, request: Any) -> tuple:
        """Consume one token from every budget, or none and say which ran out."""
        tenant = str(getattr(request, "tenant_id", "") or "")
        capability = str(getattr(request, "capability_ref", "") or "")
        operation = str(getattr(request, "operation", "") or "")
        provider = operation.split(".", 1)[0] if operation else "unknown"
        p = self._policy
        scopes = (
            ("capability", (tenant, capability), p.capability_burst, p.capability_per_minute,
             f"{capability} for this tenant"),
            ("tenant", (tenant,), p.tenant_burst, p.tenant_per_minute, "this tenant"),
            ("provider", (provider,), p.provider_burst, p.provider_per_minute,
             f"the {provider} provider (all tenants)"),
        )
        now = self._clock()
        with self._lock:
            buckets = []
            exceeded = []
            for scope, key, burst, per_minute, what in scopes:
                bucket = self._bucket((scope, *key), burst, per_minute, now)
                bucket.refill(now)
                buckets.append(bucket)
                if bucket.tokens < 1.0:
                    exceeded.append((scope, f"rate limit reached for {what} "
                                            f"({per_minute}/min, burst {burst}); "
                                            f"retry after {bucket.seconds_until_token():.1f}s"))
            if not exceeded:
                for bucket in buckets:
                    bucket.tokens -= 1.0
                self._evict_idle(now)
                return ()
        for scope, _ in exceeded:
            self._count(scope, provider)
        return tuple(reason for _, reason in exceeded)

    def _bucket(self, key: tuple, burst: int, per_minute: int, now: float) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._buckets[key] = _Bucket(burst, per_minute, now)
        return bucket

    def _evict_idle(self, now: float) -> None:
        if len(self._buckets) <= self.MAX_BUCKETS:
            return
        for key, bucket in list(self._buckets.items()):
            bucket.refill(now)
            if bucket.tokens >= bucket.capacity:
                del self._buckets[key]
            if len(self._buckets) <= self.MAX_BUCKETS // 2:
                break

    def _count(self, scope: str, provider: str) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.increment(RATE_LIMIT_METRIC, labels={"scope": scope, "provider": provider})
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            pass


def build_rate_limiter(
    *, metrics: Optional[Any] = None, environ: Optional[Mapping[str, str]] = None,
) -> TokenBucketRateLimiter:
    """The one limiter a governed runtime composes. Always on."""
    return TokenBucketRateLimiter(RateLimitPolicy.from_env(environ), metrics=metrics)
