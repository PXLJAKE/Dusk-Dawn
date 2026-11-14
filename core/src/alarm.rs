//! Alarm sounds (port of `AlarmTone` in dsp.py). Not a mixer layer: the
//! engine plays them on top of everything while the alarm rings.
//!
//! * `bells`   ("Glocken")   a soft bell arpeggio with glockenspiel partials
//! * `classic` ("Klassisch") a two-tone beep pattern
//! * `birds`   ("Vogelchor") a dense, loud dawn chorus

use crate::events::Birds;
use crate::rng::Rng;
use crate::sounds::Source;
use std::f64::consts::PI;

pub const ALARM_TONES: [&str; 3] = ["bells", "classic", "birds"];

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Tone {
    Bells,
    Classic,
    Birds,
}

impl Tone {
    /// Accepts the contract names and the German names of the reference.
    /// Unknown names fall back to bells, like the reference does.
    pub fn parse(name: &str) -> Tone {
        match name.trim().to_ascii_lowercase().as_str() {
            "classic" | "klassisch" => Tone::Classic,
            "birds" | "vogelchor" => Tone::Birds,
            _ => Tone::Bells,
        }
    }

    pub fn known(name: &str) -> bool {
        matches!(
            name.trim().to_ascii_lowercase().as_str(),
            "bells" | "glocken" | "classic" | "klassisch" | "birds" | "vogelchor"
        )
    }
}

pub enum AlarmTone {
    Loop { data: Vec<f32>, pos: usize },
    Chorus(Box<Birds>),
}

fn bell(sr: f64, f: f64, d: f64) -> Vec<f64> {
    let m = (d * sr) as usize;
    (0..m)
        .map(|i| {
            let t = i as f64 / sr;
            let mut x = 0.0;
            for (ratio, amp, tau) in [
                (1.0, 1.0, 0.9),
                (2.76, 0.45, 0.35),
                (5.40, 0.25, 0.18),
                (8.93, 0.12, 0.1),
            ] {
                x += amp * (2.0 * PI * f * ratio * t).sin() * (-t / tau).exp();
            }
            x * (1.0 - (-t / 0.002).exp())
        })
        .collect()
}

impl AlarmTone {
    pub fn new(tone: Tone, sr: f64, rng: Rng) -> Self {
        let mono: Vec<f64> = match tone {
            Tone::Birds => return AlarmTone::Chorus(Box::new(Birds::starting_now(rng, sr, (0.3, 1.2)))),
            Tone::Classic => {
                let m = (0.12 * sr) as usize;
                let last = (m - 1) as f64 / sr;
                let beep: Vec<f64> = (0..m)
                    .map(|i| {
                        let t = i as f64 / sr;
                        let s = (2.0 * PI * 880.0 * t).sin();
                        let sq = if s > 0.0 {
                            1.0
                        } else if s < 0.0 {
                            -1.0
                        } else {
                            0.0
                        };
                        let v = sq * 0.35 + (2.0 * PI * 1760.0 * t).sin() * 0.2;
                        v * (t.min(last - t) / 0.005).min(1.0)
                    })
                    .collect();
                let gap = vec![0.0; (0.1 * sr) as usize];
                let mut v = Vec::new();
                for k in 0..4 {
                    v.extend_from_slice(&beep);
                    if k < 3 {
                        v.extend_from_slice(&gap);
                    }
                }
                v.extend(std::iter::repeat(0.0).take((0.7 * sr) as usize));
                v
            }
            Tone::Bells => {
                let notes = [523.25, 659.25, 783.99, 1046.5, 783.99, 659.25];
                let step = (0.28 * sr) as usize;
                let mut v = vec![0.0; step * notes.len() + (1.2 * sr) as usize];
                for (i, &f) in notes.iter().enumerate() {
                    let b = bell(sr, f, 1.6);
                    let start = i * step;
                    for (o, x) in v[start..].iter_mut().zip(b.iter()) {
                        *o += x;
                    }
                }
                v
            }
        };
        let peak = mono.iter().fold(0.0f64, |m, v| m.max(v.abs())).max(1e-12);
        AlarmTone::Loop {
            data: mono.iter().map(|v| (v / peak * 0.7) as f32).collect(),
            pos: 0,
        }
    }

    /// Overwrite `out` with the next samples.
    pub fn render(&mut self, out: &mut [f64]) {
        match self {
            AlarmTone::Chorus(b) => {
                b.render(out);
                for v in out.iter_mut() {
                    *v *= 6.0;
                }
            }
            AlarmTone::Loop { data, pos } => {
                for o in out.iter_mut() {
                    *o = data[*pos] as f64;
                    *pos += 1;
                    if *pos >= data.len() {
                        *pos = 0;
                    }
                }
            }
        }
    }
}
