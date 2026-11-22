import json
import shutil
import socket
import subprocess
import time

import numpy as np
import pytest

from sleepgen import config
from sleepgen.app import App
from sleepgen.dsp import GENERATORS, TARGET_RMS, make_generator
from sleepgen.engine import Engine, volume_curve
from sleepgen.light import (EFFECT_SUNRISE, Lamp, NullDriver, kelvin_to_rgb,
                            rgb_to_rgbw, sunrise_color)
from sleepgen.mqtt_ha import discovery_configs, handle_command

SR = 48000


@pytest.mark.parametrize("name", [n for n in GENERATORS if n not in ("thunder", "birds")])
def test_generators_are_calibrated_and_finite(name):
    g = make_generator(name, SR, seed=2)
    x = np.concatenate([g.render(1024) for _ in range(47 * 10)])
    assert x.shape[1] == 2 and np.isfinite(x).all()
    rms = np.sqrt(np.mean(x**2))
    assert TARGET_RMS * 0.6 < rms < TARGET_RMS * 1.5, rms


@pytest.mark.parametrize("name", ["thunder", "birds"])
def test_event_generators_fire(name):
    g = make_generator(name, SR, seed=3)
    g.trigger()
    x = np.concatenate([g.render(1024) for _ in range(47 * 3)])
    assert np.abs(x).max() > 0.01 and np.isfinite(x).all()


def test_volume_curve():
    assert volume_curve(0) == 0 and volume_curve(1) == pytest.approx(1)
    vals = [volume_curve(v / 10) for v in range(11)]
    assert vals == sorted(vals)


def run(eng, seconds, block=4096):
    return np.concatenate([eng.render(block) for _ in range(int(seconds * SR / block))])


