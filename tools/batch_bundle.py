"""Private multi-audio ZIP payload, only used INSIDE RSA/AES encrypted envelopes."""
import io,json,re,zipfile
MAGIC=b"SRTBATCH1\n"
MAX_CLIPS=8
MAX_INPUT_BYTES=64*1024*1024
MAX_OUTPUT_BYTES=16*1024*1024

def clip_id(i):
    if not 1<=i<=MAX_CLIPS: raise ValueError("Batch requires 1..8 clips")
    return f"clip_{i:04d}"

def is_batch_blob(data):
    return data.startswith(MAGIC)

def _name(clip,kind):
    return f"clips/{clip}.opus" if kind=="input" else f"subtitles/{clip}.srt"

def encode_bundle(kind,clips):
    if kind not in ("input","output") or not 1<=len(clips)<=MAX_CLIPS:
        raise ValueError("Invalid batch kind or size")
    limit = MAX_INPUT_BYTES if kind == "input" else MAX_OUTPUT_BYTES
    total = 0
    for i, (name, data) in enumerate(clips, 1):
        if name != clip_id(i) or not isinstance(data, bytes) or not data:
            raise ValueError("Nonsequential, invalid or empty clip")
        total += len(data)
        if total > limit:
            raise ValueError("Batch payload too large")
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_STORED) as z:
        for name, data in clips:
            z.writestr(_name(name,kind),data)
        z.writestr("manifest.json",json.dumps({"v":1,"kind":kind,
                   "ids":[name for name,_ in clips]},separators=(",",":")))
    data=MAGIC+buf.getvalue()
    if len(data) > limit:
        raise ValueError("Batch payload too large")
    return data

def decode_bundle(data,kind):
    if kind not in ("input","output") or not is_batch_blob(data):
        raise ValueError("Not an authenticated private bundle")
    limit=MAX_INPUT_BYTES if kind=="input" else MAX_OUTPUT_BYTES
    if len(data)>limit: raise ValueError("Batch too large")
    try:
        with zipfile.ZipFile(io.BytesIO(data[len(MAGIC):])) as z:
            entries=z.infolist()
            names=[x.filename for x in entries]
            if len(names)!=len(set(names)) or "manifest.json" not in names:
                raise ValueError("Duplicate names or missing manifest")
            if sum(entry.file_size for entry in entries) > limit:
                raise ValueError("Batch contents exceed size limit")
            if z.getinfo("manifest.json").file_size>2048:
                raise ValueError("Oversize manifest")
            meta=json.loads(z.read("manifest.json").decode())
            if not isinstance(meta, dict):
                raise ValueError("Invalid batch manifest")
            ids=meta.get("ids")
            if meta.get("v")!=1 or meta.get("kind")!=kind or not isinstance(ids,list):
                raise ValueError("Invalid batch metadata")
            if not 1<=len(ids)<=MAX_CLIPS or ids!=[clip_id(i) for i in range(1,len(ids)+1)]:
                raise ValueError("Invalid batch order")
            if set(names)!={"manifest.json"}|{_name(x,kind) for x in ids}:
                raise ValueError("Unexpected ZIP members")
            results = []
            for name in ids:
                p=_name(name,kind)
                payload=z.read(p)
                if not payload:
                    raise ValueError("Invalid payload content")
                results.append((name,payload))
            return results
    except (zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError, RuntimeError) as e:
        raise ValueError("Corrupt private bundle") from e
