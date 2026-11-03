"""Make the upstream Wav2Lip repo run on current Python / torch / librosa / numpy. Idempotent.
Usage: python setup/patch_wav2lip.py tools/Wav2Lip"""
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "tools/Wav2Lip")

def sub(rel, pairs):
    p = root / rel
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8")

sub("audio.py", [("librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,",
                  "librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,")])
sub("face_detection/utils.py", [("dtype=np.int)", "dtype=int)")])
inf = root / "inference.py"
t = inf.read_text(encoding="utf-8")
shim = ("import torch as _torch\n_orig_load = _torch.load\n"
        "_torch.load = lambda *a, **k: _orig_load(*a, **{**k, 'weights_only': False})\n")
if "_orig_load" not in t:
    inf.write_text(shim + t, encoding="utf-8")
print("[patch] Wav2Lip patched")
