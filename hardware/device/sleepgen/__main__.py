"""Command line entry point.

    python -m sleepgen --config /etc/sleepgen/config.yaml        # run the device
    python -m sleepgen --render demo.wav --preset Gewitternacht   # offline preview
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import wave

import numpy as np

from . import config as config_mod


def render_file(cfg: dict, path: str, preset: str, seconds: float):
    from .engine import Engine

    sr = cfg["audio"]["sample_rate"]
    eng = Engine(sr=sr, sources=cfg["sounds"], fade_in_s=2, seed=1)
    eng.apply_preset(preset, cfg["presets"][preset])
    eng.master = 1.0
    eng.play()
    block = 4096
    frames = [eng.render(block) for _ in range(int(seconds * sr / block))]
    x = np.clip(np.concatenate(frames), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"wrote {path} ({seconds:.0f} s, preset {preset})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sleepgen")
    ap.add_argument("--config", default="/etc/sleepgen/config.yaml")
    ap.add_argument("--render", metavar="WAV", help="render a preset to a WAV file and exit")
    ap.add_argument("--preset", default=None)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--no-audio", action="store_true", help="run without a sound card")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config_mod.load(args.config)

    if args.render:
        render_file(cfg, args.render, args.preset or cfg["default_preset"], args.seconds)
        return 0

    from .app import App

    app = App(cfg)
    app.start(audio=not args.no_audio)
    signal.signal(signal.SIGTERM, lambda *_: app._stop.set())
    try:
        app.loop()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
