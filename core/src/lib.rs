//! Dusk & Dawn sound core: procedural sleep sounds (rain, waves, stream, wind,
//! thunder, birds, leaves, fire, fan, white/pink/brown noise) and alarm tones,
//! rendered as mono PCM. A Rust port of `device/sleepgen/dsp.py` and
//! `engine.py`; see `integration/CONTRACT.md` section 1 for the Python API.

pub mod alarm;
pub mod dsp;
pub mod engine;
pub mod events;
pub mod rng;
pub mod sounds;

pub use alarm::ALARM_TONES;
pub use engine::{volume_curve, Engine, EngineError, SOUNDS};

#[cfg(feature = "python")]
mod python;
