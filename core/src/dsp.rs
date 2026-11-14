//! DSP building blocks: filters, slowly wandering control values, grain
//! scattering and the grain kernels (drops, ticks, crackles, leaf grains).
//!
//! Ported from `device/sleepgen/dsp.py`. Everything here works on mono `f64`
//! blocks of at most [`MAX_BLOCK`] samples and never allocates while rendering.

use crate::rng::Rng;
use std::f64::consts::PI;

/// Loudness every generator is calibrated to (about -18 dBFS RMS).
pub const TARGET_RMS: f64 = 0.125;
/// Largest block a generator is asked to render at once.
pub const MAX_BLOCK: usize = 256;

// ------------------------------------------------------------------ filters
#[derive(Clone, Copy, Debug)]
pub enum Kind {
    Lp,
    Hp,
    Bp,
}

/// Transposed direct-form II biquad.
#[derive(Clone, Copy, Debug, Default)]
pub struct Biquad {
    b0: f64,
    b1: f64,
    b2: f64,
    a1: f64,
    a2: f64,
    z1: f64,
    z2: f64,
}

impl Biquad {
    /// RBJ cookbook coefficients, identical to `_biquad` in dsp.py.
    pub fn new(kind: Kind, f0: f64, sr: f64, q: f64) -> Self {
        let mut b = Biquad::default();
        b.set(kind, f0, sr, q);
        b
    }

    /// Change coefficients but keep the filter state.
    #[inline]
    pub fn set(&mut self, kind: Kind, f0: f64, sr: f64, q: f64) {
        let w0 = 2.0 * PI * f0.min(sr * 0.45) / sr;
        let (sw, cw) = w0.sin_cos();
        let alpha = sw / (2.0 * q);
        let (b0, b1, b2) = match kind {
            Kind::Lp => ((1.0 - cw) / 2.0, 1.0 - cw, (1.0 - cw) / 2.0),
            Kind::Hp => ((1.0 + cw) / 2.0, -(1.0 + cw), (1.0 + cw) / 2.0),
            Kind::Bp => (alpha, 0.0, -alpha),
        };
        let a0 = 1.0 + alpha;
        self.b0 = b0 / a0;
        self.b1 = b1 / a0;
        self.b2 = b2 / a0;
        self.a1 = -2.0 * cw / a0;
        self.a2 = (1.0 - alpha) / a0;
    }

    #[inline(always)]
    pub fn process(&mut self, x: f64) -> f64 {
        let y = self.b0 * x + self.z1;
        self.z1 = self.b1 * x - self.a1 * y + self.z2;
        self.z2 = self.b2 * x - self.a2 * y;
        y
    }

    #[inline]
    pub fn process_block(&mut self, buf: &mut [f64]) {
        for v in buf.iter_mut() {
            *v = self.process(*v);
        }
    }

    pub fn reset(&mut self) {
        self.z1 = 0.0;
        self.z2 = 0.0;
    }
}

/// First-order filter `y = b0 x + b1 x[-1] - a1 y[-1]`.
#[derive(Clone, Copy, Debug, Default)]
pub struct OnePole {
    b0: f64,
    b1: f64,
    a1: f64,
    x1: f64,
    y1: f64,
}

impl OnePole {
    /// `lfilter([1], [1, -p])`: leaky integrator.
    pub fn integrator(p: f64) -> Self {
        OnePole {
            b0: 1.0,
            b1: 0.0,
            a1: -p,
            ..Default::default()
        }
    }

    /// `scipy.signal.butter(1, fc, 'low')` (bilinear transform with prewarping).
    pub fn butter_lp(fc: f64, sr: f64) -> Self {
        let k = (PI * fc.min(sr * 0.45) / sr).tan();
        OnePole {
            b0: k / (1.0 + k),
            b1: k / (1.0 + k),
            a1: (k - 1.0) / (k + 1.0),
            ..Default::default()
        }
    }

