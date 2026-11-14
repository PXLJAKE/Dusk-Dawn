//! Sparse one-shot events: thunder and birds (ports of `Thunder`, `Birds` and
//! `EventGenerator` in dsp.py).
//!
//! * Thunder (the original design from dsp.py at commit 73c0381) is built into
//!   a buffer exactly like the reference (including the peak normalisation),
//!   but incrementally: a few samples of the *next* event
//!   are prepared on every render call, so a 13 s thunder roll never causes a
//!   spike in render time (the reference uses a background thread for this).
//! * Birds are synthesised on the fly by a small pool of voices, so overlapping
//!   songs need no buffers at all.

use crate::dsp::{Biquad, Kind, OnePole};
use crate::rng::Rng;
use crate::sounds::Source;
use std::f64::consts::PI;

/// Countdown to the next event, like `EventGenerator` in dsp.py.
struct EventClock {
    every: (f64, f64),
    countdown: i64,
    sr: f64,
}

impl EventClock {
    fn new(rng: &mut Rng, sr: f64, every: (f64, f64)) -> Self {
        let (lo, hi) = (every.0.min(3.0), every.0.max(3.0));
        EventClock {
            every,
            countdown: (rng.uniform(lo, hi) * sr) as i64,
            sr,
        }
    }

    /// Advance by `n` samples; true when an event is due.
    fn tick(&mut self, rng: &mut Rng, n: usize) -> bool {
        self.countdown -= n as i64;
        if self.countdown <= 0 {
            self.countdown = (rng.uniform(self.every.0, self.every.1) * self.sr) as i64;
            true
        } else {
            false
        }
    }
}

// ------------------------------------------------------------------ thunder
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Stage {
    Start,
    Generate,
    Combine,
    Ready,
}

#[derive(Default, Clone, Copy)]
struct ThunderParams {
    dur: f64,
    n: usize,
    attack: f64,
    swells: [(f64, f64); 4], // centre, width
    nswell: usize,
    crack_n: usize,
    /// Final factor on top of the peak normalisation: random level times the
    /// pan of the reference's left channel, see [`Thunder::trigger`].
    gain: f64,
}

/// Distant rolling thunder, sometimes with a closer crack (`Thunder` in the
/// original dsp.py): integrated noise through a 90..220 Hz Butterworth
/// low-pass under an attack/decay envelope with a few secondary swells; close
/// strikes add a faint high-passed crack. Each roll is peak-normalised.
pub struct Thunder {
    sr: f64,
    rng: Rng,
    clock: EventClock,
    stage: Stage,
    p: ThunderParams,
    i: usize,
    build: Vec<f32>,
    crack: Vec<f32>,
    play: Vec<f32>,
    play_len: usize,
    play_pos: usize,
    play_scale: f64,
    integ: OnePole,
    rumble_lp: Biquad,
    crack_hp: Biquad,
    peak: f64,
}

const THUNDER_MAX_S: f64 = 13.0;
/// The crack decays with exp(-t / 0.25): after 3 s it is below -100 dB.
const CRACK_S: f64 = 3.0;
/// Samples of build work per rendered sample.
const BUILD_SPEED: usize = 8;

impl Thunder {
    pub fn new(rng: Rng, sr: f64) -> Self {
        Self::with_every(rng, sr, (25.0, 90.0))
    }

    pub fn with_every(mut rng: Rng, sr: f64, every: (f64, f64)) -> Self {
        let clock = EventClock::new(&mut rng, sr, every);
        Thunder {
            sr,
            rng,
            clock,
            stage: Stage::Start,
            p: ThunderParams::default(),
            i: 0,
            build: Vec::new(),
            crack: Vec::new(),
            play: Vec::new(),
            play_len: 0,
            play_pos: 0,
            play_scale: 0.0,
            integ: OnePole::integrator(0.98),
            rumble_lp: Biquad::default(),
            crack_hp: Biquad::default(),
            peak: 0.0,
        }
    }

    fn alloc(&mut self) {
        if self.build.is_empty() {
            let cap = (THUNDER_MAX_S * self.sr) as usize + 1;
            self.build = vec![0.0; cap];
            self.play = vec![0.0; cap];
            self.crack = vec![0.0; (CRACK_S * self.sr) as usize + 1];
        }
    }

