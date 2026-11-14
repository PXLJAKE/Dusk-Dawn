"""The Rust core loader (custom_components/dusk_dawn/native)."""

from __future__ import annotations

import logging
import struct
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dusk_dawn import load_engine_class, native

# ELF e_machine values
EM_X86_64 = 62
EM_AARCH64 = 183
EXPECTED = {"x86_64": EM_X86_64, "aarch64": EM_AARCH64}


def _fake_core(name: str = "dusk_dawn_core") -> ModuleType:
    mod = ModuleType(name)
    mod.Engine = type("Engine", (), {"__module__": name})  # type: ignore[attr-defined]
    mod.SOUNDS = ["rain"]  # type: ignore[attr-defined]
    mod.__file__ = f"/somewhere/{name}.so"
    return mod


@pytest.fixture(autouse=True)
def restore_sys_modules():
    """Undo whatever a test puts into sys.modules['dusk_dawn_core']."""
    missing = object()
    saved = sys.modules.get(native.MODULE, missing)
    yield
    if saved is missing:
        sys.modules.pop(native.MODULE, None)
    else:
        sys.modules[native.MODULE] = saved


@pytest.fixture
def no_installed_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend no dusk_dawn_core wheel is installed."""
    monkeypatch.setitem(sys.modules, native.MODULE, None)  # import raises ImportError


@pytest.mark.parametrize("arch", sorted(EXPECTED))
def test_bundled_builds_are_shipped(arch: str) -> None:
    path = native.NATIVE_DIR / arch / native.SO_NAME
    assert path.is_file()
    data = path.read_bytes()
    assert data[:4] == b"\x7fELF"
    assert data[4] == 2  # 64 bit
    (machine,) = struct.unpack_from("<H", data, 18)
    assert machine == EXPECTED[arch]
    assert b"PyInit_dusk_dawn_core" in data
    assert len(data) < 2_000_000  # stripped, LTO


@pytest.mark.parametrize(
    ("machine", "arch"),
    [("x86_64", "x86_64"), ("AMD64", "x86_64"), ("aarch64", "aarch64"), ("arm64", "aarch64")],
)
def test_bundled_path_per_machine(machine: str, arch: str) -> None:
    assert native.bundled_path(machine) == native.NATIVE_DIR / arch / native.SO_NAME


@pytest.mark.parametrize("machine", ["armv7l", "i686", "riscv64", ""])
def test_no_bundled_build_for_other_machines(machine: str) -> None:
    with patch("platform.machine", return_value=machine):
        assert native.bundled_path(machine or None) is None


def test_installed_wheel_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_core()
    monkeypatch.setitem(sys.modules, native.MODULE, fake)
    with patch.object(native, "load_bundled") as bundled:
        assert native.load_core() == (fake, "installed")
    bundled.assert_not_called()


@pytest.mark.usefixtures("no_installed_core")
def test_bundled_build_on_musl(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_core()
    monkeypatch.setattr(native, "is_glibc", lambda: False)
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    with patch.object(native, "load_bundled", return_value=fake) as bundled:
        assert native.load_core() == (fake, "bundled")
    bundled.assert_called_once_with(native.NATIVE_DIR / "x86_64" / native.SO_NAME)


@pytest.mark.usefixtures("no_installed_core")
def test_glibc_skips_the_musl_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "is_glibc", lambda: True)
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    with patch.object(native, "load_bundled") as bundled:
        core, reason = native.load_core()
    assert core is None
    assert "musl" in reason
    bundled.assert_not_called()


@pytest.mark.usefixtures("no_installed_core")
def test_unknown_machine_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.machine", lambda: "armv7l")
    core, reason = native.load_core()
    assert core is None
    assert "armv7l" in reason


@pytest.mark.usefixtures("no_installed_core")
def test_load_error_falls_back(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(native, "is_glibc", lambda: False)
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    with patch.object(native, "load_bundled", side_effect=ImportError("Exec format error")):
        core, reason = native.load_core()
    assert core is None
    assert "Exec format error" in reason
    assert "Could not load the bundled sound core" in caplog.text


def test_load_bundled_registers_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A loadable extension file becomes sys.modules['dusk_dawn_core']."""
    fake = _fake_core()

    class Loader:
        def __init__(self, name: str, path: str) -> None:
            assert name == native.MODULE

        def create_module(self, spec: object) -> ModuleType:
            return fake

        def exec_module(self, mod: ModuleType) -> None:
            assert mod is fake

    sys.modules.pop(native.MODULE, None)
    monkeypatch.setattr("importlib.machinery.ExtensionFileLoader", Loader)
    so = tmp_path / native.SO_NAME
    so.write_bytes(b"")
    assert native.load_bundled(so) is fake
    assert sys.modules[native.MODULE] is fake


def test_load_bundled_rejects_wrong_module(tmp_path: Path) -> None:
    so = tmp_path / native.SO_NAME
    so.write_bytes(b"not an ELF file")
    sys.modules.pop(native.MODULE, None)
    with pytest.raises(ImportError):
        native.load_bundled(so)
    assert native.MODULE not in sys.modules


@pytest.mark.skipif(native.is_glibc(), reason="the bundled builds are linked against musl")
@pytest.mark.skipif(native.bundled_path() is None, reason="no bundled build for this machine")
def test_real_bundled_build_loads() -> None:
    sys.modules.pop(native.MODULE, None)
    mod = native.load_bundled(native.bundled_path())
    eng = mod.Engine(44100, seed=1)
    eng.set_level("rain", 1.0)
    assert len(eng.render(2205)) == 4410
    assert native.engine_kind(eng) == "rust"


def test_engine_kind() -> None:
    from custom_components.dusk_dawn.engine import Engine  # noqa: PLC0415

    assert native.engine_kind(None) is None
    assert native.engine_kind(Engine(44100, seed=1)) == "python"
    assert native.engine_kind(_fake_core().Engine()) == "rust"


@pytest.mark.rust_engine  # use the real loader, not the conftest patch
def test_load_engine_class_logs_choice(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(native, "load_core", lambda: (None, "no bundled build for testing"))
    from custom_components.dusk_dawn.engine import Engine  # noqa: PLC0415

    assert load_engine_class() == (Engine, "python")
    assert "uses the Python sound engine (no bundled build for testing)" in caplog.text

    fake = _fake_core()
    monkeypatch.setattr(native, "load_core", lambda: (fake, "bundled"))
    assert load_engine_class() == (fake.Engine, "rust")
    assert "uses the Rust sound engine (bundled" in caplog.text


async def test_spot_info_reports_engine(setup_spot: MockConfigEntry) -> None:
    assert setup_spot.runtime_data.spot_info()["engine"] == "python"
