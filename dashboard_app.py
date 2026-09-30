"""Streamlit dashboard for the six panels in config/dashboard.yaml."""

from __future__ import annotations

from datetime import datetime, timezone

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_data import DashboardSpec, LogWindow, PanelSpec, load_dashboard_spec, load_retrieval_target, read_log_window
from dashboard_metrics import (
    PanelMetrics,
    cost_metrics,
    errors_metrics,
    latency_metrics,
    quality_metrics,
    tokens_metrics,
    traffic_metrics,
)


st.set_page_config(page_title="Day 13 Monitoring", layout="wide")


def _metric(label: str, value: float | None, suffix: str, decimals: int = 1) -> None:
    display = "N/A" if value is None else f"{value:,.{decimals}f}{suffix}"
    st.metric(label, display)


def _metadata(
    panel: PanelSpec,
    spec: DashboardSpec,
    window: LogWindow,
    extra: str = "",
) -> None:
    direction = "≤" if panel.threshold.operator == "lte" else "≥"
    threshold = f"{direction} {panel.threshold.value:g} {panel.unit}"
    time_range = (
        "toàn bộ thời gian"
        if window.range_minutes is None
        else f"{window.range_minutes} phút gần nhất"
    )
    st.caption(
        f"{time_range} UTC · làm mới {spec.refresh_seconds} giây · "
        f"đơn vị: {panel.unit} · ngưỡng {panel.threshold.aggregation}: {threshold}{extra}"
    )


def _chart(
    window: LogWindow,
    metrics: PanelMetrics,
    unit: str,
    thresholds: tuple[float, ...],
    series: str | None = None,
    height: int = 220,
) -> None:
    points = [point for point in metrics.points if series is None or point.series == series]
    if not points:
        time_range = (
            "toàn bộ thời gian"
            if window.range_minutes is None
            else f"{window.range_minutes} phút qua"
        )
        st.caption(f"Chưa có dữ liệu cho chỉ số này trong {time_range}.")
        return
    rows = [
        {
            "minute": point.minute,
            "minute_utc": point.minute.strftime("%Y-%m-%d %H:%M UTC"),
            "series": point.series,
            "value": point.value,
        }
        for point in points
    ]
    data = pd.DataFrame(rows, columns=["minute", "minute_utc", "series", "value"])
    lines = alt.Chart(data).mark_line(point=True).encode(
        x=alt.X(
            "minute:T",
            title="Thời gian (UTC)",
            scale=alt.Scale(
                type="utc",
                domain=[window.start.replace(second=0, microsecond=0).isoformat(), window.end.isoformat()],
            ),
            axis=alt.Axis(
                format="%Y-%m-%d %H:%M" if window.range_minutes is None else "%H:%M"
            ),
        ),
        y=alt.Y("value:Q", title=unit),
        color=alt.Color("series:N", title="Chỉ số"),
        tooltip=[
            alt.Tooltip("minute_utc:N", title="Thời gian"),
            alt.Tooltip("series:N", title="Chỉ số"),
            alt.Tooltip("value:Q", title=unit, format=",.2f"),
        ],
    )
    chart = lines
    if thresholds:
        rules = alt.Chart(pd.DataFrame({"threshold": list(thresholds)})).mark_rule(
            color="#D96B28", strokeDash=[6, 4], strokeWidth=2
        ).encode(y="threshold:Q")
        chart = lines + rules
    st.altair_chart(chart.properties(height=height), width="stretch")


def _latency(panel: PanelSpec, spec: DashboardSpec, window: LogWindow, _: float) -> None:
    metrics = latency_metrics(window)
    _metadata(panel, spec, window)
    cols = st.columns(4)
    for col, label, key in zip(cols, ("P50", "P95", "P99", "TTFT P95"), ("p50", "p95", "p99", "ttft_p95")):
        with col:
            _metric(label, metrics.values[key], " ms", 0)
    _chart(window, metrics, "ms", (panel.threshold.value,))


def _traffic(panel: PanelSpec, spec: DashboardSpec, window: LogWindow, _: float) -> None:
    metrics = traffic_metrics(window)
    _metadata(panel, spec, window)
    cols = st.columns(2)
    with cols[0]:
        _metric("Requests", metrics.values["count"], "", 0)
    with cols[1]:
        _metric("Trung bình/phút", metrics.values["rate_per_minute"], " req/min", 2)
    _chart(window, metrics, "requests_per_minute", (panel.threshold.value,))


