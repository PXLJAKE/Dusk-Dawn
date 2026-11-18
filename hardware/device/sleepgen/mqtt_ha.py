"""Home Assistant integration over MQTT with auto discovery.

After the device connects to the broker, Home Assistant creates one device
"Soundlampe" with these entities (no YAML needed):

* switch      Sounds an/aus
* select      Preset, Sleep-Timer
* number      Lautstärke Sounds, Gerätelautstärke, one slider per sound layer,
              Sonnenaufgang Dauer
* sensor      Timer Restzeit
* light       Lampe (brightness, colour temperature, RGB, effects:
              Sonnenaufgang / Kerze / Einschlafen)
* button      Sonnenaufgang starten
* switch      Licht folgt Sleep-Timer
* switch      Wecker klingelt (an = jetzt klingeln, aus = stoppen)
* select      Weckton; number Weckdauer, Wecklautstärke
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .dsp import LABELS_DE, AlarmTone
from .light import EFFECTS

if TYPE_CHECKING:  # pragma: no cover
    from .app import App

log = logging.getLogger(__name__)

CUSTOM = "Eigene Mischung"
TIMER_OPTIONS = ["Aus", "15 min", "30 min", "45 min", "60 min", "90 min", "120 min"]

ICONS = {
    "rain": "mdi:weather-pouring",
    "waves": "mdi:waves",
    "thunder": "mdi:weather-lightning",
    "wind": "mdi:weather-windy",
    "fire": "mdi:fireplace",
    "birds": "mdi:bird",
    "fan": "mdi:fan",
    "white": "mdi:waveform",
    "pink": "mdi:waveform",
    "brown": "mdi:waveform",
    "leaves": "mdi:leaf",
    "stream": "mdi:waves-arrow-right",
}


def timer_option_minutes(option: str) -> int:
    return 0 if option == "Aus" else int(option.split()[0])


def discovery_configs(app: "App") -> dict[str, dict]:
    """Return {config_topic: payload} for every entity."""
    cfg = app.cfg
    dev_id = cfg["device_id"]
    base = f"{cfg['mqtt']['base_topic']}/{dev_id}"
    prefix = cfg["mqtt"]["discovery_prefix"]
    device = {
        "identifiers": [dev_id],
        "name": cfg["name"],
        "manufacturer": "DIY",
        "model": "SleepGenerator Soundlampe",
        "sw_version": app.version,
    }
    common = {"availability_topic": f"{base}/status", "device": device}
    state = f"{base}/state"
    out: dict[str, dict] = {}

    def add(component: str, obj: str, payload: dict):
        payload = {
            **common,
            "unique_id": f"{dev_id}_{obj}",
            # fixed entity ids (e.g. light.sleepgen_lamp) so the HA package works as is;
            # object_id for older HA versions, default_entity_id for HA >= 2025.10
            "object_id": f"{dev_id}_{obj}",
            "default_entity_id": f"{component}.{dev_id}_{obj}",
            **payload,
        }
        out[f"{prefix}/{component}/{dev_id}/{obj}/config"] = payload

    add("switch", "sound", {
        "name": "Sounds", "icon": "mdi:sleep",
        "command_topic": f"{base}/sound/set", "state_topic": state,
        "value_template": "{{ 'ON' if value_json.playing else 'OFF' }}",
    })
    add("select", "preset", {
        "name": "Preset", "icon": "mdi:playlist-music",
        "command_topic": f"{base}/preset/set", "state_topic": state,
        "options": list(cfg["presets"]) + [CUSTOM],
        "value_template": "{{ value_json.preset if value_json.preset else '%s' }}" % CUSTOM,
    })
    add("select", "timer", {
        "name": "Sleep-Timer", "icon": "mdi:timer-sand",
        "command_topic": f"{base}/timer/set", "state_topic": state,
        "options": TIMER_OPTIONS, "value_template": "{{ value_json.timer_option }}",
    })
    add("sensor", "timer_remaining", {
        "name": "Timer Restzeit", "icon": "mdi:timer-outline", "unit_of_measurement": "min",
        "state_topic": state,
        "value_template": "{{ value_json.timer_remaining_min if value_json.timer_remaining_min is not none else 0 }}",
    })
    add("number", "master", {
        "name": "Lautstärke Sounds", "icon": "mdi:volume-high",
        "command_topic": f"{base}/master/set", "state_topic": state,
        "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%", "mode": "slider",
        "value_template": "{{ (value_json.master * 100) | round(0) }}",
    })
    add("number", "device_volume", {
        "name": "Gerätelautstärke", "icon": "mdi:knob",
        "command_topic": f"{base}/device_volume/set", "state_topic": state,
        "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%", "mode": "slider",
        "value_template": "{{ (value_json.device_volume * 100) | round(0) }}",
    })
    for key in app.engine.layers:
        add("number", f"layer_{key}", {
            "name": LABELS_DE.get(key, key), "icon": ICONS.get(key, "mdi:music-note"),
            "command_topic": f"{base}/layer/{key}/set", "state_topic": state,
            "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%", "mode": "slider",
            "value_template": "{{ (value_json.levels['%s'] * 100) | round(0) }}" % key,
        })
    add("light", "lamp", {
        "name": "Lampe", "icon": "mdi:lamp", "schema": "json",
        "command_topic": f"{base}/lamp/set", "state_topic": f"{base}/lamp/state",
        "brightness": True, "supported_color_modes": ["color_temp", "rgb"],
        "color_temp_kelvin": True, "min_kelvin": 1800, "max_kelvin": 6500,
        "effect": True, "effect_list": EFFECTS,
    })
    add("number", "sunrise_minutes", {
        "name": "Sonnenaufgang Dauer", "icon": "mdi:weather-sunset-up",
        "command_topic": f"{base}/sunrise_minutes/set", "state_topic": state,
        "min": 5, "max": 60, "step": 5, "unit_of_measurement": "min",
        "value_template": "{{ value_json.sunrise_minutes }}",
    })
    add("button", "sunrise", {
        "name": "Sonnenaufgang starten", "icon": "mdi:weather-sunset-up",
        "command_topic": f"{base}/sunrise/press",
    })
    add("switch", "lamp_follows_timer", {
        "name": "Licht folgt Sleep-Timer", "icon": "mdi:weather-night",
        "command_topic": f"{base}/lamp_follows_timer/set", "state_topic": state,
        "value_template": "{{ 'ON' if value_json.lamp_follows_timer else 'OFF' }}",
    })
    add("switch", "alarm", {
        "name": "Wecker klingelt", "icon": "mdi:alarm-bell",
        "command_topic": f"{base}/alarm/set", "state_topic": state,
        "value_template": "{{ 'ON' if value_json.alarm_ringing else 'OFF' }}",
    })
    add("select", "alarm_tone", {
        "name": "Weckton", "icon": "mdi:bell-ring",
        "command_topic": f"{base}/alarm_tone/set", "state_topic": state,
        "options": AlarmTone.TONES, "value_template": "{{ value_json.alarm_tone }}",
    })
    add("number", "alarm_minutes", {
        "name": "Weckdauer", "icon": "mdi:timer-alert-outline",
        "command_topic": f"{base}/alarm_minutes/set", "state_topic": state,
        "min": 1, "max": 60, "step": 1, "unit_of_measurement": "min",
        "value_template": "{{ value_json.alarm_minutes }}",
    })
    add("number", "alarm_volume", {
        "name": "Wecklautstärke", "icon": "mdi:volume-vibrate",
        "command_topic": f"{base}/alarm_volume/set", "state_topic": state,
        "min": 0, "max": 100, "step": 1, "unit_of_measurement": "%", "mode": "slider",
        "value_template": "{{ (value_json.alarm_volume * 100) | round(0) }}",
    })
    return out


def handle_command(app: "App", sub: str, payload: str):
    """Dispatch a command for topic ``<base>/<sub>``."""
    p = payload.strip()
    if sub == "sound/set":
        app.set_playing(p.upper() == "ON")
    elif sub == "preset/set":
        if p != CUSTOM:
            app.apply_preset(p)
    elif sub == "timer/set":
        if p in TIMER_OPTIONS:
            app.set_timer_option(p)
    elif sub == "master/set":
        app.engine.set_master(float(p) / 100)
    elif sub == "device_volume/set":
        app.volume.set(float(p) / 100)
    elif sub.startswith("layer/") and sub.endswith("/set"):
        key = sub.split("/")[1]
        if key in app.engine.layers:
            app.engine.set_level(key, float(p) / 100)
    elif sub == "lamp/set":
        app.lamp.apply(json.loads(p))
    elif sub == "sunrise_minutes/set":
        app.lamp.sunrise_minutes = float(p)
        app.publish_state()
    elif sub == "sunrise/press":
        app.lamp.start_sunrise()
    elif sub == "lamp_follows_timer/set":
        app.lamp_follows_timer = p.upper() == "ON"
        app.publish_state()
    elif sub == "alarm/set":
        if p.upper() == "ON":
            app.start_alarm()
        else:
            app.stop_alarm()
    elif sub == "alarm_tone/set":
        if p in AlarmTone.TONES:
            app.alarm_tone = p
            app.publish_state()
    elif sub == "alarm_minutes/set":
        app.alarm_minutes = float(p)
        app.publish_state()
    elif sub == "alarm_volume/set":
        app.engine.alarm_volume = float(p) / 100
        app.publish_state()
    else:
        log.debug("ignoring %s", sub)


class MqttBridge:
    def __init__(self, app: "App"):
        import paho.mqtt.client as mqtt

        self.app = app
        c = app.cfg["mqtt"]
        self.base = f"{c['base_topic']}/{app.cfg['device_id']}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=app.cfg["device_id"])
        if c.get("username"):
            self.client.username_pw_set(c["username"], c.get("password"))
        self.client.will_set(f"{self.base}/status", "offline", retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(1, 30)
        self.host, self.port = c["host"], int(c["port"])

    def start(self):
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.publish(f"{self.base}/status", "offline", retain=True)
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        log.info("MQTT connected (%s)", reason_code)
        for topic, payload in discovery_configs(self.app).items():
            client.publish(topic, json.dumps(payload), retain=True)
        client.subscribe(f"{self.base}/+/set")
        client.subscribe(f"{self.base}/layer/+/set")
        client.subscribe(f"{self.base}/sunrise/press")
        client.subscribe(f"{self.app.cfg['mqtt']['discovery_prefix']}/status")
        client.publish(f"{self.base}/status", "online", retain=True)
        self.publish()

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", "replace")
        if msg.topic.endswith("/status") and msg.topic.startswith(self.app.cfg["mqtt"]["discovery_prefix"]):
            if payload == "online":  # Home Assistant restarted: announce again
                self._on_connect(client, None, None, "ha-restart")
            return
        sub = msg.topic[len(self.base) + 1 :]
        try:
            handle_command(self.app, sub, payload)
        except Exception:  # noqa: BLE001
            log.exception("bad command %s=%r", msg.topic, payload)

    def publish(self):
        if not self.client.is_connected():
            return
        self.client.publish(f"{self.base}/state", json.dumps(self.app.full_state()), retain=True)
        self.client.publish(f"{self.base}/lamp/state", json.dumps(self.app.lamp.ha_state()), retain=True)
