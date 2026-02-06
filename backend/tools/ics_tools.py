"""ICS generation utilities for calendar exports."""

from __future__ import annotations

import datetime
from typing import Dict, Iterable, List, Optional


def _escape_text(value: str) -> str:
    """Escape text per RFC 5545."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold_line(line: str, limit: int = 75) -> str:
    """Fold long lines per RFC 5545 (approximate; counts characters)."""
    if len(line) <= limit:
        return line
    parts = [line[i : i + limit] for i in range(0, len(line), limit)]
    return "\r\n ".join(parts)


def _format_dt(dt: datetime.datetime) -> str:
    utc = dt.astimezone(datetime.timezone.utc)
    return utc.strftime("%Y%m%dT%H%M%SZ")


def _parse_task_time(
    value: Optional[str], plan_date: datetime.date, tzinfo: datetime.tzinfo
) -> Optional[datetime.datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()

    try:
        dt = datetime.datetime.fromisoformat(text.replace("T", " "))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tzinfo)
        return dt.astimezone(tzinfo)
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(text, fmt)
            return dt.replace(tzinfo=tzinfo)
        except ValueError:
            continue

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.datetime.strptime(text, fmt).time()
            return datetime.datetime.combine(plan_date, t).replace(tzinfo=tzinfo)
        except ValueError:
            continue

    return None


def _status_for_task(status: Optional[str]) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"done", "completed", "complete"}:
        return "COMPLETED"
    if normalized in {"cancelled", "canceled"}:
        return "CANCELLED"
    return "CONFIRMED"


def build_ics(
    tasks: Iterable[Dict],
    plan_date: datetime.date,
    calendar_name: str = "ADHD Timebox",
    prod_id: str = "-//ADHD Timebox//EN",
) -> str:
    """Return RFC 5545 ICS content for tasks on a given date."""
    tzinfo = datetime.datetime.now().astimezone().tzinfo or datetime.timezone.utc
    now = datetime.datetime.now(tz=tzinfo)
    lines: List[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{prod_id}",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape_text(calendar_name)}",
    ]

    for idx, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue
        title = (task.get("title") or "").strip()
        if not title:
            continue
        start_dt = _parse_task_time(task.get("start"), plan_date, tzinfo)
        end_dt = _parse_task_time(task.get("end"), plan_date, tzinfo)
        if not start_dt or not end_dt or end_dt <= start_dt:
            continue

        task_id = task.get("id") or f"task-{idx}"
        uid = f"{task_id}-{plan_date.isoformat()}@adhd-timebox"
        description = (
            task.get("description")
            or task.get("notes")
            or task.get("detail")
            or ""
        )
        categories = task.get("type") or ""
        status = _status_for_task(task.get("status"))

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{_escape_text(str(uid))}",
            f"DTSTAMP:{_format_dt(now)}",
            f"SUMMARY:{_escape_text(title)}",
            f"DTSTART:{_format_dt(start_dt)}",
            f"DTEND:{_format_dt(end_dt)}",
            f"STATUS:{status}",
        ]
        if description:
            event_lines.append(f"DESCRIPTION:{_escape_text(str(description))}")
        if categories:
            event_lines.append(f"CATEGORIES:{_escape_text(str(categories))}")
        event_lines.append("END:VEVENT")

        lines.extend(event_lines)

    lines.append("END:VCALENDAR")
    folded = [_fold_line(line) for line in lines]
    return "\r\n".join(folded) + "\r\n"
