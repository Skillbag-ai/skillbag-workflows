#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path


WEEKDAYS = {
    "en": (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ),
    "de": (
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag",
    ),
    "es": ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"),
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "it": ("lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"),
    "nl": ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"),
    "pt": (
        "segunda-feira",
        "terca-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sabado",
        "domingo",
    ),
}

HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?:, ([^\n]+))?\n", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update a chronological Markdown log file."
    )
    parser.add_argument("folder", help="Target folder for the log file.")
    parser.add_argument(
        "--filename",
        default="log.md",
        help="Log filename inside the target folder. Defaults to log.md.",
    )
    parser.add_argument(
        "--date",
        help="Entry date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--text",
        required=True,
        help="Markdown content to insert into the log.",
    )
    parser.add_argument(
        "--mode",
        choices=("append", "replace"),
        default="append",
        help=(
            "For an existing date, append above existing content or replace "
            "the whole date section."
        ),
    )
    parser.add_argument(
        "--weekday-locale",
        choices=(*WEEKDAYS.keys(), "none"),
        default="en",
        help="Language for weekday labels, or none to omit weekday labels.",
    )
    return parser.parse_args()


def normalized_entry(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise SystemExit("--text must not be empty")
    return f"{stripped}\n"


def resolve_date(raw_date: str | None) -> dt.date:
    if raw_date is None:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(raw_date)
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD format") from exc


def build_heading(entry_date: dt.date, weekday_locale: str) -> str:
    if weekday_locale == "none":
        return f"## {entry_date.isoformat()}\n"
    weekday = WEEKDAYS[weekday_locale][entry_date.weekday()]
    return f"## {entry_date.isoformat()}, {weekday}\n"


def split_sections(content: str) -> list[tuple[dt.date, str, str]]:
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        stripped = content.strip()
        return [] if not stripped else [(dt.date.min, "", stripped)]

    sections: list[tuple[dt.date, str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        heading = match.group(0)
        block = content[start + len(heading) : end].strip()
        section_date = dt.date.fromisoformat(match.group(1))
        sections.append((section_date, heading, block))
    return sections


def render_sections(sections: list[tuple[dt.date, str, str]]) -> str:
    rendered: list[str] = []
    for _, heading, block in sections:
        if heading:
            rendered.append(f"{heading}{block}\n")
        elif block:
            rendered.append(f"{block}\n")
    return "\n\n".join(part.rstrip("\n") for part in rendered).rstrip() + "\n"


def update_content(
    content: str, entry_date: dt.date, heading: str, entry: str, mode: str
) -> str:
    sections = split_sections(content)

    for index, (section_date, section_heading, block) in enumerate(sections):
        if section_heading and section_date == entry_date:
            updated_block = (
                entry.strip() if mode == "replace" else f"{entry}\n{block}".strip()
            )
            sections[index] = (section_date, section_heading, updated_block)
            return render_sections(sections)

    new_section = (entry_date, heading, entry.strip())
    insert_at = len(sections)
    for index, (section_date, section_heading, _) in enumerate(sections):
        if not section_heading:
            continue
        if entry_date > section_date:
            insert_at = index
            break

    sections.insert(insert_at, new_section)
    return render_sections(sections)


def validate_filename(filename: str) -> None:
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise SystemExit("--filename must be a plain filename inside the target folder")


def main() -> None:
    args = parse_args()
    validate_filename(args.filename)

    folder = Path(args.folder)
    file_path = folder / args.filename
    folder.mkdir(parents=True, exist_ok=True)

    entry_date = resolve_date(args.date)
    heading = build_heading(entry_date, args.weekday_locale)
    entry = normalized_entry(args.text)

    content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    updated = update_content(content, entry_date, heading, entry, args.mode)
    file_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
