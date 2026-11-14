//! The continuous sound generators (noise colours, fan, rain, leaves, stream,
//! wind, waves, fire). Mono ports of the classes in `device/sleepgen/dsp.py`.
//!
//! The reference renders stereo; here every layer is rendered as one channel
//! with the same per-channel loudness (TARGET_RMS), because the engine output
//! is mono anyway. Grain panning therefore disappears, everything else (grain
//! banks, rates, filters, envelopes, calibration) is the same.

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
/// Rain: a soft bed, the patter on surfaces, and clearly audible single drops.
pub struct Rain {
    sr: f64,
    pink: Pink,
    hp: Biquad,
    lp: Biquad,
    patter: Grains,
    drops: Grains,
    big: Grains,
    intensity: SmoothRandom,
    env: [f64; MAX_BLOCK],
}

impl Rain {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Rain> {
        let patter = (0..48)
            .map(|_| {
                let tau = rng.uniform(0.0003, 0.0012);
                let f = rng.uniform(2500.0, 7000.0);
                tick(&mut rng, sr, tau, f, 1.5)
            })
            .collect();
        let drops = (0..64)
            .map(|_| {
                let (f, d, r) = (
                    rng.uniform(1400.0, 4200.0),
                    rng.uniform(0.012, 0.035),
                    rng.uniform(0.25, 0.9),
                );
                plip(&mut rng, sr, f, d, r, 0.15)
            })
            .collect();
        let big = (0..24)
            .map(|_| {
                let (f, d, r) = (
                    rng.uniform(700.0, 1500.0),
                    rng.uniform(0.03, 0.06),
                    rng.uniform(0.4, 1.2),
                );
                plip(&mut rng, sr, f, d, r, 0.3)
            })
            .collect();
        let r = Rain {
            sr,
            pink: Pink::new(rng.fork()),
            hp: Biquad::new(Kind::Hp, 600.0, sr, 0.707),
            lp: Biquad::new(Kind::Lp, 6500.0, sr, 0.707),
            patter: Grains::new(rng.fork(), patter),
            drops: Grains::new(rng.fork(), drops),
            big: Grains::new(rng.fork(), big),
            intensity: SmoothRandom::new(rng.fork(), 0.7, 1.15, 6.0, sr),
            env: [0.0; MAX_BLOCK],
        };
        Calibrated::new(r, sr, CALIBRATE_S)
    }
}