def test_engine_fades_in_and_stops_with_timer():
    eng = Engine(sr=SR, sources=["rain", "brown"], fade_in_s=2, fade_out_s=4, seed=1)
    eng.apply_preset("x", {"rain": 0.8, "brown": 0.3})
    eng.play()
    x = run(eng, 1)
    assert np.abs(x[:1000]).max() < np.abs(x[-4000:]).max()  # fades in
    eng.set_timer(10 / 60)  # 10 s
    x = run(eng, 11)
    assert not eng.playing and eng.timer_remaining is None
    tail = x[-SR // 2 :]
    assert np.abs(tail).max() < 1e-6  # silent after the timer
    mid = x[2 * SR : 4 * SR]
    assert np.abs(mid).max() > 0.01


def test_engine_never_clips():
    eng = Engine(sr=SR, sources=list(GENERATORS), seed=4)
    eng.apply_preset("all", {k: 1.0 for k in GENERATORS})
    eng.master = 1.0
    eng.play()
    x = run(eng, 5)
    assert np.abs(x).max() <= 1.0


def test_set_level_clears_preset():
    eng = Engine(sr=SR, sources=["rain"], seed=1)
    eng.apply_preset("Regen", {"rain": 0.5})
    eng.set_level("rain", 0.7)
    assert eng.preset is None and eng.state()["levels"]["rain"] == 0.7


def test_colour_helpers():
    r, g, b = kelvin_to_rgb(1800)
    assert r == 1.0 and b < 0.2
    r, g, b, w = rgb_to_rgbw(*kelvin_to_rgb(3000))
    assert w > 0.9
    b0, c0 = sunrise_color(0)
    b1, c1 = sunrise_color(1)
    assert b0 < 0.01 and b1 == pytest.approx(1)
    assert c0[2] < c1[2]  # starts red, ends bluish white


class FakeClock:
    t = 0.0

    def __call__(self):
        return self.t


def test_lamp_sunrise_and_sunset():
    clock = FakeClock()
    lamp = Lamp(NullDriver(4), clock=clock)
    lamp.apply({"state": "ON", "effect": EFFECT_SUNRISE, "transition": 600})
    assert lamp.sunrise_minutes == 10
    early = sum(lamp.frame()[0])
    clock.t = 300
    mid = sum(lamp.frame()[0])
    clock.t = 601
    lamp.frame()
    assert early < mid and lamp.state.effect is None and lamp.state.brightness == 255
    lamp.start_sunset(1)
    clock.t += 61
    lamp.frame()
    assert not lamp.state.on


def test_lamp_ha_commands():
    lamp = Lamp(NullDriver(2))
    lamp.apply({"state": "ON", "brightness": 50, "color_temp_kelvin": 2200})
    assert lamp.ha_state() == {"state": "ON", "brightness": 50, "effect": None,
                               "color_mode": "color_temp", "color_temp_kelvin": 2200}
    lamp.apply({"state": "ON", "color": {"r": 255, "g": 0, "b": 0}})
    assert lamp.ha_state()["color_mode"] == "rgb"
    lamp.apply({"state": "OFF"})
    assert lamp.frame() == [(0.0, 0.0, 0.0, 0.0)] * 2


def make_app(tmp_path):
    cfg = config.load(None)
    cfg["state_file"] = str(tmp_path / "state.json")
    cfg["alarms_file"] = str(tmp_path / "alarms.json")
    return App(cfg, hardware=False)


def test_discovery_payloads(tmp_path):
    app = make_app(tmp_path)
    confs = discovery_configs(app)
    comps = {t.split("/")[1] for t in confs}
    assert {"switch", "select", "number", "light", "button", "sensor"} <= comps
    for topic, p in confs.items():
        assert p["unique_id"].startswith("sleepgen_") and "device" in p
        json.dumps(p)
    light = next(p for t, p in confs.items() if "/light/" in t)
    assert "Sonnenaufgang" in light["effect_list"]


def test_commands(tmp_path):
    app = make_app(tmp_path)
    handle_command(app, "preset/set", "Meer")
    assert app.engine.preset == "Meer" and app.engine.layers["waves"].level > 0
    handle_command(app, "layer/rain/set", "40")
    assert app.engine.layers["rain"].level == 0.4 and app.engine.preset is None
    handle_command(app, "timer/set", "30 min")
    assert app.engine.playing and app.full_state()["timer_option"] == "30 min"
    assert 29.9 < app.full_state()["timer_remaining_min"] <= 30
    handle_command(app, "sound/set", "OFF")
    assert not app.engine.playing and app.full_state()["timer_option"] == "Aus"
    handle_command(app, "master/set", "25")
    assert app.engine.master == 0.25
    handle_command(app, "lamp/set", json.dumps({"state": "ON", "brightness": 10}))
    assert app.lamp.state.on and app.lamp.state.brightness == 10
    handle_command(app, "sunrise/press", "PRESS")
    assert app.lamp.state.effect == EFFECT_SUNRISE


def test_state_roundtrip(tmp_path):
    app = make_app(tmp_path)
    app.apply_preset("Gewitternacht")
    app.engine.play()
    app.save()
    app2 = make_app(tmp_path)
    app2.restore()
    assert app2.engine.preset == "Gewitternacht" and app2.engine.playing


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.mark.skipif(not shutil.which("mosquitto") and not shutil.which("/usr/sbin/mosquitto"),
                    reason="mosquitto not installed")
def test_mqtt_end_to_end(tmp_path):
    import paho.mqtt.client as mqtt

    port = _free_port()
    conf = tmp_path / "m.conf"
    conf.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\n")
    broker = subprocess.Popen([shutil.which("mosquitto") or "/usr/sbin/mosquitto", "-c", str(conf)])
    try:
        time.sleep(0.5)
        app = make_app(tmp_path)
        app.cfg["mqtt"].update(host="127.0.0.1", port=port)
        app.start(audio=False, knob=False)
        import threading

        threading.Thread(target=app.loop, daemon=True).start()

        got = {}
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        c.on_message = lambda cl, u, m: got.__setitem__(m.topic, m.payload.decode())
        c.connect("127.0.0.1", port)
        c.subscribe("#")
        c.loop_start()
        deadline = time.time() + 5
        while "homeassistant/light/sleepgen/lamp/config" not in got and time.time() < deadline:
            time.sleep(0.1)
        assert "homeassistant/light/sleepgen/lamp/config" in got
        assert got.get("sleepgen/sleepgen/status") == "online"

        c.publish("sleepgen/sleepgen/preset/set", "Kaminabend")
        deadline = time.time() + 5
        while time.time() < deadline:
            st = json.loads(got.get("sleepgen/sleepgen/state", "{}"))
            if st.get("preset") == "Kaminabend":
                break
            time.sleep(0.1)
        assert st["preset"] == "Kaminabend"
        c.loop_stop()
        app.stop()
    finally:
        broker.terminate()
        broker.wait()


def test_alarm_rings_and_stops(tmp_path):
    app = make_app(tmp_path)
    app.alarm_minutes = 0.1  # 6 s
    handle_command(app, "alarm/set", "ON")
    assert app.engine.alarm_ringing and app.full_state()["alarm_ringing"]
    x = run(app.engine, 2)
    assert np.abs(x).max() > 0.01  # rings although the sounds are off
    run(app.engine, 5)
    assert not app.engine.alarm_ringing  # stopped by itself after the set duration
    handle_command(app, "alarm/set", "ON")
    app.knob_click()  # a press on the knob stops it
    assert not app.engine.alarm_ringing and not app.engine.playing
    app.knob_click()  # without an alarm a press toggles the sounds
    assert app.engine.playing


@pytest.mark.parametrize("tone", ["Glocken", "Klassisch", "Vogelchor"])
def test_alarm_tones(tone):
    eng = Engine(sr=SR, sources=["rain"], seed=1)
    eng.start_alarm(tone, 1, 1.0)
    x = run(eng, 3)
    assert np.isfinite(x).all() and np.abs(x).max() <= 1.0 and np.abs(x).max() > 0.01


def _tone(path, seconds, freq, amp=0.4, fmt="wav"):
    out = path / f"t{freq}.{fmt}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={seconds}", "-af", f"volume={amp}", str(out)], check=True)
    return out


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg missing")
def test_file_loop_folder_is_seamless_and_normalised(tmp_path, monkeypatch):
    _tone(tmp_path, 20, 300)
    _tone(tmp_path, 20, 700, fmt="mp3")
    monkeypatch.setattr("sleepgen.dsp.tempfile.gettempdir", lambda: str(tmp_path / "cache"))
    gen = make_generator(f"file:{tmp_path}", SR, seed=2)
    out = np.concatenate([gen.render(2400) for _ in range(20 * 60)])  # 60 s
    assert out.shape == (60 * SR, 2)
    assert np.max(np.abs(np.diff(out[:, 0]))) < 0.2  # no clicks at the crossfades
    rms = [np.sqrt(np.mean(out[i:i + SR] ** 2)) for i in range(0, 59 * SR, SR)]
    assert min(rms) > 0.6 * max(rms)
    assert np.sqrt(np.mean(out**2)) == pytest.approx(TARGET_RMS, rel=0.25)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg missing")
