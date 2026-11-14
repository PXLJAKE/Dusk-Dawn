//! The mixer: one layer per sound with smoothed levels, a ramping master
//! volume, the alarm on top, and the soft limiter. Port of
//! `device/sleepgen/engine.py`, reduced to the API in integration/CONTRACT.md
//! (play/stop, presets and the sleep timer live in the integration).

use crate::alarm::{AlarmTone, Tone};
use crate::dsp::MAX_BLOCK;
use crate::events::{Birds, Thunder};
use crate::rng::Rng;
use crate::sounds::*;

pub const SOUNDS: [&str; 12] = [
    "rain", "waves", "stream", "wind", "thunder", "birds", "leaves", "fire", "fan", "white", "pink", "brown",
];

/// Time constant of the per-layer level smoothing (reaches the target in ~0.5 s).
const LEVEL_TAU_S: f64 = 0.1;
/// De-click smoothing of the applied master gain.
const MASTER_TAU_S: f64 = 0.02;
/// Fade when an alarm stops (explicitly or after its duration).
const ALARM_RELEASE_S: f64 = 0.03;
/// Default master volume (as in the reference engine).
pub const DEFAULT_MASTER: f64 = 0.6;

/// Map a 0..1 slider to a perceptually even gain (about 40 dB range).
pub fn volume_curve(v: f64) -> f64 {
    let v = if v.is_nan() { 0.0 } else { v.clamp(0.0, 1.0) };
    if v <= 0.0 {
        return 0.0;
    }
    10f64.powf((v - 1.0) * 2.0) * (v * 10.0).min(1.0)
}

fn clamp01(v: f64) -> f64 {
    if v.is_nan() {
        0.0
    } else {
        v.clamp(0.0, 1.0)
    }
}

/// Seed for one component, independent of construction order.
fn sub_seed(seed: u64, k: u64) -> u64 {
    let mut r = Rng::new(seed ^ k.wrapping_mul(0xA24B_AED4_963E_E407));
    r.next_u64()
}

pub fn make_source(name: &str, sr: f64, seed: u64) -> Option<Box<dyn Source>> {
    let rng = Rng::new(seed);
    Some(match name {
        "rain" => Box::new(Rain::new(rng, sr)),
        "waves" => Box::new(Waves::new(rng, sr)),
        "stream" => Box::new(Stream::new(rng, sr)),
        "wind" => Box::new(Wind::new(rng, sr)),
        "thunder" => Box::new(Thunder::new(rng, sr)),
        "birds" => Box::new(Birds::new(rng, sr)),
        "leaves" => Box::new(Leaves::new(rng, sr)),
        "fire" => Box::new(Fire::new(rng, sr)),
        "fan" => Box::new(Fan::new(rng, sr)),
        "white" => Box::new(White::new(rng)),
        "pink" => Box::new(Pink::new(rng)),
        "brown" => Box::new(Brown::new(rng, sr)),
        _ => return None,
    })
}

struct Layer {
    gen: Box<dyn Source>,
    level: f64,
    target: f64,
    gain: f64,
}

struct Alarm {
    tone: AlarmTone,
    age: u64,
    duration: u64,
    ramp: f64,
    volume: f64,
    /// Samples left of the release fade, once stopped.
    release: Option<u32>,
}

pub struct Engine {
    sr: u32,
    rng: Rng,
    layers: Vec<Layer>,
    level_coef: f64,
    master_coef: f64,
    master_from: f64,
    master_to: f64,
    ramp_len: u64,
    ramp_pos: u64,
    master_gain: f64,
    alarm: Option<Alarm>,
    mix: [f64; MAX_BLOCK],
    tmp: [f64; MAX_BLOCK],
}

#[derive(Debug, PartialEq)]
pub enum EngineError {
    BadRate(u32),
    UnknownSound(String),
}

impl std::fmt::Display for EngineError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EngineError::BadRate(r) => write!(f, "unsupported sample rate {r} (8000..=192000)"),
            EngineError::UnknownSound(s) => write!(f, "unknown sound '{s}'. Known: {}", SOUNDS.join(", ")),
        }
    }
}

impl std::error::Error for EngineError {}

