"""Audio streaming: engine -> ffmpeg (MP3) -> any number of HTTP clients.

One :class:`SpotStream` per spot. The pipeline only runs while at least one
HTTP client (a speaker) is connected:

    render thread --PCM s16le--> ffmpeg stdin
    ffmpeg stdout --MP3--> reader thread --> event loop --> client queues

The render thread keeps the engine close to real time (a small lead so the
speakers can fill their buffer quickly) instead of rendering ahead without
bound. Slow clients lose their oldest chunks rather than growing memory.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import subprocess
import threading
import time
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import BLOCK_S, DOMAIN, STREAM_URL

if TYPE_CHECKING:
    from .runtime import SpotRuntime

_LOGGER = logging.getLogger(__name__)

LEAD_S = 0.6  # how far the encoder may run ahead of the wall clock
CLIENT_QUEUE = 128  # MP3 chunks buffered per client before dropping old ones
IDLE_STOP_S = 10.0  # keep the pipeline a little after the last client left
READ_CHUNK = 4096


class SpotStream:
    """Engine + MP3 encoder with fan-out to HTTP clients for one spot."""

    def __init__(self, hass: HomeAssistant, entry_id: str, engine: Any, ffmpeg_binary: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.engine = engine
        self.ffmpeg_binary = ffmpeg_binary
        self.token = secrets.token_urlsafe(24)
        self._clients: set[asyncio.Queue[bytes | None]] = set()
        self._proc: subprocess.Popen[bytes] | None = None
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._idle_handle: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------ token / url
    def rotate_token(self) -> str:
        """New token: old URLs stop working, connected clients are dropped."""
        self.token = secrets.token_urlsafe(24)
        self.close_clients()
        return self.token

    def check_token(self, token: str) -> bool:
        return bool(token) and secrets.compare_digest(token, self.token)

    @property
    def path(self) -> str:
        return f"{STREAM_URL.format(entry_id=self.entry_id)}?token={self.token}"

    @property
    def running(self) -> bool:
        return self._proc is not None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ------------------------------------------------------------ clients
    @callback
    def add_client(self) -> asyncio.Queue[bytes | None]:
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=CLIENT_QUEUE)
        self._clients.add(queue)
        if self._idle_handle:
            self._idle_handle.cancel()
            self._idle_handle = None
        if self._proc is None:
            self._start_pipeline()
        return queue

    @callback
    def remove_client(self, queue: asyncio.Queue[bytes | None]) -> None:
        self._clients.discard(queue)
        if not self._clients and self._proc is not None and self._idle_handle is None:
            self._idle_handle = self.hass.loop.call_later(IDLE_STOP_S, self._idle_stop)

    @callback
    def close_clients(self) -> None:
        """Tell every connected client to finish its response."""
        for queue in list(self._clients):
            _put_drop_oldest(queue, None)

    @callback
    def _idle_stop(self) -> None:
        self._idle_handle = None
        if not self._clients:
            self.hass.async_create_background_task(self.async_stop_pipeline(), "dusk_dawn stop encoder")

    @callback
    def _fan_out(self, chunk: bytes | None) -> None:
        for queue in list(self._clients):
            _put_drop_oldest(queue, chunk)

    # ------------------------------------------------------------ pipeline
    def encoder_command(self) -> list[str]:
        """ffmpeg: PCM s16le mono 44.1 kHz in, MP3 128k CBR out."""
        return [
            self.ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "s16le", "-ar", str(self.engine.rate), "-ac", "1", "-i", "pipe:0",
            "-codec:a", "libmp3lame", "-b:a", "128k", "-write_xing", "0",
            "-flush_packets", "1", "-f", "mp3", "pipe:1",
        ]

    def _start_pipeline(self) -> None:
        cmd = self.encoder_command()
        _LOGGER.debug("Starting encoder for %s: %s", self.entry_id, cmd)
        try:
            # Popen only forks; it does not wait for the process
            self._proc = subprocess.Popen(  # noqa: S603
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
            )
        except OSError as err:
            _LOGGER.error("Cannot start ffmpeg (%s): %s", self.ffmpeg_binary, err)
            self._proc = None
            self.close_clients()
            return
        self._stop = threading.Event()
        proc, stop, loop = self._proc, self._stop, self.hass.loop
        self._threads = [
            threading.Thread(target=self._render_loop, args=(proc, stop), name=f"dusk_dawn_render_{self.entry_id}",
                             daemon=True),
            threading.Thread(target=self._read_loop, args=(proc, loop), name=f"dusk_dawn_read_{self.entry_id}",
                             daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def _render_loop(self, proc: subprocess.Popen[bytes], stop: threading.Event) -> None:
        """Feed the encoder in 50 ms blocks, paced to the wall clock."""
        rate = self.engine.rate
        block = int(rate * BLOCK_S)
        produced = 0
        start = time.monotonic()
        stdin = proc.stdin
        assert stdin is not None
        try:
            while not stop.is_set():
                ahead = produced / rate - (time.monotonic() - start)
                if ahead > LEAD_S:
                    stop.wait(min(ahead - LEAD_S + BLOCK_S / 2, BLOCK_S))
                    continue
                stdin.write(self.engine.render(block))
                produced += block
        except (BrokenPipeError, OSError, ValueError):
            pass
        except Exception:
            _LOGGER.exception("Sound engine failed")
        finally:
            try:
                stdin.close()
            except OSError:
                pass

    def _read_loop(self, proc: subprocess.Popen[bytes], loop: asyncio.AbstractEventLoop) -> None:
        stdout = proc.stdout
        assert stdout is not None
        fd = stdout.fileno()
        while True:
            try:
                chunk = os.read(fd, READ_CHUNK)
            except OSError:
                break
            if not chunk:
                break
            loop.call_soon_threadsafe(self._fan_out, chunk)
        try:
            loop.call_soon_threadsafe(self._encoder_ended, proc)
        except RuntimeError:  # loop already closed
            pass

    @callback
    def _encoder_ended(self, proc: subprocess.Popen[bytes]) -> None:
        if self._proc is proc and not self._stop.is_set():
            _LOGGER.warning("Encoder for %s ended unexpectedly", self.entry_id)
            self.close_clients()
            self.hass.async_create_background_task(self.async_stop_pipeline(), "dusk_dawn stop encoder")

    async def async_stop_pipeline(self) -> None:
        """Stop the encoder and its threads."""
        if self._idle_handle:
            self._idle_handle.cancel()
            self._idle_handle = None
        proc, threads = self._proc, self._threads
        if proc is None:
            return
        self._proc, self._threads = None, []
        self._stop.set()
        self.close_clients()
        await self.hass.async_add_executor_job(_terminate, proc, threads)

    async def async_shutdown(self) -> None:
        self.close_clients()
        await self.async_stop_pipeline()
        wait = getattr(self.engine, "wait_ready", None)
        if wait is not None:  # fallback engine builds generators in threads
            await self.hass.async_add_executor_job(wait, 10)


def _terminate(proc: subprocess.Popen[bytes], threads: list[threading.Thread]) -> None:
    for thread in threads:
        if thread.name.startswith("dusk_dawn_render"):
            thread.join(2)
    try:
        proc.terminate()
        proc.wait(3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(3)
    except OSError:
        pass
    for thread in threads:
        thread.join(2)
    if proc.stdout:
        proc.stdout.close()


def _put_drop_oldest(queue: asyncio.Queue[bytes | None], item: bytes | None) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(item)


class StreamView(HomeAssistantView):
    """GET /api/dusk_dawn/stream/{entry_id}.mp3?token=..."""

    url = STREAM_URL
    name = "api:dusk_dawn:stream"
    requires_auth = False  # speakers cannot authenticate; the rotating token protects it

    async def get(self, request: web.Request, entry_id: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        runtime: SpotRuntime = entry.runtime_data
        stream = runtime.stream
        if stream is None:  # DIY lamp: plays locally, no stream
            return web.Response(status=HTTPStatus.NOT_FOUND)
        if not stream.check_token(request.query.get("token", "")):
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        response = web.StreamResponse(
            headers={
                "Content-Type": "audio/mpeg",
                "Cache-Control": "no-cache, no-store",
                "icy-name": f"Dusk & Dawn – {runtime.name}",
            }
        )
        response.enable_chunked_encoding()
        await response.prepare(request)
        queue = stream.add_client()
        try:
            while (chunk := await queue.get()) is not None:
                await response.write(chunk)
        except (ConnectionResetError, ConnectionError):
            pass
        finally:
            stream.remove_client(queue)
        return response
