#!/usr/bin/env python3
"""Calculate per-person statistics from the generated chat archive."""

from __future__ import annotations

import argparse
import json
import re
import struct
from collections import Counter
from pathlib import Path

BIDI_RE = re.compile(r"[\u200e\u200f\ufeff\u202a-\u202e\u2066-\u2069]")
CALL_RE = re.compile(r"^(Missed )?(Voice|Video) call\s+(.+)$", re.IGNORECASE)
EDIT_RE = re.compile(r"\s*<This message was edited>\s*$", re.IGNORECASE)
OMITTED_RE = re.compile(
    r"\s*(image|audio|video|sticker|video note|document) omitted\s*$",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
DELETED = {"This message was deleted.", "You deleted this message."}


def load_chats(path: Path) -> list[dict]:
    html = path.read_text(encoding="utf-8")
    marker = "const D="
    start = html.index(marker) + len(marker)
    end = html.index(";\nconst C=JSON.parse(D)", start)
    encoded_json = json.loads(html[start:end])
    return json.loads(encoded_json)


def clean(text: str) -> str:
    return BIDI_RE.sub("", text).replace("\u202f", " ").strip()


def is_admin(text: str) -> bool:
    lowered = text.lower()
    return (
        "messages and calls are end-to-end encrypted" in lowered
        or "uses a default timer for disappearing messages" in lowered
        or lowered.endswith(" is a contact.")
        or "turned off disappearing messages" in lowered
        or text == "You pinned a message"
    )


def call_info(text: str) -> tuple[str, str, int | None] | None:
    match = CALL_RE.match(clean(text))
    if not match:
        return None
    missed, call_type, detail = match.groups()
    duration = None
    duration_match = re.fullmatch(r"(\d+)\s*(sec|min|hr)", detail, re.IGNORECASE)
    if duration_match:
        value = int(duration_match.group(1))
        duration = value * {"sec": 1, "min": 60, "hr": 3600}[duration_match.group(2).lower()]
    if missed:
        status = "missed"
    elif duration is not None:
        status = "connected"
    else:
        status = detail.lower()
    return call_type.lower(), status, duration


def authored_text(entry: dict) -> str:
    text = clean(entry.get("text", ""))
    if not text or entry.get("media") or call_info(text) or is_admin(text) or text in DELETED:
        return ""
    text = EDIT_RE.sub("", text).strip()
    text = OMITTED_RE.sub("", text).strip()
    return text


def opus_duration(path: Path) -> float | None:
    """Read duration from the final Ogg granule position (Opus uses 48 kHz)."""
    data = path.read_bytes()
    position = 0
    final_granule = None
    while True:
        position = data.find(b"OggS", position)
        if position < 0 or position + 27 > len(data):
            break
        segment_count = data[position + 26]
        segment_table_end = position + 27 + segment_count
        if segment_table_end > len(data):
            break
        body_size = sum(data[position + 27 : segment_table_end])
        page_end = segment_table_end + body_size
        if page_end > len(data):
            position += 4
            continue
        granule = struct.unpack_from("<q", data, position + 6)[0]
        if granule >= 0:
            final_granule = granule
        position = page_end
    return final_granule / 48_000 if final_granule is not None else None


def media_kind(media: dict) -> str:
    extension = Path(media.get("path", "")).suffix.lower()
    content_type = media.get("contentType", "") or ""
    if extension == ".opus" or content_type.startswith("audio/"):
        return "Voice messages"
    if extension == ".webp":
        return "Stickers"
    if extension in {".jpg", ".jpeg", ".png", ".heic"} or content_type.startswith("image/"):
        return "Photos"
    if extension == ".mp4" or content_type.startswith("video/"):
        return "Videos"
    return "Other playable files"


def fmt_duration(seconds: float) -> str:
    rounded = round(seconds)
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}h {minutes}m {secs}s"


def pct(value: float, total: float) -> str:
    return f"{value / total * 100:.2f}%" if total else "0.00%"


def analyze(chat: dict, archive_path: Path) -> tuple[list[str], dict[str, dict[str, float]]]:
    entries = chat["entries"]
    participants = sorted({entry["sender"] for entry in entries}, key=lambda name: (name != "You", name))
    stats = {person: Counter() for person in participants}
    voice_seconds = Counter()
    call_seconds = Counter()

    for entry in entries:
        person = entry["sender"]
        if person not in stats:
            continue
        stat = stats[person]
        stat["Entries"] += 1

        text = authored_text(entry)
        if text:
            stat["Written messages"] += 1
            stat["Characters"] += len(text)
            stat["Words"] += len(WORD_RE.findall(text))
            stat["Links"] += len(URL_RE.findall(text))

        cleaned = clean(entry.get("text", ""))
        if cleaned in DELETED:
            stat["Deleted messages"] += 1

        call = call_info(cleaned)
        if call:
            stat["Call records"] += 1
            if call[2] is not None:
                call_seconds[person] += call[2]

        for media in entry.get("media", []):
            stat["All playable media"] += 1
            kind = media_kind(media)
            stat[kind] += 1
            if kind == "Voice messages":
                archive_root = archive_path.parent.resolve()
                relative = Path(media["path"])
                media_path = (archive_root / relative).resolve()
                if relative.is_absolute() or ".." in relative.parts or not media_path.is_relative_to(archive_root / "media"):
                    raise ValueError("Unsafe archived media path")
                if media_path.exists():
                    duration = opus_duration(media_path)
                    if duration is not None:
                        voice_seconds[person] += duration

    rows = [
        "Entries", "Written messages", "Characters", "Words",
        "Voice messages", "Voice-message minutes", "Photos", "Stickers",
        "Videos", "All playable media", "Call records", "Connected-call time",
        "Links", "Deleted messages",
    ]
    for person in participants:
        stats[person]["Voice-message minutes"] = voice_seconds[person] / 60
        stats[person]["Connected-call time"] = call_seconds[person]
    return rows, stats


def render_markdown(chat_name: str, rows: list[str], stats: dict[str, dict[str, float]]) -> str:
    participants = list(stats)
    labels = [name.replace("|", "\\|").replace("\n", " ") for name in participants]
    title = chat_name.replace("\n", " ")
    lines = [f"# {title} chat statistics", "", "| All-time metric | " + " | ".join(labels) + " |", "|---|" + "---:|" * len(participants)]
    integer_rows = {"Entries", "Written messages", "Characters", "Words", "Voice messages", "Photos", "Stickers", "Videos", "All playable media", "Call records", "Links", "Deleted messages"}
    for row in rows:
        total = sum(stats[person][row] for person in participants)
        cells = []
        for person in participants:
            value = stats[person][row]
            if row == "Voice-message minutes":
                cell = f"{value:.2f} ({pct(value, total)})"
            elif row == "Connected-call time":
                cell = f"{fmt_duration(value)} ({pct(value, total)})"
            elif row in integer_rows:
                cell = f"{int(value):,} ({pct(value, total)})"
            else:
                cell = str(value)
            cells.append(cell)
        lines.append(f"| {row} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/index.html"))
    parser.add_argument("--chat", required=True, help="Exact chat name in the generated archive")
    args = parser.parse_args()

    try:
        chats = load_chats(args.input)
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot read generated archive: {exc}")
    matches = [chat for chat in chats if chat.get("name") == args.chat]
    if len(matches) != 1:
        raise SystemExit(f"Expected one chat named {args.chat!r}; found {len(matches)}")
    rows, stats = analyze(matches[0], args.input)
    print(render_markdown(args.chat, rows, stats))


if __name__ == "__main__":
    main()