    /// Magnitude response at frequency `f`.
    pub fn gain_at(&self, f: f64, sr: f64) -> f64 {
        let w = 2.0 * PI * f / sr;
        let (s, c) = w.sin_cos();
        // H(e^jw) = (b0 + b1 e^-jw) / (1 + a1 e^-jw)
        let nr = self.b0 + self.b1 * c;
        let ni = -self.b1 * s;
        let dr = 1.0 + self.a1 * c;
        let di = -self.a1 * s;
        ((nr * nr + ni * ni) / (dr * dr + di * di)).sqrt()
    }

    #[inline(always)]
    pub fn process(&mut self, x: f64) -> f64 {
        let y = self.b0 * x + self.b1 * self.x1 - self.a1 * self.y1;
        self.x1 = x;
        self.y1 = y;
        y
    }

    pub fn reset(&mut self) {
        self.x1 = 0.0;
        self.y1 = 0.0;
    }
}

/// Paul Kellet style pink noise filter (-3 dB/octave), 3rd order IIR,
/// calibrated so the output has `TARGET_RMS` for unit-variance input.
#[derive(Clone, Debug, Default)]
pub struct PinkFilter {
    z: [f64; 3],
}

impl PinkFilter {
    const B: [f64; 4] = [0.049922035, -0.095993537, 0.050612699, -0.004408786];
    const A: [f64; 4] = [1.0, -2.494956002, 2.017265875, -0.522189400];
    const GAIN: f64 = TARGET_RMS / 0.0864;

    #[inline(always)]
    pub fn process(&mut self, x: f64) -> f64 {
        let (b, a) = (&Self::B, &Self::A);
        let y = b[0] * x + self.z[0];
        self.z[0] = b[1] * x - a[1] * y + self.z[1];
        self.z[1] = b[2] * x - a[2] * y + self.z[2];
        self.z[2] = b[3] * x - a[3] * y;
        y * Self::GAIN
    }
}

// ------------------------------------------------------------------ control
/// Slowly wandering random value in [lo, hi], cosine-interpolated per sample.
#[derive(Clone, Debug)]
pub struct SmoothRandom {
    rng: Rng,
    lo: f64,
    hi: f64,
    period: usize,
    cur: f64,
    nxt: f64,
    pos: usize,
    // rotating phasor for cos(pi * pos / period)
    c: f64,
    s: f64,
    dc: f64,
    ds: f64,
}

impl SmoothRandom {
    /// `rate` is the number of values per second (the sample rate, or a
    /// control rate for block-wise use).
    pub fn new(mut rng: Rng, lo: f64, hi: f64, period_s: f64, rate: f64) -> Self {
        let period = ((period_s * rate) as usize).max(1);
        let cur = rng.uniform(lo, hi);
        let nxt = rng.uniform(lo, hi);
        let d = PI / period as f64;
        SmoothRandom {
            rng,
            lo,
            hi,
            period,
            cur,
            nxt,
            pos: 0,
            c: 1.0,
            s: 0.0,
            dc: d.cos(),
            ds: d.sin(),
        }
    }

    #[inline(always)]
    pub fn next_value(&mut self) -> f64 {
        let v = self.cur + (self.nxt - self.cur) * (0.5 - 0.5 * self.c);
        self.pos += 1;
        if self.pos >= self.period {
            self.pos = 0;
            self.cur = self.nxt;
            self.nxt = self.rng.uniform(self.lo, self.hi);
            self.c = 1.0;
            self.s = 0.0;
        } else {
            let c = self.c * self.dc - self.s * self.ds;
            self.s = self.s * self.dc + self.c * self.ds;
            self.c = c;
        }
        v
    }

    pub fn fill(&mut self, out: &mut [f64]) {
        for v in out.iter_mut() {
            *v = self.next_value();
        }
    }
}

// ------------------------------------------------------------------ grains
/// Scatters short mono kernels over the output. Tails that run past the end of
/// a block are kept in a ring buffer and played in the next block.
pub struct Grains {
    rng: Rng,
    kernels: Vec<Vec<f64>>,
    acc: Vec<f64>,
    mask: usize,
    head: usize,
}

