//! The continuous sound generators (noise colours, fan, rain, leaves, stream,
//! wind, waves, fire), rendered as one mono channel.
//!
//! White, pink and brown noise, fan, rain, wind, waves and fire are exact
//! ports of the original generators (`device/sleepgen/dsp.py` at commit
//! 73c0381): same filters, same random structure, same envelopes. The
//! reference renders two independent channels; here one channel is rendered
//! at the same per-channel loudness (TARGET_RMS), because the engine output is
//! mono. Leaves and stream are newer grain-based designs.
//!
//! Audio-rate noise uses [`Rng::noise`] (unit-variance, spectrally white)
//! instead of Gaussian samples; after the filters the two are identical.

use crate::dsp::*;
use crate::rng::Rng;
use std::f64::consts::PI;

/// A sound layer. `render` overwrites `out` (at most [`MAX_BLOCK`] samples).
pub trait Source: Send {
    fn render(&mut self, out: &mut [f64]);
}

// ------------------------------------------------------------------ noise colours
pub struct White {
    rng: Rng,
}

impl White {
    pub fn new(rng: Rng) -> Self {
        White { rng }
    }
}

impl Source for White {
    fn render(&mut self, out: &mut [f64]) {
        for v in out.iter_mut() {
            *v = self.rng.noise() * TARGET_RMS;
        }
    }
}

pub struct Pink {
    rng: Rng,
    f: PinkFilter,
}

impl Pink {
    pub fn new(rng: Rng) -> Self {
        Pink {
            rng,
            f: PinkFilter::default(),
        }
    }
    #[inline(always)]
    pub fn sample(&mut self) -> f64 {
        self.f.process(self.rng.noise())
    }
}

impl Source for Pink {
    fn render(&mut self, out: &mut [f64]) {
        for v in out.iter_mut() {
            *v = self.sample();
        }
    }
}

/// Integrated white noise with a gentle DC blocker.
pub struct Brown {
    rng: Rng,
    integ: OnePole,
    hp: Biquad,
}

impl Brown {
    pub fn new(rng: Rng, sr: f64) -> Self {
        Brown {
            rng,
            integ: OnePole::integrator(0.997),
            hp: Biquad::new(Kind::Hp, 20.0, sr, 0.707),
        }
    }
    #[inline(always)]
    pub fn sample(&mut self) -> f64 {
        self.hp.process(self.integ.process(self.rng.noise())) * (TARGET_RMS / 7.5)
    }
}

impl Source for Brown {
    fn render(&mut self, out: &mut [f64]) {
        for v in out.iter_mut() {
            *v = self.sample();
        }
    }
}

/// Phase accumulator in cycles, kept in [0, 1) so long runs stay precise.
#[derive(Clone, Copy, Default)]
struct Phase {
    p: f64,
    inc: f64,
}

impl Phase {
    fn new(f: f64, sr: f64) -> Self {
        Phase { p: 0.0, inc: f / sr }
    }
    #[inline(always)]
    fn sin_next(&mut self) -> f64 {
        let v = (2.0 * PI * self.p).sin();
        self.p += self.inc;
        if self.p >= 1.0 {
            self.p -= 1.0;
        }
        v
    }
}

/// Steady air noise with a faint rotating hum.
pub struct Fan {
    pink: Pink,
    lp: Biquad,
    wob: Phase,
    hum: Phase,
    hum_mod: Phase,
}

impl Fan {
    pub fn new(mut rng: Rng, sr: f64) -> Self {
        Fan {
            pink: Pink::new(rng.fork()),
            lp: Biquad::new(Kind::Lp, 1400.0, sr, 0.6),
            wob: Phase::new(7.3, sr),
            hum: Phase::new(98.0, sr),
            hum_mod: Phase::new(0.2, sr),
        }
    }
}

impl Source for Fan {
    fn render(&mut self, out: &mut [f64]) {
        for v in out.iter_mut() {
            let y = self.lp.process(self.pink.sample());
            let wobble = 1.0 + 0.04 * self.wob.sin_next();
            let hum = 0.012 * self.hum.sin_next() * (1.0 + 0.3 * self.hum_mod.sin_next());
            *v = y * wobble * 1.25 + hum;
        }
    }
}

// ------------------------------------------------------------------ calibration
/// Seconds of output measured to calibrate a generator. The reference uses
/// 8 s (16 s for waves); longer is cheap here and makes the loudness of
/// slowly varying sounds (gusts, rain intensity) less dependent on the seed.
pub const CALIBRATE_S: f64 = 24.0;

