"""Zero-API, fully automatic punctuation-aware and prosodic SRT segmentation.

Uses ASR word timestamps plus *original* punctuation before punctuation removal.
Respects token boundaries: never invents Chinese character timestamps or splits
English words. Heuristic semantic cues are not a substitute for a language
understanding model, but permit automatic sensible phrase breaks on CPU.
"""
from __future__ import annotations

import math
import re
import unicodedata

try:
    import jieba
except ImportError:  # Code-only optional callers keep deterministic fallback.
    jieba = None

# Common Traditional-Chinese school/educational terms not reliably present
# in the default Simplified-oriented dictionary. This is not a transcript edit.
PROTECTED_TERMS = ("形容詞", "心情")

STRONG = "。！？!?;"
CLAUSE = "，,；：;:"
END_CONNECTOR = re.compile(
    r"(?:因為|但是|如果|所以|而且|或者|以及|不過|雖然|假如|為了|關於|由於|和|與|及|的|把|被|在|對|跟|了)$"
)
ENGLISH_INCOMPLETE_END = {
    "a", "an", "the", "and", "or", "but", "because", "if", "when",
    "while", "of", "to", "for", "with", "at", "in", "on", "from",
    "as", "that", "which", "who", "is", "are", "was", "were", "will"
}
NEXT_CLAUSE = re.compile(
    r"^(?:但是|不過|然而|因此|所以|接著|然後|首先|其次|最後|另外|此外|例如|總之|如果|假如|因為|But\b|However\b|Therefore\b|Then\b|Next\b|First\b|Finally\b|For example\b)",
    re.IGNORECASE
)
ENGLISH_BAD_START = {"of", "to", "with", "for", "from", "at", "in", "on", "and", "or"}
PUNCT = set("，。！？；：、,.!?;:…")


def visual_width(text: str) -> int:
    """Latin uses ~1 visual column, CJK wide characters ~2."""
    width = 0
    for ch in text:
        if ch in "\n\r":
            continue
        if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
    return width


def _text(words) -> str:
    pieces = []
    for item in words:
        chunk = item.word
        # Whisper word timestamps sometimes omit the leading space even
        # between separate English words; insert *display only* spacing.
        if (pieces and chunk and chunk[0].isascii() and chunk[0].isalpha()
                and not chunk[0].isspace()
                and re.search(r"[A-Za-z.!?]$", pieces[-1])):
            pieces.append(" ")
        pieces.append(chunk)
    result = re.sub(r"\s+", " ", "".join(pieces)).strip()
    # Also handle glued English punctuation within ONE source word token.
    return re.sub(r"(?<=[A-Za-z][.!?])(?=[A-Za-z])", " ", result)


def _protected_boundaries(words):
    """Indices where splitting would break a recognized Chinese lexical word.

    Use only existing Whisper word-token boundaries and original timestamps.
    Jieba's bundled local dictionary is offline and does not invent timing.
    """
    if len(words) < 2:
        return set()
    raw = "".join(w.word for w in words)
    protected = set()
    offsets = []
    index = 0
    for item in words[:-1]:
        index += len(item.word)
        offsets.append(index)
    if jieba is not None:
        # Build local lexicon once (jieba handles repeated add_word safely).
        for term in PROTECTED_TERMS:
            jieba.add_word(term)
        tokens = [(start, end) for _token, start, end in jieba.tokenize(raw, HMM=True)
                  if end - start > 1]
    else:
        tokens = []
    # Supplement known Traditional forms even when the external tokenizer is
    # unavailable; does not alter user text or invent Chinese per-character time.
    for term in PROTECTED_TERMS:
        start = 0
        while True:
            start = raw.find(term, start)
            if start < 0:
                break
            tokens.append((start, start + len(term)))
            start += len(term)
    for i, offset in enumerate(offsets, 1):
        left = words[i - 1].word.rstrip()
        right = words[i].word.lstrip()
        if not (left and right and "\u4e00" <= left[-1] <= "\u9fff"
                and "\u4e00" <= right[0] <= "\u9fff"):
            continue
        if any(start < offset < end for start, end in tokens):
            protected.add(i)
    return protected


def _ending(raw: str) -> str:
    return raw.rstrip().rstrip('”"\'）)」』').rstrip()


def _boundary_penalty(left, right, gap: float) -> float:
    """Lower score means a more natural place for a new subtitle."""
    raw = _ending(left.word)
    suffix = raw[-1:] if raw else ""
    right_text = right.word.strip()
    if suffix in STRONG:
        score = -5.5
    elif suffix in CLAUSE:
        score = -3.2
    elif gap >= .65:
        score = -3.5
    elif gap >= .35:
        score = -2.2
    elif gap >= .18:
        score = -1.0
    else:
        score = 1.3

    if NEXT_CLAUSE.match(right_text):
        score -= 1.8
    lower = re.sub(r"[^A-Za-z']", "", raw).lower()
    if lower in ENGLISH_INCOMPLETE_END or END_CONNECTOR.search(raw):
        score += 5
    first = re.match(r"[A-Za-z']+", right_text)
    if first and first.group().lower() in ENGLISH_BAD_START:
        score += 2
    if right_text.startswith(("的", "了", "嗎", "呢", "吧", "們")):
        score += 2
    return score



