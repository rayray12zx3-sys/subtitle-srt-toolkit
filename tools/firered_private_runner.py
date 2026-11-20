"""GitHub-hosted FireRedASR2-AED private SRT benchmark, no hosted AI inference.
All user content stays RSA/AES-GCM encrypted outside the ephemeral runner.
"""
import argparse,base64,contextlib,io,math,os,re,subprocess,sys,tempfile,time,wave
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from huggingface_hub import snapshot_download
from tools.cloud_handshake import pack,unpack,fetch_public_drive_blob,INPUT_AAD,OUTPUT_AAD
from delivery_gate import validate_delivery

SOURCE_SHA="4e7d9aaf4482a47cec1724807026b9b151926eb5"
WEIGHT_SHA="2304afed56eacfee6256dee5937ed22ffa0b64ec"

def private_output_key(s):
    if s.startswith("rsa-n:"):
        v=s[6:]
        raw=base64.urlsafe_b64decode(v+"="*(-len(v)%4))
        if len(raw)!=256: raise ValueError("Invalid RSA modulus")
        return rsa.RSAPublicNumbers(65537,int.from_bytes(raw,"big")).public_key()
    return serialization.load_der_public_key(base64.b64decode(s,validate=True))

def timecode(seconds):
    v=round(max(0.,seconds)*1000)
    h,v=divmod(v,3600000);m,v=divmod(v,60000);s,ms=divmod(v,1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def normalize_words(words):
    out=""
    for item in words:
        word=re.sub(r"\s+"," ",str(item).replace("▁"," ").replace("<blank>","").replace("<sil>",""))
        if not word.strip():continue
        if out and out[-1].isascii() and out[-1].isalnum() and word[0].isascii() and word[0].isalnum():
            out+=" "
        out+=word
    return re.sub(r"\s+"," ",out).strip()

def split_audio(path,workdir):
    import numpy as np
    with wave.open(str(path),"rb") as f:
        assert (f.getnchannels(),f.getframerate(),f.getsampwidth())==(1,16000,2)
        samples=np.frombuffer(f.readframes(f.getnframes()),dtype="<i2")
    sr=16000;n=len(samples)
    cuts=[0]
    while n-cuts[-1] > 16*sr:
        target=cuts[-1]+13*sr
        lo=max(cuts[-1]+8*sr,target-2*sr)
        hi=min(n-6*sr,target+2*sr)
        if hi<=lo:break
        best=(float("inf"),target)
        for p in range(lo,hi,640):
            w=samples[max(0,p-1280):min(n,p+1280)]
            score=float(np.mean(w.astype("float32")**2))*(1+.04*abs(p-target)/sr)
            if score<best[0]:best=(score,p)
        cuts.append(best[1])
    cuts.append(n)
    out=[]
    for i,(a,b) in enumerate(zip(cuts,cuts[1:])):
        p=workdir/f"chunk_{i}.wav"
        with wave.open(str(p),"wb") as f:
            f.setnchannels(1);f.setframerate(sr);f.setsampwidth(2);f.writeframes(samples[a:b].tobytes())
        out.append((p,a/sr,(b-a)/sr))
    return out

def make_cues(sections,audio_seconds,convert):
    words=[]
    for offset,duration,rows in sections:
        for r in rows:
            if len(r)!=3:continue
            label,a,b=r
            label=str(label).strip()
            if not label:continue
            try:a=float(a);b=float(b)
            except (ValueError,TypeError):continue
            if not math.isfinite(a) or not math.isfinite(b):continue
            a=max(0.,min(duration,a));b=max(a,min(duration,b))
            if b-a<.001:b=min(duration,a+.001)
            if b<=a:continue
            words.append((offset+a,min(audio_seconds,offset+b),label))
    if not words:raise RuntimeError("No real timestamped tokens")
    groups=[];parts=[];first=last=None
    for a,b,label in words:
        if last is not None:a=max(a,last)
        b=max(b,a+.001)
        b=min(audio_seconds,b)
        if b<=a:continue
        if parts and (a-last>.6 or b-first>4.6 or len(normalize_words(parts+[label]))>26):
            text=convert(normalize_words(parts))
            if text.strip():groups.append((first,last,text))
            parts=[];first=last=None
        if first is None:first=a
        last=b;parts.append(label)
    if parts:
        text=convert(normalize_words(parts))
        if text.strip():groups.append((first,last,text))
    return groups

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--drive-id",required=True)
    parser.add_argument("--output-pub",required=True)
    parser.add_argument("--max-wait",type=int,default=1800)
    args=parser.parse_args()
    return_pub=private_output_key(args.output_pub)
    receiver=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    der=receiver.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    print("FIRERED_INPUT_PUBLIC_KEY_B64="+base64.b64encode(der).decode(),flush=True)
    print("WAITING_FOR_ENCRYPTED_INPUT",flush=True)
    data=None;start=time.monotonic()
    while time.monotonic()-start<args.max_wait:
        blob=fetch_public_drive_blob(args.drive_id)
        if blob:
            try:data=unpack(blob,receiver,INPUT_AAD)
            except Exception:pass
        if data:break
        time.sleep(10)
    if not data:raise SystemExit("BLOCKED: encrypted audio unavailable")
    with tempfile.TemporaryDirectory(prefix="firered_private_") as folder:
        root=Path(folder);orig=root/"source.opus";wav=root/"source.wav";out=root/"result.srt"
        orig.write_bytes(data);del data
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(orig),
                        "-ar","16000","-ac","1","-c:a","pcm_s16le",str(wav)],check=True)
        orig.unlink()
        chunks=split_audio(wav,root)
        print("FIRERED_CHUNKS="+str(len(chunks)),flush=True)
        src=root/"source_code"
        subprocess.run(["git","clone","--quiet","https://github.com/FireRedTeam/FireRedASR2S.git",str(src)],check=True)
        subprocess.run(["git","-C",str(src),"checkout","--detach","--quiet",SOURCE_SHA],check=True)
        t=time.monotonic()
        models=root/"models"
        snapshot_download(repo_id="FireRedTeam/FireRedASR2-AED",revision=WEIGHT_SHA,local_dir=str(models))
        download_s=time.monotonic()-t
        sys.path.insert(0,str(src))
        import torch
        from opencc import OpenCC
        from fireredasr2s.fireredasr2 import FireRedAsr2,FireRedAsr2Config
        torch.set_num_threads(4)
        config=FireRedAsr2Config(use_gpu=False,use_half=False,beam_size=3,nbest=1,return_timestamp=True)
        t=time.monotonic()
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            model=FireRedAsr2.from_pretrained("aed",str(models),config)
        load_s=time.monotonic()-t
        sections=[];t=time.monotonic()
        for i,(p,offset,duration) in enumerate(chunks):
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                response=model.transcribe([f"private_{i}"],[str(p)])
            if not response or not response[0].get("text") or not response[0].get("timestamp"):
                raise RuntimeError(f"Missing timed recognition in segment {i}")
            sections.append((offset,duration,response[0]["timestamp"]))
            p.unlink()
        asr_s=time.monotonic()-t
        cues=make_cues(sections,sum(x[2] for x in sections),OpenCC("s2t").convert)
        if not cues:raise RuntimeError("No SRT cues")
        with out.open("w",encoding="utf-8-sig",newline="\n") as fp:
            for i,(a,b,text) in enumerate(cues,1):
                if b<=a or not text.strip():raise RuntimeError("Invalid cue")
                fp.write(f"{i}\n{timecode(a)} --> {timecode(b)}\n{text}\n\n")
        validation=validate_delivery(wav,out)
        if validation["status"]!="OUTPUT_VALIDATED_NOT_YET_DELIVERED":
            raise SystemExit("BLOCKED: failed SRT validation")
        encrypted=pack(out.read_bytes(),return_pub,OUTPUT_AAD)
        print("FIRERED_OUTPUT_CIPHER_B64="+base64.b64encode(encrypted).decode(),flush=True)
        print(f"FIRERED_MODEL_DOWNLOAD_SECONDS={download_s:.2f}",flush=True)
        print(f"FIRERED_MODEL_LOAD_SECONDS={load_s:.2f}",flush=True)
        print(f"FIRERED_ASR_SECONDS={asr_s:.2f}",flush=True)
        print("FIRERED_VALIDATED_CUES="+str(validation["cues"]),flush=True)
        print("FIRERED_AUDIO_SECONDS="+str(validation["audio_seconds"]),flush=True)
        print("OUTPUT_VALIDATED_NOT_YET_DELIVERED",flush=True)

if __name__=="__main__":main()
