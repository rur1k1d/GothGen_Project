#!/usr/bin/env python3
"""Small offline name generator for historical and historically inspired names."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from datetime import date as date_cls
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_NAMES = DATA_DIR / "names.csv"
DEFAULT_SOURCES = DATA_DIR / "sources.csv"
DEFAULT_LEXICON = DATA_DIR / "lexicon.csv"
DEFAULT_BYNAMES = DATA_DIR / "bynames.csv"

KNOWN_CULTURES = {
    "gothic",
    "geat",
    "anglo_saxon",
    "norse",
    "varangian_rus",
    "scythian",
    "alan_sarmatian",
}
KNOWN_BYNAME_TYPES = {"epithet", "title"}

CONFIDENCE_WEIGHTS = {"high": 4.0, "medium": 2.0, "low": 1.0, "uncertain": 0.5}

LEET_MAP = str.maketrans(
    {
        "A": "4",
        "E": "3",
        "I": "1",
        "O": "0",
        "T": "7",
        "S": "5",
        "G": "9",
    }
)

SPECIAL_ASCII = str.maketrans(
    {
        "ø": "o",
        "Ø": "O",
        "æ": "ae",
        "Æ": "AE",
        "þ": "th",
        "Þ": "Th",
        "ð": "d",
        "Ð": "D",
        "ł": "l",
        "Ł": "L",
        "•": ".",
    }
)

DEFAULT_CULTURE = "gothic"
CULTURE_GROUPS = {
    "gothic": {"gothic", "norse", "geat"},
    "norse": {"norse", "gothic", "geat"},
    "geat": {"geat", "gothic", "norse", "anglo_saxon"},
    "varangian_rus": {"varangian_rus", "norse"},
}


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def c(self, code: str, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"{code}{text}{self.RESET}"

    def bold(self, text: str) -> str:
        return self.c(self.BOLD, text)

    def dim(self, text: str) -> str:
        return self.c(self.DIM, text)

    def cyan(self, text: str) -> str:
        return self.c(self.CYAN, text)

    def green(self, text: str) -> str:
        return self.c(self.GREEN, text)

    def yellow(self, text: str) -> str:
        return self.c(self.YELLOW, text)

    def red(self, text: str) -> str:
        return self.c(self.RED, text)

    def blue(self, text: str) -> str:
        return self.c(self.BLUE, text)


COLOR = Color(False)


def should_use_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


@dataclass(frozen=True)
class NameEntry:
    id: str
    name: str
    ascii: str
    gender: str
    name_type: str
    culture: str
    subculture: str
    origin: str
    era: str
    source_id: str
    source_locator: str
    meaning: str
    elements: str
    variants: str
    status: str
    confidence: str
    gothic_like: bool
    notes: str
    source: dict[str, str] = field(default_factory=dict, compare=False)

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "NameEntry":
        return cls(
            id=(row.get("id") or "").strip(),
            name=(row.get("name") or "").strip(),
            ascii=(row.get("ascii") or "").strip(),
            gender=(row.get("gender") or "").strip(),
            name_type=(row.get("name_type") or "").strip(),
            culture=(row.get("culture") or "").strip(),
            subculture=(row.get("subculture") or "").strip(),
            origin=(row.get("origin") or "").strip(),
            era=(row.get("era") or "").strip(),
            source_id=(row.get("source_id") or "").strip(),
            source_locator=(row.get("source_locator") or "").strip(),
            meaning=(row.get("meaning") or "").strip(),
            elements=(row.get("elements") or "").strip(),
            variants=(row.get("variants") or "").strip(),
            status=(row.get("status") or "").strip(),
            confidence=(row.get("confidence") or "").strip(),
            gothic_like=parse_bool(row.get("gothic_like")),
            notes=(row.get("notes") or "").strip(),
        )

    def display_source(self) -> str:
        source = self.source
        author = source.get("author", "").strip()
        title = source.get("title", "").strip() or self.source_id
        year = source.get("year", "").strip()
        locator = self.source_locator
        parts = [part for part in [author, title] if part]
        label = ", ".join(parts)
        if year:
            label = f"{label} ({year})"
        if locator and locator.lower() != title.lower():
            label = f"{label}, {locator}"
        return label or "source not recorded"


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_names(path: Path = DEFAULT_NAMES, sources_path: Path = DEFAULT_SOURCES) -> list[NameEntry]:
    sources = {row["source_id"]: row for row in read_csv(sources_path) if row.get("source_id")}
    entries: list[NameEntry] = []
    for row in read_csv(path):
        if not (row.get("id") or "").strip():
            continue
        entry = NameEntry.from_row(row)
        entry = replace(entry, source=sources.get(entry.source_id, {}))
        entries.append(entry)
    return entries


def load_lexicon(path: Path = DEFAULT_LEXICON) -> list[dict[str, str]]:
    return [row for row in read_csv(path) if (row.get("element") or "").strip()]


def load_bynames(path: Path = DEFAULT_BYNAMES) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return [row for row in read_csv(path) if (row.get("byname") or "").strip()]


def ascii_fold(value: str) -> str:
    value = value.translate(SPECIAL_ASCII)
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def leetspeak(value: str) -> str:
    base = ascii_fold(value).upper()
    return base.translate(LEET_MAP)


def weighted_choice(rng: random.Random, entries: Iterable[NameEntry]) -> NameEntry:
    pool = list(entries)
    weights = [CONFIDENCE_WEIGHTS.get(entry.confidence, 1.0) for entry in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def filter_entries(
    entries: Iterable[NameEntry],
    culture: str | None = None,
    gender: str | None = None,
    include_places: bool = False,
) -> list[NameEntry]:
    result = []
    allowed = None
    if culture:
        allowed = CULTURE_GROUPS.get(culture, {culture})
    for entry in entries:
        if not include_places and entry.name_type != "person":
            continue
        if allowed is not None and entry.culture not in allowed:
            continue
        if gender and entry.gender != gender:
            continue
        result.append(entry)
    return result


def filter_bynames(bynames: Iterable[dict[str, str]], culture: str | None = None) -> list[dict[str, str]]:
    result = []
    for b in bynames:
        if culture and b.get("culture") != culture:
            continue
        result.append(b)
    return result


def generate_bynames(bynames: Iterable[dict[str, str]], culture: str | None = None, count: int = 5, seed: int | None = None) -> list[dict[str, str]]:
    pool = filter_bynames(bynames, culture=culture)
    if not pool:
        raise ValueError("no bynames match the requested filter")
    rng = random.Random(seed)
    picked = []
    seen = set()
    attempts = 0
    while len(picked) < count and attempts < count * 50:
        attempts += 1
        b = rng.choice(pool)
        key = b.get("byname", "").lower()
        if key in seen:
            continue
        seen.add(key)
        picked.append(b)
    return picked


def combine_name_with_byname(name_entry: NameEntry, byname: dict[str, str]) -> str:
    name = name_entry.name
    by = byname.get("byname", "").strip()
    if not by:
        return name
    # Try simple combination: short name + byname, or name + byname
    if len(name) <= 4:
        return f"{name}{by}"
    return f"{name} {by}"


def daily_entries(
    entries: Iterable[NameEntry],
    day: str | None = None,
    culture: str | None = None,
    top: int = 1,
) -> list[NameEntry]:
    if top < 1:
        raise ValueError("--top must be at least 1")
    day = day or date_cls.today().isoformat()
    pool = filter_entries(entries, culture=culture)
    if not pool:
        raise ValueError("no names match the requested filter")
    ranked = sorted(
        pool,
        key=lambda entry: hashlib.sha256(f"{day}:{culture or 'all'}:{entry.id}".encode()).hexdigest(),
    )
    return ranked[: max(1, top)]


def generate_entries(
    entries: Iterable[NameEntry],
    culture: str | None = None,
    gender: str | None = None,
    count: int = 5,
    seed: int | None = None,
    include_places: bool = False,
) -> list[NameEntry]:
    pool = filter_entries(entries, culture=culture, gender=gender, include_places=include_places)
    if not pool:
        raise ValueError("no names match the requested filter")
    rng = random.Random(seed)
    picked: list[NameEntry] = []
    seen: set[str] = set()
    attempts = 0
    while len(picked) < count and attempts < count * 50:
        attempts += 1
        entry = weighted_choice(rng, pool)
        if entry.id in seen:
            continue
        seen.add(entry.id)
        picked.append(entry)
    return picked


COMBINE_LANGUAGES = {
    "gothic": ["gothic"],
    "geat": ["anglo_saxon", "norse"],
    "anglo_saxon": ["anglo_saxon"],
    "norse": ["norse"],
    "varangian_rus": ["norse", "slavic"],
}

UNSAFE_COMBINE_CULTURES = {
    "scythian": "Scythian names are attested-only here; no safe combinatorial lexicon is used.",
    "alan_sarmatian": "Alanic names are attested-only here; no safe combinatorial lexicon is used.",
}


def combine_entries(
    lexicon: Iterable[dict[str, str]],
    culture: str,
    count: int = 5,
    seed: int | None = None,
) -> list[dict[str, str]]:
    if culture in UNSAFE_COMBINE_CULTURES:
        raise ValueError(UNSAFE_COMBINE_CULTURES[culture])
    languages = COMBINE_LANGUAGES.get(culture)
    if not languages:
        raise ValueError(f"unsupported combine culture: {culture}")
    pool = [row for row in lexicon if row.get("language") in languages and row.get("element")]
    if len(pool) < 2:
        raise ValueError(f"not enough lexicon elements for culture: {culture}")
    rng = random.Random(seed)
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    attempts = 0
    while len(results) < count and attempts < count * 100:
        attempts += 1
        first, second = rng.sample(pool, 2)
        name = (first["element"].capitalize() + second["element"].lower()).strip()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        results.append(
            {
                "name": name,
                "culture": culture,
                "meaning": f"{first.get('meaning', '?')} + {second.get('meaning', '?')}",
                "elements": f"{first['element']}+{second['element']}",
                "status": "constructed",
                "confidence": "low",
                "note": "Constructed from historical lexicon elements; not an attested personal name.",
            }
        )
    return results


def brand_suggestions(entry: NameEntry) -> list[str]:
    name = ascii_fold(entry.name).upper()
    return [
        f"I1•{name.title()}",
        f"{name.title()}•Studio",
        f"{name.title()}•History",
    ]


def color_confidence(c: Color, conf: str) -> str:
    if conf == "high":
        return c.green(conf)
    if conf == "medium":
        return c.yellow(conf)
    if conf in ("low", "uncertain"):
        return c.red(conf)
    return conf


def color_status(c: Color, status: str) -> str:
    if status == "attested":
        return c.green(status)
    if status == "constructed":
        return c.yellow(status)
    return status


def format_entry(entry: NameEntry, brand: str | None = None, include_leet: bool = True, use_color: bool | None = None) -> str:
    c = COLOR if use_color is None else Color(use_color)
    lines = []
    lines.append(f"{c.blue('Name:')}        {c.bold(entry.name)}")
    lines.append(f"{c.dim('ASCII:')}       {ascii_fold(entry.name)}")
    if include_leet:
        lines.append(f"{c.dim('Leet:')}        {c.cyan(leetspeak(entry.name))}")
    lines.append(f"{c.dim('Culture:')}     {c.cyan(entry.culture)} / {entry.subculture}")
    lines.append(f"{c.dim('Gender:')}      {entry.gender}")
    lines.append(f"{c.dim('Type:')}        {entry.name_type}")
    lines.append(f"{c.dim('Meaning:')}     {entry.meaning or 'not recorded'}")
    lines.append(f"{c.dim('Elements:')}    {entry.elements or 'not recorded'}")
    lines.append(f"{c.dim('Variants:')}    {entry.variants or 'none recorded'}")
    lines.append(f"{c.dim('Status:')}      {color_status(c, entry.status)}")
    lines.append(f"{c.dim('Confidence:')}  {color_confidence(c, entry.confidence)}")
    lines.append(f"{c.dim('Gothic-like:')} {'yes' if entry.gothic_like else 'no'}")
    lines.append(f"{c.dim('Source:')}      {c.dim(entry.display_source())}")
    if entry.notes:
        lines.append(f"{c.dim('Notes:')}       {entry.notes}")
    if brand:
        lines.append(f"{c.dim('Brand:')}       {brand}")
    lines.append(c.yellow("Check domain and trademark availability before use."))
    return "\n".join(lines)


def format_offer(entry: NameEntry, brand: str | None = None) -> str:
    lines = [format_entry(entry, brand=brand)]
    lines.append("")
    lines.append(COLOR.bold("Brand directions:"))
    for item in brand_suggestions(entry):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(COLOR.bold("Leet handles (check availability):"))
    lines.append(f"- @{leetspeak(entry.name).lower()}")
    lines.append(f"- @{ascii_fold(entry.name).lower()}")
    return "\n".join(lines)


def find_entry(entries: Iterable[NameEntry], query: str) -> NameEntry:
    needle = query.strip().lower()
    for entry in entries:
        if needle in {entry.id.lower(), entry.name.lower(), ascii_fold(entry.name).lower()}:
            return entry
    raise KeyError(f"name not found: {query}")


def entry_to_json(entry: NameEntry) -> str:
    payload = asdict(entry)
    payload["source"] = entry.source
    payload["leet"] = leetspeak(entry.name)
    payload["ascii_fold"] = ascii_fold(entry.name)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def cmd_stats(entries: list[NameEntry], use_json: bool = False):
    from collections import Counter
    cultures = Counter(e.culture for e in entries)
    genders = Counter(e.gender for e in entries)
    statuses = Counter(e.status for e in entries)
    confs = Counter(e.confidence for e in entries)
    sources = Counter(e.source_id for e in entries)
    data = {
        "total": len(entries),
        "cultures": dict(sorted(cultures.items())),
        "genders": dict(sorted(genders.items())),
        "statuses": dict(sorted(statuses.items())),
        "confidence": dict(sorted(confs.items())),
        "sources": dict(sorted(sources.items())),
    }
    if use_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(COLOR.bold("Name Generator - Stats"))
    print(f"Total names: {len(entries)}")
    if len(entries) < 100:
        print(COLOR.yellow("Warning: corpus has fewer than 100 names"))
    print("\nCultures:")
    for k, v in sorted(cultures.items()):
        print(f"  {k}: {v}")
    print("\nGenders:")
    for k, v in sorted(genders.items()):
        print(f"  {k}: {v}")
    print("\nStatus / Confidence:")
    print(f"  attested: {statuses.get('attested', 0)}, constructed: {statuses.get('constructed', 0)}")
    print(f"  high: {confs.get('high', 0)}, medium: {confs.get('medium', 0)}, low: {confs.get('low', 0)}, uncertain: {confs.get('uncertain', 0)}")
    print("\nSources:")
    for k, v in sorted(sources.items()):
        print(f"  {k}: {v}")


def cmd_validate(entries: list[NameEntry], lexicon: list[dict[str, str]], sources: dict[str, dict], use_json: bool = False, bynames: list[dict[str, str]] | None = None):
    errors = []
    warnings = []
    required_names = ['id','name','ascii','gender','name_type','culture','subculture','origin','era','source_id','source_locator','meaning','elements','variants','status','confidence','gothic_like','notes']
    for e in entries:
        if not e.id: errors.append("empty id")
        if not e.name: errors.append(f"{e.id}: empty name")
        if not e.ascii: errors.append(f"{e.id}: empty ascii")
        if e.gender not in ('m','f','n/a'): errors.append(f"{e.id}: invalid gender {e.gender}")
        if e.name_type not in ('person','place'): errors.append(f"{e.id}: invalid name_type {e.name_type}")
        if e.status not in ('attested','constructed'): errors.append(f"{e.id}: invalid status {e.status}")
        if e.confidence not in ('high','medium','low','uncertain'): errors.append(f"{e.id}: invalid confidence {e.confidence}")
        if e.gothic_like not in (True, False): errors.append(f"{e.id}: invalid gothic_like")
        if e.source_id and e.source_id not in sources: errors.append(f"{e.id}: unknown source_id {e.source_id}")
        if e.culture and e.culture not in KNOWN_CULTURES: warnings.append(f"{e.id}: unknown culture {e.culture}")
        expected = ascii_fold(e.name)
        if e.ascii != expected and e.ascii != e.name:  # be lenient but check
            pass
        if not e.meaning: warnings.append(f"{e.id}: missing meaning")
    ids = [e.id for e in entries]
    if len(ids) != len(set(ids)): errors.append("duplicate ids")
    names_low = [e.name.lower() for e in entries]
    if len(names_low) != len(set(names_low)): errors.append("duplicate names")
    # lexicon
    for row in lexicon:
        if not row.get('element'): errors.append("lexicon: empty element")
        if row.get('language') not in ('gothic','anglo_saxon','norse','slavic','alan_sarmatian'): warnings.append(f"lexicon: unusual language {row.get('language')}")
    # bynames
    if bynames is None:
        bynames = load_bynames()
    by_ids = []
    for row in bynames:
        bid = (row.get('id') or row.get('byname') or '').strip().lower().replace(' ', '_')
        byname = (row.get('byname') or '').strip()
        if not byname: errors.append("bynames: empty byname")
        if not row.get('id'): warnings.append(f"bynames: missing id for {byname or '?'}")
        if not row.get('culture'): errors.append(f"bynames: missing culture for {byname or '?'}")
        if row.get('culture') and row.get('culture') not in KNOWN_CULTURES: warnings.append(f"bynames: unknown culture {row.get('culture')} for {byname or '?'}")
        if not row.get('source_id'): errors.append(f"bynames: missing source_id for {byname or '?'}")
        if row.get('source_id') and sources and row.get('source_id') not in sources: errors.append(f"bynames: unknown source_id {row.get('source_id')} for {byname or '?'}")
        if row.get('status') and row.get('status') not in ('attested','constructed'): errors.append(f"bynames: invalid status for {byname or '?'}")
        if row.get('confidence') and row.get('confidence') not in ('high','medium','low','uncertain'): errors.append(f"bynames: invalid confidence for {byname or '?'}")
        if row.get('type') and row.get('type') not in KNOWN_BYNAME_TYPES: warnings.append(f"bynames: unusual type {row.get('type')} for {byname or '?'}")
        if bid: by_ids.append(bid)
    if by_ids and len(by_ids) != len(set(by_ids)): errors.append("bynames: duplicate ids")
    by_vals = [(r.get('byname') or '').strip().lower() for r in bynames if (r.get('byname') or '').strip()]
    if by_vals and len(by_vals) != len(set(by_vals)): errors.append("bynames: duplicate bynames")
    data = {"errors": errors, "warnings": warnings, "ok": len(errors) == 0}
    if use_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(COLOR.bold("Name Generator - Validate"))
        if errors:
            print(COLOR.red(f"ERRORS: {len(errors)}"))
            for e in errors: print(f"  - {e}")
        if warnings:
            print(COLOR.yellow(f"WARNINGS: {len(warnings)}"))
            for w in warnings: print(f"  - {w}")
        if not errors:
            print(COLOR.green("OK - no errors found"))
    if errors:
        raise SystemExit(2)
    return 0



def menu_loop(entries: list[NameEntry], lexicon: list[dict[str, str]]):
    if not sys.stdout.isatty():
        print("Interactive menu requires a TTY. Use commands like 'daily', 'generate', etc.")
        raise SystemExit(0)
    global COLOR
    banner = r"""
  ____       _   _      ____           
 / ___| ___ | |_| |__  / ___| ___ _ __ 
