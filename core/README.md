# dusk-dawn-core

Rust sound engine for the **Dusk & Dawn** Home Assistant integration, with Python
bindings (PyO3). It renders procedural sleep sounds: rain, waves, stream, wind,
thunder, birds, leaves, fire, fan, and white, pink and brown noise. It also renders
alarm tones (bells, classic, birds). Output is mono signed 16-bit little-endian PCM.

The engine is a port of `device/sleepgen/dsp.py` and `engine.py`. It uses the same
grain banks, event generators, filters, calibration to equal loudness
(`TARGET_RMS = 0.125`), level smoothing and `tanh` soft limiter. The API is defined
in `integration/CONTRACT.md`, section 1. The integration loads this module if it is
installed and otherwise falls back to its pure-Python engine:

```python
from dusk_dawn_core import Engine

eng = Engine(rate=44100, seed=None)
eng.set_master(0.5, ramp_s=8.0)
eng.set_level("rain", 0.7)
eng.set_level("thunder", 0.4)
pcm = eng.render(2205)          # 50 ms -> 4410 bytes of s16le mono
eng.start_alarm("bells", seconds=600, volume=0.7, ramp_s=40.0)
```

## Design notes

- Pure Rust with no dependencies except `pyo3`, which is optional. The crate
  includes its own xoshiro256++ RNG.
- The render hot path does not allocate. Thunder rolls are built a few samples at a
  time on each render call, which replaces the reference's background thread.
  Birds are synthesised by a fixed pool of voices.
- Layers are rendered as one channel at the reference's per-channel loudness.
  Silent layers are skipped, and when every level is 0 and no alarm rings,
  `render` only writes zeros.
- `render` releases the GIL. Control calls from other threads are safe and take
  effect on the next 256-sample block.
- Same seed and same calls give byte-identical output.

## Build and test

```sh
cargo test --release                  # Rust unit tests (no Python needed)
pip install maturin && maturin develop --release
pytest tests/test_parity.py           # API, formats, loudness vs. the Python reference
python bench.py                       # realtime factor for 4 active sounds
```

`tests/test_parity.py` needs `numpy` and `scipy`, because it imports the reference
engine from `device/sleepgen`.

## Wheels

`.github/workflows/wheels.yml` builds abi3 wheels (one wheel per platform for
CPython 3.12 and newer). It covers manylinux and musllinux on x86_64 and aarch64,
plus musllinux armv7, and also builds an sdist. It runs on `core-v*` tags and on
manual dispatch. Publishing to PyPI uses trusted publishing, only runs on tags, and
is disabled until the PyPI project is configured. See the comment in the workflow.