/// Raw (uncalibrated) generator; [`Calibrated`] scales it to TARGET_RMS.
pub trait Raw: Send {
    fn raw(&mut self, out: &mut [f64]);
}

pub struct Calibrated<T: Raw> {
    inner: T,
    gain: f64,
}

impl<T: Raw> Calibrated<T> {
    /// Measure the raw RMS over `seconds` of output (like `_calibrate` in
    /// dsp.py; the generator simply keeps running from there).
    pub fn new(mut inner: T, sr: f64, seconds: f64) -> Self {
        let mut buf = [0.0; MAX_BLOCK];
        let blocks = ((seconds * sr) as usize / MAX_BLOCK).max(1);
        let mut sum = 0.0;
        for _ in 0..blocks {
            inner.raw(&mut buf);
            sum += buf.iter().map(|v| v * v).sum::<f64>();
        }
        let rms = (sum / (blocks * MAX_BLOCK) as f64).sqrt();
        let gain = if rms > 0.0 { TARGET_RMS / rms } else { 1.0 };
        Calibrated { inner, gain }
    }
}

impl<T: Raw> Source for Calibrated<T> {
    fn render(&mut self, out: &mut [f64]) {
        self.inner.raw(out);
        for v in out.iter_mut() {
            *v *= self.gain;
        }
    }
}

#[inline]
fn mean(x: &[f64]) -> f64 {
    if x.is_empty() {
        0.0
    } else {
        x.iter().sum::<f64>() / x.len() as f64
    }
}

// ------------------------------------------------------------------ rain
/// Steady rain bed plus individual drops hitting surfaces (`Rain` in the
/// original dsp.py): pink noise band-limited to 500..7000 Hz, plus sparse
/// Pareto-weighted impulses through a 2.8 kHz band-pass, all under a slowly
/// wandering intensity.
pub struct Rain {
    rng: Rng,
    pink: Pink,
    hp: Biquad,
    lp: Biquad,
    drops: Biquad,
    p: f64,
    intensity: SmoothRandom,
}

impl Rain {
    pub const DROPS_PER_S: f64 = 900.0;

    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Rain> {
        let r = Rain {
            pink: Pink::new(rng.fork()),
            hp: Biquad::new(Kind::Hp, 500.0, sr, 0.707),
            lp: Biquad::new(Kind::Lp, 7000.0, sr, 0.707),
            drops: Biquad::new(Kind::Bp, 2800.0, sr, 0.9),
            p: Self::DROPS_PER_S / sr,
            intensity: SmoothRandom::new(rng.fork(), 0.75, 1.15, 6.0, sr),
            rng,
        };
        Calibrated::new(r, sr, CALIBRATE_S)
    }
}

impl Raw for Rain {
    fn raw(&mut self, out: &mut [f64]) {
        for o in out.iter_mut() {
            let bed = self.lp.process(self.hp.process(self.pink.sample()));
            let hit = if self.rng.random() < self.p {
                self.rng.pareto(3.0).min(3.0)
            } else {
                0.0
            };
            let drop = self.drops.process(hit);
            *o = (bed * 1.6 + drop * 0.35) * self.intensity.next_value();
        }
    }
}

// ------------------------------------------------------------------ leaves
/// Rustling leaves: gusts sweep through the canopy, thousands of soft grains.
pub struct Leaves {
    sr: f64,
    grains: Grains,
    gust: SmoothRandom,
    pink: Pink,
    hp: Biquad,
    g: [f64; MAX_BLOCK],
}

impl Leaves {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Leaves> {
        let kernels = (0..64)
            .map(|_| {
                let (d, f, q) = (
                    rng.uniform(0.004, 0.035),
                    rng.uniform(1800.0, 7000.0),
                    rng.uniform(0.8, 2.0),
                );
                leaf_grain(&mut rng, sr, d, f, q)
            })
            .collect();
        let l = Leaves {
            sr,
            grains: Grains::new(rng.fork(), kernels),
            gust: SmoothRandom::new(rng.fork(), 0.0, 1.0, 2.6, sr),
            pink: Pink::new(rng.fork()),
            hp: Biquad::new(Kind::Hp, 2200.0, sr, 0.707),
            g: [0.0; MAX_BLOCK],
        };
        Calibrated::new(l, sr, CALIBRATE_S)
    }
}

