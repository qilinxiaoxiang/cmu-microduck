#!/usr/bin/env python3
"""MicroDuck: cut duck recordings into single calls for the random voice player (duck_voice.py).

Usage: build_duck_calls.py MALLARD.ogg VOICES_DIR OUT_DIR
  MALLARD.ogg  Wikimedia Commons "Anas platyrhynchos - Mallard - XC62258.ogg" (Jonathon Jongsma, CC BY-SA 3.0),
               or - for the simulator voices only (guide/firmware/a7z/install_teleop.sh does this when the file is absent)
  VOICES_DIR   microduck-simulator/app/public/assets/voices (Pollen Robotics; duck1..duck4/chirp_*.wav)
  OUT_DIR      gets mallard_N.wav and duckK_chirp_X.wav, 44.1 kHz mono 16 bit
Every call is high-passed twice at 500 Hz (the speaker's resonance is 560-840 Hz), raised 10 dB into a -1 dBFS
limiter and faded 5 ms at both ends. Needs ffmpeg and numpy (Mac side); copy OUT_DIR to the Pi.
"""
import glob
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

RATE = 44100
CHAIN = "highpass=f=500,highpass=f=500,volume=10dB,alimiter=limit=0.89:attack=1:release=50:level=disabled"


def ff(src, dst, af):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", str(RATE), "-af", af,
                    "-c:a", "pcm_s16le", dst], check=True)


def read(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32768


def write(path, x):
    fade = int(0.005 * RATE)
    x = x.copy()
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    x *= 10 ** (-1 / 20) / max(np.abs(x).max(), 1e-9)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def segments(x, thresh_db=-35, frame=0.01, min_len=0.08, pad=0.02):
    n = int(frame * RATE)
    e = np.array([np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, len(x) - n, n)])
    on = 20 * np.log10(e + 1e-9) > thresh_db
    out, start = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if (i - start) * frame >= min_len:
                out.append((max(0, int((start * frame - pad) * RATE)), min(len(x), int((i * frame + pad) * RATE))))
            start = None
    return out


def main():
    mallard, voices, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cuts = []
        if mallard != "-":
            raw = os.path.join(tmp, "m.wav")
            ff(mallard, raw, "anull")
            proc = os.path.join(tmp, "p.wav")
            ff(mallard, proc, CHAIN)
            cuts = segments(read(raw))
            y = read(proc)
            for k, (a, b) in enumerate(cuts, 1):
                write(os.path.join(out, f"mallard_{k}.wav"), y[a:b])
        count = len(cuts)
        for src in sorted(glob.glob(os.path.join(voices, "duck*", "chirp_*.wav"))):
            name = f"{os.path.basename(os.path.dirname(src))}_{os.path.basename(src)}"
            ff(src, os.path.join(tmp, "c.wav"), CHAIN)
            write(os.path.join(out, name), read(os.path.join(tmp, "c.wav")))
            count += 1
    print(f"{out}: {len(cuts)} mallard calls, {count} calls in total")


if __name__ == "__main__":
    main()
