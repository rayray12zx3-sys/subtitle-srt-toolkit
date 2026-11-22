"""Optional official Qwen3-ForcedAligner CPU alignment, with fail-closed text matching.

This module never downloads model weights or calls a remote inference API;
caller must supply pre-downloaded official model files. Text mismatches,
nonmonotonic times or unsupported languages are rejected, allowing the
transcription pipeline to fall back automatically to original Whisper timings.
"""
from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

LANGUAGES={"zh":"Chinese","en":"English"}


def norm(text: str) -> str:
    return "".join(c.casefold() for c in text if c.isalnum())


def map_aligned_words(words, aligned, duration: float):
    """Preserve every original character/punctuation mark with model timestamps."""
    original="".join(w.word for w in words)
    if not original or not aligned or duration <= 0:
        raise ValueError("Empty transcript, alignment or audio")
    aligned_text="".join(str(item["text"]) for item in aligned)
    if norm(original)!=norm(aligned_text):
        raise ValueError("Forced-alignment text does not match ASR source exactly")
    pos=0;previous_end=0.;result=[]
    for item in aligned:
        marker=norm(str(item["text"]))
        if not marker:
            continue
        number=len(marker)
        piece=[]
        count=0
        while pos<len(original) and count<number:
            char=original[pos]
            pos+=1;piece.append(char)
            if char.isalnum():count+=len(char.casefold())
        if count!=number:
            raise ValueError("Invalid original-to-alignment token mapping")
        while pos<len(original) and not original[pos].isalnum():
            piece.append(original[pos])
            pos+=1
        start=float(item["start_time"]);end=float(item["end_time"])
        if (not math.isfinite(start) or not math.isfinite(end)
            or start < -.01 or end > duration+.25
            or end <= start or start < previous_end-.16):
            raise ValueError("Unreliable, impossible or unsorted forced alignment")
        start=max(0.,start,previous_end)
        end=min(duration,end)
        if end<=start:
            raise ValueError("Aligned token collapsed to nonpositive time")
        result.append(SimpleNamespace(word="".join(piece), start=start, end=end))
        previous_end=end
    if pos!=len(original) or "".join(item.word for item in result)!=original:
        raise ValueError("Forced alignment lost recognized text")
    return result



def alignment_boundary_shifts(original_words, aligned_words):
    """Absolute boundary movements against Whisper, NEVER reference accuracy.

    The aligned model may split Chinese words into characters, so compare
    timestamps after matching the unchanged original character positions.
    Reject missing/reordered text. Return only anonymous numeric seconds.
    """
    original = "".join(w.word for w in original_words)
    aligned = "".join(w.word for w in aligned_words)
    if not original or original != aligned:
        raise ValueError("Cannot compare timestamp boundaries with altered text")

    indexed = []
    offset = 0
    for item in aligned_words:
        end = offset + len(item.word)
        indexed.append((offset, end, item))
        offset = end

    offsets = 0
    differences = []
    for word in original_words:
        first, last = offsets, offsets + len(word.word)
        offsets = last
        # For Whisper's token, only actual letters/digits are speech units;
        # whitespace and punctuation can attach to either neighboring word.
        lexical = [i for i in range(first, last) if original[i].isalnum()]
        if not lexical:
            continue
        low, high = lexical[0], lexical[-1] + 1
        matching = [(a, b, item) for a, b, item in indexed
                    if any(original[j].isalnum()
                           for j in range(max(low, a), min(high, b)))]
        if not matching:
            raise ValueError("No aligned lexical token for original word")
        aligned_start = float(matching[0][2].start)
        aligned_end = float(matching[-1][2].end)
        original_start = float(word.start)
        original_end = float(word.end)
        if any(not math.isfinite(t) for t in
               (aligned_start, aligned_end, original_start, original_end)):
            raise ValueError("Nonfinite candidate boundary")
        differences.extend((abs(original_start - aligned_start),
                            abs(original_end - aligned_end)))
    if not differences:
        raise ValueError("No lexical boundary to compare")
    return differences



class QwenCPUAligner:
    def __init__(self, model_dir: Path):
        import torch
        from transformers import AutoProcessor, AutoModelForTokenClassification
        model_dir=Path(model_dir).resolve()
        if not (model_dir/"config.json").is_file():
            raise ValueError("Pre-downloaded Qwen alignment model is missing")
        torch.set_num_threads(min(4,torch.get_num_threads()))
        self.torch=torch
        self.processor=AutoProcessor.from_pretrained(str(model_dir),local_files_only=True)
        self.model=AutoModelForTokenClassification.from_pretrained(
            str(model_dir),dtype=torch.float32,local_files_only=True).to("cpu").eval()

    def align(self, audio: Path, words, language: str, duration: float):
        code=LANGUAGES.get(language)
        if code is None:
            raise ValueError("Qwen alignment only attempted for Chinese or English")
        transcript="".join(w.word for w in words)
        inputs,lists=self.processor.prepare_forced_aligner_inputs(
            audio=str(audio),transcript=transcript,language=code)
        inputs=inputs.to("cpu",self.torch.float32)
        with self.torch.inference_mode():
            output=self.model(**inputs)
        stamps=self.processor.decode_forced_alignment(
            logits=output.logits,input_ids=inputs["input_ids"],
            word_lists=lists,timestamp_token_id=self.model.config.timestamp_token_id,
        )[0]
        return map_aligned_words(words,stamps,duration)
