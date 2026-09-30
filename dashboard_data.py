"""Read the dashboard contract and a safe, UTC-normalized log window."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
LOG_SOURCE = "data/logs.jsonl"
PANEL_IDS = frozenset({"latency", "traffic", "errors", "cost", "tokens", "quality"})
SAFE_ERROR_TYPES = frozenset(
    {
        "RuntimeError",
        "TimeoutError",
        "ConnectionError",
        "ValueError",
        "TypeError",
        "KeyError",
        "AttributeError",
        "OSError",
        "HTTPError",
        "Exception",
    }
)


@dataclass(frozen=True, slots=True)
class Threshold:
    aggregation: str
    operator: str
    value: float


@dataclass(frozen=True, slots=True)
class PanelSpec:
    id: str
    title: str
    unit: str
    source: str
    threshold: Threshold


@dataclass(frozen=True, slots=True)
class DashboardSpec:
    title: str
    time_range_minutes: int
    refresh_seconds: int
    panels: tuple[PanelSpec, ...]


@dataclass(frozen=True, slots=True)
class LogEvent:
    ts: datetime
    event: str
    latency_ms: float | None
    ttft_ms: float | None
    cost_usd: float | None
    tokens_in: float | None
    tokens_out: float | None
    quality_score: float | None
    tool_success: bool | None
    error_type: str | None


@dataclass(frozen=True, slots=True)
class LogWindow:
    start: datetime
    end: datetime
    events: tuple[LogEvent, ...]
    skipped_lines: int


def _yaml_object(path: Path) -> dict:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được cấu hình {path.name}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Cấu hình {path.name} phải là YAML object.")
    return payload


def load_dashboard_spec() -> DashboardSpec:
    data = _yaml_object(ROOT / "config" / "dashboard.yaml").get("dashboard")
    if not isinstance(data, dict):
        raise ValueError("Thiếu dashboard trong config/dashboard.yaml.")
    panels = data.get("panels")
    if not isinstance(panels, list) or len(panels) != 6:
        raise ValueError("Dashboard cần đúng 6 panel.")
    if data.get("time_range_minutes") != 60 or data.get("refresh_seconds") != 30:
        raise ValueError("Dashboard cần cửa sổ 60 phút và refresh 30 giây.")

    parsed: list[PanelSpec] = []
    for panel in panels:
        if not isinstance(panel, dict) or not isinstance(panel.get("threshold"), dict):
            raise ValueError("Định nghĩa panel trong dashboard.yaml không hợp lệ.")
        threshold = panel["threshold"]
        if panel.get("source") != LOG_SOURCE:
            raise ValueError("Mọi panel phải dùng data/logs.jsonl.")
        if isinstance(threshold.get("value"), bool) or not isinstance(threshold.get("value"), (int, float)):
            raise ValueError("Threshold của panel phải là số.")
        if not math.isfinite(float(threshold["value"])):
            raise ValueError("Threshold của panel phải là số hữu hạn.")
        parsed.append(
            PanelSpec(
                id=panel["id"],
                title=panel["title"],
                unit=panel["unit"],
                source=panel["source"],
                threshold=Threshold(
                    aggregation=threshold["aggregation"],
                    operator=threshold["operator"],
                    value=float(threshold["value"]),
                ),
            )
        )
    if {panel.id for panel in parsed} != PANEL_IDS or len({panel.id for panel in parsed}) != 6:
        raise ValueError("Dashboard phải có đủ sáu panel ID duy nhất.")
    return DashboardSpec(
        title=data["title"],
        time_range_minutes=data["time_range_minutes"],
        refresh_seconds=data["refresh_seconds"],
        panels=tuple(parsed),
    )


def load_retrieval_target() -> float:
    data = _yaml_object(ROOT / "config" / "slo.yaml")
    try:
        target = float(data["guardrails"]["retrieval_success_rate_pct_min"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Thiếu guardrail retrieval success trong config/slo.yaml.") from exc
    if not math.isfinite(target) or not 0 <= target <= 100:
        raise ValueError("Guardrail retrieval success phải nằm trong 0–100%.")
    return target


def _utc_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _event(row: dict, ts: datetime) -> LogEvent:
    error_type = row.get("error_type")
    if isinstance(error_type, str):
        error_type = error_type if error_type in SAFE_ERROR_TYPES else "Other"
    else:
        error_type = None
    tool_success = row.get("tool_success")
    if not isinstance(tool_success, bool):
        tool_success = None
    return LogEvent(
        ts=ts,
        event=row["event"],
        latency_ms=_number(row.get("latency_ms")),
        ttft_ms=_number(row.get("ttft_ms")),
        cost_usd=_number(row.get("cost_usd")),
        tokens_in=_number(row.get("tokens_in")),
        tokens_out=_number(row.get("tokens_out")),
        quality_score=_number(row.get("quality_score")),
        tool_success=tool_success,
        error_type=error_type,
    )


def read_log_window(now: datetime, minutes: int = 60) -> LogWindow:
    end = now.astimezone(timezone.utc)
    start = end - timedelta(minutes=minutes)
    rows: list[LogEvent] = []
    skipped = 0
    try:
        with (ROOT / LOG_SOURCE).open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    skipped += 1
                    continue
                if not isinstance(row, dict) or not isinstance(row.get("event"), str):
                    skipped += 1
                    continue
                ts = _utc_ts(row.get("ts"))
                if ts is None:
                    skipped += 1
                    continue
                if start <= ts <= end:
                    rows.append(_event(row, ts))
    except FileNotFoundError:
        pass
    rows.sort(key=lambda row: row.ts)
    return LogWindow(start=start, end=end, events=tuple(rows), skipped_lines=skipped)
