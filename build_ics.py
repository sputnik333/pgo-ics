#!/usr/bin/env python3
"""Convert vivific's pgocalendar JSON into an iCalendar (.ics) feed.

Usage:
    python build_ics.py                      # downloads the JSON, writes calendar.ics
    python build_ics.py events.json out.ics  # use a local JSON file instead
"""
import hashlib
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

SOURCE_URL = "https://vivific.github.io/pgocalendar/data/calendar_events.json"
CAL_NAME = "Pokémon GO Calendar"


def load(path=None):
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "pgo-ics-builder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def esc(text):
    """Escape a TEXT value per RFC 5545."""
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line):
    """Fold lines to max 75 octets without splitting UTF-8 characters."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74  # continuation lines start with a space
        if len(cur) + len(b) > limit:
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def parse_day(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def describe_obtainable(items):
    lines = []
    for o in items or []:
        name = o.get("pokemon") or o.get("name") or o.get("type")
        if not name:
            continue
        extras = [x for x in (o.get("form"), o.get("costume")) if x]
        label = name + (f" ({', '.join(map(str, extras))})" if extras else "")
        if any(m.get("shiny") for m in o.get("methods") or []):
            label += " ✨"
        methods = sorted({m.get("method") for m in o.get("methods") or [] if m.get("method")})
        if methods:
            label += f" – {', '.join(methods)}"
        lines.append(f"• {label}")
    return lines


def describe_bonuses(items):
    lines = []
    for b in items or []:
        label = b.get("label")
        if not label:
            parts = [b.get("action"), b.get("type")]
            if b.get("multiplier"):
                parts.insert(0, f"{b['multiplier']}×")
            label = " ".join(str(p) for p in parts if p)
        if label:
            lines.append(f"• {label}")
    return lines


def build(data):
    events = data.get("events", data if isinstance(data, list) else [])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//pgo-ics-builder//vivific pgocalendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(CAL_NAME)}",
        "X-PUBLISHED-TTL:PT6H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
    ]
    seen = set()
    count = 0
    for ev in events:
        start = parse_day(ev.get("start"))
        if not start:
            continue
        end = parse_day(ev.get("end"))
        open_ended = end is None
        if end is None or end < start:
            end = start
        # All-day events: DTEND is exclusive, so add one day to the inclusive end date.
        dtend = end + timedelta(days=1)

        ident = ev.get("identifier") or ev.get("name", "event")
        uid_base = f"{ident}-{start.isoformat()}"
        if uid_base in seen:
            uid_base += "-" + hashlib.sha1(json.dumps(ev, sort_keys=True).encode()).hexdigest()[:8]
        seen.add(uid_base)

        desc = []
        kind = " / ".join(dict.fromkeys(x for x in (ev.get("type"), ev.get("subtype")) if x))
        if kind:
            desc.append(f"Type: {kind}")
        if open_ended:
            desc.append("Ingen slutdato angivet (vist som én dag).")
        avail = ev.get("availability") or {}
        if avail.get("ticketed"):
            desc.append("Kræver billet")
        ob = describe_obtainable(ev.get("obtainable"))
        if ob:
            desc += ["", "Kan fås:"] + ob
        bo = describe_bonuses(ev.get("bonuses"))
        if bo:
            desc += ["", "Bonusser:"] + bo
        if ev.get("notes"):
            desc += ["", str(ev["notes"])]
        sources = [s.get("url") for s in ev.get("sources") or [] if isinstance(s, dict) and s.get("url")]
        if sources:
            desc += ["", "Kilder:"] + sources

        locs = avail.get("locations") or avail.get("regions") or []
        if isinstance(locs, (str, dict)):
            locs = [locs]
        loc_text = ", ".join(
            (l.get("name") or l.get("city") or json.dumps(l, ensure_ascii=False)) if isinstance(l, dict) else str(l)
            for l in locs
        )

        lines = [
            "BEGIN:VEVENT",
            f"UID:{esc(uid_base)}@pgocalendar",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{dtend.strftime('%Y%m%d')}",
            f"SUMMARY:{esc(ev.get('name') or ident)}",
            "TRANSP:TRANSPARENT",
        ]
        if desc:
            lines.append(f"DESCRIPTION:{esc(chr(10).join(desc))}")
        if loc_text:
            lines.append(f"LOCATION:{esc(loc_text)}")
        if kind:
            lines.append(f"CATEGORIES:{esc(ev.get('type') or kind)}")
        if sources:
            lines.append(f"URL:{sources[0]}")
        lines.append("END:VEVENT")
        out += [fold(l) for l in lines]
        count += 1
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n", count


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    dst = sys.argv[2] if len(sys.argv) > 2 else "calendar.ics"
    ics, n = build(load(src))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(ics)
    print(f"Wrote {n} events to {dst}")


if __name__ == "__main__":
    main()
