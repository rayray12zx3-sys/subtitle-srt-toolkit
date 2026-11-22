"""Pure, no-model parser for whitelisted private Runner alignment metrics."""
import re

def parse_alignment_metrics(output: str) -> dict:
    """Parse only numeric alignment diagnostics, including TWO keys on one line.

    The Whisper CLI combines attempted/succeeded values in a single status
    line. Do not print or persist its stdout: it includes a private temp path.
    """
    allowed={
        "ALIGNER_ATTEMPTED_CHUNKS":"attempted",
        "ALIGNER_SUCCEEDED_CHUNKS":"succeeded",
        "ALIGNER_FALLBACK_CHUNKS":"fallback",
        "ALIGNER_BOUNDARY_COMPARISON_SAMPLES":"samples",
        "ALIGNER_BOUNDARY_MEDIAN_ABS_SHIFT_SECONDS":"median",
        "ALIGNER_BOUNDARY_P95_ABS_SHIFT_SECONDS":"p95",
        "ALIGNER_BOUNDARY_MAX_ABS_SHIFT_SECONDS":"max",
    }
    stats={}
    for match in re.finditer(r"(?<![A-Z_])(ALIGNER_[A-Z_]+)=(\d+(?:\.\d+)?)", output):
        key=allowed.get(match.group(1))
        if key is None:
            continue
        if key in stats:
            raise RuntimeError("Duplicate alignment diagnostic")
        stats[key]=float(match.group(2))
    if any(k not in stats for k in
           ("attempted","succeeded","fallback","samples")):
        raise RuntimeError("Alignment diagnostic counters missing")
    if stats["attempted"] != stats["succeeded"] + stats["fallback"]:
        raise RuntimeError("Inconsistent alignment chunk counts")
    return stats