impl Engine {
    pub fn new(rate: u32, seed: Option<u64>) -> Result<Engine, EngineError> {
        if !(8000..=192_000).contains(&rate) {
            return Err(EngineError::BadRate(rate));
        }
        let seed = seed.unwrap_or_else(Rng::entropy_seed);
        let sr = rate as f64;
        let layers = SOUNDS
            .iter()
            .enumerate()
            .map(|(i, name)| Layer {
                gen: make_source(name, sr, sub_seed(seed, i as u64 + 1)).expect("known sound"),
                level: 0.0,
                target: 0.0,
                gain: 0.0,
            })
            .collect();
        Ok(Engine {
            sr: rate,
            rng: Rng::new(sub_seed(seed, 1000)),
            layers,
            level_coef: 1.0 - (-1.0 / (LEVEL_TAU_S * sr)).exp(),
            master_coef: 1.0 - (-1.0 / (MASTER_TAU_S * sr)).exp(),
            master_from: DEFAULT_MASTER,
            master_to: DEFAULT_MASTER,
            ramp_len: 0,
            ramp_pos: 0,
            master_gain: volume_curve(DEFAULT_MASTER),
            alarm: None,
            mix: [0.0; MAX_BLOCK],
            tmp: [0.0; MAX_BLOCK],
        })
    }

    pub fn rate(&self) -> u32 {
        self.sr
    }