def reading_units(text: str) -> float:
    """Estimated reading load, not a linguistic proof or human reading rate.

    One Han character ~= 1 unit. An English word is 1.0..2.1 units
    (rather than counting its letters like Chinese glyphs). Numbers and
    spoken punctuation also count modestly; spaces do not.
    """
    parts = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:[.,]\d+)*|[^\W\d_]|[^\s]",text,re.UNICODE)
    load = 0.0
    for part in parts:
        if re.fullmatch(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",part):
            load += min(2.15, 0.85 + 0.18 * len(part))
        elif part[0].isdigit():
            load += min(2.1, 0.95 + 0.2 * len(part))
        elif part in PUNCT or unicodedata.category(part[0]).startswith("P"):
            load += 0.15
        elif not part.isspace():
            load += 1.0
    return load


def reading_rate(words) -> float:
    if not words:
        return 0.
    return reading_units(_text(words))/max(.25, words[-1].end-words[0].start)


def _rate_penalty(text: str, duration: float, target: float=5.7,
                  soft_limit: float=7.5) -> float:
    """Keep subtitles readable within the natural audio timing where possible."""
    rate = reading_units(text) / max(0.25, duration)
    return (max(0.0, rate-target)**2 * .30 +
            max(0.0, rate-soft_limit)**2 * 1.5)

def _boundaries(words, max_chars: int, max_seconds: float,
                max_gap: float, line_chars: int, max_lines: int):
    """Dynamic programming: globally choose minimal-cost ASR-token boundaries."""
    n = len(words)
    if not n:
        return []
    # Existing --max-chars is in approximate *Chinese-character* units.
    width_limit = min(2 * max_chars, 2 * line_chars * max_lines)
    protected = _protected_boundaries(words)
    dp = [math.inf] * (n + 1)
    nxt = [-1] * (n + 1)
    dp[n] = 0.
    max_tokens = 48
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, min(n, i + max_tokens) + 1):
            fragment = words[i:j]
            text = _text(fragment)
            dur = max(0., fragment[-1].end - fragment[0].start)
            size = visual_width(text)
            # If ASR returns an unbreakable long token, do not fabricate
            # per-character timestamps. Allow it alone with a layout warning.
            if j > i + 1 and (size > width_limit or dur > max_seconds):
                break
            if j > i + 1 and (fragment[-1].start - fragment[-2].end > max_gap * 2.5):
                break
            if j == i + 1 and not text:
                continue
            end_cost = 0. if j == n else _boundary_penalty(
                words[j - 1], words[j],
                max(0., words[j].start - words[j - 1].end),
            )
            # Respect dictionary-supported Chinese lexical continuity where
            # another boundary is available, without fabricating word timings.
            if j in protected:
                end_cost += 15.0
            # Penalize very short captions, especially without punctuation.
            short = max(0., 1.0 - dur) * 2.8
            too_wide = max(0., size - width_limit) * 1.5
            overflow = max(0., dur - max_seconds) * 8.
            # Favor durations around 2-3 seconds without overriding clauses.
            tempo = abs(dur - 2.5) * .35
            readability = _rate_penalty(text, dur)
            if j == n and dur < .8:
                short *= .4  # do not force unnatural last-line splitting
            cost = 2.2 + short + too_wide + overflow + tempo + readability + end_cost + dp[j]
            if cost < dp[i]:
                dp[i], nxt[i] = cost, j
    groups = []
    i = 0
    while i < n:
        j = nxt[i]
        if j <= i:
            raise ValueError("Could not construct semantic subtitle segments")
        groups.append(words[i:j])
        i = j
    return groups


def segment_words(words, max_chars=22, max_duration=4.0,
                  gap=.45, line_chars=12, max_lines=2):
    if max_chars < 1 or max_duration <= 0 or gap < 0:
        raise ValueError("Invalid segmentation limits")
    if line_chars < 1 or max_lines not in (1, 2):
        raise ValueError("Only 1 or 2 subtitle lines are supported")
    filtered = [word for word in words if word.word.strip()]
    return _boundaries(filtered, max_chars, max_duration, gap, line_chars, max_lines)


def break_lines(words, line_chars=12, max_lines=2):
    """Return original word pieces with optional line split; no token splitting."""
    if max_lines == 1 or len(words) < 2:
        return [_text(words)]
    full = _text(words)
    limit = line_chars * 2
    if visual_width(full) <= limit:
        return [full]
    choices = []
    protected = _protected_boundaries(words)
    for i in range(1, len(words)):
        left = _text(words[:i])
        right = _text(words[i:])
        left_width = visual_width(left)
        right_width = visual_width(right)
        if not left or not right:
            continue
        pause = max(0., words[i].start - words[i - 1].end)
        boundary = _boundary_penalty(words[i - 1], words[i], pause)
        over = (max(0, left_width - limit) + max(0, right_width - limit))
        balance = abs(left_width - right_width) / max(1, limit)
        choices.append((over * 10 + balance + boundary +
                        (15.0 if i in protected else 0.0), over, left, right))
    if not choices:
        return [full]  # do not invent intra-token timing
    score, overflow, left, right = min(choices, key=lambda x: x[0])
    if overflow and visual_width(full) <= limit:
        return [full]
    return [left, right]
