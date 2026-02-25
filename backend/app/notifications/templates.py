from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text_body: str
    html_body: str | None
    short_text: str


def _format_date_de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def render_task_due_soon(payload: dict) -> RenderedEmail:
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    grouped: dict[str, list[dict]] = {
        "heute": [],
        "morgen": [],
        "in 2 Tagen": [],
        "in 3 Tagen": [],
        "sp\u00e4ter": [],
    }

    for task in tasks:
        due_in_days = int(task.get("due_in_days", 99))
        if due_in_days <= 0:
            bucket = "heute"
        elif due_in_days == 1:
            bucket = "morgen"
        elif due_in_days == 2:
            bucket = "in 2 Tagen"
        elif due_in_days == 3:
            bucket = "in 3 Tagen"
        else:
            bucket = "sp\u00e4ter"
        grouped[bucket].append(task)

    total = len(tasks)
    subject = "1 Aufgabe bald f\u00e4llig" if total == 1 else f"{total} Aufgaben bald f\u00e4llig"

    greeting_name = payload.get("user_display_name")
    greeting = (
        f"Hallo {greeting_name}," if isinstance(greeting_name, str) and greeting_name else "Hallo,"
    )

    lines = [greeting, "", "die folgenden Aufgaben stehen bald an:", ""]
    for bucket in ("heute", "morgen", "in 2 Tagen", "in 3 Tagen"):
        bucket_tasks = grouped[bucket]
        if not bucket_tasks:
            continue
        lines.append(f"{bucket}:")
        for task in bucket_tasks[:10]:
            due_date_raw = task.get("due_date")
            due_date = (
                datetime.fromisoformat(due_date_raw).date()
                if isinstance(due_date_raw, str)
                else date.today()
            )
            lines.append(
                f"- {task.get('title', 'Aufgabe')} ({_format_date_de(due_date)})"
            )
        if len(bucket_tasks) > 10:
            lines.append(f"- ... und {len(bucket_tasks) - 10} weitere")
        lines.append("")

    lines.append(f"Plan \u00f6ffnen: {payload.get('plan_url', '')}")
    lines.append(f"Einstellungen: {payload.get('settings_url', '')}")
    lines.append(f"Abmelden: {payload.get('unsubscribe_url', '')}")

    text_body = "\n".join(lines)

    html_lines = [
        "<p>" + greeting + "</p>",
        "<p>die folgenden Aufgaben stehen bald an:</p>",
    ]
    for bucket in ("heute", "morgen", "in 2 Tagen", "in 3 Tagen"):
        bucket_tasks = grouped[bucket]
        if not bucket_tasks:
            continue
        html_lines.append(f"<h3>{bucket}</h3><ul>")
        for task in bucket_tasks[:10]:
            due_date_raw = task.get("due_date")
            due_date = (
                datetime.fromisoformat(due_date_raw).date()
                if isinstance(due_date_raw, str)
                else date.today()
            )
            html_lines.append(
                f"<li>{task.get('title', 'Aufgabe')} ({_format_date_de(due_date)})</li>"
            )
        if len(bucket_tasks) > 10:
            html_lines.append(f"<li>... und {len(bucket_tasks) - 10} weitere</li>")
        html_lines.append("</ul>")

    html_lines.extend(
        [
            f"<p><a href=\"{payload.get('plan_url', '')}\">Plan \u00f6ffnen</a></p>",
            f"<p><a href=\"{payload.get('settings_url', '')}\">Benachrichtigungseinstellungen</a></p>",
            f"<p><a href=\"{payload.get('unsubscribe_url', '')}\">Abmelden</a></p>",
        ]
    )

    short_text = subject

    return RenderedEmail(
        subject=subject,
        text_body=text_body,
        html_body="\n".join(html_lines),
        short_text=short_text,
    )
