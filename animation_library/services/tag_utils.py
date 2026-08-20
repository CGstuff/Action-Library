"""
Tag normalization.

THE PROBLEM
    Tags had no normalization anywhere. `Combat`, `combat`, `COMBAT` and
    `combat ` were four different tags: four entries in the filter dropdown, four
    separate filters, four rows from get_all_tags(). Meanwhile free-text SEARCH
    folds case - so the app told you they were the same thing when you searched,
    then treated them as different everywhere else. Nobody notices they've made a
    variant until the dropdown has three spellings of one word.

THE RULE: case-preserving, case-insensitive - like Windows filenames.
    `Combat` and `combat` ARE the same tag. Whichever spelling the library used
    first is the one that displays and gets stored, so `GameDev` stays `GameDev`
    rather than being flattened to `gamedev` - but typing `gamedev` later can't
    create a second one.

SCOPE: this is a GUARD, not a migration.
    It stops NEW variants being created. Tags already in a library are left
    exactly as they are - nothing is rewritten, so there's nothing to undo and no
    migration that can fail halfway. If a library already contains variants,
    canonical_spelling() simply picks the most-used one to steer new input at.
"""

import unicodedata
from typing import Dict, Iterable, List


def tag_key(tag: str) -> str:
    """The comparison key for a tag: what makes two spellings 'the same tag'.

    NFKC-normalized (so visually identical unicode compares equal), trimmed, and
    case-folded (casefold, not lower - it handles non-ASCII properly).
    """
    if not isinstance(tag, str):
        return ""
    return unicodedata.normalize("NFKC", tag).strip().casefold()


def clean_tag(tag: str) -> str:
    """The stored form: trimmed and unicode-normalized, ORIGINAL CASING KEPT."""
    if not isinstance(tag, str):
        return ""
    return unicodedata.normalize("NFKC", tag).strip()


def dedupe_tags(tags: Iterable[str]) -> List[str]:
    """Drop blanks and case-insensitive duplicates. First spelling wins, order kept."""
    seen = set()
    result = []
    for tag in tags or []:
        cleaned = clean_tag(tag)
        if not cleaned:
            continue
        key = tag_key(cleaned)
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def canonical_spelling(tags: Iterable[str]) -> Dict[str, str]:
    """Build {tag_key: the spelling to use} from the tags a library already has.

    Where a library already contains variants (this guard doesn't merge them),
    the most-used spelling wins, ties broken alphabetically so the result is
    stable rather than depending on row order.

    Args:
        tags: every tag occurrence in the library - repeats included, since the
              count is what decides.
    """
    counts: Dict[str, Dict[str, int]] = {}
    for tag in tags or []:
        cleaned = clean_tag(tag)
        if not cleaned:
            continue
        counts.setdefault(tag_key(cleaned), {}).setdefault(cleaned, 0)
        counts[tag_key(cleaned)][cleaned] += 1

    return {
        key: sorted(spellings.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        for key, spellings in counts.items()
    }


def apply_canonical(tags: Iterable[str], canonical: Dict[str, str]) -> List[str]:
    """Rewrite tags to the library's established spelling, then dedupe.

    A tag the library has never seen keeps exactly what the user typed (trimmed) -
    they're the one defining its spelling.
    """
    mapped = []
    for tag in tags or []:
        cleaned = clean_tag(tag)
        if not cleaned:
            continue
        mapped.append(canonical.get(tag_key(cleaned), cleaned))
    return dedupe_tags(mapped)


__all__ = [
    'tag_key',
    'clean_tag',
    'dedupe_tags',
    'canonical_spelling',
    'apply_canonical',
]