def test_engine_own_recording_replaces_synth(tmp_path, monkeypatch):
    f = _tone(tmp_path, 10, 440)
    monkeypatch.setattr("sleepgen.dsp.tempfile.gettempdir", lambda: str(tmp_path / "cache"))
    eng = Engine(sr=SR, sources=[f"rain=file:{f}", "brown"], seed=1)
    assert set(eng.layers) == {"rain", "brown"}
    assert type(eng.layers["rain"].gen).__name__ == "FileLoop"


# ------------------------------------------------------------ offline alarms
from datetime import datetime  # noqa: E402

from sleepgen.alarms import AlarmScheduler, next_ring, prev_ring  # noqa: E402

MON = datetime(2026, 11, 23, 6, 0)  # a Monday


def alarm_dict(**kw):
    a = {"id": "a1", "enabled": True, "time": "06:30", "days": [0, 1, 2, 3, 4], "tone": "bells",
         "duration_min": 5, "volume": 0.6, "sunrise": False, "sunrise_min": 30}
    a.update(kw)
    return a


def make_sched(tmp_path, clock):
    app = make_app(tmp_path)
    sched = AlarmScheduler(app, tmp_path / "alarms.json", now=lambda: clock[0])
    return app, sched


def test_next_and_prev_ring():
    a = alarm_dict()
    assert next_ring(a, MON) == datetime(2026, 11, 23, 6, 30)
    assert next_ring(a, datetime(2026, 11, 27, 7, 0)) == datetime(2026, 11, 30, 6, 30)  # Fri -> Mon
    assert prev_ring(a, datetime(2026, 11, 23, 6, 31)) == datetime(2026, 11, 23, 6, 30)
    assert prev_ring(a, datetime(2026, 11, 29, 12, 0)) == datetime(2026, 11, 27, 6, 30)  # Sun -> Fri