impl Grains {
    pub fn new(rng: Rng, kernels: Vec<Vec<f64>>) -> Self {
        let maxlen = kernels.iter().map(|k| k.len()).max().unwrap_or(1);
        let size = (MAX_BLOCK + maxlen + 1).next_power_of_two();
        Grains {
            rng,
            kernels,
            acc: vec![0.0; size],
            mask: size - 1,
            head: 0,
        }
    }

    /// Add grains to `out`.
    ///
    /// * `rate`: expected grains per sample over this block
    /// * `gain`: uniform gain range per grain
    /// * `heavy` > 0 adds a long tail to the gain distribution
    /// * `mult`: overall output factor
    pub fn render(&mut self, out: &mut [f64], rate: f64, gain: (f64, f64), heavy: f64, mult: f64) {
        let n = out.len();
        let k = self.rng.poisson(rate.max(0.0) * n as f64);
        for _ in 0..k {
            let p = self.rng.integers(0, n as i64) as usize;
            let mut g = self.rng.uniform(gain.0, gain.1);
            if heavy > 0.0 {
                g *= 1.0 + self.rng.pareto(heavy).min(4.0);
            }
            let ki = self.rng.integers(0, self.kernels.len() as i64) as usize;
            let ker = &self.kernels[ki];
            let start = (self.head + p) & self.mask;
            let first = ker.len().min(self.acc.len() - start);
            for (a, &kv) in self.acc[start..start + first].iter_mut().zip(&ker[..first]) {
                *a += kv * g;
            }
            for (a, &kv) in self.acc.iter_mut().zip(&ker[first..]) {
                *a += kv * g;
            }
        }
        for (i, o) in out.iter_mut().enumerate() {
            let j = (self.head + i) & self.mask;
            *o += mult * self.acc[j];
            self.acc[j] = 0.0;
        }
        self.head = (self.head + n) & self.mask;
    }
}

// ------------------------------------------------------------------ kernels
fn normalize(mut k: Vec<f64>) -> Vec<f64> {
    let peak = k.iter().fold(0.0f64, |m, v| m.max(v.abs()));
    if peak > 0.0 {
        for v in k.iter_mut() {
            *v /= peak;
        }
    }
    k
}

/// Water drop: a short sine that glides upwards (the typical 'plip').
pub fn plip(rng: &mut Rng, sr: f64, f0: f64, dur: f64, rise: f64, click: f64) -> Vec<f64> {
    let m = ((dur * sr) as usize).max(8);
    let mut k = Vec::with_capacity(m);
    let mut ph = 0.0;
    for i in 0..m {
        let t = i as f64 / sr;
        let f = f0 * (1.0 + rise * (t / dur).powf(0.7));
        ph += 2.0 * PI * f / sr;
        let env = (1.0 - (-t / 0.0006).exp()) * (-t / (dur / 3.5)).exp();
        k.push(ph.sin() * env);
    }
    if click != 0.0 {
        for (i, v) in k.iter_mut().enumerate() {
            let t = i as f64 / sr;
            *v += click * rng.normal() * (-t / 0.0007).exp();
        }
    }
    normalize(k)
}

/// Short band-passed noise burst: a tap, a crackle or a leaf brushing.
pub fn tick(rng: &mut Rng, sr: f64, tau: f64, f0: f64, q: f64) -> Vec<f64> {
    let dur = tau * 7.0;
    let m = ((dur * sr) as usize).max(8);
    let mut bq = Biquad::new(Kind::Bp, f0, sr, q);
    let k = (0..m)
        .map(|i| {
            let t = i as f64 / sr;
            bq.process(rng.normal() * (-t / tau).exp())
        })
        .collect();
    normalize(k)
}