impl Raw for Leaves {
    fn raw(&mut self, out: &mut [f64]) {
        let n = out.len();
        let g = &mut self.g[..n];
        for v in g.iter_mut() {
            let x = self.gust.next_value();
            *v = x * x;
        }
        for (o, gv) in out.iter_mut().zip(g.iter()) {
            *o = self.hp.process(self.pink.sample()) * (0.05 + 0.5 * gv);
        }
        let rate = (60.0 + 2600.0 * mean(g)) / self.sr;
        self.grains.render(out, rate, (0.1, 0.6), 0.0, 1.0);
    }
}

// ------------------------------------------------------------------ stream
/// Forest brook: babbling water with bubbles and little splashes.
pub struct Stream {
    sr: f64,
    pink: Pink,
    bp: Biquad,
    bubbles: Grains,
    splash: Grains,
    babble: SmoothRandom,
}

impl Stream {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Stream> {
        let bubbles = (0..64)
            .map(|_| {
                let (f, d, r) = (
                    rng.uniform(500.0, 2200.0),
                    rng.uniform(0.008, 0.025),
                    rng.uniform(0.6, 2.0),
                );
                plip(&mut rng, sr, f, d, r, 0.05)
            })
            .collect();
        let splash = (0..24)
            .map(|_| {
                let (tau, f) = (rng.uniform(0.002, 0.008), rng.uniform(1500.0, 5000.0));
                tick(&mut rng, sr, tau, f, 0.7)
            })
            .collect();
        let s = Stream {
            sr,
            pink: Pink::new(rng.fork()),
            bp: Biquad::new(Kind::Bp, 900.0, sr, 0.5),
            bubbles: Grains::new(rng.fork(), bubbles),
            splash: Grains::new(rng.fork(), splash),
            babble: SmoothRandom::new(rng.fork(), 0.5, 1.2, 0.15, sr),
        };
        Calibrated::new(s, sr, CALIBRATE_S)
    }
}

impl Raw for Stream {
    fn raw(&mut self, out: &mut [f64]) {
        let mut msum = 0.0;
        for o in out.iter_mut() {
            let m = self.babble.next_value();
            msum += m;
            *o = self.bp.process(self.pink.sample()) * m * 1.4;
        }
        let m = msum / out.len().max(1) as f64;
        let sr = self.sr;
        self.bubbles.render(out, 70.0 / sr * m, (0.15, 0.6), 0.0, 0.6);
        self.splash.render(out, 8.0 / sr, (0.1, 0.4), 0.0, 0.3);
    }
}

// ------------------------------------------------------------------ wind
const CTRL_BLOCK: usize = 256;

/// Gusty wind: band-limited noise with wandering cutoff and level.
pub struct Wind {
    sr: f64,
    rng: Rng,
    cut: SmoothRandom,
    level: SmoothRandom,
    lp: Biquad,
    bp: Biquad,
    ctrl: usize, // samples left until the next cutoff update
}

impl Wind {
    pub fn new(mut rng: Rng, sr: f64) -> Self {
        Wind {
            sr,
            cut: SmoothRandom::new(rng.fork(), 250.0, 900.0, 4.0, sr / CTRL_BLOCK as f64),
            level: SmoothRandom::new(rng.fork(), 0.35, 1.2, 5.0, sr),
            lp: Biquad::new(Kind::Lp, 1800.0, sr, 0.6),
            bp: Biquad::default(),
            ctrl: 0,
            rng,
        }
    }
}

impl Source for Wind {
    fn render(&mut self, out: &mut [f64]) {
        const G: f64 = TARGET_RMS / 0.120;
        for o in out.iter_mut() {
            if self.ctrl == 0 {
                let c = self.cut.next_value();
                self.bp.set(Kind::Bp, c, self.sr, 1.2);
                self.ctrl = CTRL_BLOCK;
            }
            self.ctrl -= 1;
            let x = self.lp.process(self.rng.noise());
            *o = self.bp.process(x) * self.level.next_value() * G;
        }
    }
}

// ------------------------------------------------------------------ waves
/// Ocean waves: swells that build, break and wash back out (`Waves` in the
/// original dsp.py). Pink + brown noise through a low-pass whose cutoff
/// follows the wave envelope (updated every 256 samples), times the envelope.
///
/// The reference pans the surf slightly between its two channels with
/// `1 -/+ pan`; the mono sum of both channels cancels that exactly, so it is
/// left out here.
pub struct Waves {
    sr: f64,
    rng: Rng,
    pink: Pink,
    brown: Brown,
    lp: Biquad,
    ctrl: usize,
    // current wave: rise, fall, then a gap at the floor level
    seg: u8, // 0 rise, 1 fall, 2 gap
    i: usize,
    len: [usize; 3],
    peak: f64,
    fall_decay: f64, // exp(-3.5 / fall_len), applied per sample
    fall_exp: f64,
}