    fn start_event(&mut self) {
        let (sr, rng) = (self.sr, &mut self.rng);
        let mut p = ThunderParams::default();
        p.dur = rng.uniform(6.0, 13.0);
        p.n = ((p.dur * sr) as usize).min(self.build.len());
        let close = rng.random() < 0.3;
        let fc = rng.uniform(90.0, 220.0);
        p.attack = if close {
            rng.uniform(0.05, 0.4)
        } else {
            rng.uniform(0.6, 1.8)
        };
        p.nswell = rng.integers(2, 5) as usize;
        for k in 0..p.nswell {
            p.swells[k] = (rng.uniform(0.5, p.dur * 0.7), rng.uniform(0.3, 1.2));
        }
        p.crack_n = if close { p.n.min(self.crack.len()) } else { 0 };
        // The reference pans the two channels with (1 - pan, 1 + pan) and then
        // normalises to the peak of both. The louder channel peaks at about
        // (1 + |pan|) times the unpanned peak; the left channel is rendered.
        let pan = rng.uniform(-0.5, 0.5);
        p.gain = rng.uniform(0.35, 0.8) * (1.0 - pan) / (1.0 + pan.abs());
        self.p = p;
        self.integ.reset();
        self.rumble_lp = Biquad::new(Kind::Lp, fc, sr, std::f64::consts::FRAC_1_SQRT_2);
        self.crack_hp = Biquad::new(Kind::Hp, 1500.0, sr, std::f64::consts::FRAC_1_SQRT_2);
        self.peak = 0.0;
        self.i = 0;
        self.stage = Stage::Generate;
    }

    /// Do up to `budget` samples of work on the next event.
    fn work(&mut self, mut budget: usize) {
        self.alloc();
        while budget > 0 {
            match self.stage {
                Stage::Ready => return,
                Stage::Start => self.start_event(),
                Stage::Generate => {
                    let end = self.i.saturating_add(budget).min(self.p.n);
                    for i in self.i..end {
                        // butter(2, fc) == RBJ low-pass with Q = 1/sqrt(2)
                        let r = self.rumble_lp.process(self.integ.process(self.rng.noise()));
                        self.build[i] = r as f32;
                        if i < self.p.crack_n {
                            self.crack[i] = self.crack_hp.process(self.rng.noise()) as f32;
                        }
                    }
                    budget -= end - self.i;
                    self.i = end;
                    if end >= self.p.n {
                        self.i = 0;
                        self.stage = Stage::Combine;
                    }
                }
                Stage::Combine => {
                    let end = self.i.saturating_add(budget).min(self.p.n);
                    let p = self.p;
                    let sr = self.sr;
                    let decay = p.dur / 3.2;
                    for i in self.i..end {
                        let t = i as f64 / sr;
                        let mut env = (t / p.attack).min(1.0) * (-t / decay).exp();
                        // rolling: a few secondary swells
                        for &(c, w) in &p.swells[..p.nswell] {
                            let x = (t - c) / w;
                            if x.abs() < 6.0 {
                                env *= 1.0 + 0.9 * (-x * x).exp();
                            }
                        }
                        let mut y = self.build[i] as f64 * env;
                        if i < p.crack_n {
                            y += self.crack[i] as f64 * (-t / 0.25).exp() * 0.02;
                        }
                        self.peak = self.peak.max(y.abs());
                        self.build[i] = y as f32;
                    }
                    budget -= end - self.i;
                    self.i = end;
                    if end >= p.n {
                        self.stage = Stage::Ready;
                    }
                }
            }
        }
    }

    fn trigger(&mut self) {
        if self.stage != Stage::Ready {
            self.work(usize::MAX); // not ready yet (only possible right at the start)
        }
        std::mem::swap(&mut self.build, &mut self.play);
        self.play_len = self.p.n;
        self.play_pos = 0;
        self.play_scale = self.p.gain / self.peak.max(1e-12);
        self.stage = Stage::Start;
    }
}

impl Source for Thunder {
    fn render(&mut self, out: &mut [f64]) {
        let n = out.len();
        if self.clock.tick(&mut self.rng, n) {
            self.trigger();
        }
        let take = n.min(self.play_len - self.play_pos);
        let scale = self.play_scale;
        for (o, &v) in out[..take]
            .iter_mut()
            .zip(&self.play[self.play_pos..self.play_pos + take])
        {
            *o = v as f64 * scale;
        }
        out[take..].fill(0.0);
        self.play_pos += take;
        self.work(BUILD_SPEED * n);
    }
}

// ------------------------------------------------------------------ birds
const MAX_SEGS: usize = 80;
const VOICES: usize = 16;

#[derive(Clone, Copy, Default)]
struct Seg {
    len: u32, // samples
    note: bool,
    f0: f64,
    f1: f64,
    d: f64,
    vib: f64,
    vib_hz: f64,
    harm: f64,
}