/// Several crackles in quick succession: the 'tsk-tsk-tsk' of burning wood.
pub fn cluster(rng: &mut Rng, sr: f64, n_ticks: usize, span: f64, f_lo: f64, f_hi: f64) -> Vec<f64> {
    let m = (span * sr) as usize + (0.02 * sr) as usize;
    let mut out = vec![0.0; m];
    for _ in 0..n_ticks {
        let tau = rng.uniform(0.0002, 0.0015);
        let f = rng.uniform(f_lo, f_hi);
        let k = tick(rng, sr, tau, f, 0.9);
        let p = ((rng.uniform(0.0, span) * sr) as usize).min(m);
        let g = rng.uniform(0.3, 1.0);
        for (o, kv) in out[p..].iter_mut().zip(k.iter()) {
            *o += kv * g;
        }
    }
    normalize(out)
}

/// Leaf grain: soft-edged, band-limited noise snippet.
pub fn leaf_grain(rng: &mut Rng, sr: f64, dur: f64, f0: f64, q: f64) -> Vec<f64> {
    let m = ((dur * sr) as usize).max(16);
    let mut bq = Biquad::new(Kind::Bp, f0, sr, q);
    let k = (0..m)
        .map(|i| {
            let w = 0.5 - 0.5 * (2.0 * PI * i as f64 / (m - 1) as f64).cos();
            bq.process(rng.normal() * w.powf(0.6))
        })
        .collect();
    normalize(k)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rms(x: &[f64]) -> f64 {
        (x.iter().map(|v| v * v).sum::<f64>() / x.len() as f64).sqrt()
    }

    #[test]
    fn pink_filter_is_calibrated() {
        let mut r = Rng::new(1);
        let mut f = PinkFilter::default();
        let x: Vec<f64> = (0..400_000).map(|_| f.process(r.noise())).collect();
        let v = rms(&x[10_000..]);
        assert!((v / TARGET_RMS - 1.0).abs() < 0.08, "pink rms {v}");
    }

    #[test]
    fn lowpass_attenuates_highs() {
        let sr = 44100.0;
        let mut lp = Biquad::new(Kind::Lp, 500.0, sr, 0.707);
        let x: Vec<f64> = (0..44100)
            .map(|i| lp.process((2.0 * PI * 8000.0 * i as f64 / sr).sin()))
            .collect();
        assert!(rms(&x[4000..]) < 0.02);
    }

    #[test]
    fn smooth_random_stays_in_range_and_is_continuous() {
        let mut s = SmoothRandom::new(Rng::new(5), 0.3, 1.0, 0.01, 44100.0);
        let mut prev = s.next_value();
        for _ in 0..100_000 {
            let v = s.next_value();
            assert!((0.3 - 1e-9..=1.0 + 1e-9).contains(&v));
            assert!((v - prev).abs() < 0.01);
            prev = v;
        }
    }

    #[test]
    fn kernels_are_normalized() {
        let mut r = Rng::new(2);
        for k in [
            plip(&mut r, 44100.0, 2000.0, 0.02, 0.5, 0.15),
            tick(&mut r, 44100.0, 0.001, 3000.0, 1.2),
            cluster(&mut r, 44100.0, 5, 0.1, 1500.0, 6000.0),
            leaf_grain(&mut r, 44100.0, 0.02, 3000.0, 1.0),
        ] {
            let peak = k.iter().fold(0.0f64, |m, v| m.max(v.abs()));
            assert!((peak - 1.0).abs() < 1e-9);
        }
    }

    #[test]
    fn grains_carry_tails_over_blocks() {
        let k = vec![vec![1.0; 1000]];
        let mut g = Grains::new(Rng::new(1), k);
        let mut total = 0.0;
        let mut out = [0.0; MAX_BLOCK];
        // one block with a huge rate, then silence: tails must still arrive
        g.render(&mut out, 0.02, (1.0, 1.0), 0.0, 1.0);
        total += out.iter().sum::<f64>();
        let grains_energy_first = total;
        for _ in 0..8 {
            out.fill(0.0);
            g.render(&mut out, 0.0, (1.0, 1.0), 0.0, 1.0);
            total += out.iter().sum::<f64>();
        }
        assert!(grains_energy_first > 0.0);
        // every grain is 1000 samples of 1.0
        assert!((total % 1000.0).abs() < 1e-6, "total {total}");
    }
}