    pub fn sounds(&self) -> &'static [&'static str] {
        &SOUNDS
    }

    fn index(sound: &str) -> Result<usize, EngineError> {
        SOUNDS
            .iter()
            .position(|s| *s == sound)
            .ok_or_else(|| EngineError::UnknownSound(sound.to_string()))
    }

    /// Set a layer level (0..1). The applied gain follows within ~0.5 s.
    pub fn set_level(&mut self, sound: &str, level: f64) -> Result<(), EngineError> {
        let i = Self::index(sound)?;
        let l = &mut self.layers[i];
        l.level = clamp01(level);
        l.target = volume_curve(l.level);
        Ok(())
    }

    pub fn level(&self, sound: &str) -> Result<f64, EngineError> {
        Ok(self.layers[Self::index(sound)?].level)
    }

    pub fn levels(&self) -> impl Iterator<Item = (&'static str, f64)> + '_ {
        SOUNDS.iter().zip(&self.layers).map(|(n, l)| (*n, l.level))
    }

    /// Current (possibly ramping) master volume, 0..1.
    pub fn master(&self) -> f64 {
        if self.ramp_pos >= self.ramp_len {
            self.master_to
        } else {
            self.master_from + (self.master_to - self.master_from) * self.ramp_pos as f64 / self.ramp_len as f64
        }
    }

    /// Ramp the master volume linearly to `volume` over `ramp_s` seconds.
    pub fn set_master(&mut self, volume: f64, ramp_s: f64) {
        let cur = self.master();
        self.master_from = cur;
        self.master_to = clamp01(volume);
        let ramp_s = if ramp_s.is_finite() { ramp_s.max(0.0) } else { 0.0 };
        self.ramp_len = (ramp_s * self.sr as f64) as u64;
        self.ramp_pos = 0;
    }

    pub fn start_alarm(&mut self, tone: &str, seconds: f64, volume: f64, ramp_s: f64) {
        let sr = self.sr as f64;
        let seconds = if seconds.is_finite() { seconds.max(0.1) } else { 0.1 };
        let ramp_s = if ramp_s.is_finite() { ramp_s.max(0.0) } else { 0.0 };
        self.alarm = Some(Alarm {
            tone: AlarmTone::new(Tone::parse(tone), sr, self.rng.fork()),
            age: 0,
            duration: (seconds * sr) as u64,
            ramp: (ramp_s * sr).max(1.0),
            volume: volume_curve(volume),
            release: None,
        });
    }

    pub fn stop_alarm(&mut self) {
        if let Some(a) = self.alarm.as_mut() {
            if a.release.is_none() {
                a.release = Some((ALARM_RELEASE_S * self.sr as f64) as u32);
            }
        }
    }

    pub fn alarm_ringing(&self) -> bool {
        matches!(self.alarm, Some(Alarm { release: None, .. }))
    }

    fn any_layer_active(&self) -> bool {
        self.layers.iter().any(|l| l.gain > 0.0 || l.target > 0.0)
    }

    /// Advance the master ramp by `n` samples; returns the gain target.
    fn advance_master(&mut self, n: usize) -> f64 {
        self.ramp_pos = (self.ramp_pos + n as u64).min(self.ramp_len);
        volume_curve(self.master())
    }

    /// Render `out.len()` mono samples in [-1, 1].
    pub fn render(&mut self, out: &mut [f64]) {
        for chunk in out.chunks_mut(MAX_BLOCK) {
            self.render_block(chunk);
        }
    }

    fn render_block(&mut self, out: &mut [f64]) {
        let n = out.len();
        let master_target = self.advance_master(n);
        let layers_on = self.any_layer_active();
        if !layers_on && self.alarm.is_none() {
            // silence costs (almost) nothing
            out.fill(0.0);
            let k = (1.0 - self.master_coef).powi(n as i32);
            self.master_gain = master_target + (self.master_gain - master_target) * k;
            return;
        }
        let mix = &mut self.mix[..n];
        mix.fill(0.0);
        if layers_on {
            let tmp = &mut self.tmp[..n];
            let c = self.level_coef;
            for l in self.layers.iter_mut() {
                if l.target == 0.0 && l.gain < 1e-5 {
                    l.gain = 0.0;
                    continue;
                }
                l.gen.render(tmp);
                let (mut g, t) = (l.gain, l.target);
                for (m, &x) in mix.iter_mut().zip(tmp.iter()) {
                    g += (t - g) * c;
                    *m += x * g;
                }
                l.gain = g;
            }
        }
        let mc = self.master_coef;
        let mut mg = self.master_gain;
        for m in mix.iter_mut() {
            mg += (master_target - mg) * mc;
            *m *= mg;
        }
        self.master_gain = mg;

        let mut alarm_done = false;
        if let Some(a) = self.alarm.as_mut() {
            let tmp = &mut self.tmp[..n];
            a.tone.render(tmp);
            let rel_len = (ALARM_RELEASE_S * self.sr as f64).max(1.0);
            for (m, &x) in mix.iter_mut().zip(tmp.iter()) {
                a.age += 1;
                if a.release.is_none() && a.age >= a.duration {
                    a.release = Some(rel_len as u32);
                }
                let mut g = (0.15 + 0.85 * (a.age as f64 / a.ramp).min(1.0)) * a.volume;
                if let Some(r) = a.release.as_mut() {
                    g *= *r as f64 / rel_len;
                    *r = r.saturating_sub(1);
                }
                *m += x * g;
            }
            alarm_done = a.release == Some(0);
        }
        if alarm_done {
            self.alarm = None;
        }
        // soft limiter, transparent below ~-6 dBFS
        for (o, &m) in out.iter_mut().zip(mix.iter()) {
            *o = (m * 1.2).tanh() / 1.2;
        }
    }

    /// Render `frames` samples as signed 16-bit little-endian mono PCM.
    pub fn render_s16le(&mut self, frames: usize, bytes: &mut Vec<u8>) {
        bytes.clear();
        bytes.reserve(frames * 2);
        let mut buf = [0.0f64; MAX_BLOCK];
        let mut left = frames;
        while left > 0 {
            let n = left.min(MAX_BLOCK);
            self.render_block(&mut buf[..n]);
            for &v in &buf[..n] {
                let s = (v * 32767.0).round().clamp(-32768.0, 32767.0) as i16;
                bytes.extend_from_slice(&s.to_le_bytes());
            }
            left -= n;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SR: u32 = 22050;

    fn rms(x: &[f64]) -> f64 {
        (x.iter().map(|v| v * v).sum::<f64>() / x.len().max(1) as f64).sqrt()
    }

    fn render(e: &mut Engine, seconds: f64) -> Vec<f64> {
        let mut v = vec![0.0; (seconds * e.rate() as f64) as usize];
        e.render(&mut v);
        v
    }

    #[test]
    fn volume_curve_matches_reference() {
        assert_eq!(volume_curve(0.0), 0.0);
        assert!((volume_curve(1.0) - 1.0).abs() < 1e-12);
        assert!((volume_curve(0.5) - 0.1).abs() < 1e-12);
        assert!((volume_curve(0.05) - 10f64.powf(-1.9) * 0.5).abs() < 1e-12);
    }

    #[test]
    fn silent_by_default() {
        let mut e = Engine::new(SR, Some(1)).unwrap();
        let x = render(&mut e, 1.0);
        assert!(x.iter().all(|v| *v == 0.0));
    }

    #[test]
    fn every_sound_is_calibrated() {
        for (i, name) in SOUNDS.iter().enumerate() {
            let mut e = Engine::new(SR, Some(10 + i as u64)).unwrap();
            e.set_master(1.0, 0.0);
            e.set_level(name, 1.0).unwrap();
            let secs = match *name {
                "thunder" => 240.0,
                "birds" => 60.0,
                _ => 20.0,
            };
            let x = render(&mut e, secs);
            let r = rms(&x[SR as usize..]);
            let db = 20.0 * (r / 0.125).log10();
            let (lo, hi) = match *name {
                "thunder" | "birds" => (-30.0, 3.0), // sparse events
                _ => (-2.5, 2.0),
            };
            assert!(db > lo && db < hi, "{name}: {db:.1} dB re TARGET_RMS");
            assert!(
                x.iter().all(|v| v.abs() < 1.0 / 1.2 + 1e-9),
                "{name} exceeds limiter ceiling"
            );
        }
    }

    #[test]
    fn levels_are_smoothed() {
        let mut e = Engine::new(SR, Some(2)).unwrap();
        e.set_master(1.0, 0.0);
        e.set_level("pink", 1.0).unwrap();
        let a = render(&mut e, 0.02);
        let b = render(&mut e, 1.0);
        assert!(rms(&a) < 0.5 * rms(&b[SR as usize / 2..]));
        e.set_level("pink", 0.0).unwrap();
        render(&mut e, 2.0);
        let c = render(&mut e, 0.5);
        assert!(c.iter().all(|v| *v == 0.0));
    }

    #[test]
    fn master_ramps_linearly() {
        let mut e = Engine::new(SR, Some(3)).unwrap();
        e.set_master(0.0, 0.0);
        assert_eq!(e.master(), 0.0);
        e.set_master(1.0, 10.0);
        render(&mut e, 5.0);
        assert!((e.master() - 0.5).abs() < 1e-3, "{}", e.master());
        render(&mut e, 6.0);
        assert_eq!(e.master(), 1.0);
    }

    #[test]
    fn alarm_rings_then_stops() {
        for tone in ["bells", "classic", "birds", "Glocken", "nonsense"] {
            let mut e = Engine::new(SR, Some(4)).unwrap();
            e.start_alarm(tone, 2.0, 1.0, 1.0);
            assert!(e.alarm_ringing());
            let x = render(&mut e, 1.9);
            assert!(rms(&x) > 0.005, "{tone} too quiet: {}", rms(&x));
            assert!(e.alarm_ringing());
            render(&mut e, 0.2);
            assert!(!e.alarm_ringing());
            let y = render(&mut e, 0.5);
            assert!(y.iter().all(|v| *v == 0.0));
        }
    }

    #[test]
    fn stop_alarm_is_immediate() {
        let mut e = Engine::new(SR, Some(5)).unwrap();
        e.start_alarm("classic", 60.0, 0.7, 40.0);
        render(&mut e, 0.5);
        e.stop_alarm();
        assert!(!e.alarm_ringing());
        render(&mut e, 0.1);
        assert!(render(&mut e, 0.2).iter().all(|v| *v == 0.0));
    }

    #[test]
    fn deterministic_with_seed() {
        let mk = || {
            let mut e = Engine::new(SR, Some(77)).unwrap();
            for s in ["rain", "waves", "birds", "thunder", "fire"] {
                e.set_level(s, 0.8).unwrap();
            }
            let mut b = Vec::new();
            e.render_s16le(SR as usize * 5, &mut b);
            b
        };
        assert_eq!(mk(), mk());
        let mut other = Engine::new(SR, Some(78)).unwrap();
        other.set_level("rain", 0.8).unwrap();
        let mut b = Vec::new();
        other.render_s16le(SR as usize * 5, &mut b);
        assert_ne!(mk(), b);
    }

    #[test]
    fn unknown_sound_and_bad_rate() {
        assert!(Engine::new(100, None).is_err());
        let mut e = Engine::new(SR, None).unwrap();
        assert_eq!(e.set_level("nope", 1.0), Err(EngineError::UnknownSound("nope".into())));
    }

    #[test]
    fn s16_format() {
        let mut e = Engine::new(SR, Some(6)).unwrap();
        e.set_level("white", 1.0).unwrap();
        let mut b = Vec::new();
        e.render_s16le(1000, &mut b);
        assert_eq!(b.len(), 2000);
        e.render_s16le(0, &mut b);
        assert!(b.is_empty());
    }
}
