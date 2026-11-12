#!/usr/bin/env python3
"""luma_trace.py - find brightness flashes and dark dips in a rendered film (a whip that cut through an object, a light that popped).

  python3 -I scripts/luma_trace.py plates.mp4 [--jump 18] [--range 0 190]

Prints every frame whose mean luma (0-255) differs from the previous frame by more than --jump, and the min / max over the range.
A one-frame spike or a short dark run inside a camera whip almost always means the camera path passes through geometry: reroute the
waypoints (arc over it) and re-render only that range. A step that stays (a change of scene) is not a flash. Needs ffmpeg on PATH.
"""
import argparse, subprocess, sys


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--jump", type=float, default=18.0)
    ap.add_argument("--range", type=int, nargs=2, metavar=("F0", "F1"))
    a = ap.parse_args()
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    v = [float(l.split("=")[1]) for l in out.splitlines() if "YAVG" in l]
    if not v: sys.exit("no frames read from " + a.video)
    f0, f1 = a.range if a.range else (0, len(v) - 1)
    f1 = min(f1, len(v) - 1)
    hits = [(i, v[i - 1], v[i]) for i in range(max(1, f0), f1 + 1) if abs(v[i] - v[i - 1]) > a.jump]
    for i, p, q in hits:
        back = i + 1 <= f1 and abs(v[i + 1] - p) < a.jump / 2                    # returns next frame: a one-frame flash or dip
        print("frame %5d  %3.0f -> %3.0f%s" % (i, p, q, "   ONE-FRAME (flash or dip)" if back else ""))
    print("%d frames, luma min %.0f max %.0f, %d jump(s) over %.0f" % (f1 - f0 + 1, min(v[f0:f1 + 1]), max(v[f0:f1 + 1]), len(hits), a.jump))


if __name__ == "__main__":
    main()