def _errors(panel: PanelSpec, spec: DashboardSpec, window: LogWindow, retrieval_target: float) -> None:
    metrics = errors_metrics(window)
    _metadata(panel, spec, window, f" · retrieval success ≥ {retrieval_target:g}%")
    cols = st.columns(2)
    with cols[0]:
        _metric("Error rate", metrics.values["error_rate_pct"], "%", 1)
    with cols[1]:
        _metric("Retrieval success", metrics.values["tool_success_rate_pct"], "%", 1)
    if metrics.error_types:
        st.caption("Loại lỗi: " + ", ".join(f"{name} {count}" for name, count in metrics.error_types))
    else:
        st.caption("Loại lỗi: chưa có request_failed.")
    st.caption(f"Error rate theo phút · ngưỡng {panel.threshold.value:g}%")
    _chart(window, metrics, "percent", (panel.threshold.value,), series="Error rate", height=150)
    st.caption(f"Retrieval success theo phút · ngưỡng {retrieval_target:g}%")
    _chart(window, metrics, "percent", (retrieval_target,), series="Retrieval success", height=150)


def _cost(panel: PanelSpec, spec: DashboardSpec, window: LogWindow, _: float) -> None:
    metrics = cost_metrics(window)
    if window.range_minutes is None:
        extra = " · tổng lũy kế toàn thời gian; ngưỡng cấu hình chỉ áp dụng cho 60 phút"
        thresholds = ()
    else:
        extra = " · ngưỡng áp dụng cho tổng chi phí tích lũy trong cửa sổ đã chọn"
        thresholds = (panel.threshold.value,)
    _metadata(panel, spec, window, extra)
    _metric("Tổng chi phí", metrics.values["total"], " USD", 4)
    _chart(window, metrics, "usd", thresholds)


def _tokens(panel: PanelSpec, spec: DashboardSpec, window: LogWindow, _: float) -> None:
    metrics = tokens_metrics(window)
    _metadata(panel, spec, window, " cho từng field")
    cols = st.columns(2)
    with cols[0]:
        _metric("Input tokens", metrics.values["tokens_in"], "", 0)
    with cols[1]:
        _metric("Output tokens", metrics.values["tokens_out"], "", 0)
    _chart(window, metrics, "tokens", (panel.threshold.value,))


def _quality(panel: PanelSpec, spec: DashboardSpec, window: LogWindow, _: float) -> None:
    metrics = quality_metrics(window)
    _metadata(panel, spec, window)
    _metric("Mean quality", metrics.values["mean"], "", 3)
    _chart(window, metrics, "score_0_to_1", (panel.threshold.value,))


RENDERERS = {
    "latency": _latency,
    "traffic": _traffic,
    "errors": _errors,
    "cost": _cost,
    "tokens": _tokens,
    "quality": _quality,
}


def render_dashboard(spec: DashboardSpec, retrieval_target: float) -> None:
    selection = st.radio(
        "Khoảng thời gian",
        ("60 phút gần nhất", "Toàn bộ thời gian"),
        horizontal=True,
        key="dashboard_time_range",
    )
    minutes = spec.time_range_minutes if selection == "60 phút gần nhất" else None
    window = read_log_window(datetime.now(timezone.utc), minutes)
    st.caption(f"Dữ liệu đến {window.end:%Y-%m-%d %H:%M:%S} UTC · {len(window.events)} events trong cửa sổ")
    if window.skipped_lines:
        st.caption(f"Bỏ qua {window.skipped_lines} dòng log không hợp lệ.")
    for index in range(0, len(spec.panels), 2):
        columns = st.columns(2)
        for column, panel in zip(columns, spec.panels[index : index + 2]):
            with column:
                with st.container(border=True):
                    st.subheader(panel.title)
                    RENDERERS[panel.id](panel, spec, window, retrieval_target)


def main() -> None:
    try:
        spec = load_dashboard_spec()
        retrieval_target = load_retrieval_target()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.title(spec.title)
    st.fragment(run_every=f"{spec.refresh_seconds}s")(render_dashboard)(spec, retrieval_target)


if __name__ == "__main__":
    main()