#[derive(Clone, Copy)]
struct Voice {
    active: bool,
    segs: [Seg; MAX_SEGS],
    nseg: usize,
    si: usize,
    sp: u32,
    ph: f64,
    far: bool,
    lp: OnePole,
    scale: f64,
}

impl Default for Voice {
    fn default() -> Self {
        Voice {
            active: false,
            segs: [Seg::default(); MAX_SEGS],
            nseg: 0,
            si: 0,
            sp: 0,
            ph: 0.0,
            far: false,
            lp: OnePole::default(),
            scale: 0.0,
        }
    }
}

/// Peak of `sin x + h sin 2x`.
fn harm_peak(h: f64) -> f64 {
    if h == 0.0 {
        return 1.0;
    }
    (0..1024)
        .map(|k| {
            let x = 2.0 * PI * k as f64 / 1024.0;
            (x.sin() + h * (2.0 * x).sin()).abs()
        })
        .fold(0.0, f64::max)
}

/// A lively dawn chorus: chirps (finch, sparrow), trills (wren, robin),
/// whistles (blackbird) and a rare cuckoo far away.
pub struct Birds {
    sr: f64,
    rng: Rng,
    clock: EventClock,
    voices: Box<[Voice; VOICES]>,
    far_lp: OnePole,
}

impl Birds {
    pub fn new(rng: Rng, sr: f64) -> Self {
        Self::with_every(rng, sr, (1.2, 4.5))
    }

    pub fn with_every(mut rng: Rng, sr: f64, every: (f64, f64)) -> Self {
        let clock = EventClock::new(&mut rng, sr, every);
        Birds {
            sr,
            rng,
            clock,
            voices: Box::new([Voice::default(); VOICES]),
            far_lp: OnePole::butter_lp(3500.0, sr),
        }
    }

    /// Like [`Birds::with_every`], but the first song starts immediately
    /// (used by the alarm, which should not begin with seconds of silence).
    pub fn starting_now(rng: Rng, sr: f64, every: (f64, f64)) -> Self {
        let mut b = Self::with_every(rng, sr, every);
        b.clock.countdown = 0;
        b
    }

    fn trigger(&mut self) {
        let Some(slot) = self.voices.iter().position(|v| !v.active) else {
            return; // too many birds at once: skip this one
        };
        let (sr, rng) = (self.sr, &mut self.rng);
        let v = &mut self.voices[slot];
        let mut n = 0usize;
        let mut push = |s: Seg| {
            if n < MAX_SEGS {
                v.segs[n] = s;
                n += 1;
            }
        };
        let note = |f0: f64, f1: f64, d: f64, vib: f64, vib_hz: f64, harm: f64| Seg {
            len: (d * sr) as u32,
            note: true,
            f0,
            f1,
            d,
            vib,
            vib_hz,
            harm,
        };
        let gap = |s: f64| Seg {
            len: (s * sr) as u32,
            ..Default::default()
        };

        let u = rng.random();
        let kind = if u < 0.42 {
            0
        } else if u < 0.67 {
            1
        } else if u < 0.95 {
            2
        } else {
            3
        };
        match kind {
            0 => {
                // chirp
                let base = rng.uniform(2800.0, 5500.0);
                for _ in 0..rng.integers(3, 10) {
                    let f0 = base * rng.uniform(0.85, 1.15);
                    let f1 = f0 * rng.uniform(0.6, 1.5);
                    push(note(f0, f1, rng.uniform(0.03, 0.14), 0.0, 0.0, 0.0));
                    push(gap(rng.uniform(0.02, 0.1)));
                }
            }
            1 => {
                // trill
                let mut f0 = rng.uniform(3500.0, 6500.0);
                let rate = rng.uniform(12.0, 24.0);
                let count = (rng.uniform(0.6, 1.6) * rate) as usize;
                for _ in 0..count {
                    push(note(f0, f0 * 0.82, 0.6 / rate, 0.0, 0.0, 0.0));
                    push(gap(0.4 / rate));
                    f0 *= rng.uniform(0.985, 1.01);
                }
            }
            2 => {
                // whistle
                for _ in 0..rng.integers(3, 7) {
                    let f0 = rng.uniform(1700.0, 3400.0);
                    let f1 = f0 * rng.uniform(0.75, 1.3);
                    let d = rng.uniform(0.12, 0.38);
                    push(note(f0, f1, d, 0.015, rng.uniform(25.0, 45.0), 0.15));
                    push(gap(rng.uniform(0.04, 0.18)));
                }
            }
            _ => {
                // cuckoo
                let f0 = rng.uniform(560.0, 700.0);
                for _ in 0..rng.integers(2, 4) {
                    push(note(f0, f0, 0.22, 0.0, 0.0, 0.1));
                    push(gap(rng.uniform(0.06, 0.1)));
                    push(note(f0 * 0.8, f0 * 0.8, 0.3, 0.0, 0.0, 0.1));
                    push(gap(rng.uniform(0.6, 0.9)));
                }
            }
        }
        let near = rng.random();
        let far = near < 0.4;
        let mut level = if far {
            rng.uniform(0.04, 0.09)
        } else {
            rng.uniform(0.09, 0.2)
        };
        if kind == 3 {
            level = 0.06;
        }
        // The reference normalises the finished song to its peak. The peak of a
        // note sits at its envelope centre, so it can be computed up front.
        let mut peak = 0.0f64;
        for s in v.segs[..n].iter().filter(|s| s.note) {
            let p = if far {
                let fc = 0.5 * (s.f0 + s.f1);
                let g1 = self.far_lp.gain_at(fc, sr);
                let g2 = self.far_lp.gain_at(2.0 * fc, sr);
                g1 * harm_peak(s.harm * g2 / g1.max(1e-9))
            } else {
                harm_peak(s.harm)
            };
            peak = peak.max(p);
        }
        v.active = n > 0;
        v.nseg = n;
        v.si = 0;
        v.sp = 0;
        v.ph = 0.0;
        v.far = far;
        v.lp = self.far_lp;
        v.lp.reset();
        v.scale = level / peak.max(1e-9);
    }
}

