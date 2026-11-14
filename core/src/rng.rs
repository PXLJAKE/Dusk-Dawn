//! Small, fast, seedable PRNG (xoshiro256++), plus the few distributions the
//! generators need. No external crates, no allocation.

#[derive(Clone, Debug)]
pub struct Rng {
    s: [u64; 4],
    spare: Option<f64>,
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

impl Rng {
    pub fn new(seed: u64) -> Self {
        let mut st = seed;
        let mut s = [0u64; 4];
        for v in s.iter_mut() {
            *v = splitmix64(&mut st);
        }
        if s == [0; 4] {
            s[0] = 1;
        }
        Rng { s, spare: None }
    }

    /// Seed from the clock and a process-wide counter (for `seed=None`).
    pub fn entropy_seed() -> u64 {
        use std::sync::atomic::{AtomicU64, Ordering};
        use std::time::{SystemTime, UNIX_EPOCH};
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let t = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        let c = COUNTER.fetch_add(1, Ordering::Relaxed);
        let local = 0u8;
        let addr = &local as *const u8 as u64;
        let mut st = t ^ c.wrapping_mul(0x9E37_79B9_7F4A_7C15) ^ addr.rotate_left(32);
        splitmix64(&mut st)
    }

    /// Derive an independent child generator (used to seed sub-components).
    pub fn fork(&mut self) -> Rng {
        Rng::new(self.next_u64())
    }

    #[inline(always)]
    pub fn next_u64(&mut self) -> u64 {
        let s = &mut self.s;
        let result = s[0].wrapping_add(s[3]).rotate_left(23).wrapping_add(s[0]);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        result
    }

    /// Uniform in [0, 1).
    #[inline(always)]
    pub fn random(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    /// Uniform in [lo, hi).
    #[inline(always)]
    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.random()
    }

    /// Integer in [lo, hi) like numpy's `integers(lo, hi)`.
    #[inline]
    pub fn integers(&mut self, lo: i64, hi: i64) -> i64 {
        debug_assert!(hi > lo);
        let span = (hi - lo) as u64;
        lo + ((self.next_u64() >> 11) % span) as i64
    }

    /// Exact standard normal (Marsaglia polar method). Used for kernels and
    /// event parameters, not per audio sample.
    pub fn normal(&mut self) -> f64 {
        if let Some(v) = self.spare.take() {
            return v;
        }
        loop {
            let u = 2.0 * self.random() - 1.0;
            let v = 2.0 * self.random() - 1.0;
            let s = u * u + v * v;
            if s > 0.0 && s < 1.0 {
                let m = (-2.0 * s.ln() / s).sqrt();
                self.spare = Some(v * m);
                return u * m;
            }
        }
    }

    /// Cheap unit-variance noise for audio-rate use: the sum of two uniforms
    /// (triangular distribution) from a single 64-bit draw. Spectrally white;
    /// after any filtering it is indistinguishable from Gaussian noise.
    #[inline(always)]
    pub fn noise(&mut self) -> f64 {
        const SCALE: f64 = 1.224_744_871_391_589 / 2_147_483_648.0; // sqrt(1.5) / 2^31
        let r = self.next_u64();
        let a = (r as u32) as f64;
        let b = (r >> 32) as f64;
        (a + b - 4_294_967_295.0) * SCALE
    }

    /// Poisson-distributed count with mean `lam`.
    pub fn poisson(&mut self, lam: f64) -> u32 {
        if lam.is_nan() || lam <= 0.0 {
            return 0;
        }
        if lam < 30.0 {
            let l = (-lam).exp();
            let mut k = 0u32;
            let mut p = self.random();
            while p > l {
                k += 1;
                p *= self.random();
            }
            k
        } else {
            let v = lam + lam.sqrt() * self.normal();
            if v < 0.0 {
                0
            } else {
                (v + 0.5) as u32
            }
        }
    }

    /// numpy's `pareto(a)` (Lomax / Pareto II): `U^(-1/a) - 1`.
    pub fn pareto(&mut self, a: f64) -> f64 {
        let u = 1.0 - self.random(); // (0, 1]
        u.powf(-1.0 / a) - 1.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic() {
        let mut a = Rng::new(42);
        let mut b = Rng::new(42);
        for _ in 0..100 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }

    #[test]
    fn noise_has_unit_variance() {
        let mut r = Rng::new(1);
        let n = 200_000;
        let (mut s, mut s2) = (0.0, 0.0);
        for _ in 0..n {
            let x = r.noise();
            s += x;
            s2 += x * x;
        }
        let mean = s / n as f64;
        let var = s2 / n as f64 - mean * mean;
        assert!(mean.abs() < 0.01, "mean {mean}");
        assert!((var - 1.0).abs() < 0.02, "var {var}");
    }

    #[test]
    fn poisson_mean() {
        let mut r = Rng::new(3);
        for &lam in &[0.5, 5.0, 50.0] {
            let n = 20_000;
            let s: u64 = (0..n).map(|_| r.poisson(lam) as u64).sum();
            let m = s as f64 / n as f64;
            assert!((m - lam).abs() < lam * 0.05 + 0.02, "lam {lam} mean {m}");
        }
    }

    #[test]
    fn normal_moments() {
        let mut r = Rng::new(9);
        let n = 100_000;
        let (mut s, mut s2) = (0.0, 0.0);
        for _ in 0..n {
            let x = r.normal();
            s += x;
            s2 += x * x;
        }
        assert!((s / n as f64).abs() < 0.02);
        assert!((s2 / n as f64 - 1.0).abs() < 0.03);
    }
}