const WAVE_FLOOR: f64 = 0.12;

impl Waves {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Waves> {
        let mut w = Waves {
            sr,
            pink: Pink::new(rng.fork()),
            brown: Brown::new(rng.fork(), sr),
            lp: Biquad::new(Kind::Lp, 300.0, sr, 0.6),
            ctrl: 0,
            seg: 0,
            i: 0,
            len: [0; 3],
            peak: 0.0,
            fall_decay: 0.0,
            fall_exp: 1.0,
            rng,
        };
        w.new_wave();
        Calibrated::new(w, sr, 2.0 * CALIBRATE_S)
    }

    fn new_wave(&mut self) {
        let (rng, sr) = (&mut self.rng, self.sr);
        let rise = rng.uniform(2.5, 4.0);
        let fall = rng.uniform(4.0, 7.0);
        let gap = rng.uniform(0.0, 1.5);
        self.peak = rng.uniform(0.6, 1.0);
        self.len = [(rise * sr) as usize, (fall * sr) as usize, (gap * sr) as usize];
        self.fall_decay = (-3.5 / self.len[1].max(1) as f64).exp();
        self.seg = 0;
        self.i = 0;
    }

    /// Next envelope value (the reference's `_envelope`).
    #[inline]
    fn env(&mut self) -> f64 {
        while self.i >= self.len[self.seg as usize] {
            self.i = 0;
            if self.seg == 2 {
                self.new_wave();
            } else {
                self.seg += 1;
                self.fall_exp = 1.0;
            }
        }
        let k = self.i;
        self.i += 1;
        let span = self.peak - WAVE_FLOOR;
        match self.seg {
            0 => WAVE_FLOOR + span * (k as f64 / self.len[0] as f64).powf(2.2),
            1 => {
                let t = k as f64 / self.len[1] as f64;
                let v = WAVE_FLOOR + span * self.fall_exp * (1.0 - t);
                self.fall_exp *= self.fall_decay;
                v
            }
            _ => WAVE_FLOOR,
        }
    }
}

impl Raw for Waves {
    fn raw(&mut self, out: &mut [f64]) {
        for o in out.iter_mut() {
            let e = self.env();
            if self.ctrl == 0 {
                self.lp.set(Kind::Lp, 300.0 + 3500.0 * e.powf(1.5), self.sr, 0.6);
                self.ctrl = CTRL_BLOCK;
            }
            self.ctrl -= 1;
            let x = self.pink.sample() * 0.7 + self.brown.sample() * 0.6;
            *o = self.lp.process(x) * e * 3.2;
        }
    }
}

// ------------------------------------------------------------------ fire
/// Crackling fireplace: low roar plus random crackles and pops (`Fire` in the
/// original dsp.py). Brown noise below 500 Hz, plus random-sign impulses at a
/// wandering rate of 2..40 per second through a 1.8 kHz high-pass.
pub struct Fire {
    sr: f64,
    rng: Rng,
    brown: Brown,
    lp: Biquad,
    hp: Biquad,
    activity: SmoothRandom,
}

impl Fire {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Fire> {
        let f = Fire {
            sr,
            brown: Brown::new(rng.fork(), sr),
            lp: Biquad::new(Kind::Lp, 500.0, sr, 0.707),
            hp: Biquad::new(Kind::Hp, 1800.0, sr, 0.707),
            activity: SmoothRandom::new(rng.fork(), 2.0, 40.0, 1.5, sr),
            rng,
        };
        Calibrated::new(f, sr, CALIBRATE_S)
    }
}

impl Raw for Fire {
    fn raw(&mut self, out: &mut [f64]) {
        let inv_sr = 1.0 / self.sr;
        for o in out.iter_mut() {
            let roar = self.lp.process(self.brown.sample());
            let rate = self.activity.next_value() * inv_sr;
            let hit = if self.rng.random() < rate {
                self.rng.uniform(-1.0, 1.0) * (self.rng.pareto(2.5).min(3.0) + 0.2)
            } else {
                0.0
            };
            *o = roar * 0.8 + self.hp.process(hit) * 0.5;
        }
    }
}
