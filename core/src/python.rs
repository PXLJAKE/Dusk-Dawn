//! PyO3 bindings: `dusk_dawn_core.Engine`, exactly the API in
//! integration/CONTRACT.md section 1.

use crate::alarm::ALARM_TONES;
use crate::engine::{Engine as Core, EngineError, SOUNDS};
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::sync::{Mutex, MutexGuard};

fn err(e: EngineError) -> PyErr {
    match e {
        EngineError::UnknownSound(_) => PyKeyError::new_err(e.to_string()),
        EngineError::BadRate(_) => PyValueError::new_err(e.to_string()),
    }
}

/// Procedural sleep-sound engine. Mono, signed 16-bit little-endian output.
///
/// Thread-safe: `render` runs without the GIL, control calls may come from
/// other threads at any time and take effect on the next rendered block.
#[pyclass(name = "Engine", module = "dusk_dawn_core", frozen)]
pub struct PyEngine {
    inner: Mutex<Core>,
    rate: u32,
    buf: Mutex<Vec<u8>>,
}

impl PyEngine {
    fn core(&self) -> MutexGuard<'_, Core> {
        self.inner.lock().unwrap_or_else(|p| p.into_inner())
    }
}

#[pymethods]
impl PyEngine {
    #[new]
    #[pyo3(signature = (rate = 44100, seed = None))]
    fn new(py: Python<'_>, rate: i64, seed: Option<i64>) -> PyResult<Self> {
        if !(8000..=192_000).contains(&rate) {
            return Err(PyValueError::new_err(format!(
                "unsupported sample rate {rate} (8000..=192000)"
            )));
        }
        let rate = rate as u32;
        // building the generators (kernel banks, calibration) takes a moment
        let core = py.detach(|| Core::new(rate, seed.map(|s| s as u64))).map_err(err)?;
        Ok(PyEngine {
            inner: Mutex::new(core),
            rate,
            buf: Mutex::new(Vec::new()),
        })
    }

    /// Sample rate in Hz (read-only).
    #[getter]
    fn rate(&self) -> u32 {
        self.rate
    }

    /// The sound names, in a fixed order.
    fn sounds(&self) -> Vec<&'static str> {
        SOUNDS.to_vec()
    }

    /// Set one layer's level (0..1); the engine smooths it over ~0.5 s.
    fn set_level(&self, sound: &str, level: f64) -> PyResult<()> {
        self.core().set_level(sound, level).map_err(err)
    }

    /// Current level settings of all sounds.
    fn levels<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        for (k, v) in self.core().levels() {
            d.set_item(k, v)?;
        }
        Ok(d)
    }

    /// Master volume 0..1, ramped linearly over `ramp_s` seconds.
    #[pyo3(signature = (volume, ramp_s = 0.0))]
    fn set_master(&self, volume: f64, ramp_s: f64) {
        self.core().set_master(volume, ramp_s)
    }

    /// Current (possibly ramping) master volume.
    #[getter]
    fn master(&self) -> f64 {
        self.core().master()
    }

    /// Ring `tone` ("bells", "classic", "birds") on top of the mix for
    /// `seconds`, rising from 15 % to `volume` over `ramp_s` seconds.
    #[pyo3(signature = (tone, seconds, volume, ramp_s = 40.0))]
    fn start_alarm(&self, py: Python<'_>, tone: &str, seconds: f64, volume: f64, ramp_s: f64) {
        let tone = tone.to_string();
        py.detach(|| self.core().start_alarm(&tone, seconds, volume, ramp_s))
    }

    fn stop_alarm(&self) {
        self.core().stop_alarm()
    }

    #[getter]
    fn alarm_ringing(&self) -> bool {
        self.core().alarm_ringing()
    }

    /// Render `frames` mono samples as signed 16-bit little-endian bytes.
    fn render<'py>(&self, py: Python<'py>, frames: i64) -> PyResult<Bound<'py, PyBytes>> {
        if frames < 0 {
            return Err(PyValueError::new_err("frames must be >= 0"));
        }
        let frames = frames as usize;
        let mut buf = self.buf.lock().unwrap_or_else(|p| p.into_inner());
        let out: &mut Vec<u8> = &mut buf;
        py.detach(|| self.core().render_s16le(frames, out));
        Ok(PyBytes::new(py, &buf))
    }

    fn __repr__(&self) -> String {
        let c = self.core();
        let active: Vec<String> = c
            .levels()
            .filter(|(_, v)| *v > 0.0)
            .map(|(k, v)| format!("{k}={v:.2}"))
            .collect();
        format!(
            "<dusk_dawn_core.Engine rate={} master={:.2} [{}]>",
            self.rate,
            c.master(),
            active.join(", ")
        )
    }
}

#[pymodule]
fn dusk_dawn_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyEngine>()?;
    m.add("SOUNDS", SOUNDS.to_vec())?;
    m.add("ALARM_TONES", ALARM_TONES.to_vec())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