impl Raw for Rain {
    fn raw(&mut self, out: &mut [f64]) {
        let n = out.len();
        let env = &mut self.env[..n];
        self.intensity.fill(env);
        let e = mean(env);
        for v in out.iter_mut() {
            *v = self.lp.process(self.hp.process(self.pink.sample())) * 0.9;
        }
        let sr = self.sr;
        self.patter.render(out, 1400.0 / sr * e, (0.05, 0.25), 0.0, 0.35);
        self.drops.render(out, 22.0 / sr * e, (0.15, 0.5), 2.5, 0.55);
        self.big.render(out, 2.5 / sr, (0.4, 0.9), 0.0, 0.6);
        for (v, e) in out.iter_mut().zip(env.iter()) {
            *v *= e;
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
/// One wave: swells, curls over, breaks with a bright crash, then washes out.
#[derive(Clone, Copy, Default)]
struct Wave {
    start: u64,
    len: u64,
    rise: f64,
    rise_idx: u64,
    size: f64,
    crash_gain: f64,
    spread: f64, // 1 + |pan|: the louder stereo channel of the reference
    // decay factors per sample (after the break)
    d_sw: f64,
    d_cr: f64,
    d_w1: f64,
    d_w2: f64,
    // running exponentials
    e_sw: f64,
    e_cr: f64,
    e_w1: f64,
    e_w2: f64,
    tau_sw: f64,
    tau_cr: f64,
    tau_w2: f64,
}

/// Ocean surf. Each wave swells, breaks with a bright crash and then washes
/// out as fizzing foam while the next one builds. Waves overlap and vary in size.
pub struct Waves {
    sr: f64,
    rng: Rng,
    pink: Pink,
    brown: Brown,
    wpink: Pink,
    lp: Biquad,
    bed_lp: Biquad,
    hp: Biquad,
    crash_lp: Biquad,
    foam: Grains,
    pos: u64,
    next_start: u64,
    waves: [Wave; 6],
    nwaves: usize,
    ctrl: usize,
    sw: [f64; MAX_BLOCK],
    cr: [f64; MAX_BLOCK],
    cmax: [f64; MAX_BLOCK],
    wa: [f64; MAX_BLOCK],
    wmax: [f64; MAX_BLOCK],
}

impl Waves {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Waves> {
        let foam = (0..64)
            .map(|_| {
                let (f, d, r) = (
                    rng.uniform(2000.0, 6500.0),
                    rng.uniform(0.003, 0.012),
                    rng.uniform(0.5, 2.5),
                );
                plip(&mut rng, sr, f, d, r, 0.4)
            })
            .collect();
        let w = Waves {
            sr,
            pink: Pink::new(rng.fork()),
            brown: Brown::new(rng.fork(), sr),
            wpink: Pink::new(rng.fork()),
            lp: Biquad::new(Kind::Lp, 380.0, sr, 0.6),
            bed_lp: Biquad::new(Kind::Lp, 650.0, sr, 0.6),
            hp: Biquad::new(Kind::Hp, 1800.0, sr, 0.707),
            crash_lp: Biquad::new(Kind::Lp, 500.0, sr, 0.6),
            foam: Grains::new(rng.fork(), foam),
            pos: 0,
            next_start: 0,
            waves: [Wave::default(); 6],
            nwaves: 0,
            ctrl: 0,
            sw: [0.0; MAX_BLOCK],
            cr: [0.0; MAX_BLOCK],
            cmax: [0.0; MAX_BLOCK],
            wa: [0.0; MAX_BLOCK],
            wmax: [0.0; MAX_BLOCK],
            rng,
        };
        Calibrated::new(w, sr, 2.0 * CALIBRATE_S)
    }

    fn new_wave(&mut self, start: u64) {
        let (rng, sr) = (&mut self.rng, self.sr);
        let rise = rng.uniform(2.8, 4.5);
        let fall = rng.uniform(6.0, 9.0);
        let size = rng.uniform(0.55, 1.0);
        let len = ((rise + fall) * sr) as u64;
        let tau_cr = rng.uniform(0.9, 1.6);
        let pan = rng.uniform(-0.45, 0.45);
        let crash_gain = rng.uniform(0.6, 1.0);
        let tau_sw = fall / 2.2;
        let tau_w2 = fall / 2.5;
        let wave = Wave {
            start,
            len,
            rise,
            rise_idx: (rise * sr).ceil() as u64,
            size,
            crash_gain,
            spread: 1.0 + pan.abs(),
            d_sw: (-1.0 / (tau_sw * sr)).exp(),
            d_cr: (-1.0 / (tau_cr * sr)).exp(),
            d_w1: (-1.0 / (0.7 * sr)).exp(),
            d_w2: (-1.0 / (tau_w2 * sr)).exp(),
            tau_sw,
            tau_cr,
            tau_w2,
            ..Default::default()
        };
        if self.nwaves < self.waves.len() {
            self.waves[self.nwaves] = wave;
            self.nwaves += 1;
        }
    }

    fn envelopes(&mut self, n: usize) {
        let sr = self.sr;
        while self.next_start < self.pos + n as u64 {
            let s = self.next_start;
            self.new_wave(s);
            self.next_start += (self.rng.uniform(5.0, 9.5) * sr) as u64;
        }
        self.sw[..n].fill(0.0);
        self.cr[..n].fill(0.0);
        self.cmax[..n].fill(0.0);
        self.wa[..n].fill(0.0);
        self.wmax[..n].fill(0.0);
        let taper_len = 1.5 * sr;
        for w in self.waves[..self.nwaves].iter_mut() {
            let a = self.pos.max(w.start);
            let b = (self.pos + n as u64).min(w.start + w.len);
            for abs in a..b {
                let i = abs - w.start;
                let d = (abs - self.pos) as usize;
                let t = i as f64 / sr;
                let taper = ((w.len - i) as f64 / taper_len).min(1.0) * w.size;
                let (sw, cr, wa);
                if i < w.rise_idx {
                    let x = t / w.rise;
                    sw = x * x;
                    let curl = ((t - (w.rise - 1.3)) / 1.3).clamp(0.0, 1.0);
                    cr = curl * curl * curl.sqrt();
                    wa = 0.0;
                } else {
                    if i == w.rise_idx {
                        let tc = t - w.rise;
                        w.e_sw = (-tc / w.tau_sw).exp();
                        w.e_cr = (-tc / w.tau_cr).exp();
                        w.e_w1 = (-tc / 0.7).exp();
                        w.e_w2 = (-tc / w.tau_w2).exp();
                    } else {
                        w.e_sw *= w.d_sw;
                        w.e_cr *= w.d_cr;
                        w.e_w1 *= w.d_w1;
                        w.e_w2 *= w.d_w2;
                    }
                    sw = w.e_sw;
                    cr = w.e_cr;
                    wa = (1.0 - w.e_w1) * w.e_w2;
                }
                self.sw[d] += sw * taper;
                let c = cr * taper * w.crash_gain;
                self.cr[d] += c;
                self.cmax[d] += c * w.spread;
                self.wa[d] += wa * taper;
                self.wmax[d] += wa * taper * w.spread; // louder channel: drives the foam rate
            }
        }
        // drop finished waves
        let end = self.pos + n as u64;
        let mut k = 0;
        for j in 0..self.nwaves {
            if self.waves[j].start + self.waves[j].len > end {
                self.waves[k] = self.waves[j];
                k += 1;
            }
        }
        self.nwaves = k;
        self.pos = end;
    }
}

impl Raw for Waves {
    fn raw(&mut self, out: &mut [f64]) {
        let n = out.len();
        let sr = self.sr;
        self.envelopes(n);
        let mut wsum = 0.0;
        #[allow(clippy::needless_range_loop)]
        for i in 0..n {
            if self.ctrl == 0 {
                let e = self.cmax[i].min(1.0);
                self.crash_lp.set(Kind::Lp, 500.0 + 7000.0 * e.powf(0.8), sr, 0.6);
                self.ctrl = CTRL_BLOCK;
            }
            self.ctrl -= 1;
            let body = self.lp.process(self.brown.sample());
            let bed = self.bed_lp.process(self.wpink.sample());
            let crash = self.crash_lp.process(self.pink.sample());
            let hiss = self.hp.process(self.rng.noise());
            wsum += self.wmax[i];
            out[i] = bed * 0.35 + body * self.sw[i] * 1.4 + crash * self.cr[i] * 1.6 + hiss * self.wa[i] * 0.18;
        }
        let wmax = wsum / n.max(1) as f64;
        self.foam.render(out, 900.0 / sr * wmax, (0.05, 0.3), 0.0, 0.5);
    }
}

// ------------------------------------------------------------------ fire
/// Fireplace: low roar, soft hiss, and clearly audible crackles and pops.
pub struct Fire {
    sr: f64,
    brown: Brown,
    lp: Biquad,
    pink: Pink,
    hp: Biquad,
    ticks: Grains,
    clusters: Grains,
    pops: Grains,
    activity: SmoothRandom,
}

impl Fire {
    pub fn new(mut rng: Rng, sr: f64) -> Calibrated<Fire> {
        let ticks = (0..48)
            .map(|_| {
                let (tau, f) = (rng.uniform(0.0002, 0.0012), rng.uniform(1800.0, 6500.0));
                tick(&mut rng, sr, tau, f, 0.9)
            })
            .collect();
        let clusters = (0..32)
            .map(|_| {
                let (k, span) = (rng.integers(3, 12) as usize, rng.uniform(0.03, 0.18));
                cluster(&mut rng, sr, k, span, 1500.0, 6000.0)
            })
            .collect();
        let pops = (0..16)
            .map(|_| {
                let (tau, f) = (rng.uniform(0.003, 0.012), rng.uniform(500.0, 1400.0));
                tick(&mut rng, sr, tau, f, 1.4)
            })
            .collect();
        let f = Fire {
            sr,
            brown: Brown::new(rng.fork(), sr),
            lp: Biquad::new(Kind::Lp, 420.0, sr, 0.707),
            pink: Pink::new(rng.fork()),
            hp: Biquad::new(Kind::Hp, 3000.0, sr, 0.707),
            ticks: Grains::new(rng.fork(), ticks),
            clusters: Grains::new(rng.fork(), clusters),
            pops: Grains::new(rng.fork(), pops),
            activity: SmoothRandom::new(rng.fork(), 0.3, 1.0, 2.0, sr),
        };
        Calibrated::new(f, sr, CALIBRATE_S)
    }
}

impl Raw for Fire {
    fn raw(&mut self, out: &mut [f64]) {
        let mut asum = 0.0;
        for o in out.iter_mut() {
            let act = self.activity.next_value();
            asum += act;
            let roar = self.lp.process(self.brown.sample());
            let hiss = self.hp.process(self.pink.sample());
            *o = roar * 0.55 + hiss * 0.08 * act;
        }
        let act = asum / out.len().max(1) as f64;
        let sr = self.sr;
        self.ticks.render(out, 45.0 / sr * act, (0.1, 0.5), 2.5, 0.45);
        self.clusters.render(out, 2.2 / sr * act, (0.3, 0.9), 0.0, 0.55);
        self.pops.render(out, 0.35 / sr, (0.6, 1.0), 0.0, 0.7);
    }
}
