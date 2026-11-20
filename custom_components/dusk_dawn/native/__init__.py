"""Loader for the Rust sound core (``dusk_dawn_core``).

The Rust module is not on PyPI, so the integration ships compiled builds of it
for Home Assistant OS / the HA container images (Alpine, musl libc)::

    native/x86_64/dusk_dawn_core.abi3.so    (amd64)
    native/aarch64/dusk_dawn_core.abi3.so   (arm64, e.g. Raspberry Pi 4/5)

Both are abi3 builds for CPython >= 3.12, made by ``.github/workflows/wheels.yml``
from ``core/``. Order of preference:

1. an installed ``dusk_dawn_core`` (wheel built from ``core/``),
2. the bundled build for ``platform.machine()``, on musl systems,
3. ``None``: the caller uses the pure-Python engine.

This module only uses the standard library, so it can be tested without
Home Assistant.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import logging
import os
import platform
import sys
import sysconfig
from pathlib import Path
from types import ModuleType
from typing import Any

_LOGGER = logging.getLogger(__name__)

MODULE = "dusk_dawn_core"
NATIVE_DIR = Path(__file__).parent
SO_NAME = f"{MODULE}.abi3.so"
MIN_PYTHON = (3, 12)

# platform.machine() spellings -> directory under native/
ARCH_DIRS = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def is_glibc() -> bool:
    """True on glibc systems; the bundled builds are linked against musl."""
    try:
        return bool(os.confstr("CS_GNU_LIBC_VERSION"))
    except (AttributeError, ValueError, OSError):
        return False


def bundled_path(machine: str | None = None) -> Path | None:
    """Path of the bundled build for this CPU, if there is one."""
    arch = ARCH_DIRS.get((machine or platform.machine()).lower())
    if arch is None:
        return None
    path = NATIVE_DIR / arch / SO_NAME
    return path if path.is_file() else None


def _usable(mod: ModuleType) -> bool:
    return callable(getattr(mod, "Engine", None)) and isinstance(getattr(mod, "SOUNDS", None), list)


def load_bundled(path: Path) -> ModuleType:
    """Load an extension module file as ``dusk_dawn_core``. Raises ImportError."""
    loader = importlib.machinery.ExtensionFileLoader(MODULE, str(path))
    spec = importlib.util.spec_from_file_location(MODULE, path, loader=loader)
    if spec is None:
        raise ImportError(f"cannot create a module spec for {path}")
    mod = importlib.util.module_from_spec(spec)  # dlopen + PyInit_dusk_dawn_core
    loader.exec_module(mod)
    if not _usable(mod):
        raise ImportError(f"{path} does not provide the Engine API")
    sys.modules[MODULE] = mod  # later `import dusk_dawn_core` gets the same module
    return mod


def load_core() -> tuple[ModuleType | None, str]:
    """Find the Rust core. Returns ``(module, origin)``.

    ``origin`` is ``"installed"``, ``"bundled"`` or, with ``module`` None, the
    reason why the Python fallback is used.
    """
    try:
        mod = importlib.import_module(MODULE)
        if _usable(mod):
            return mod, "installed"
        _LOGGER.warning("Installed %s lacks the Engine API, ignoring it", MODULE)
    except ImportError:
        pass

    if sys.version_info < MIN_PYTHON:
        return None, f"Python {platform.python_version()} is older than 3.12"
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        return None, "free-threaded Python cannot load abi3 modules"
    path = bundled_path()
    if path is None:
        return None, f"no bundled build for {platform.machine()}"
    if is_glibc():
        return None, f"bundled build needs musl libc (this system uses {os.confstr('CS_GNU_LIBC_VERSION')})"
    try:
        return load_bundled(path), "bundled"
    except (ImportError, OSError) as err:
        _LOGGER.warning("Could not load the bundled sound core %s: %s", path, err)
        return None, f"loading {path.name} failed: {err}"


def engine_kind(engine: Any) -> str | None:
    """``"rust"`` or ``"python"`` for an engine instance, None without engine."""
    if engine is None:
        return None
    engine = getattr(engine, "inner", engine)  # SampleEngine wraps the real engine
    return "rust" if type(engine).__module__.startswith(MODULE) else "python"