| |  _ / _ \| __| '_ \| |  _ / _ \ '_ \
| |_| | (_) | |_| | | | |_| |  __/ | | |
 \____|\___/ \__|_| |_|\____|\___|_| |_|
"""
    print(COLOR.blue(banner))
    print(COLOR.bold("  GOTHGEN"))
    print(COLOR.dim(f"  {len(entries)} nicknames | default: gothic+norse/geat, gender m"))
    print(COLOR.dim("  (other cultures optional via --culture)"))
    print()
    opts = [
        ("1", "Daily pick", "One deterministic nickname for today (--top 1 default)"),
        ("2", "Generate", "Random filtered list from attested nicknames"),
        ("3", "Combine", "Construct a nickname from lexicon elements"),
        ("4", "Bynames", "Random byname/epithet (Gothic style)"),
        ("5", "Name+Byname", "Combine a nickname with a byname"),
        ("6", "Leet", "ASCII and leetspeak variants"),
        ("7", "Offer", "Full card with brand directions and handles"),
        ("8", "Explain", "Provenance and source record"),
        ("9", "Stats", "Corpus counts"),
        ("10", "Validate", "Check data integrity"),
        ("11", "Manual", "Open the man page"),
        ("0", "Exit", "Exit menu"),
    ]
    for k, name, desc in opts:
        print(f"  {COLOR.cyan(k)}) {COLOR.bold(name)}   {COLOR.dim(desc)}")
    print()
    while True:
        try:
            choice = input(COLOR.cyan("Select> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if choice == "0":
            break
        elif choice == "1":
            try:
                day = input("Date (YYYY-MM-DD, empty=today): ").strip() or None
                print(COLOR.bold("Daily pick - choose group"))
                cultures = [
                    ("1", "gothic", "gothic + norse + geat (default)"),
                    ("2", "norse", "norse only"),
                    ("3", "geat", "geat only"),
                    ("4", "anglo_saxon", "anglo-saxon"),
                    ("5", "varangian_rus", "varangian rus"),
                    ("6", "scythian", "scythian (attested-only)"),
                    ("7", "alan_sarmatian", "alan/sarmatian (attested-only)"),
                ]
                for k, c, d in cultures:
                    print(f"  {COLOR.cyan(k)}) {COLOR.bold(c)}   {COLOR.dim(d)}")
                ch = input(f"{COLOR.cyan('>')} ").strip()
                cmap = {"1": DEFAULT_CULTURE, "2": "norse", "3": "geat", "4": "anglo_saxon", "5": "varangian_rus", "6": "scythian", "7": "alan_sarmatian"}
                cult = cmap.get(ch, DEFAULT_CULTURE)
                top_s = input("Top (empty=1): ").strip() or "1"
                top = int(top_s)
                for idx, entry in enumerate(daily_entries(entries, day, cult, top), 1):
                    if top > 1: print(f"=== {idx} ===")
                    print(format_entry(entry))
                    print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "2":
            try:
                print(COLOR.bold("Generate - choose group"))
                cultures = [
                    ("1", "gothic", "gothic + norse + geat (default)"),
                    ("2", "norse", "norse only"),
                    ("3", "geat", "geat only"),
                    ("4", "anglo_saxon", "anglo-saxon"),
                    ("5", "varangian_rus", "varangian rus"),
                    ("6", "scythian", "scythian (attested-only)"),
                    ("7", "alan_sarmatian", "alan/sarmatian (attested-only)"),
                ]
                for k, c, d in cultures:
                    print(f"  {COLOR.cyan(k)}) {COLOR.bold(c)}   {COLOR.dim(d)}")
                ch = input(f"{COLOR.cyan('>')} ").strip()
                cmap = {"1": DEFAULT_CULTURE, "2": "norse", "3": "geat", "4": "anglo_saxon", "5": "varangian_rus", "6": "scythian", "7": "alan_sarmatian"}
                cult = cmap.get(ch, DEFAULT_CULTURE)
                try:
                    cnt = int(input("Count (default 5): ").strip() or "5")
                except Exception:
                    cnt = 5
                seed_s = input("Seed (empty=random): ").strip()
                seed = int(seed_s) if seed_s else None
                gender = input("Gender (m/f/n/a/empty=all): ").strip() or None
                for idx, entry in enumerate(generate_entries(entries, cult, gender, cnt, seed), 1):
                    print(f"=== {idx} ===")
                    print(format_entry(entry))
                    print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "3":
            try:
                cult = input("Culture (gothic/geat/anglo_saxon/norse/varangian_rus): ").strip()
                cnt = int(input("Count (default 5): ").strip() or "5")
                seed_s = input("Seed (empty=random): ").strip()
                seed = int(seed_s) if seed_s else None
                lex = load_lexicon()
                res = combine_entries(lex, cult, cnt, seed)
                for idx, item in enumerate(res, 1):
                    print(f"=== {idx} ===")
                    print(f"{COLOR.bold('Name:')}        {COLOR.bold(item['name'])}")
                    print(f"{COLOR.dim('Culture:')}     {COLOR.cyan(item['culture'])}")
                    print(f"{COLOR.dim('Meaning:')}     {item['meaning']}")
                    print(f"{COLOR.dim('Elements:')}    {item['elements']}")
                    print(f"{COLOR.dim('Status:')}      {COLOR.yellow(item['status'])}")
                    print(f"{COLOR.dim('Confidence:')}  {COLOR.red(item['confidence'])}")
                    print(f"{COLOR.dim('Note:')}        {item['note']}")
                    print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "4":
            try:
                cult = input("Culture (gothic/empty): ").strip() or "gothic"
                cnt = int(input("Count (default 5): ").strip() or "5")
                seed_s = input("Seed (empty=random): ").strip()
                seed = int(seed_s) if seed_s else None
                byns = load_bynames()
                res = generate_bynames(byns, culture=cult, count=cnt, seed=seed)
                for idx, item in enumerate(res, 1):
                    print(f"=== {idx} ===")
                    print(f"{COLOR.bold('Byname:')}     {COLOR.bold(item['byname'])}")
                    print(f"{COLOR.dim('Culture:')}     {COLOR.cyan(item.get('culture',''))}")
                    print(f"{COLOR.dim('Meaning:')}     {item.get('meaning','')}")
                    print(f"{COLOR.dim('Type:')}        {item.get('type','')}")
                    print(f"{COLOR.dim('Status:')}      {COLOR.green(item.get('status',''))}")
                    print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "5":
            try:
                name_q = input("Name: ").strip()
                entry = find_entry(entries, name_q)
                cult = input("Byname culture (gothic/empty): ").strip() or entry.culture
                byns = load_bynames()
                pool = filter_bynames(byns, culture=cult)
                if not pool:
                    print(COLOR.red("error: no bynames match"))
                else:
                    import random as _r
                    seed_s = input("Seed (empty=random): ").strip()
                    rng = _r.Random(int(seed_s) if seed_s else None)
                    b = rng.choice(pool)
                    print(f"{COLOR.bold('Combined:')}   {COLOR.bold(combine_name_with_byname(entry, b))}")
                    print(f"{COLOR.dim('Byname:')}      {b['byname']} ({b.get('meaning','')})")
                    print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "6":
            try:
                name = input("Name: ").strip()
                print(f"ASCII: {ascii_fold(name).upper()}")
                print(f"{COLOR.cyan('Leet:')}  {leetspeak(name)}")
                print(f"Lower: {leetspeak(name).lower()}")
                print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "7":
            try:
                name = input("Name: ").strip()
                entry = find_entry(entries, name)
                brand = input("Brand (empty=none): ").strip() or None
                print(format_offer(entry, brand=brand))
                print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "6":
            try:
                name = input("Name: ").strip()
                entry = find_entry(entries, name)
                print(entry_to_json(entry))
                print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "7":
            try:
                cmd_stats(entries, use_json=False)
                print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        elif choice == "8":
            try:
                sources_dict = {row["source_id"]: row for row in read_csv(DEFAULT_SOURCES) if row.get("source_id")}
                cmd_validate(entries, load_lexicon(), sources_dict, use_json=False, bynames=load_bynames())
                print()
            except SystemExit as se:
                if se.code != 2: raise
                print()
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
                print()
        elif choice == "11":
            try:
                man_path = BASE_DIR / "man" / "namegen.1"
                if man_path.exists():
                    os.system(f"man {man_path}")
                else:
                    print(COLOR.yellow("man/namegen.1 not found"))
            except Exception as e:
                print(COLOR.red(f"error: {e}"))
        else:
            print(COLOR.red("Invalid choice"))
        input(COLOR.dim("Press Enter to continue..."))
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="namegen", description=__doc__)
    parser.add_argument("--names", type=Path, default=DEFAULT_NAMES, help="names CSV")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="sources CSV")
    parser.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON, help="lexicon CSV")
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto", help="color output")
    sub = parser.add_subparsers(dest="command")

    daily = sub.add_parser("daily", help="deterministic picks for a date")
    daily.add_argument("--date", help="ISO date, default today")
    daily.add_argument("--culture", help="gothic|norse|geat|anglo_saxon|varangian_rus|scythian|alan_sarmatian (default: gothic; gothic includes norse/geat)")
    daily.add_argument("--top", type=int, default=1)
    daily.add_argument("--json", action="store_true")

    gen = sub.add_parser("generate", help="sample attested names")
    gen.add_argument("--culture", help="gothic|norse|geat|anglo_saxon|varangian_rus|scythian|alan_sarmatian (default: gothic; gothic includes norse/geat)")
    gen.add_argument("--gender", choices=["m", "f", "n/a"], help="default: m")
    gen.add_argument("--count", type=int, default=5)
    gen.add_argument("--seed", type=int)
    gen.add_argument("--include-places", action="store_true")
    gen.add_argument("--json", action="store_true")

    comb = sub.add_parser("combine", help="construct names from lexicon elements")
    comb.add_argument("--culture", default="gothic", help="default: gothic")
    comb.add_argument("--count", type=int, default=5)
    comb.add_argument("--seed", type=int)
    comb.add_argument("--json", action="store_true")

    leet = sub.add_parser("leet", help="show leetspeak variants")
    leet.add_argument("name")

    offer = sub.add_parser("offer", help="full name card with brand directions")
    offer.add_argument("name")
    offer.add_argument("--brand")
    offer.add_argument("--json", action="store_true")

    explain = sub.add_parser("explain", help="show full record and source")
    explain.add_argument("name")
    explain.add_argument("--json", action="store_true")

    stats = sub.add_parser("stats", help="corpus counts")
    stats.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate", help="data integrity check")
    validate.add_argument("--json", action="store_true")

    bynames = sub.add_parser("bynames", help="generate bynames/epithets")
    bynames.add_argument("--culture", default="gothic")
    bynames.add_argument("--count", type=int, default=5)
    bynames.add_argument("--seed", type=int)
    bynames.add_argument("--json", action="store_true")

    combine_b = sub.add_parser("combine-with", help="combine name with byname")
    combine_b.add_argument("name")
    combine_b.add_argument("--byname")
    combine_b.add_argument("--culture", default="gothic")
    combine_b.add_argument("--seed", type=int)
    combine_b.add_argument("--json", action="store_true")

    menu = sub.add_parser("menu", help="interactive menu")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    global COLOR
    use_color = should_use_color(args.color)
    # Don't use color for JSON output
    COLOR = Color(use_color)
    # For CLI tests expecting clean output, avoid auto-validating here
    # (keep validate command explicit)
    try:
        entries = load_names(args.names, args.sources)
        if args.command is None:
            # interactive menu if tty, else help
            if sys.stdout.isatty():
                menu_loop(entries, load_lexicon(args.lexicon))
                return 0
            else:
                parser.print_help()
                return 0
        if args.command == "menu":
            menu_loop(entries, load_lexicon(args.lexicon))
            return 0
        if args.command == "daily":
            if args.top < 1:
                raise ValueError("--top must be at least 1")
            culture = args.culture if args.culture is not None else DEFAULT_CULTURE
            picks = daily_entries(entries, args.date, culture, args.top)
            for index, entry in enumerate(picks, 1):
                if args.top > 1:
                    print(f"=== {index} ===")
                print(format_entry(entry))
                print()
            return 0
        if args.command == "generate":
            if (not sys.stdout.isatty() or args.culture is not None or args.gender is not None) and not args.json:
                # if called non-interactively or with flags keep old behavior
                pass
            if sys.stdout.isatty() and args.culture is None and args.gender is None and not args.json and args.seed is None and args.count == 5 and not args.include_places:
                print(COLOR.bold("Generate - choose group"))
                cultures = [
                    ("1", "gothic", "gothic + norse + geat (default)"),
                    ("2", "norse", "norse only"),
                    ("3", "geat", "geat only"),
                    ("4", "anglo_saxon", "anglo-saxon"),
                    ("5", "varangian_rus", "varangian rus"),
                    ("6", "scythian", "scythian (attested-only)"),
                    ("7", "alan_sarmatian", "alan/sarmatian (attested-only)"),
                    ("0", "cancel", "cancel"),
                ]
                for k, c, d in cultures:
                    print(f"  {COLOR.cyan(k)}) {COLOR.bold(c)}   {COLOR.dim(d)}")
                ch = input(f"\n{COLOR.cyan('>')} ").strip()
                cmap = {"1": DEFAULT_CULTURE, "2": "norse", "3": "geat", "4": "anglo_saxon", "5": "varangian_rus", "6": "scythian", "7": "alan_sarmatian"}
                if ch == "0" or ch not in cmap:
                    return 0
                culture = cmap[ch]
                gender = "m"
                try:
                    cstr = input(f"{COLOR.dim('Count')} [5]: ").strip()
                    count = int(cstr) if cstr else 5
                except Exception:
                    count = 5
                try:
                    sstr = input(f"{COLOR.dim('Seed')} (empty=random): ").strip()
                    seed = int(sstr) if sstr else None
                except Exception:
                    seed = None
                picked = generate_entries(entries, culture=culture, gender=gender, count=count, seed=seed, include_places=False)
                for index, entry in enumerate(picked, 1):
                    print(f"=== {index} ===")
                    print(format_entry(entry))
                    print()
                return 0
            culture = args.culture if args.culture is not None else DEFAULT_CULTURE
            gender = args.gender if args.gender is not None else "m"
            picked = generate_entries(
                entries,
                culture=culture,
                gender=gender,
                count=args.count,
                seed=args.seed,
                include_places=args.include_places,
)

            if args.json:
                COLOR = Color(False)
                print(json.dumps([json.loads(entry_to_json(entry)) for entry in picked], ensure_ascii=False, indent=2))
            else:
                for index, entry in enumerate(picked, 1):
                    print(f"=== {index} ===")
                    print(format_entry(entry))
                    print()
            return 0
        if args.command == "combine":
            lexicon = load_lexicon(args.lexicon)
            results = combine_entries(lexicon, args.culture, args.count, args.seed)
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                for index, item in enumerate(results, 1):
                    print(f"=== {index} ===")
                    print(f"{COLOR.bold('Name:')}        {COLOR.bold(item['name'])}")
                    print(f"{COLOR.dim('Culture:')}     {COLOR.cyan(item['culture'])}")
                    print(f"{COLOR.dim('Meaning:')}     {item['meaning']}")
                    print(f"{COLOR.dim('Elements:')}    {item['elements']}")
                    print(f"{COLOR.dim('Status:')}      {COLOR.yellow(item['status'])}")
                    print(f"{COLOR.dim('Confidence:')}  {COLOR.red(item['confidence'])}")
                    print(f"{COLOR.dim('Note:')}        {item['note']}")
                    print()
            return 0
        if args.command == "leet":
            name = args.name
            print(f"ASCII: {ascii_fold(name).upper()}")
            print(f"{COLOR.cyan('Leet:')}  {leetspeak(name)}")
            print(f"Lower: {leetspeak(name).lower()}")
            return 0
        if args.command == "stats":
            cmd_stats(entries, use_json=args.json)
            return 0
        if args.command == "validate":
            sources_dict = {row["source_id"]: row for row in read_csv(args.sources) if row.get("source_id")}
            cmd_validate(entries, load_lexicon(args.lexicon), sources_dict, use_json=args.json, bynames=load_bynames())
            return 0
        if args.command == "bynames":
            byns = load_bynames()
            res = generate_bynames(byns, culture=args.culture, count=args.count, seed=args.seed)
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                for index, item in enumerate(res, 1):
                    print(f"=== {index} ===")
                    print(f"{COLOR.bold('Byname:')}     {COLOR.bold(item['byname'])}")
                    print(f"{COLOR.dim('Culture:')}     {COLOR.cyan(item.get('culture',''))}")
                    print(f"{COLOR.dim('Meaning:')}     {item.get('meaning','')}")
                    print(f"{COLOR.dim('Type:')}        {item.get('type','')}")
                    print(f"{COLOR.dim('Status:')}      {COLOR.green(item.get('status',''))}")
                    print()
            return 0
        if args.command == "combine-with":
            entry = find_entry(entries, args.name)
            byns = load_bynames()
            if args.byname:
                # find byname
                b = None
                for x in byns:
                    if x.get('byname','').lower() == args.byname.lower():
                        b = x
                        break
                if not b:
                    raise ValueError(f"byname not found: {args.byname}")
            else:
                pool = filter_bynames(byns, culture=args.culture)
                if not pool:
                    raise ValueError("no bynames match")
                import random as _r
                rng = _r.Random(args.seed)
                b = rng.choice(pool)
            combined = combine_name_with_byname(entry, b)
            if args.json:
                print(json.dumps({"name": entry.name, "byname": b.get('byname'), "combined": combined}, ensure_ascii=False, indent=2))
            else:
                print(f"{COLOR.bold('Combined:')}   {COLOR.bold(combined)}")
                print(f"{COLOR.dim('Byname:')}      {b.get('byname')} ({b.get('meaning','')})")
            return 0
        if args.command in ("offer", "explain", "leet"):
            if args.command == "offer":
                entry = find_entry(entries, args.name)
                if args.json:
                    COLOR = Color(False)
                    print(entry_to_json(entry))
                else:
                    print(format_offer(entry, brand=args.brand))
                return 0
            if args.command == "explain":
                entry = find_entry(entries, args.name)
                if args.json:
                    COLOR = Color(False)
                    print(entry_to_json(entry))
                else:
                    print(format_entry(entry, include_leet=True))
                return 0
            if args.command == "leet":
                name = args.name
                print(f"ASCII: {ascii_fold(name).upper()}")
                print(f"{COLOR.cyan('Leet:')}  {leetspeak(name)}")
                print(f"Lower: {leetspeak(name).lower()}")
                return 0
        sources_dict = {row["source_id"]: row for row in read_csv(args.sources) if row.get("source_id")}
        if args.command == "validate":
            cmd_validate(entries, load_lexicon(args.lexicon), sources_dict, use_json=args.json, bynames=load_bynames())
            return 0
        if args.command == "stats":
            cmd_stats(entries, use_json=args.json)
            return 0
        if args.command == "bynames":
            byns = load_bynames()
            res = generate_bynames(byns, culture=args.culture, count=args.count, seed=args.seed)
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                for index, item in enumerate(res, 1):
                    print(f"=== {index} ===")
                    print(f"{COLOR.bold('Byname:')}     {COLOR.bold(item['byname'])}")
                    print(f"{COLOR.dim('Culture:')}     {COLOR.cyan(item.get('culture',''))}")
                    print(f"{COLOR.dim('Meaning:')}     {item.get('meaning','')}")
                    print(f"{COLOR.dim('Type:')}        {item.get('type','')}")
                    print(f"{COLOR.dim('Status:')}      {COLOR.green(item.get('status',''))}")
                    print()
            return 0
        if args.command == "combine-with":
            entry = find_entry(entries, args.name)
            byns = load_bynames()
            if args.byname:
                b = None
                for x in byns:
                    if x.get('byname','').lower() == args.byname.lower():
                        b = x
                        break
                if not b:
                    raise ValueError(f"byname not found: {args.byname}")
            else:
                pool = filter_bynames(byns, culture=args.culture)
                if not pool:
                    raise ValueError("no bynames match")
                import random as _r
                rng = _r.Random(args.seed)
                b = rng.choice(pool)
            combined = combine_name_with_byname(entry, b)
            if args.json:
                print(json.dumps({"name": entry.name, "byname": b.get('byname'), "combined": combined}, ensure_ascii=False, indent=2))
            else:
                print(f"{COLOR.bold('Combined:')}   {COLOR.bold(combined)}")
                print(f"{COLOR.dim('Byname:')}      {b.get('byname')} ({b.get('meaning','')})")
            return 0
        entry = find_entry(entries, args.name)
        if args.command == "offer":
            entry = find_entry(entries, args.name)
            byns = load_bynames()
            if args.byname:
                b = None
                for x in byns:
                    if x.get('byname','').lower() == args.byname.lower():
                        b = x
                        break
                if not b:
                    raise ValueError(f"byname not found: {args.byname}")
            else:
                pool = filter_bynames(byns, culture=args.culture)
                if not pool:
                    raise ValueError("no bynames match")
                import random as _r
                rng = _r.Random(args.seed)
                b = rng.choice(pool)
            combined = combine_name_with_byname(entry, b)
            if args.json:
                print(json.dumps({"name": entry.name, "byname": b.get('byname'), "combined": combined}, ensure_ascii=False, indent=2))
            else:
                print(f"{COLOR.bold('Combined:')}   {COLOR.bold(combined)}")
                print(f"{COLOR.dim('Byname:')}      {b.get('byname')} ({b.get('meaning','')})")
            return 0
        if args.command in ("offer", "explain", "leet"):
            if args.command == "offer":
                entry = find_entry(entries, args.name)
                if args.json:
                    COLOR = Color(False)
                    print(entry_to_json(entry))
                else:
                    print(format_offer(entry, brand=args.brand))
                return 0
            if args.command == "explain":
                entry = find_entry(entries, args.name)
                if args.json:
                    COLOR = Color(False)
                    print(entry_to_json(entry))
                else:
                    print(format_entry(entry, include_leet=True))
                return 0
            if args.command == "leet":
                name = args.name
                print(f"ASCII: {ascii_fold(name).upper()}")
                print(f"{COLOR.cyan('Leet:')}  {leetspeak(name)}")
                print(f"Lower: {leetspeak(name).lower()}")
                return 0
        # ... rest

    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(f"{COLOR.red('error:')} {exc}", file=sys.stderr)
        return 2
    except SystemExit:
        raise
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
