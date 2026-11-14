"""Realtime benchmark for dusk_dawn_core.

Renders 50 ms blocks (like the integration does) with 4 active sounds and prints
the realtime factor (seconds of audio per second of CPU) and the share of one
core needed for real-time playback.

    python bench.py [--rate 44100] [--seconds 120]
"""

from __future__ import annotations

import argparse
import time

from dusk_dawn_core import Engine

MIXES = {
    "rain+waves+wind+birds": {"rain": 0.8, "waves": 0.7, "wind": 0.5, "birds": 0.6},
    "fire+leaves+stream+thunder": {"fire": 0.8, "leaves": 0.6, "stream": 0.7, "thunder": 0.6},
    "all 12 sounds": None,
    "silence (all levels 0)": {},
}


def run(levels, rate, seconds, alarm=False):
    eng = Engine(rate, seed=1)
    eng.set_master(0.8)
    for name in eng.sounds() if levels is None else levels:
        eng.set_level(name, 0.7 if levels is None else levels[name])
    if alarm:
        eng.start_alarm("bells", seconds * 2, 0.7)
    block = rate // 20  # 50 ms
    eng.render(rate)  # warm-up: level smoothing, first thunder build
    blocks = int(seconds * rate / block)
    t0 = time.perf_counter()
    for _ in range(blocks):
        eng.render(block)
    cpu = time.perf_counter() - t0
    audio = blocks * block / rate
    return audio / cpu, 100.0 * cpu / audio, 1e3 * cpu / blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, default=44100)
    ap.add_argument("--seconds", type=float, default=120.0)
    args = ap.parse_args()
    t0 = time.perf_counter()
    Engine(args.rate, seed=1)
    print(f"Engine() construction: {1e3 * (time.perf_counter() - t0):.0f} ms")
    print(f"{args.rate} Hz, {args.seconds:.0f} s of audio per mix, 50 ms blocks")
    for name, levels in MIXES.items():
        rtf, pct, ms = run(levels, args.rate, args.seconds)
        print(f"  {name:28s} realtime x{rtf:8.0f}   {pct:6.3f} % of one core   {ms:6.3f} ms/block")
    rtf, pct, ms = run(MIXES["rain+waves+wind+birds"], args.rate, args.seconds, alarm=True)
    print(f"  {'4 sounds + bells alarm':28s} realtime x{rtf:8.0f}   {pct:6.3f} % of one core   {ms:6.3f} ms/block")


if __name__ == "__main__":
    main()
