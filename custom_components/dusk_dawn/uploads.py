"""HTTP upload of own recordings: POST /api/dusk_dawn/upload/{sound}?name=...

The body is the raw file (any audio or video format ffmpeg reads). The panel sends
it with ``hass.fetchWithAuth``; only administrators may upload.
"""

from __future__ import annotations

import logging
import tempfile
from http import HTTPStatus
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN, UPLOAD_URL
from .samples import FILE_SOUNDS, DecodeError, SampleEngine, SoundLibrary

_LOGGER = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 400 * 1024 * 1024
DATA_LIBRARY = f"{DOMAIN}_library"


def get_library(hass: HomeAssistant) -> SoundLibrary:
    return hass.data[DATA_LIBRARY]


def refresh_engines(hass: HomeAssistant, sound: str | None = None) -> None:
    """Tell every spot's engine that the library changed."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        if isinstance(entry.runtime_data.engine, SampleEngine):
            entry.runtime_data.engine.refresh(sound)
        entry.runtime_data.async_library_changed()


class UploadView(HomeAssistantView):
    url = UPLOAD_URL
    name = "api:dusk_dawn:upload"
    requires_auth = True

    async def post(self, request: web.Request, sound: str) -> web.Response:
        hass = request.app[KEY_HASS]
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return web.json_response({"error": "admin required"}, status=HTTPStatus.FORBIDDEN)
        if sound not in FILE_SOUNDS:
            return web.json_response({"error": "unknown sound"}, status=HTTPStatus.NOT_FOUND)
        name = Path(request.query.get("name", "Aufnahme")).stem or "Aufnahme"
        library = get_library(hass)
        size = 0
        with tempfile.NamedTemporaryFile(prefix="dusk_dawn_", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            try:
                async for chunk in request.content.iter_chunked(1 << 20):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        return web.json_response({"error": "file too large (max 400 MB)"},
                                                 status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    await hass.async_add_executor_job(tmp.write, chunk)
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise
        try:
            from . import ffmpeg_binary  # noqa: PLC0415

            entry = await hass.async_add_executor_job(library.add, ffmpeg_binary(hass), sound, tmp_path, name)
        except DecodeError as err:
            return web.json_response({"error": str(err)}, status=HTTPStatus.UNPROCESSABLE_ENTITY)
        finally:
            tmp_path.unlink(missing_ok=True)
        refresh_engines(hass, sound)
        _LOGGER.info("Added sound file %s for %s (%.0f s)", entry.name, sound, entry.duration)
        return web.json_response({"file": entry.info(), "files": library.listing()})
