"""Apply private lesson spelling to words already present in timed SRT cues."""
from __future__ import annotations

import codecs
from collections import defaultdict
from pathlib import Path
import re

MAX_LESSON_BYTES = 1024 * 1024
_WORD = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9]*(?:['’][A-Za-z0-9]+)*(?![A-Za-z0-9_])")
_CUE_BREAK = re.compile(r"(\r?\n(?:[ \t]*\r?\n)+)")
_HAN_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


def han_pairs(text: str):
    for match in _HAN_RUN.finditer(text):
        han = match.group()
        yield from zip(han, han[1:])


def read_lesson(path: Path) -> str:
    with path.open("rb") as source:
        raw = source.read(MAX_LESSON_BYTES + 1)
    if len(raw) > MAX_LESSON_BYTES:
        raise ValueError("Lesson reference exceeds 1 MiB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("Lesson reference must be UTF-8 text") from None
    if not text.strip() or "\0" in text:
        raise ValueError("Lesson reference must contain nonempty text")
    return text


def apply_lesson_reference(raw_srt: bytes, lesson: str) -> tuple[bytes, dict]:
    """Keep every word and timestamp. Use case agreement and local context only."""
    choices = defaultdict(set)
    matches = list(_WORD.finditer(lesson))
    for word in matches:
        choices[word.group().lower()].add(word.group())
    # A normal Title-case word needs neighboring evidence. An acronym or
    # mixed-case name can be matched on its own when its reference case is unique.
    contextual_forms = set()
    for left, right in zip(matches, matches[1:]):
        if re.fullmatch(r"[ \t]+", lesson[left.end():right.start()]):
            contextual_forms.add((left.group().lower(), right.group().lower()))

    reference_pairs = set(han_pairs(lesson))
    stats = {"matched_english_words": 0, "matched_han_pairs": 0, "case_changes": 0}
    blocks = _CUE_BREAK.split(raw_srt.decode("utf-8-sig"))
    for index in range(0, len(blocks), 2):
        lines = blocks[index].splitlines(keepends=True)
        body = "".join(lines[2:])  # cue number and timing always stay untouched
        stats["matched_han_pairs"] += sum(pair in reference_pairs for pair in han_pairs(body))
        words = list(_WORD.finditer(body))
        parts = []
        end = 0
        for i, word in enumerate(words):
            original = word.group()
            key = original.lower()
            variants = choices.get(key)
            replacement = original
            if variants:
                stats["matched_english_words"] += 1
                if len(variants) == 1:
                    candidate = next(iter(variants))
                    before = words[i - 1] if i else None
                    after = words[i + 1] if i + 1 < len(words) else None
                    has_context = (
                        before is not None
                        and body[before.end():word.start()].isspace()
                        and (before.group().lower(), key) in contextual_forms
                    ) or (
                        after is not None
                        and body[word.end():after.start()].isspace()
                        and (key, after.group().lower()) in contextual_forms
                    )
                    if candidate[1:] != candidate[1:].lower() or (
                        len(candidate) >= 2 and candidate[0].isupper() and has_context
                    ):
                        replacement = candidate
            stats["case_changes"] += int(replacement != original)
            parts.extend((body[end:word.start()], replacement))
            end = word.end()
        blocks[index] = "".join(lines[:2]) + "".join(parts) + body[end:]
    if not stats["case_changes"]:
        return raw_srt, stats
    bom = codecs.BOM_UTF8 if raw_srt.startswith(codecs.BOM_UTF8) else b""
    return bom + "".join(blocks).encode("utf-8"), stats