def test_alarm_rings_without_homeassistant(tmp_path):
    clock = [MON]
    app, sched = make_sched(tmp_path, clock)
    sched.set_all({"enabled": True, "alarms": [alarm_dict()]})
    sched.tick(datetime(2026, 11, 23, 6, 29, 59))
    assert not app.engine.alarm_ringing
    clock[0] = datetime(2026, 11, 23, 6, 30, 1)
    sched.tick()
    assert app.engine.alarm_ringing
    app.stop_alarm()
    sched.tick(datetime(2026, 11, 23, 6, 31))  # does not ring twice
    assert not app.engine.alarm_ringing


def test_alarm_survives_restart_and_catches_up_after_power_cut(tmp_path):
    clock = [MON]
    app, sched = make_sched(tmp_path, clock)
    sched.set_all({"enabled": True, "alarms": [alarm_dict()]})
    app2, sched2 = make_sched(tmp_path, clock)  # new process, no MQTT, only the file
    sched2.load()
    assert [a["time"] for a in sched2.alarms] == ["06:30"]
    sched2.tick(datetime(2026, 11, 23, 6, 40))  # back 10 min late: rings
    assert app2.engine.alarm_ringing
    app3, sched3 = make_sched(tmp_path, clock)
    sched3.load()
    sched3.tick(datetime(2026, 11, 23, 8, 0))  # hours late: stays quiet
    assert not app3.engine.alarm_ringing


def test_new_alarm_in_the_past_does_not_ring_at_once(tmp_path):
    clock = [datetime(2026, 11, 23, 6, 32)]
    app, sched = make_sched(tmp_path, clock)
    sched.set_all({"enabled": True, "alarms": [alarm_dict()]})
    sched.tick()
    assert not app.engine.alarm_ringing
    sched.set_all({"enabled": True, "alarms": [alarm_dict()]})  # retained message again: unchanged
    sched.tick()
    assert not app.engine.alarm_ringing


def test_one_off_and_disabled_alarms(tmp_path):
    clock = [MON]
    app, sched = make_sched(tmp_path, clock)
    sched.set_all({"enabled": True, "alarms": [alarm_dict(id="x", days=[]), alarm_dict(id="y", enabled=False)]})
    sched.tick(datetime(2026, 11, 23, 6, 30, 5))
    assert app.engine.alarm_ringing
    snap = {a["id"]: a for a in sched.snapshot()["alarms"]}
    assert snap["x"]["enabled"] is False  # one-off switches itself off
    app.stop_alarm()
    sched.tick(datetime(2026, 11, 24, 6, 30, 5))
    assert not app.engine.alarm_ringing  # "y" is disabled, "x" already rang
    sched.set_all({"enabled": False, "alarms": [alarm_dict(id="z")]})
    sched.tick(datetime(2026, 11, 25, 6, 30, 5))
    assert not app.engine.alarm_ringing  # master switch off


def test_sunrise_starts_ahead_of_the_alarm(tmp_path):
    clock = [MON]
    app, sched = make_sched(tmp_path, clock)
    sched.set_all({"enabled": True, "alarms": [alarm_dict(sunrise=True, sunrise_min=30)]})
    sched.tick(datetime(2026, 11, 23, 5, 59))
    assert app.lamp.state.effect is None
    sched.tick(datetime(2026, 11, 23, 6, 1))
    assert app.lamp.state.effect == EFFECT_SUNRISE and 28 < app.lamp.sunrise_minutes <= 29


def test_alarms_set_over_mqtt_command(tmp_path):
    app = make_app(tmp_path)
    handle_command(app, "alarms/set", json.dumps({"enabled": True, "alarms": [alarm_dict()]}))
    assert app.alarms.snapshot()["alarms"][0]["time"] == "06:30"
