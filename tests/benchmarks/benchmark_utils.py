import asyncio
import time
import statistics
import functools
from typing import Any, Callable, Coroutine, List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class BenchmarkResult:
    name: str
    samples: List[float] = field(default_factory=list)
    warmup_samples: List[float] = field(default_factory=list)

    def record(self, duration_ms: float, warmup: bool = False) -> None:
        (self.warmup_samples if warmup else self.samples).append(duration_ms)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def min_ms(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def median_ms(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        idx = min(int(len(sorted_s) * 0.95), len(sorted_s) - 1)
        return sorted_s[idx]

    @property
    def p99_ms(self) -> float:
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        idx = min(int(len(sorted_s) * 0.99), len(sorted_s) - 1)
        return sorted_s[idx]

    @property
    def stdev_ms(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) >= 2 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "stdev_ms": round(self.stdev_ms, 2),
        }


class BenchmarkRunner:
    def __init__(self, iterations: int = 100, warmup: int = 10):
        self.iterations = iterations
        self.warmup = warmup
        self.results: List[BenchmarkResult] = []

    def create_result(self, name: str) -> BenchmarkResult:
        result = BenchmarkResult(name=name)
        self.results.append(result)
        return result

    async def run_async(
        self,
        name: str,
        fn: Callable[..., Coroutine],
        *,
        iterations: Optional[int] = None,
        warmup: Optional[int] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkResult:
        result = self.create_result(name)
        n = iterations or self.iterations
        w = warmup or self.warmup
        kw = kwargs or {}
        for i in range(n + w):
            start = time.monotonic()
            await fn(**kw)
            elapsed = (time.monotonic() - start) * 1000
            result.record(elapsed, warmup=(i < w))
        return result

    def run_sync(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        iterations: Optional[int] = None,
        warmup: Optional[int] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkResult:
        result = self.create_result(name)
        n = iterations or self.iterations
        w = warmup or self.warmup
        kw = kwargs or {}
        for i in range(n + w):
            start = time.monotonic()
            fn(**kw)
            elapsed = (time.monotonic() - start) * 1000
            result.record(elapsed, warmup=(i < w))
        return result

    def report(self) -> str:
        lines = [
            f"{'Benchmark':<50} {'Count':>6} {'Min(ms)':>10} {'Avg(ms)':>10} {'Median(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'Max(ms)':>10}",
            "-" * 126,
        ]
        for r in self.results:
            d = r.to_dict()
            lines.append(
                f"{d['name']:<50} {d['count']:>6} {d['min_ms']:>10.2f} {d['avg_ms']:>10.2f} "
                f"{d['median_ms']:>10.2f} {d['p95_ms']:>10.2f} {d['p99_ms']:>10.2f} {d['max_ms']:>10.2f}"
            )
        return "\n".join(lines)


def latency_stub(delay_ms: float = 1.0) -> Callable[[], None]:
    def _stub() -> None:
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
    return _stub


async def async_latency_stub(delay_ms: float = 1.0) -> None:
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)
