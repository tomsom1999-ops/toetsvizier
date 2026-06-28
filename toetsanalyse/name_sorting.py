from __future__ import annotations


DUTCH_SURNAME_PREFIXES = {
    "'t",
    "aan",
    "bij",
    "de",
    "del",
    "den",
    "der",
    "di",
    "du",
    "het",
    "in",
    "la",
    "le",
    "onder",
    "op",
    "over",
    "te",
    "ten",
    "ter",
    "uit",
    "van",
    "ver",
    "von",
}


def sortable_last_name(last_name: str | None, display_name: str | None = None) -> str:
    """Return the part of a surname that should determine alphabetical order."""
    raw_name = str(last_name or "").strip()
    if not raw_name:
        display_parts = str(display_name or "").strip().split()
        raw_name = " ".join(display_parts[1:]) if len(display_parts) > 1 else " ".join(display_parts)
    parts = raw_name.split()
    while len(parts) > 1 and parts[0].strip(".").casefold() in DUTCH_SURNAME_PREFIXES:
        parts.pop(0)
    return " ".join(parts)


def student_sort_key(
    display_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> tuple[str, str, str]:
    surname = sortable_last_name(last_name, display_name).casefold()
    return (surname, str(first_name or "").casefold(), str(display_name or "").casefold())
