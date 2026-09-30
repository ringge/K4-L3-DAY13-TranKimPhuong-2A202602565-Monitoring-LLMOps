"""Pure aggregations for the six dashboard panels."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from dashboard_data import LogEvent, LogWindow


@dataclass(frozen=True, slots=True)
class ChartPoint:
    minute: datetime
    series: str
    value: float


@dataclass(frozen=True, slots=True)
class PanelMetrics:
    values: dict[str, float | None]
    points: tuple[ChartPoint, ...]
    error_types: tuple[tuple[str, int], ...] = ()


def _minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def _minutes(window: LogWindow):
    minute = _minute(window.start)
    last = _minute(window.end)
    while minute <= last:
        yield minute
        minute += timedelta(minutes=1)


def _percentile(values: list[float], percent: int) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percent / 100
    low = int(index)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (index - low)


def _valid(value: float | None, low: float = 0, high: float | None = None) -> bool:
    return value is not None and value >= low and (high is None or value <= high)


def latency_metrics(window: LogWindow) -> PanelMetrics:
    responses = [row for row in window.events if row.event == "response_sent"]
    latencies = [row.latency_ms for row in responses if _valid(row.latency_ms)]
    ttfts = [row.ttft_ms for row in responses if _valid(row.ttft_ms)]
    values = {
        "p50": _percentile(latencies, 50),
        "p95": _percentile(latencies, 95),
        "p99": _percentile(latencies, 99),
        "ttft_p95": _percentile(ttfts, 95),
    }
    grouped: dict[datetime, list[LogEvent]] = defaultdict(list)
    for row in responses:
        grouped[_minute(row.ts)].append(row)
    points: list[ChartPoint] = []
    for minute, rows in sorted(grouped.items()):
        minute_latency = [row.latency_ms for row in rows if _valid(row.latency_ms)]
        minute_ttft = [row.ttft_ms for row in rows if _valid(row.ttft_ms)]
        for key, label, sample, percent in (
            ("p50", "P50", minute_latency, 50),
            ("p95", "P95", minute_latency, 95),
            ("p99", "P99", minute_latency, 99),
            ("ttft_p95", "TTFT P95", minute_ttft, 95),
        ):
            value = _percentile(sample, percent)
            if value is not None:
                points.append(ChartPoint(minute, label, value))
    return PanelMetrics(values, tuple(points))


def traffic_metrics(window: LogWindow) -> PanelMetrics:
    counts = Counter(_minute(row.ts) for row in window.events if row.event == "request_received")
    points = tuple(ChartPoint(minute, "Requests/min", float(counts[minute])) for minute in _minutes(window))
    total = sum(counts.values())
    duration_minutes = (window.end - window.start).total_seconds() / 60
    return PanelMetrics({"count": float(total), "rate_per_minute": total / duration_minutes}, points)


def errors_metrics(window: LogWindow) -> PanelMetrics:
    received = [row for row in window.events if row.event == "request_received"]
    failed = [row for row in window.events if row.event == "request_failed"]
    retrieval = [row for row in window.events if row.tool_success is not None]
    values = {
        "error_rate_pct": len(failed) / len(received) * 100 if received else None,
        "tool_success_rate_pct": (
            sum(row.tool_success is True for row in retrieval) / len(retrieval) * 100
            if retrieval else None
        ),
    }
    received_by_minute = Counter(_minute(row.ts) for row in received)
    failed_by_minute = Counter(_minute(row.ts) for row in failed)
    retrieval_by_minute: dict[datetime, list[bool]] = defaultdict(list)
    for row in retrieval:
        retrieval_by_minute[_minute(row.ts)].append(row.tool_success is True)
    points: list[ChartPoint] = []
    for minute in _minutes(window):
        if received_by_minute[minute]:
            points.append(
                ChartPoint(minute, "Error rate", failed_by_minute[minute] / received_by_minute[minute] * 100)
            )
        results = retrieval_by_minute.get(minute)
        if results:
            points.append(ChartPoint(minute, "Retrieval success", sum(results) / len(results) * 100))
    error_types = tuple(Counter(row.error_type or "Unknown" for row in failed).most_common())
    return PanelMetrics(values, tuple(points), error_types)


def cost_metrics(window: LogWindow) -> PanelMetrics:
    amounts = [row for row in window.events if row.event == "response_sent" and _valid(row.cost_usd)]
    by_minute: dict[datetime, float] = defaultdict(float)
    for row in amounts:
        by_minute[_minute(row.ts)] += row.cost_usd
    points: list[ChartPoint] = []
    cumulative = 0.0
    if amounts:
        for minute in _minutes(window):
            minute_cost = by_minute[minute]
            cumulative += minute_cost
            points.extend((ChartPoint(minute, "USD/min", minute_cost), ChartPoint(minute, "Cumulative USD", cumulative)))
    return PanelMetrics({"total": cumulative if amounts else None}, tuple(points))


def tokens_metrics(window: LogWindow) -> PanelMetrics:
    responses = [row for row in window.events if row.event == "response_sent"]
    input_by_minute: dict[datetime, float] = defaultdict(float)
    output_by_minute: dict[datetime, float] = defaultdict(float)
    has_input = has_output = False
    for row in responses:
        if _valid(row.tokens_in):
            input_by_minute[_minute(row.ts)] += row.tokens_in
            has_input = True
        if _valid(row.tokens_out):
            output_by_minute[_minute(row.ts)] += row.tokens_out
            has_output = True
    points: list[ChartPoint] = []
    input_total = output_total = 0.0
    for minute in _minutes(window):
        input_total += input_by_minute[minute]
        output_total += output_by_minute[minute]
        if has_input:
            points.append(ChartPoint(minute, "Input tokens", input_total))
        if has_output:
            points.append(ChartPoint(minute, "Output tokens", output_total))
    return PanelMetrics(
        {"tokens_in": input_total if has_input else None, "tokens_out": output_total if has_output else None},
        tuple(points),
    )


def quality_metrics(window: LogWindow) -> PanelMetrics:
    scores = [row for row in window.events if row.event == "response_sent" and _valid(row.quality_score, 0, 1)]
    by_minute: dict[datetime, list[float]] = defaultdict(list)
    for row in scores:
        by_minute[_minute(row.ts)].append(row.quality_score)
    count = 0
    total = 0.0
    points: list[ChartPoint] = []
    for minute in _minutes(window):
        samples = by_minute.get(minute, [])
        count += len(samples)
        total += sum(samples)
        if count:
            points.append(ChartPoint(minute, "Mean quality", total / count))
    return PanelMetrics({"mean": total / count if count else None}, tuple(points))
