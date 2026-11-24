"""Title-case helpers for procedure type names."""

from __future__ import annotations

# Short conjunctions / prepositions stay lowercase mid-phrase (Chicago-style),
# except "with" which we capitalize so names read like "Cystoscopy With Biopsy".
_SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to"}

DEFAULT_PROCEDURE_TYPE = "Diagnostic Cystoscopy"
CUSTOM_PROCEDURE_TYPE = "Other / Custom Procedure"

PREDEFINED_PROCEDURES = [
    "Prostate Biopsy",
    "Diagnostic Cystoscopy",
    "Transrectal Ultrasound",
    "SpaceOAR and Fiducial Marker Placement",
    CUSTOM_PROCEDURE_TYPE,
]


def title_case(text: str) -> str:
    """Title-case a procedure name, keeping mixed-case brands (e.g. SpaceOAR).

    ALL-CAPS words are folded to Title Case. Mid-phrase small words stay lowercase.
    """
    if not text:
        return text
    words = text.split()
    out: list[str] = []
    for i, word in enumerate(words):
        # Preserve intentional internal capitals (SpaceOAR), but not ALL CAPS.
        if any(c.isupper() for c in word[1:]) and not word.isupper():
            out.append(word)
        elif i > 0 and word.lower() in _SMALL_WORDS:
            out.append(word.lower())
        else:
            base = word.lower() if word.isupper() else word
            out.append(base[:1].upper() + base[1:])
    return " ".join(out)


def normalize_procedure_name(name: str | None, *, default: str | None = None) -> str:
    """Strip and Title-Case a procedure name; optional default when empty."""
    cleaned = (name or "").strip()
    if not cleaned:
        if default is None:
            return ""
        return default
    return title_case(cleaned)
