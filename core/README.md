# dusk-dawn-core

Rust sound engine for the **Dusk & Dawn** Home Assistant integration, with Python
bindings (PyO3). It renders procedural sleep sounds: rain, waves, wind, thunder, fan, and white, pink
and brown noise (the engine can also render stream, birds, leaves and fire, which the
integration no longer exposes). It also renders
alarm tones (bells, classic, birds). Output is mono signed 16-bit little-endian PCM.

The engine is a port of `hardware/device/sleepgen/dsp.py` and `engine.py`. White, pink and
brown noise, fan, rain, wind, waves, fire and thunder are the original designs
(`dsp.py` at commit 73c0381: same filters, random structure and envelopes); birds,
leaves and stream are the newer grain-based designs. It uses the same calibration to
equal loudness (`TARGET_RMS = 0.125`), level smoothing and `tanh` soft limiter. The API is defined
in `docs/CONTRACT.md`, section 1. The integration loads this module if it is
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

`tests/test_parity.py` needs `numpy`, `scipy` and the git history: it loads the
reference generators from commits 73c0381 (original sounds; loudness within 3 dB,
spectral centroid within 15 %) and 3603211 (birds, leaves, stream; loudness within
3 dB).

## Wheels

`.github/workflows/wheels.yml` builds abi3 wheels (one wheel per platform for
CPython 3.12 and newer). It covers manylinux and musllinux on x86_64 and aarch64,
plus musllinux armv7, and also builds an sdist. It runs on `core-v*` tags and on
manual dispatch. Publishing to PyPI uses trusted publishing, only runs on tags, and
is disabled until the PyPI project is configured. See the comment in the workflow.

## Bundled with the integration

The module is not on PyPI, so the integration also ships it for Home Assistant OS
and the HA container images, which are Alpine (musl) based:
`custom_components/dusk_dawn/native/{x86_64,aarch64}/dusk_dawn_core.abi3.so`
(abi3, CPython 3.12 and newer, musllinux_1_2). `native/__init__.py` loads an
installed `dusk_dawn_core` first, then the bundled file for `platform.machine()`
(musl systems only), and otherwise the integration uses its Python engine. The
log says which engine is used, and the websocket `dusk_dawn/spots` result has
`engine: "rust" | "python"` per spot.

`.github/workflows/native.yml` builds them with a pinned toolchain and checks
that both load and render on Alpine. The release workflow runs that build for
every release and commits exactly its output, and the release notes link the
build run and list the SHA-256 checksums. To rebuild them by hand:

```sh
pip install maturin ziglang
rustup target add x86_64-unknown-linux-musl aarch64-unknown-linux-musl
for arch in x86_64 aarch64; do
  maturin build --profile bundle --zig --target $arch-unknown-linux-musl \
    --compatibility musllinux_1_2 --out dist
  python -m zipfile -e dist/dusk_dawn_core-*musllinux_1_2_$arch.whl /tmp/whl-$arch
  cp /tmp/whl-$arch/dusk_dawn_core/dusk_dawn_core.abi3.so \
    ../custom_components/dusk_dawn/native/$arch/
done
```

The `bundle` profile is `release` plus stripping, which
keeps each file around 0.5 MB. It keeps `panic = "unwind"`, so a Rust panic
raises a Python exception instead of ending the Home Assistant process.