impl Source for Birds {
    fn render(&mut self, out: &mut [f64]) {
        let n = out.len();
        out.fill(0.0);
        if self.clock.tick(&mut self.rng, n) {
            self.trigger();
        }
        let sr = self.sr;
        for v in self.voices.iter_mut().filter(|v| v.active) {
            let mut i = 0;
            while i < n {
                if v.si >= v.nseg {
                    v.active = false;
                    break;
                }
                let s = v.segs[v.si];
                let take = ((s.len - v.sp) as usize).min(n - i);
                if s.note {
                    let k_sweep = (s.f1 - s.f0) / s.d;
                    for o in out[i..i + take].iter_mut() {
                        let t = v.sp as f64 / sr;
                        let mut f = s.f0 + k_sweep * t;
                        if s.vib != 0.0 {
                            f *= 1.0 + s.vib * (2.0 * PI * s.vib_hz * t).sin();
                        }
                        v.ph += 2.0 * PI * f / sr;
                        let e = (PI * t / s.d).sin();
                        let mut y = (v.ph.sin()
                            + if s.harm != 0.0 {
                                s.harm * (2.0 * v.ph).sin()
                            } else {
                                0.0
                            })
                            * e
                            * e;
                        if v.far {
                            y = v.lp.process(y);
                        }
                        *o += y * v.scale;
                        v.sp += 1;
                    }
                } else {
                    if v.far {
                        for o in out[i..i + take].iter_mut() {
                            *o += v.lp.process(0.0) * v.scale;
                        }
                    }
                    v.sp += take as u32;
                }
                i += take;
                if v.sp >= s.len {
                    v.si += 1;
                    v.sp = 0;
                    v.ph = 0.0;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn harm_peak_values() {
        assert_eq!(harm_peak(0.0), 1.0);
        let p = harm_peak(0.15);
        assert!(p > 1.0 && p < 1.15, "{p}");
    }

    #[test]
    fn thunder_events_are_normalised() {
        let sr = 22050.0;
        let mut th = Thunder::with_every(Rng::new(7), sr, (8.0, 9.0));
        let mut buf = [0.0; 256];
        let mut peak = 0.0f64;
        let mut energy = 0.0;
        for _ in 0..(60.0 * sr / 256.0) as usize {
            th.render(&mut buf);
            for v in buf {
                peak = peak.max(v.abs());
                energy += v * v;
            }
        }
        assert!(energy > 0.0);
        assert!(peak <= 0.8 + 1e-6 && peak > 0.1, "peak {peak}");
    }

    #[test]
    fn birds_sing_within_level() {
        let sr = 44100.0;
        let mut b = Birds::new(Rng::new(3), sr);
        let mut buf = [0.0; 256];
        let mut peak = 0.0f64;
        for _ in 0..(40.0 * sr / 256.0) as usize {
            b.render(&mut buf);
            for v in buf {
                peak = peak.max(v.abs());
            }
        }
        // single songs peak at <= 0.2; overlaps can add up a little
        assert!(peak > 0.03 && peak < 0.45, "peak {peak}");
    }
}
