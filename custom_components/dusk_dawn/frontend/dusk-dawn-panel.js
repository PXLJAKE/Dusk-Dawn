/*
 * Dusk & Dawn – Home Assistant sidebar panel.
 *
 * One self-contained ES module: plain HTMLElement + shadow DOM, no imports, no build.
 * HA sets the properties `hass`, `narrow`, `panel` and `route`.
 * Talks to the integration only through the websocket API in integration/CONTRACT.md §4:
 *   dusk_dawn/spots, dusk_dawn/subscribe, dusk_dawn/command, dusk_dawn/config, dusk_dawn/entities.
 *
 * Rendering: every change builds the whole view as an HTML string; a tiny DOM morph patches
 * the live tree, so focused inputs and sliders that are being dragged are kept.
 */

const VERSION = "0.1.0";

/* ------------------------------------------------------------------ data */

const SOUNDS = ["rain", "waves", "stream", "wind", "thunder", "birds", "leaves", "fire", "fan", "white", "pink", "brown"];
const GROUPS = [
  { key: "water", sounds: ["rain", "waves", "stream"] },
  { key: "weather", sounds: ["wind", "thunder"] },
  { key: "nature", sounds: ["birds", "leaves", "fire"] },
  { key: "noise", sounds: ["fan", "white", "pink", "brown"] },
];
const TONES = ["bells", "classic", "birds"];
const TIMERS = [null, 15, 30, 45, 60, 90];
const BUILTIN_PRESETS = ["Regen", "Gewitternacht", "Meer", "Kaminabend", "Waldmorgen", "Wald", "Ventilator", "Brown Noise", "Pink Noise", "White Noise"];
const PRESET_ICON_CHOICES = ["moon", "rain", "thunder", "waves", "stream", "wind", "leaves", "birds", "fire", "fan", "brown"];
const ICON_TO_MDI = {
  moon: "mdi:weather-night", rain: "mdi:weather-rainy", thunder: "mdi:weather-lightning-rainy", waves: "mdi:waves",
  stream: "mdi:water", wind: "mdi:weather-windy", leaves: "mdi:leaf", birds: "mdi:bird", fire: "mdi:fireplace",
  fan: "mdi:fan", white: "mdi:sine-wave", pink: "mdi:sine-wave", brown: "mdi:sine-wave",
};
const MDI_TO_ICON = {
  "mdi:weather-night": "moon", "mdi:sleep": "moon", "mdi:power-sleep": "moon",
  "mdi:weather-rainy": "rain", "mdi:weather-pouring": "rain", "mdi:umbrella": "rain",
  "mdi:weather-lightning-rainy": "thunder", "mdi:weather-lightning": "thunder", "mdi:flash": "thunder",
  "mdi:waves": "waves", "mdi:wave": "waves", "mdi:beach": "waves",
  "mdi:water": "stream", "mdi:waterfall": "stream",
  "mdi:weather-windy": "wind", "mdi:weather-windy-variant": "wind",
  "mdi:leaf": "leaves", "mdi:forest": "leaves", "mdi:pine-tree": "leaves", "mdi:tree": "leaves",
  "mdi:bird": "birds", "mdi:twitter": "birds",
  "mdi:fireplace": "fire", "mdi:fire": "fire", "mdi:campfire": "fire",
  "mdi:fan": "fan",
  "mdi:sine-wave": "brown", "mdi:waveform": "brown", "mdi:square-wave": "white", "mdi:volume-high": "brown",
};

/* ----------------------------------------------------------------- icons */
// 24×24, stroked unless marked fill. Hand-drawn small set.
const ICONS = {
  play: { d: "M8 5.5v13l10.5-6.5z", fill: true },
  pause: { d: "M7 5h3.6v14H7zM13.4 5H17v14h-3.6z", fill: true },
  stop: { d: "M7 7h10v10H7z", fill: true },
  moon: { d: "M20 14.6A8.2 8.2 0 1 1 9.4 4a6.6 6.6 0 0 0 10.6 10.6z" },
  sunrise: { d: "M3 18h18M6.5 18a5.5 5.5 0 0 1 11 0M12 5v3.5M4.6 9.6l2 2M19.4 9.6l-2 2M8 22h8" },
  alarm: { d: "M12 21a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15zM12 9.5v4l2.6 1.6M3.5 6 6.5 3.5M20.5 6l-3-2.5" },
  sliders: { d: "M5 21v-7M5 10V3M12 21v-9M12 8V3M19 21v-5M19 12V3M2.5 14h5M9.5 8h5M16.5 16h5" },
  sparkle: { d: "M11 3l1.9 5.1L18 10l-5.1 1.9L11 17l-1.9-5.1L4 10l5.1-1.9zM18.5 15l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z" },
  gear: {
    d: "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z",
    fill: true,
  },
  menu: { d: "M3 6.5h18M3 12h18M3 17.5h18" },
  plus: { d: "M12 5v14M5 12h14" },
  close: { d: "M6 6l12 12M18 6 6 18" },
  check: { d: "M5 12.5l4.5 4.5L19 7.5" },
  trash: { d: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" },
  edit: { d: "M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4" },
  speaker: { d: "M4 9.5h3.5L12 6v12l-4.5-3.5H4zM15.5 9.5a3.5 3.5 0 0 1 0 5M18 7a7 7 0 0 1 0 10" },
  bulb: { d: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2h5c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z" },
  timer: { d: "M10 2.5h4M12 13.5l3-3M12 21.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15z" },
  candle: { d: "M9 21h6V11H9zM12 11V8.5M12 3c1.5 1.8 2 2.8 2 3.7a2 2 0 0 1-4 0c0-.9.5-1.9 2-3.7z" },
  fade: { d: "M3 7h18M6 12h12M9 17h6" },
  person: { d: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 21a7.5 7.5 0 0 1 15 0" },
  music: { d: "M9 18V5l11-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" },
  external: { d: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" },
  back: { d: "M15 5l-7 7 7 7" },
  // sounds
  rain: { d: "M7 14.5a4 4 0 0 1-.4-8A5.5 5.5 0 0 1 17 6a4.3 4.3 0 0 1 .5 8.5zM8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5" },
  thunder: { d: "M7 14.5a4 4 0 0 1-.4-8A5.5 5.5 0 0 1 17 6a4.3 4.3 0 0 1 .5 8.5M13 12.5 10.5 17h3.5l-2.5 4.5" },
  waves: { d: "M2 8c1.5 0 2.5-2 4-2s2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2.5-2 4-2M2 13c1.5 0 2.5-2 4-2s2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2.5-2 4-2M2 18c1.5 0 2.5-2 4-2s2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2.5-2 4-2" },
  stream: { d: "M12 3s6 6.4 6 10.8a6 6 0 0 1-12 0C6 9.4 12 3 12 3zM9.5 14.5a2.6 2.6 0 0 0 2.5 2.5" },
  wind: { d: "M3 8h10a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7" },
  birds: { d: "M2.5 10c2-2.2 4-2.2 6 0 2-2.2 4-2.2 6 0M11 16c1.6-1.7 3.2-1.7 4.8 0 1.6-1.7 3.2-1.7 4.7 0" },
  leaves: { d: "M5 19C5 11 10 5 20 5c0 10-6 15-14 15M5 19l8-8" },
  fire: { d: "M12 3c1 3.2 5.5 5.3 5.5 10.3a5.5 5.5 0 0 1-11 0c0-2.3 1.1-3.9 2.2-4.9 0 2 1 3.2 2.3 3.2C11 8.6 10 6.4 12 3z" },
  fan: { d: "M12 13.6a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2zM12 10.4C11 6.3 11.8 3.5 14.2 3.8s1.8 4.2-.9 7.4M13.4 12.8c4 1.2 6.2 3.2 5.3 5.4s-4.5.6-6.1-4.7M10.6 12.6c-3 3-5.8 3.9-6.9 1.8s1.7-4.2 7-3.4" },
  white: { d: "M3 12h2l1.5-6 2 12 2-14 2 16 2-12 1.5 8 1-4H21" },
  pink: { d: "M3 12h3l2-5 3 10 3-12 3 10 2-3h2" },
  brown: { d: "M3 12c2 0 2.2-4 4.5-4s2.6 8 5 8 2.6-8 5-8S19.2 12 21 12" },
};

function icon(name, cls = "") {
  const i = ICONS[name] || ICONS.moon;
  const paint = i.fill
    ? 'fill="currentColor" stroke="none"'
    : 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"';
  return `<svg class="ic ${cls}" viewBox="0 0 24 24" ${paint} aria-hidden="true" focusable="false"><path d="${i.d}"/></svg>`;
}

/* --------------------------------------------------------------- strings */

const STR = {
  de: {
    menu: "Menü öffnen", settings: "Einstellungen", spots: "Schlafplätze", sections: "Bereiche",
    now: "Jetzt", sounds: "Klänge", alarms: "Wecker", auto: "Automatik",
    play: "Klang starten", stop: "Klang stoppen", playing: "Läuft", ready: "Bereit – zum Starten tippen",
    custom_mix: "Eigene Mischung", nothing: "Noch kein Klang gewählt",
    on_speakers: "über {s}", diy: "DIY-Soundlampe", no_speaker: "Kein Lautsprecher gewählt",
    volume: "Lautstärke", timer: "Sleep-Timer", timer_off: "Aus", remaining: "noch {m} min · bis {t}",
    light: "Licht", light_toggle: "Licht ein/aus", brightness: "Helligkeit", kelvin: "Farbtemperatur", effect: "Lichteffekt",
    eff_sunrise: "Sonnenaufgang", eff_candle: "Kerze", eff_fade: "Langsam aus", effect_started: "{e} gestartet",
    no_light: "Diesem Schlafplatz ist kein Licht zugeordnet.",
    good_night: "Gute Nacht", good_night_hint: "Abendklang, warmes gedimmtes Licht und Sleep-Timer in einem Schritt.",
    good_night_done: "Gute Nacht – schlaf gut.",
    next_alarm: "Nächster Wecker", no_alarm: "Kein Wecker aktiv", in_time: "in {d}",
    presets: "Klangwelten", presets_hint: "Antippen zum Übernehmen, darunter fein mischen.",
    mixer: "Mischpult", mixer_hint: "Jede Ebene hat ihre eigene Lautstärke.",
    group_water: "Wasser", group_weather: "Wetter", group_nature: "Natur", group_noise: "Rauschen",
    save_preset: "Als Klangwelt speichern", preset_name: "Name der Klangwelt", preset_icon: "Symbol",
    save: "Speichern", cancel: "Abbrechen", delete: "Löschen", confirm_delete: "Wirklich löschen?",
    delete_preset: "Klangwelt „{n}“ löschen", preset_saved: "Klangwelt „{n}“ gespeichert", mix_empty: "Schiebe mindestens einen Regler hoch, um eine Klangwelt zu speichern.",
    active: "aktiv", off: "aus",
    add_alarm: "Wecker hinzufügen", edit_alarm: "Wecker bearbeiten", new_alarm: "Neuer Wecker", edit_alarm_at: "Wecker {t} bearbeiten",
    alarm_toggle: "Wecker {t} aktiv", time: "Uhrzeit", days: "Wochentage", once_hint: "Ohne Wochentag klingelt der Wecker nur einmal.",
    tone: "Weckton", preview: "Probehören", previewing: "Spiele „{t}“ kurz an …", duration: "Klingeldauer", alarm_volume: "Wecker-Lautstärke",
    sunrise: "Sonnenaufgang", sunrise_desc: "Das Licht wird vorher langsam heller.", sunrise_min: "Vorlauf",
    sunrise_nolight: "Für den Sonnenaufgang braucht der Schlafplatz ein Licht.", enabled: "Wecker aktiv",
    every_day: "Täglich", weekdays: "Werktags", weekends: "Am Wochenende", once: "Einmalig",
    no_alarms: "Noch kein Wecker. Lege einen an, um sanft mit Licht und Klang geweckt zu werden.",
    test_ring: "Probeklingeln", min_long: "{m} min", alarm_saved: "Wecker gespeichert", alarm_deleted: "Wecker gelöscht",
    ringing: "Wecker klingelt", ringing_since: "Guten Morgen! Zeit aufzustehen.", stop_alarm: "Wecker stoppen",
    presence_title: "Anwesenheit", presence_start: "Klang automatisch starten",
    presence_start_desc: "Wenn {s} jemanden erkennt – nur im Zeitfenster.", from: "Von", to: "Bis",
    presence_stop: "Stoppen, wenn niemand mehr da ist", presence_stop_after: "nach {m} min", never: "nie",
    no_presence: "Kein Anwesenheitssensor gewählt.", choose_in_settings: "In den Einstellungen wählen",
    music_title: "Musik", pause_on_music: "Pausieren, wenn Musik läuft", pause_desc: "Hält an, sobald auf dem Lautsprecher etwas anderes gespielt wird, und macht danach weiter.",
    light_title: "Licht", night_light: "Nachtlicht mit Klang", night_light_desc: "Schaltet das Licht gedimmt und warm ein, wenn der Klang startet.",
    name: "Name", speakers: "Lautsprecher", speakers_hint: "Hierhin wird der Klang gestreamt.",
    lights: "Lichter", lights_hint: "Für Nachtlicht und Sonnenaufgang.", presence: "Anwesenheitssensor", presence_hint: "Für den automatischen Start.",
    none: "Keiner", filter: "Filtern …", filter_label: "{x} filtern", saved: "Gespeichert", no_entities: "Keine passenden Entitäten gefunden.",
    diy_hint: "Dieser Schlafplatz nutzt eine DIY-Soundlampe. Der Klang läuft direkt auf der Lampe, nicht als Stream.",
    manage: "Integration verwalten", add_spot_hint: "Weitere Schlafplätze legst du in der Integration an.",
    back: "Zurück", unsaved: "Ungespeicherte Änderungen", selected_n: "{n} ausgewählt",
    empty_title: "Noch kein Schlafplatz",
    empty_text: "Ein Schlafplatz verbindet Lautsprecher, Licht und Anwesenheitssensor eines Zimmers. Lege ihn unter Einstellungen → Geräte & Dienste → Dusk & Dawn an.",
    empty_btn: "Schlafplatz anlegen", empty_nonadmin: "Bitte eine Person mit Admin-Rechten, einen Schlafplatz anzulegen.",
    loading: "Lade …", load_error: "Dusk & Dawn antwortet gerade nicht.", retry: "Erneut versuchen",
    err_cmd: "Das hat nicht geklappt", close: "Schließen", percent: "{n} %",
  },
  en: {
    menu: "Open menu", settings: "Settings", spots: "Sleep spots", sections: "Sections",
    now: "Now", sounds: "Sounds", alarms: "Alarms", auto: "Automation",
    play: "Start sound", stop: "Stop sound", playing: "Playing", ready: "Ready – tap to start",
    custom_mix: "Custom mix", nothing: "No sound chosen yet",
    on_speakers: "on {s}", diy: "DIY sound lamp", no_speaker: "No speaker selected",
    volume: "Volume", timer: "Sleep timer", timer_off: "Off", remaining: "{m} min left · until {t}",
    light: "Light", light_toggle: "Light on/off", brightness: "Brightness", kelvin: "Colour temperature", effect: "Light effect",
    eff_sunrise: "Sunrise", eff_candle: "Candle", eff_fade: "Fade out", effect_started: "{e} started",
    no_light: "No light is assigned to this spot.",
    good_night: "Good night", good_night_hint: "Bedtime sound, warm dimmed light and sleep timer in one step.",
    good_night_done: "Good night – sleep well.",
    next_alarm: "Next alarm", no_alarm: "No alarm set", in_time: "in {d}",
    presets: "Soundscapes", presets_hint: "Tap to apply, then fine-tune below.",
    mixer: "Mixer", mixer_hint: "Every layer has its own volume.",
    group_water: "Water", group_weather: "Weather", group_nature: "Nature", group_noise: "Noise",
    save_preset: "Save as soundscape", preset_name: "Soundscape name", preset_icon: "Icon",
    save: "Save", cancel: "Cancel", delete: "Delete", confirm_delete: "Really delete?",
    delete_preset: "Delete soundscape “{n}”", preset_saved: "Soundscape “{n}” saved", mix_empty: "Raise at least one slider to save a soundscape.",
    active: "active", off: "off",
    add_alarm: "Add alarm", edit_alarm: "Edit alarm", new_alarm: "New alarm", edit_alarm_at: "Edit alarm {t}",
    alarm_toggle: "Alarm {t} enabled", time: "Time", days: "Days", once_hint: "With no day selected the alarm rings once.",
    tone: "Tone", preview: "Preview", previewing: "Playing “{t}” briefly …", duration: "Ring for", alarm_volume: "Alarm volume",
    sunrise: "Sunrise", sunrise_desc: "The light slowly brightens beforehand.", sunrise_min: "Starts before",
    sunrise_nolight: "The sunrise needs a light assigned to this spot.", enabled: "Alarm enabled",
    every_day: "Every day", weekdays: "Weekdays", weekends: "Weekends", once: "Once",
    no_alarms: "No alarm yet. Add one to wake up gently with light and sound.",
    test_ring: "Test ring", min_long: "{m} min", alarm_saved: "Alarm saved", alarm_deleted: "Alarm deleted",
    ringing: "Alarm ringing", ringing_since: "Good morning! Time to get up.", stop_alarm: "Stop alarm",
    presence_title: "Presence", presence_start: "Start sound automatically",
    presence_start_desc: "When {s} detects someone – only within the time window.", from: "From", to: "To",
    presence_stop: "Stop when nobody is there", presence_stop_after: "after {m} min", never: "never",
    no_presence: "No presence sensor selected.", choose_in_settings: "Choose one in settings",
    music_title: "Music", pause_on_music: "Pause while music plays", pause_desc: "Pauses as soon as something else plays on the speaker and resumes afterwards.",
    light_title: "Light", night_light: "Night light with sound", night_light_desc: "Turns the light on dimmed and warm when the sound starts.",
    name: "Name", speakers: "Speakers", speakers_hint: "The sound is streamed to these.",
    lights: "Lights", lights_hint: "Used for night light and sunrise.", presence: "Presence sensor", presence_hint: "Used for the automatic start.",
    none: "None", filter: "Filter …", filter_label: "Filter {x}", saved: "Saved", no_entities: "No matching entities found.",
    diy_hint: "This spot uses a DIY sound lamp. The sound plays on the lamp itself, not as a stream.",
    manage: "Manage integration", add_spot_hint: "Add more sleep spots in the integration.",
    back: "Back", unsaved: "Unsaved changes", selected_n: "{n} selected",
    empty_title: "No sleep spot yet",
    empty_text: "A sleep spot ties together the speaker, light and presence sensor of one room. Add one under Settings → Devices & services → Dusk & Dawn.",
    empty_btn: "Add sleep spot", empty_nonadmin: "Ask an administrator to add a sleep spot.",
    loading: "Loading …", load_error: "Dusk & Dawn is not responding right now.", retry: "Try again",
    err_cmd: "That didn't work", close: "Close", percent: "{n}%",
  },
};

const SOUND_LABELS = {
  de: { rain: "Regen", waves: "Meereswellen", stream: "Bach", wind: "Wind", thunder: "Gewitter", birds: "Vögel", leaves: "Blätterrauschen", fire: "Kaminfeuer", fan: "Ventilator", white: "White Noise", pink: "Pink Noise", brown: "Brown Noise" },
  en: { rain: "Rain", waves: "Ocean waves", stream: "Stream", wind: "Wind", thunder: "Thunderstorm", birds: "Birds", leaves: "Rustling leaves", fire: "Fireplace", fan: "Fan", white: "White noise", pink: "Pink noise", brown: "Brown noise" },
};
const TONE_LABELS = {
  de: { bells: "Glocken", classic: "Klassisch", birds: "Vogelchor" },
  en: { bells: "Bells", classic: "Classic", birds: "Bird chorus" },
};
const DAY_SHORT = { de: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] };
const DAY_LONG = {
  de: ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
  en: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
};
const PRESET_EN = {
  Regen: "Rain", Gewitternacht: "Thunder night", Meer: "Seaside", Kaminabend: "Fireside evening",
  Waldmorgen: "Forest morning", Wald: "Forest", Ventilator: "Fan",
};

/* --------------------------------------------------------------- helpers */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const pad2 = (n) => String(n).padStart(2, "0");
const clone = (o) => (o == null ? o : JSON.parse(JSON.stringify(o)));
const lsGet = (k) => { try { return window.localStorage.getItem(k); } catch (_e) { return null; } };
const lsSet = (k, v) => { try { window.localStorage.setItem(k, v); } catch (_e) { /* private mode */ } };

/** Patch `from`'s children so they match `to`'s children. Keeps nodes (and focus) where possible. */
function morphChildren(from, to) {
  const a = Array.from(from.childNodes);
  const b = Array.from(to.childNodes);
  for (let i = 0; i < b.length; i++) {
    const n = b[i];
    const o = a[i];
    if (!o) { from.appendChild(n.cloneNode(true)); continue; }
    if (
      o.nodeType !== n.nodeType || o.nodeName !== n.nodeName ||
      (o.nodeType === 1 && o.getAttribute("data-key") !== n.getAttribute("data-key"))
    ) { from.replaceChild(n.cloneNode(true), o); continue; }
    if (o.nodeType !== 1) { if (o.nodeValue !== n.nodeValue) o.nodeValue = n.nodeValue; continue; }
    morphEl(o, n);
  }
  for (let i = a.length - 1; i >= b.length; i--) from.removeChild(a[i]);
}

function morphEl(o, n) {
  for (const { name } of Array.from(o.attributes)) if (!n.hasAttribute(name)) o.removeAttribute(name);
  for (const { name, value } of Array.from(n.attributes)) if (o.getAttribute(name) !== value) o.setAttribute(name, value);
  if (o.tagName === "INPUT") {
    if (o.type === "checkbox" || o.type === "radio") {
      const c = n.hasAttribute("checked");
      if (o.checked !== c) o.checked = c;
    } else {
      const v = n.getAttribute("value") ?? "";
      const focused = o.getRootNode().activeElement === o;
      // never rewrite text the user is typing; sliders follow optimistic state anyway
      if (o.value !== v && (!focused || o.type === "range")) o.value = v;
    }
    return;
  }
  morphChildren(o, n);
}

/* ----------------------------------------------------------------- style */

const STYLE = `
:host {
  --bg: #0b1020;
  --bg-glow: #18213f;
  --surface: #141b31;
  --surface-2: #1a2340;
  --sunken: #0e1428;
  --line: #27304f;
  --line-2: #364371;
  --fg: #eeece6;
  --muted: #aeb5ca;
  --faint: #8a93ae;
  --brass: #e3b062;
  --brass-hi: #f4cb84;
  --brass-dim: rgba(227, 176, 98, 0.14);
  --brass-fg: #1e1506;
  --danger: #ff9b8f;
  --danger-bg: rgba(255, 120, 105, 0.12);
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", "URW Palladio L", "P052", Georgia, "DejaVu Serif", serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace;
  --r: 16px;
  display: block;
  min-height: 100%;
  background: var(--bg);
  color: var(--fg);
  font: 15px/1.5 var(--sans);
  -webkit-font-smoothing: antialiased;
  color-scheme: dark;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
button, input { font: inherit; color: inherit; }
button { cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .5; }
:focus { outline: none; }
:focus-visible { outline: 2px solid var(--brass-hi); outline-offset: 2px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.ic { width: 22px; height: 22px; flex: none; display: block; }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.num { font-variant-numeric: tabular-nums; }

.app {
  min-height: 100vh;
  background:
    radial-gradient(1200px 520px at 85% -120px, var(--bg-glow), transparent 70%),
    radial-gradient(800px 400px at -10% -80px, #141b36, transparent 70%),
    var(--bg);
}

/* toolbar */
.toolbar {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; gap: 8px;
  height: 56px; padding: 0 12px 0 16px;
  background: rgba(11, 16, 32, 0.86);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.narrow .toolbar { padding-left: 4px; }
.brand { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; }
.brand .ic { color: var(--brass); width: 24px; height: 24px; }
.brand h1 { margin: 0; font: 600 21px/1 var(--serif); letter-spacing: .01em; white-space: nowrap; }
.iconbtn {
  width: 44px; height: 44px; border-radius: 50%; border: 0; background: transparent; color: var(--muted);
  display: grid; place-items: center; flex: none;
}
.iconbtn:hover { background: var(--surface-2); color: var(--fg); }
.iconbtn[aria-pressed="true"] { color: var(--brass); background: var(--brass-dim); }

/* spot tabs */
.spotbar { display: flex; gap: 6px; padding: 12px 16px 0; overflow-x: auto; scrollbar-width: none; max-width: 1240px; margin: 0 auto; }
.spotbar::-webkit-scrollbar { display: none; }
.spot {
  display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
  padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line); background: transparent; color: var(--muted);
  font-weight: 600; font-size: 14px;
}
.spot:hover { color: var(--fg); border-color: var(--line-2); }
.spot[aria-selected="true"] { background: var(--surface-2); color: var(--fg); border-color: var(--line-2); }
.spot .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--line-2); }
.spot .dot.on { background: var(--brass); box-shadow: 0 0 0 3px var(--brass-dim); }

/* main layout */
.main { max-width: 1240px; margin: 0 auto; padding: 16px 16px 48px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
.cols { display: grid; gap: 20px; align-items: start; }
.wide .cols { grid-template-columns: minmax(340px, 400px) minmax(0, 1fr); }
.stack { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; min-width: 0; }

/* section nav */
.nav {
  display: flex; gap: 4px; padding: 4px; border-radius: 14px; background: var(--sunken); border: 1px solid var(--line);
}
.narrow-layout .nav { position: sticky; top: 64px; z-index: 4; box-shadow: 0 8px 18px -10px rgba(0,0,0,.6); }
.nav button {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-height: 42px; padding: 6px 10px; border-radius: 10px; border: 0; background: transparent; color: var(--muted);
  font-weight: 600; font-size: 14px; white-space: nowrap;
}
.nav button .ic { width: 19px; height: 19px; }
.nav button:hover { color: var(--fg); }
.nav button[aria-selected="true"] { background: var(--surface-2); color: var(--fg); box-shadow: inset 0 0 0 1px var(--line-2); }
.nav button[aria-selected="true"] .ic { color: var(--brass); }
.xs .nav button { flex-direction: column; gap: 2px; font-size: 12px; min-height: 52px; padding: 6px 4px; }

/* cards */
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r);
  padding: 18px; display: grid; gap: 14px; min-width: 0; align-content: start;
}
.card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.card-head > div { display: grid; gap: 2px; }
h2 { margin: 0; font: 600 20px/1.2 var(--serif); letter-spacing: .005em; }
h3 { margin: 0; font-size: 12px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; color: var(--muted); }
.hint { margin: 0; font-size: 13px; color: var(--muted); }
.divider { height: 1px; background: var(--line); margin: 2px 0; }

/* hero (Jetzt) */
.hero {
  background: linear-gradient(180deg, #172042 0%, var(--surface) 62%);
  border-color: var(--line-2); gap: 18px; position: relative; overflow: hidden;
}
.hero::before {
  content: ""; position: absolute; inset: -40% -30% auto auto; width: 320px; height: 320px; border-radius: 50%;
  background: radial-gradient(circle, rgba(227,176,98,.22), transparent 65%); opacity: 0; transition: opacity .8s ease; pointer-events: none;
}
.hero.on::before { opacity: 1; }
.hero > * { position: relative; }
.transport { display: flex; align-items: center; gap: 16px; }
.playbtn {
  width: 84px; height: 84px; border-radius: 50%; border: 0; flex: none;
  background: var(--brass); color: var(--brass-fg); display: grid; place-items: center;
  box-shadow: 0 10px 28px -8px rgba(227,176,98,.55), inset 0 -3px 0 rgba(0,0,0,.15);
  transition: transform .12s ease, background .2s ease;
}
.playbtn:hover { background: var(--brass-hi); }
.playbtn:active { transform: scale(.96); }
.playbtn .ic { width: 34px; height: 34px; }
.playbtn.on { background: var(--surface-2); color: var(--brass-hi); box-shadow: inset 0 0 0 2px var(--brass); }
.now-meta { display: grid; gap: 3px; min-width: 0; }
.now-name { font: 600 25px/1.15 var(--serif); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.now-sub { font-size: 14px; color: var(--muted); }
.now-sub b { color: var(--brass-hi); font-weight: 600; }
.now-where { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); min-width: 0; }
.now-where .ic { width: 16px; height: 16px; }
.now-where span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* fields + sliders */
.field { display: grid; gap: 8px; min-width: 0; }
.field-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; font-size: 14px; }
.field-head label, .field-head .lbl { color: var(--muted); font-weight: 500; }
.field-head output, .field-head .val { white-space: nowrap; font-variant-numeric: tabular-nums; color: var(--fg); font-weight: 600; font-size: 14px; }
input[type=range] {
  -webkit-appearance: none; appearance: none; width: 100%; height: 28px; margin: 0; background: transparent; cursor: pointer;
  --p: 50%;
}
input[type=range]::-webkit-slider-runnable-track {
  height: 6px; border-radius: 3px;
  background: linear-gradient(90deg, var(--brass) 0 var(--p), var(--line-2) var(--p) 100%);
}
input[type=range]::-moz-range-track { height: 6px; border-radius: 3px; background: var(--line-2); }
input[type=range]::-moz-range-progress { height: 6px; border-radius: 3px; background: var(--brass); }
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 22px; height: 22px; margin-top: -8px; border-radius: 50%;
  background: var(--fg); border: 3px solid var(--brass); box-shadow: 0 2px 6px rgba(0,0,0,.4);
}
input[type=range]::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: var(--fg); border: 3px solid var(--brass); }
input[type=range]:focus-visible { outline: none; }
input[type=range]:focus-visible::-webkit-slider-thumb { outline: 2px solid var(--brass-hi); outline-offset: 3px; }
input[type=range]:focus-visible::-moz-range-thumb { outline: 2px solid var(--brass-hi); outline-offset: 3px; }
input[type=range]:disabled { opacity: .45; cursor: not-allowed; }
input[type=range].kelvin::-webkit-slider-runnable-track { background: linear-gradient(90deg, #ff9a3c, #ffc98f 30%, #fff3e2 60%, #e3ecff); }
input[type=range].kelvin::-moz-range-track { background: linear-gradient(90deg, #ff9a3c, #ffc98f 30%, #fff3e2 60%, #e3ecff); }
input[type=range].kelvin::-moz-range-progress { background: transparent; }

/* chips */
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  min-height: 38px; padding: 7px 14px; border-radius: 999px; border: 1px solid var(--line-2);
  background: transparent; color: var(--fg); font-weight: 600; font-size: 14px;
  display: inline-flex; align-items: center; gap: 7px;
}
.chip .ic { width: 18px; height: 18px; color: var(--muted); }
.chip:hover { background: var(--surface-2); }
.chip[aria-pressed="true"] { background: var(--brass); color: var(--brass-fg); border-color: var(--brass); }
.chip[aria-pressed="true"] .ic { color: var(--brass-fg); }
.chips.days, .chips.timer { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
.chips.timer { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.chips.days .chip, .chips.timer .chip { justify-content: center; padding: 7px 0; min-width: 0; }

/* buttons */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-height: 42px; padding: 9px 16px; border-radius: 12px; border: 1px solid var(--line-2);
  background: var(--surface-2); color: var(--fg); font-weight: 600; font-size: 14px; text-decoration: none;
}
.btn .ic { width: 19px; height: 19px; }
.btn:hover { border-color: var(--muted); }
.btn.primary { background: var(--brass); border-color: var(--brass); color: var(--brass-fg); }
.btn.primary:hover { background: var(--brass-hi); }
.btn.ghost { background: transparent; }
.btn.danger { background: transparent; color: var(--danger); border-color: rgba(255,155,143,.4); }
.btn.danger:hover { background: var(--danger-bg); }
.btn.block { width: 100%; }
.btns { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.btns .grow { flex: 1; }
.linkbtn { background: none; border: 0; padding: 0; color: var(--brass-hi); font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }

.goodnight {
  width: 100%; display: flex; align-items: center; gap: 14px; text-align: left;
  padding: 14px 16px; border-radius: 14px; border: 1px solid rgba(227,176,98,.5);
  background: linear-gradient(90deg, rgba(227,176,98,.14), rgba(227,176,98,.04));
}
.goodnight:hover { background: linear-gradient(90deg, rgba(227,176,98,.22), rgba(227,176,98,.08)); }
.goodnight .ic { width: 28px; height: 28px; color: var(--brass-hi); }
.goodnight b { display: block; font: 600 18px/1.2 var(--serif); }
.goodnight > span { display: grid; gap: 2px; }
.goodnight > span > span { font-size: 13px; color: var(--muted); }

.nextalarm {
  display: flex; align-items: center; gap: 12px; width: 100%; text-align: left;
  padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line); background: var(--sunken);
}
.nextalarm:hover { border-color: var(--line-2); }
.nextalarm .ic { color: var(--brass); }
.nextalarm .t { display: grid; gap: 0; min-width: 0; }
.nextalarm small { font-size: 12px; color: var(--muted); }
.nextalarm strong { font-weight: 600; }
.nextalarm .rel { margin-left: auto; font-size: 13px; color: var(--muted); white-space: nowrap; }

/* switch */
.switch {
  position: relative; width: 52px; height: 30px; flex: none; border-radius: 999px; border: 1px solid var(--line-2);
  background: var(--sunken); padding: 0; transition: background .2s ease, border-color .2s ease;
}
.switch::after {
  content: ""; position: absolute; top: 3px; left: 3px; width: 22px; height: 22px; border-radius: 50%;
  background: var(--muted); transition: transform .2s ease, background .2s ease;
}
.switch[aria-checked="true"] { background: var(--brass); border-color: var(--brass); }
.switch[aria-checked="true"]::after { transform: translateX(22px); background: var(--brass-fg); }
.row {
  display: flex; align-items: center; gap: 14px; justify-content: space-between;
}
.row .txt { display: grid; gap: 2px; min-width: 0; }
.row .txt b { font-weight: 600; }
.row .txt span { font-size: 13px; color: var(--muted); }
.row .lead { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; background: var(--surface-2); color: var(--brass); flex: none; }
.row .lead .ic { width: 22px; height: 22px; }
.row .txt { flex: 1; }

/* presets */
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.narrow-layout .tiles, .xs .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.tile { position: relative; }
.tile > .apply {
  width: 100%; height: 100%; display: grid; gap: 10px; align-content: start; text-align: left;
  padding: 14px; border-radius: 14px; border: 1px solid var(--line); background: var(--sunken);
}
.tile > .apply:hover { border-color: var(--line-2); background: var(--surface-2); }
.tile .tico { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; background: var(--surface-2); color: var(--brass); }
.tile .tname { font-weight: 650; font-size: 15px; line-height: 1.25; padding-right: 16px; }
.tile .tsum { font-size: 12px; color: var(--muted); line-height: 1.35; }
.tile > .apply[aria-pressed="true"] { border-color: var(--brass); background: linear-gradient(180deg, rgba(227,176,98,.16), rgba(227,176,98,.04)); }
.tile > .apply[aria-pressed="true"] .tico { background: var(--brass); color: var(--brass-fg); }
.tile .badge { position: absolute; top: 12px; right: 12px; color: var(--brass-hi); }
.tile .badge .ic { width: 18px; height: 18px; }
.tile .del {
  position: absolute; top: 8px; right: 8px; width: 34px; height: 34px; border-radius: 10px; border: 0;
  background: transparent; color: var(--faint); display: grid; place-items: center;
}
.tile .del .ic { width: 18px; height: 18px; }
.tile .del:hover { color: var(--danger); background: var(--danger-bg); }
.tile .del.confirm { width: auto; padding: 0 10px; background: var(--danger); color: #2a0a06; font-size: 12px; font-weight: 700; }

/* mixer */
.groups { display: grid; gap: 18px 28px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.narrow-layout .groups { grid-template-columns: minmax(0, 1fr); }
.group { display: grid; gap: 4px; align-content: start; }
.group h3 { margin-bottom: 4px; }
.layer { display: grid; grid-template-columns: 32px minmax(0, 1fr) 48px; align-items: center; gap: 4px 12px; padding: 4px 0; }
.layer .lic { width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; color: var(--faint); background: var(--sunken); }
.layer .lic .ic { width: 20px; height: 20px; }
.layer.on .lic { color: var(--brass-hi); background: var(--brass-dim); }
.layer .lbody { display: grid; gap: 0; min-width: 0; }
.layer label { font-size: 14px; font-weight: 600; color: var(--muted); }
.layer.on label { color: var(--fg); }
.layer output { font-size: 13px; text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
.layer.on output { color: var(--fg); }

.saveform { display: grid; gap: 14px; padding: 16px; border-radius: 14px; background: var(--sunken); border: 1px solid var(--line); }
.text {
  width: 100%; min-height: 44px; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--line-2);
  background: var(--surface); color: var(--fg);
}
.text::placeholder { color: var(--faint); }
.text:focus-visible { outline: 2px solid var(--brass-hi); outline-offset: 1px; }
input[type=time].text { font: 600 18px var(--mono); width: auto; min-width: 130px; }
.icopick { display: flex; flex-wrap: wrap; gap: 6px; }
.icopick button {
  width: 42px; height: 42px; border-radius: 12px; border: 1px solid var(--line-2); background: var(--surface);
  color: var(--muted); display: grid; place-items: center;
}
.icopick button[aria-pressed="true"] { background: var(--brass); border-color: var(--brass); color: var(--brass-fg); }

/* alarms */
.alarmlist { display: grid; gap: 10px; }
.alarm {
  display: flex; align-items: center; gap: 8px; padding: 6px 14px 6px 6px; border-radius: 14px;
  border: 1px solid var(--line); background: var(--sunken);
}
.alarm .open {
  flex: 1; min-width: 0; display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; column-gap: 16px;
  padding: 10px; border: 0; border-radius: 10px; background: transparent; text-align: left;
}
.alarm .open:hover { background: var(--surface-2); }
.alarm .atime { font: 600 34px/1 var(--serif); font-variant-numeric: tabular-nums; letter-spacing: .01em; }
.alarm .ainfo { display: grid; gap: 2px; min-width: 0; }
.alarm .ainfo b { font-weight: 600; }
.alarm .ainfo span { font-size: 13px; color: var(--muted); }
.alarm.off .atime, .alarm.off .ainfo b { color: var(--faint); }
.alarm .ainfo .tags { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.alarm .ainfo .tags span { display: inline-flex; align-items: center; gap: 4px; }
.alarm .ainfo .tags .ic { width: 15px; height: 15px; }
.empty-note { padding: 22px; border-radius: 14px; border: 1px dashed var(--line-2); color: var(--muted); text-align: center; }

/* banner */
.ring {
  display: flex; align-items: center; gap: 18px; padding: 18px 20px; border-radius: 18px;
  background: linear-gradient(100deg, #f1c27a, #e3a04f 55%, #d9844a); color: #231503;
  box-shadow: 0 14px 40px -12px rgba(227,160,79,.6);
  animation: glow 2.4s ease-in-out infinite;
}
.ring .ic { width: 40px; height: 40px; flex: none; animation: wiggle 1.2s ease-in-out infinite; }
.ring .rt { flex: 1; min-width: 0; display: grid; gap: 2px; }
.ring b { font: 700 24px/1.15 var(--serif); }
.ring .rt > span { font-size: 14px; font-weight: 500; }
.ring button {
  min-height: 56px; min-width: 140px; padding: 10px 26px; border-radius: 999px; border: 0;
  background: #1c1305; color: #fff3df; font-size: 18px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; gap: 10px;
}
.ring button .ic { width: 22px; height: 22px; animation: none; }
.ring button:focus-visible { outline: 3px solid #1c1305; outline-offset: 3px; }
.narrow-layout .ring { flex-wrap: wrap; }
.narrow-layout .ring button { width: 100%; }
@keyframes glow { 50% { box-shadow: 0 14px 56px -8px rgba(241,194,122,.85); } }
@keyframes wiggle { 0%, 60%, 100% { transform: rotate(0); } 10%, 30%, 50% { transform: rotate(-12deg); } 20%, 40% { transform: rotate(12deg); } }

/* settings */
.picklist { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; max-height: 320px; overflow: auto; padding: 4px; border-radius: 12px; border: 1px solid var(--line); background: var(--sunken); }
.pick { display: flex; align-items: center; gap: 12px; padding: 9px 10px; border-radius: 9px; cursor: pointer; }
.pick:hover { background: var(--surface-2); }
.pick input { width: 20px; height: 20px; accent-color: var(--brass); flex: none; margin: 0; cursor: pointer; }
.pick .pt { display: grid; min-width: 0; }
.pick .pt b { font-weight: 600; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pick .pt small { font-size: 12px; color: var(--muted); font-family: var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.settings-grid { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.narrow-layout .settings-grid { grid-template-columns: minmax(0, 1fr); }
.settings-grid .span { grid-column: 1 / -1; }
.savebar {
  position: sticky; bottom: 12px; z-index: 3; display: flex; align-items: center; gap: 12px; justify-content: flex-end;
  padding: 12px 14px; border-radius: 14px; background: rgba(26, 35, 64, .95); border: 1px solid var(--line-2);
  box-shadow: 0 12px 30px -10px rgba(0,0,0,.7);
}
.savebar .grow { flex: 1; color: var(--muted); font-size: 14px; }
.settings-head { display: flex; align-items: center; gap: 8px; min-width: 0; }
.settings-head h2 { min-width: 0; overflow-wrap: anywhere; }
.row.wrap { flex-wrap: wrap; }
.row.wrap .txt { flex: 1 1 220px; }
.savebar .grow { min-width: 0; }
.narrow-layout .savebar .grow { display: none; }
.narrow-layout .savebar .btn { flex: 1; }
.narrow-layout .dfoot .grow { display: none; }
.narrow-layout .dfoot .btn { flex: 1 1 0; padding: 9px 8px; }

/* empty + states */
.center { display: grid; place-items: center; text-align: center; padding: 56px 16px; }
.empty { max-width: 520px; display: grid; gap: 16px; justify-items: center; }
.empty .moon {
  width: 96px; height: 96px; border-radius: 50%; display: grid; place-items: center; color: var(--brass-hi);
  background: radial-gradient(circle at 35% 35%, rgba(244,203,132,.25), rgba(227,176,98,.06) 70%);
  box-shadow: 0 0 60px -10px rgba(227,176,98,.35);
}
.empty .moon .ic { width: 48px; height: 48px; }
.empty h2 { font-size: 26px; }
.empty p { margin: 0; color: var(--muted); }
.stars { position: absolute; inset: 0; pointer-events: none; }

/* dialog */
.scrim {
  position: fixed; inset: 0; z-index: 20; background: rgba(4, 6, 14, .72);
  display: grid; place-items: center; padding: 16px;
}
.dialog {
  width: min(560px, 100%); max-height: calc(100vh - 32px); overflow: auto;
  background: var(--surface); border: 1px solid var(--line-2); border-radius: 20px;
  box-shadow: 0 30px 80px -20px rgba(0,0,0,.8); display: flex; flex-direction: column; overflow: hidden;
}
.dbody { flex: 1 1 auto; overflow: auto; min-height: 0; }
.dhead, .dfoot { flex: none; }
.narrow-layout .scrim { padding: 0; place-items: end stretch; }
.narrow-layout .dialog { width: 100%; max-height: 94vh; border-radius: 20px 20px 0 0; }
.dhead { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 14px 10px 6px 20px; }
.dbody { display: grid; gap: 20px; padding: 8px 20px 20px; }
.dfoot { display: flex; gap: 10px; align-items: center; padding: 14px 20px 18px; border-top: 1px solid var(--line); flex-wrap: wrap; }
.dfoot .grow { flex: 1; }
.tonepick { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

/* toast */
.toast {
  position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 30;
  max-width: calc(100vw - 32px); padding: 12px 18px; border-radius: 12px;
  background: #f1ede3; color: #171c2c; font-weight: 600; font-size: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.5);
}
.toast.err { background: #ffd8d2; color: #3a0d07; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
`;

/* ----------------------------------------------------------------- panel */

class DuskDawnPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._narrow = false;
    this._width = 0;
    this._spots = null; // null = not loaded yet
    this._loadError = null;
    this._active = lsGet("dusk_dawn.spot");
    this._view = lsGet("dusk_dawn.view") || "now";
    this._ov = {}; // optimistic overrides: entry_id -> path -> {value, until}
    this._timers = {}; // debounce timers
    this._gen = 0;
    this._unsub = null;
    this._dlg = null; // alarm dialog draft
    this._saveForm = null; // save-preset draft
    this._confirmDel = null;
    this._entities = null;
    this._cfg = null; // settings draft
    this._filters = {};
    this._toastMsg = null;
    this._lastHtml = "";
    this._raf = 0;

    const style = document.createElement("style");
    style.textContent = STYLE;
    this._root = document.createElement("div");
    this._root.className = "app";
    this.shadowRoot.append(style, this._root);

    const sr = this.shadowRoot;
    sr.addEventListener("click", (e) => this._onClick(e));
    sr.addEventListener("input", (e) => this._onInput(e));
    sr.addEventListener("change", (e) => this._onChange(e));
    sr.addEventListener("keydown", (e) => this._onKey(e));
  }

  /* ---- HA properties */
  set hass(h) {
    const prevLang = this._lang;
    this._hass = h;
    this._lang = String(h?.language || h?.locale?.language || "en").toLowerCase().startsWith("de") ? "de" : "en";
    if (this.isConnected) this._connect();
    if (prevLang !== this._lang) this._lastHtml = "";
    this._schedule();
  }
  get hass() { return this._hass; }
  set narrow(v) { this._narrow = !!v; this._schedule(); }
  get narrow() { return this._narrow; }
  set panel(v) { this._panel = v; }
  get panel() { return this._panel; }
  set route(v) { this._route = v; }
  get route() { return this._route; }

  connectedCallback() {
    if (!this._ro && "ResizeObserver" in window) {
      this._ro = new ResizeObserver((entries) => {
        const w = Math.round(entries[0].contentRect.width);
        if (w !== this._width) { this._width = w; this._schedule(); }
      });
    }
    this._ro?.observe(this);
    this._width = this.getBoundingClientRect().width || window.innerWidth;
    this._tick = window.setInterval(() => this._schedule(), 20000);
    this._connect();
    this._schedule();
  }

  disconnectedCallback() {
    this._gen++;
    if (this._unsub) {
      try { const r = this._unsub(); if (r && r.catch) r.catch(() => {}); } catch (_e) { /* connection gone */ }
    }
    this._unsub = null;
    this._subscribing = false;
    this._ro?.disconnect();
    window.clearInterval(this._tick);
    this._flushAll();
  }

  /* ---- websocket */
  _connect() {
    const hass = this._hass;
    if (!hass || !hass.connection || this._unsub || this._subscribing) return;
    this._subscribing = true;
    const gen = ++this._gen;
    if (this._spots === null || this._loadError) this._loadSpots();
    hass.connection
      .subscribeMessage((msg) => this._onPush(msg), { type: "dusk_dawn/subscribe" })
      .then((unsub) => {
        if (gen !== this._gen || !this.isConnected) { try { unsub(); } catch (_e) { /* ignore */ } return; }
        this._unsub = unsub;
        this._subscribing = false;
      })
      .catch((err) => {
        if (gen !== this._gen) return;
        this._subscribing = false;
        console.warn("[dusk-dawn] subscribe failed", err);
      });
  }

  async _loadSpots() {
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({ type: "dusk_dawn/spots" });
      const spots = (res && res.spots) || [];
      spots.forEach((s) => { s.state = this._overlay(s.entry_id, s.state || {}); });
      this._spots = spots;
      this._loadError = null;
      if (!spots.find((s) => s.entry_id === this._active)) this._active = spots[0]?.entry_id || null;
      if (this._view === "settings" && this._cfg) this._initCfg(true);
    } catch (err) {
      console.warn("[dusk-dawn] load spots failed", err);
      if (this._spots === null) this._loadError = err;
    }
    this._schedule();
  }

  _onPush(msg) {
    if (!msg || !msg.entry_id) return;
    const spot = this._spots?.find((s) => s.entry_id === msg.entry_id);
    if (!spot) { this._loadSpots(); return; }
    spot.state = this._overlay(msg.entry_id, msg.state || {});
    this._schedule();
  }

  async _cmd(action, data = {}, optimistic) {
    const spot = this._spot();
    if (!spot || !this._hass) return null;
    const id = spot.entry_id;
    if (optimistic) { optimistic(spot.state); this._schedule(); }
    try {
      const res = await this._hass.callWS({ type: "dusk_dawn/command", entry_id: id, action, ...data });
      const s = this._spots?.find((x) => x.entry_id === id);
      if (s && res && res.state) { s.state = this._overlay(id, res.state); this._schedule(); }
      return res || {};
    } catch (err) {
      console.warn("[dusk-dawn] command failed", action, err);
      this._toast(`${this._t("err_cmd")}${err && err.message ? `: ${err.message}` : ""}`, true);
      this._loadSpots(); // resync after a failed optimistic change
      return null;
    }
  }

  /* optimistic overrides keep slider values stable while the server catches up */
  _setOv(path, value, ms = 1500) {
    const id = this._active;
    (this._ov[id] ||= {})[path] = { value, until: Date.now() + ms };
  }

  _overlay(id, state) {
    const ov = this._ov[id];
    if (!ov) return state;
    const now = Date.now();
    for (const [path, o] of Object.entries(ov)) {
      if (o.until < now) { delete ov[path]; continue; }
      const parts = path.split(".");
      let t = state;
      for (let i = 0; i < parts.length - 1; i++) t = t[parts[i]] ||= {};
      t[parts[parts.length - 1]] = o.value;
    }
    return state;
  }

  _debounce(key, fn, ms = 150) {
    clearTimeout(this._timers[key]?.t);
    this._timers[key] = { t: setTimeout(() => { delete this._timers[key]; fn(); }, ms), fn };
  }
  _flush(key) {
    const d = this._timers[key];
    if (!d) return;
    clearTimeout(d.t);
    delete this._timers[key];
    d.fn();
  }
  _flushAll() { Object.keys(this._timers).forEach((k) => this._flush(k)); }

  /* ---- helpers */
  _t(key, vars) {
    let s = (STR[this._lang] || STR.en)[key] ?? STR.en[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(v);
    return s;
  }
  _pct(v) { return this._t("percent", { n: Math.round(v) }); }
  _sound(k) { return (SOUND_LABELS[this._lang] || SOUND_LABELS.en)[k] || k; }
  _tone(k) { return (TONE_LABELS[this._lang] || TONE_LABELS.en)[k] || k; }
  _presetName(p) { return this._lang === "en" && PRESET_EN[p.name] ? PRESET_EN[p.name] : p.name; }
  _spot() { return this._spots?.find((s) => s.entry_id === this._active) || null; }
  _isAdmin() { return !!this._hass?.user?.is_admin; }
  _wide() { return !this._narrow && (this._width || window.innerWidth) >= 940; }
  _fmtTime(d) { return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`; }
  _entityName(id) {
    const st = this._hass?.states?.[id];
    const n = st?.attributes?.friendly_name;
    if (n) return n;
    const e = this._entities?.find((x) => x.entity_id === id);
    return e?.name || id;
  }
  _isUserPreset(p) {
    if (p.builtin === true) return false;
    if (p.builtin === false || p.user === true) return true;
    return !BUILTIN_PRESETS.includes(p.name);
  }
  _presetIcon(p) {
    const ic = p.icon;
    if (ic && ICONS[ic]) return ic;
    if (ic && MDI_TO_ICON[ic]) return MDI_TO_ICON[ic];
    const lv = p.levels || {};
    const top = Object.keys(lv).sort((a, b) => lv[b] - lv[a])[0];
    return top && ICONS[top] ? top : "moon";
  }
  _presetSummary(levels) {
    const lv = levels || {};
    return Object.keys(lv).filter((k) => lv[k] > 0.01).sort((a, b) => lv[b] - lv[a]).slice(0, 3).map((k) => this._sound(k)).join(" · ");
  }
  _daysText(days) {
    const d = [...(days || [])].sort((a, b) => a - b);
    const key = d.join(",");
    if (d.length === 7) return this._t("every_day");
    if (key === "0,1,2,3,4") return this._t("weekdays");
    if (key === "5,6") return this._t("weekends");
    if (!d.length) return this._t("once");
    return d.map((i) => DAY_SHORT[this._lang][i]).join(", ");
  }
  _rel(ms) {
    const mins = Math.max(0, Math.round(ms / 60000));
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    const d = this._lang === "de" ? (h ? `${h} Std ${m} min` : `${m} min`) : (h ? `${h} h ${m} min` : `${m} min`);
    return this._t("in_time", { d });
  }
  _toast(msg, err = false) {
    this._toastMsg = { msg, err };
    clearTimeout(this._toastT);
    this._toastT = setTimeout(() => { this._toastMsg = null; this._schedule(); }, 3200);
    this._schedule();
  }
  _setView(v) {
    this._view = v;
    if (v !== "settings") lsSet("dusk_dawn.view", v);
    this._saveForm = null;
    this._schedule();
  }
  _navigate(path) {
    try {
      history.pushState(null, "", path);
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    } catch (_e) {
      window.location.href = path;
    }
  }

  /* ---- render */
  _schedule() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => { this._raf = 0; this._render(); });
  }

  _render() {
    if (!this.isConnected) return;
    const html = this._tpl();
    if (html === this._lastHtml) return;
    this._lastHtml = html;
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    morphChildren(this._root, tpl.content);
    if (this._focusNext) {
      const el = this.shadowRoot.querySelector(this._focusNext);
      this._focusNext = null;
      el?.focus();
    }
  }

  _tpl() {
    const wide = this._wide();
    const xs = (this._width || window.innerWidth) < 420;
    this._root.className = `app ${wide ? "wide" : "narrow-layout"} ${this._narrow ? "narrow" : ""} ${xs ? "xs" : ""}`;
    const spot = this._spot();
    const admin = this._isAdmin();
    const showGear = admin && spot;
    const head = `
      <header class="toolbar">
        ${this._narrow ? `<button class="iconbtn" data-action="menu" aria-label="${esc(this._t("menu"))}">${icon("menu")}</button>` : ""}
        <div class="brand">${icon("moon")}<h1>Dusk &amp; Dawn</h1></div>
        ${showGear ? `<button class="iconbtn" data-action="settings" aria-label="${esc(this._t("settings"))}" aria-pressed="${this._view === "settings"}">${icon("gear")}</button>` : ""}
      </header>`;

    let body;
    if (this._spots === null && !this._loadError) body = `<div class="center"><p class="hint" role="status">${esc(this._t("loading"))}</p></div>`;
    else if (this._spots === null && this._loadError) body = this._tplError();
    else if (!this._spots.length) body = this._tplEmpty();
    else body = this._tplSpot(spot, wide);

    const toast = this._toastMsg
      ? `<div class="toast ${this._toastMsg.err ? "err" : ""}" role="${this._toastMsg.err ? "alert" : "status"}">${esc(this._toastMsg.msg)}</div>`
      : `<div class="sr" role="status"></div>`;
    return head + body + (this._dlg ? this._tplDialog() : "") + toast;
  }

  _tplError() {
    return `<div class="center"><div class="empty">
      <div class="moon">${icon("moon")}</div>
      <h2>${esc(this._t("load_error"))}</h2>
      <button class="btn" data-action="retry">${esc(this._t("retry"))}</button>
    </div></div>`;
  }

  _tplEmpty() {
    const admin = this._isAdmin();
    return `<div class="center" data-key="empty"><div class="empty">
      <div class="moon">${icon("moon")}</div>
      <h2>${esc(this._t("empty_title"))}</h2>
      <p>${esc(this._t("empty_text"))}</p>
      ${admin
        ? `<a class="btn primary" href="/config/integrations/integration/dusk_dawn" data-nav="/config/integrations/integration/dusk_dawn">${icon("plus")}${esc(this._t("empty_btn"))}</a>`
        : `<p class="hint">${esc(this._t("empty_nonadmin"))}</p>`}
    </div></div>`;
  }

  _tplSpot(spot, wide) {
    const st = spot.state || {};
    const spots = this._spots;
    const spotTabs = spots.length > 1
      ? `<div class="spotbar" role="tablist" aria-label="${esc(this._t("spots"))}">${spots.map((s) => `
          <button class="spot" role="tab" data-action="spot" data-id="${esc(s.entry_id)}" aria-selected="${s.entry_id === spot.entry_id}" tabindex="${s.entry_id === spot.entry_id ? 0 : -1}">
            <span class="dot ${s.state?.playing ? "on" : ""}" aria-hidden="true"></span>${esc(s.name)}</button>`).join("")}</div>`
      : "";
    const ring = st.alarm_ringing ? this._tplRing(spot) : "";

    if (this._view === "settings" && this._isAdmin()) {
      return `${spotTabs}<main class="main" data-key="settings">${ring}${this._tplSettings(spot)}</main>`;
    }
    let view = this._view;
    if (view === "settings") view = "now";
    const items = [
      ["now", "play"], ["sounds", "sliders"], ["alarms", "alarm"], ["auto", "sparkle"],
    ].filter(([k]) => !(wide && k === "now"));
    if (wide && view === "now") view = "sounds";
    const nav = `<div class="nav" role="tablist" aria-label="${esc(this._t("sections"))}">${items.map(([k, ic]) => `
        <button role="tab" id="tab-${k}" aria-controls="view" data-action="view" data-view="${k}" aria-selected="${view === k}" tabindex="${view === k ? 0 : -1}">${icon(ic)}<span>${esc(this._t(k))}</span></button>`).join("")}</div>`;
    const viewHtml = `<div id="view" class="stack" role="tabpanel" aria-labelledby="tab-${view}" data-key="view-${view}">${this._tplView(view, spot)}</div>`;

    if (wide) {
      return `${spotTabs}<main class="main">${ring}<div class="cols">
          <div class="left stack">${this._tplNow(spot)}</div>
          <div class="stack">${nav}${viewHtml}</div>
        </div></main>`;
    }
    return `${spotTabs}<main class="main">${ring}${nav}${viewHtml}</main>`;
  }

  _tplView(view, spot) {
    if (view === "now") return this._tplNow(spot);
    if (view === "sounds") return this._tplSounds(spot);
    if (view === "alarms") return this._tplAlarms(spot);
    return this._tplAuto(spot);
  }

  _tplRing(spot) {
    const st = spot.state;
    const now = this._fmtTime(new Date());
    return `<section class="ring" role="alert" aria-live="assertive">
      ${icon("alarm")}
      <div class="rt"><b>${esc(this._t("ringing"))} · <span class="num">${now}</span></b><span>${esc(this._t("ringing_since"))}${this._spots.length > 1 ? ` · ${esc(spot.name)}` : ""}</span></div>
      <button data-action="stop_alarm" aria-label="${esc(this._t("stop_alarm"))}">${icon("stop")}${esc(this._lang === "de" ? "Stopp" : "Stop")}</button>
    </section>`;
  }

  /* ---- Jetzt */
  _tplNow(spot) {
    const st = spot.state || {};
    const playing = !!st.playing;
    const presets = st.presets || [];
    const preset = presets.find((p) => p.id === st.preset);
    const anyLevel = Object.values(st.levels || {}).some((v) => v > 0.01);
    const name = preset ? this._presetName(preset) : anyLevel ? this._t("custom_mix") : this._t("nothing");
    const vol = Math.round((st.volume ?? 0.5) * 100);
    const tm = st.timer || {};
    let sub = playing ? this._t("playing") : this._t("ready");
    if (playing && tm.ends_at) {
      const end = new Date(tm.ends_at);
      const left = Math.max(0, Math.ceil((end - Date.now()) / 60000));
      sub = `${this._t("playing")} · <b>${esc(this._t("remaining", { m: left, t: this._fmtTime(end) }))}</b>`;
    } else sub = esc(sub);
    const where = spot.diy_device
      ? this._t("diy")
      : (spot.speakers || []).length
        ? this._t("on_speakers", { s: spot.speakers.map((e) => this._entityName(e)).join(", ") })
        : this._t("no_speaker");

    const timerChips = TIMERS.map((m) => {
      const sel = (tm.minutes ?? null) === m;
      return `<button class="chip" data-action="timer" data-min="${m ?? ""}" aria-pressed="${sel}">${m == null ? esc(this._t("timer_off")) : `${m}`}</button>`;
    }).join("");

    const hasLight = (spot.lights || []).length || spot.diy_device;
    const li = st.light || {};
    const bri = Math.round(((li.brightness ?? 128) / 255) * 100);
    const kel = li.kelvin ?? 2200;
    const lightHtml = hasLight
      ? `<div class="divider"></div>
        <div class="row">
          <div class="txt"><b>${esc(this._t("light"))}</b>${(spot.lights || []).length ? `<span>${esc(spot.lights.map((e) => this._entityName(e)).join(", "))}</span>` : ""}</div>
          <button class="switch" role="switch" data-action="light_toggle" aria-checked="${!!li.on}" aria-label="${esc(this._t("light_toggle"))}"></button>
        </div>
        <div class="field">
          <div class="field-head"><label for="bri">${esc(this._t("brightness"))}</label><output for="bri">${esc(this._pct(bri))}</output></div>
          <input type="range" id="bri" min="1" max="100" step="1" value="${bri}" style="--p:${bri}%" data-input="brightness">
        </div>
        <div class="field">
          <div class="field-head"><label for="kel">${esc(this._t("kelvin"))}</label><output for="kel">${kel} K</output></div>
          <input type="range" class="kelvin" id="kel" min="2000" max="6500" step="50" value="${kel}" data-input="kelvin">
        </div>
        <div class="field">
          <div class="field-head"><span class="lbl" id="eff-l">${esc(this._t("effect"))}</span></div>
          <div class="chips" role="group" aria-labelledby="eff-l">
            <button class="chip" data-action="effect" data-effect="sunrise">${icon("sunrise")}${esc(this._t("eff_sunrise"))}</button>
            <button class="chip" data-action="effect" data-effect="candle">${icon("candle")}${esc(this._t("eff_candle"))}</button>
            <button class="chip" data-action="effect" data-effect="fade">${icon("fade")}${esc(this._t("eff_fade"))}</button>
          </div>
        </div>`
      : "";

    let next = "";
    if (st.next_alarm) {
      const d = new Date(st.next_alarm);
      next = `<button class="nextalarm" data-action="view" data-view="alarms">
        ${icon("alarm")}
        <span class="t"><small>${esc(this._t("next_alarm"))}</small><strong>${esc(DAY_LONG[this._lang][(d.getDay() + 6) % 7])}, <span class="num">${this._fmtTime(d)}</span></strong></span>
        <span class="rel">${esc(this._rel(d - Date.now()))}</span></button>`;
    } else {
      next = `<button class="nextalarm" data-action="view" data-view="alarms">${icon("alarm")}<span class="t"><small>${esc(this._t("next_alarm"))}</small><strong>${esc(this._t("no_alarm"))}</strong></span></button>`;
    }

    return `<section class="card hero ${playing ? "on" : ""}" aria-label="${esc(this._t("now"))}">
      <div class="transport">
        <button class="playbtn ${playing ? "on" : ""}" data-action="toggle" aria-label="${esc(this._t(playing ? "stop" : "play"))}" aria-pressed="${playing}">${icon(playing ? "pause" : "play")}</button>
        <div class="now-meta">
          <span class="now-name">${esc(name)}</span>
          <span class="now-sub">${sub}</span>
          <span class="now-where">${icon("speaker")}<span>${esc(where)}</span></span>
        </div>
      </div>
      <div class="field">
        <div class="field-head"><label for="vol">${esc(this._t("volume"))}</label><output for="vol">${esc(this._pct(vol))}</output></div>
        <input type="range" id="vol" min="0" max="100" step="1" value="${vol}" style="--p:${vol}%" data-input="volume">
      </div>
      <div class="field">
        <div class="field-head"><span class="lbl" id="timer-l">${esc(this._t("timer"))}</span><span class="val">${tm.minutes ? `${tm.minutes} min` : esc(this._t("timer_off"))}</span></div>
        <div class="chips timer" role="group" aria-labelledby="timer-l">${timerChips}</div>
      </div>
      ${lightHtml}
      <div class="divider"></div>
      <button class="goodnight" data-action="good_night">${icon("moon")}<span><b>${esc(this._t("good_night"))}</b><span>${esc(this._t("good_night_hint"))}</span></span></button>
      ${next}
    </section>`;
  }

  /* ---- Klänge */
  _tplSounds(spot) {
    const st = spot.state || {};
    const levels = st.levels || {};
    const presets = st.presets || [];
    const tiles = presets.map((p) => {
      const sel = st.preset === p.id;
      const user = this._isUserPreset(p);
      const confirm = this._confirmDel === p.id;
      return `<div class="tile" data-key="p-${esc(p.id)}">
        <button class="apply" data-action="preset" data-id="${esc(p.id)}" aria-pressed="${sel}">
          <span class="tico">${icon(this._presetIcon(p))}</span>
          <span class="tname">${esc(this._presetName(p))}</span>
          <span class="tsum">${esc(this._presetSummary(p.levels))}</span>
        </button>
        ${user
          ? `<button class="del ${confirm ? "confirm" : ""}" data-action="del_preset" data-id="${esc(p.id)}" aria-label="${esc(this._t("delete_preset", { n: p.name }))}">${confirm ? esc(this._t("confirm_delete")) : icon("trash")}</button>`
          : sel ? `<span class="badge">${icon("check")}</span>` : ""}
      </div>`;
    }).join("");

    const groups = GROUPS.map((g) => `
      <div class="group" role="group" aria-labelledby="g-${g.key}">
        <h3 id="g-${g.key}">${esc(this._t(`group_${g.key}`))}</h3>
        ${g.sounds.map((s) => {
          const v = Math.round((levels[s] || 0) * 100);
          return `<div class="layer ${v > 0 ? "on" : ""}">
            <span class="lic">${icon(s)}</span>
            <div class="lbody">
              <label for="lvl-${s}">${esc(this._sound(s))}</label>
              <input type="range" id="lvl-${s}" min="0" max="100" step="1" value="${v}" style="--p:${v}%" data-input="level" data-sound="${s}">
            </div>
            <output for="lvl-${s}">${esc(this._pct(v))}</output>
          </div>`;
        }).join("")}
      </div>`).join("");

    const anyLevel = Object.values(levels).some((v) => v > 0.01);
    let save;
    if (this._saveForm) {
      const f = this._saveForm;
      save = `<form class="saveform" data-form="preset" novalidate>
        <div class="field"><label class="lbl" for="pname">${esc(this._t("preset_name"))}</label>
          <input class="text" id="pname" type="text" maxlength="40" autocomplete="off" value="${esc(f.name)}" data-input="preset_name"></div>
        <div class="field"><span class="lbl" id="pico-l">${esc(this._t("preset_icon"))}</span>
          <div class="icopick" role="group" aria-labelledby="pico-l">${PRESET_ICON_CHOICES.map((ic) => `<button type="button" data-action="preset_icon" data-icon="${ic}" aria-pressed="${f.icon === ic}" aria-label="${esc(ic === "moon" ? this._t("good_night") : this._sound(ic))}">${icon(ic)}</button>`).join("")}</div></div>
        <div class="btns"><button type="submit" class="btn primary" data-action="save_preset" ${f.name.trim() ? "" : "disabled"}>${icon("check")}${esc(this._t("save"))}</button>
          <button type="button" class="btn ghost" data-action="cancel_preset">${esc(this._t("cancel"))}</button></div>
      </form>`;
    } else {
      save = `<div class="btns"><button class="btn" data-action="open_save" ${anyLevel ? "" : "disabled"}>${icon("plus")}${esc(this._t("save_preset"))}</button>
        ${anyLevel ? "" : `<span class="hint">${esc(this._t("mix_empty"))}</span>`}</div>`;
    }

    return `<section class="card" aria-labelledby="h-presets">
        <div class="card-head"><div><h2 id="h-presets">${esc(this._t("presets"))}</h2><p class="hint">${esc(this._t("presets_hint"))}</p></div></div>
        <div class="tiles">${tiles}</div>
      </section>
      <section class="card" aria-labelledby="h-mixer">
        <div class="card-head"><div><h2 id="h-mixer">${esc(this._t("mixer"))}</h2><p class="hint">${esc(this._t("mixer_hint"))}</p></div></div>
        <div class="groups">${groups}</div>
        <div class="divider"></div>
        ${save}
      </section>`;
  }

  /* ---- Wecker */
  _tplAlarms(spot) {
    const st = spot.state || {};
    const alarms = [...(st.alarms || [])].sort((a, b) => String(a.time).localeCompare(String(b.time)));
    const list = alarms.length
      ? `<div class="alarmlist">${alarms.map((a) => {
          const tags = [
            `<span>${icon("music")}${esc(this._tone(a.tone))}</span>`,
            `<span>${icon("timer")}${esc(this._t("min_long", { m: a.duration_min ?? 10 }))}</span>`,
            `<span>${icon("speaker")}${esc(this._pct((a.volume ?? 0.7) * 100))}</span>`,
            a.sunrise ? `<span>${icon("sunrise")}${esc(this._t("min_long", { m: a.sunrise_min ?? 30 }))}</span>` : "",
          ].join("");
          return `<div class="alarm ${a.enabled ? "" : "off"}" data-key="a-${esc(a.id)}">
            <button class="open" data-action="edit_alarm" data-id="${esc(a.id)}" aria-label="${esc(this._t("edit_alarm_at", { t: a.time }))}">
              <span class="atime">${esc(a.time)}</span>
              <span class="ainfo"><b>${esc(this._daysText(a.days))}</b><span class="tags">${tags}</span></span>
            </button>
            <button class="switch" role="switch" data-action="alarm_toggle" data-id="${esc(a.id)}" aria-checked="${!!a.enabled}" aria-label="${esc(this._t("alarm_toggle", { t: a.time }))}"></button>
          </div>`;
        }).join("")}</div>`
      : `<p class="empty-note">${esc(this._t("no_alarms"))}</p>`;

    let next = "";
    if (st.next_alarm) {
      const d = new Date(st.next_alarm);
      next = `<p class="hint">${esc(this._t("next_alarm"))}: <strong style="color:var(--fg)">${esc(DAY_LONG[this._lang][(d.getDay() + 6) % 7])}, ${this._fmtTime(d)}</strong> · ${esc(this._rel(d - Date.now()))}</p>`;
    }
    return `<section class="card" aria-labelledby="h-alarms">
      <div class="card-head"><div><h2 id="h-alarms">${esc(this._t("alarms"))}</h2>${next}</div></div>
      ${list}
      <div class="btns">
        <button class="btn primary" data-action="new_alarm">${icon("plus")}${esc(this._t("add_alarm"))}</button>
        <span class="grow"></span>
        <button class="btn ghost" data-action="ring">${icon("alarm")}${esc(this._t("test_ring"))}</button>
      </div>
    </section>`;
  }

  _tplDialog() {
    const d = this._dlg;
    const a = d.alarm;
    const spot = this._spot();
    const hasLight = spot && ((spot.lights || []).length || spot.diy_device);
    const dur = a.duration_min ?? 10;
    const vol = Math.round((a.volume ?? 0.7) * 100);
    const sun = a.sunrise_min ?? 30;
    const days = DAY_SHORT[this._lang].map((n, i) => `<button type="button" class="chip" data-action="dlg_day" data-day="${i}" aria-pressed="${a.days.includes(i)}" aria-label="${esc(DAY_LONG[this._lang][i])}">${n}</button>`).join("");
    const tones = TONES.map((tn) => `<button type="button" class="chip" data-action="dlg_tone" data-tone="${tn}" aria-pressed="${a.tone === tn}">${esc(this._tone(tn))}</button>`).join("");
    return `<div class="scrim" data-action="dlg_scrim">
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title" data-key="dlg">
        <div class="dhead"><h2 id="dlg-title">${esc(this._t(d.isNew ? "new_alarm" : "edit_alarm"))}</h2>
          <button class="iconbtn" data-action="dlg_close" aria-label="${esc(this._t("close"))}">${icon("close")}</button></div>
        <div class="dbody">
          <div class="row">
            <div class="field"><label class="lbl" for="dlg-time" style="color:var(--muted);font-size:14px">${esc(this._t("time"))}</label>
              <input class="text" id="dlg-time" type="time" value="${esc(a.time)}" data-input="dlg_time" required></div>
            <div class="row" style="gap:10px"><span class="lbl" id="dlg-en-l" style="color:var(--muted);font-size:14px">${esc(this._t("enabled"))}</span>
              <button type="button" class="switch" role="switch" data-action="dlg_enabled" aria-checked="${!!a.enabled}" aria-labelledby="dlg-en-l"></button></div>
          </div>
          <div class="field">
            <div class="field-head"><span class="lbl" id="dlg-days-l">${esc(this._t("days"))}</span><span class="val">${esc(this._daysText(a.days))}</span></div>
            <div class="chips days" role="group" aria-labelledby="dlg-days-l">${days}</div>
            ${a.days.length ? "" : `<p class="hint">${esc(this._t("once_hint"))}</p>`}
          </div>
          <div class="field">
            <div class="field-head"><span class="lbl" id="dlg-tone-l">${esc(this._t("tone"))}</span></div>
            <div class="tonepick"><div class="chips" role="group" aria-labelledby="dlg-tone-l">${tones}</div>
              <button type="button" class="btn ghost" data-action="dlg_preview">${icon("play")}${esc(this._t("preview"))}</button></div>
          </div>
          <div class="field">
            <div class="field-head"><label for="dlg-dur">${esc(this._t("duration"))}</label><output for="dlg-dur">${dur} min</output></div>
            <input type="range" id="dlg-dur" min="1" max="30" step="1" value="${dur}" style="--p:${((dur - 1) / 29) * 100}%" data-input="dlg_dur">
          </div>
          <div class="field">
            <div class="field-head"><label for="dlg-vol">${esc(this._t("alarm_volume"))}</label><output for="dlg-vol">${esc(this._pct(vol))}</output></div>
            <input type="range" id="dlg-vol" min="5" max="100" step="1" value="${vol}" style="--p:${((vol - 5) / 95) * 100}%" data-input="dlg_vol">
          </div>
          <div class="divider"></div>
          <div class="row">
            <div class="txt"><b id="dlg-sun-l">${esc(this._t("sunrise"))}</b><span>${esc(hasLight ? this._t("sunrise_desc") : this._t("sunrise_nolight"))}</span></div>
            <button type="button" class="switch" role="switch" data-action="dlg_sunrise" aria-checked="${!!a.sunrise}" aria-labelledby="dlg-sun-l" ${hasLight ? "" : "disabled"}></button>
          </div>
          ${a.sunrise ? `<div class="field">
            <div class="field-head"><label for="dlg-sun">${esc(this._t("sunrise_min"))}</label><output for="dlg-sun">${sun} min</output></div>
            <input type="range" id="dlg-sun" min="5" max="60" step="5" value="${sun}" style="--p:${((sun - 5) / 55) * 100}%" data-input="dlg_sun">
          </div>` : ""}
        </div>
        <div class="dfoot">
          ${d.isNew ? "" : `<button type="button" class="btn danger" data-action="dlg_delete">${icon("trash")}${esc(this._t("delete"))}</button>`}
          <span class="grow"></span>
          <button type="button" class="btn ghost" data-action="dlg_close">${esc(this._t("cancel"))}</button>
          <button type="button" class="btn primary" data-action="dlg_save" ${/^\d{2}:\d{2}$/.test(a.time) ? "" : "disabled"}>${icon("check")}${esc(this._t("save"))}</button>
        </div>
      </div>
    </div>`;
  }

  /* ---- Automatik */
  _tplAuto(spot) {
    const st = spot.state || {};
    const au = { presence_start: false, presence_from: "20:00", presence_to: "02:00", presence_stop_min: 0, pause_on_music: false, night_light_with_sound: false, ...(st.auto || {}) };
    const hasPresence = !!spot.presence;
    const hasLight = (spot.lights || []).length || spot.diy_device;
    const stopMin = au.presence_stop_min || 0;
    const presenceDesc = hasPresence
      ? esc(this._t("presence_start_desc", { s: this._entityName(spot.presence) }))
      : `${esc(this._t("no_presence"))}${this._isAdmin() ? ` <button class="linkbtn" data-action="settings">${esc(this._t("choose_in_settings"))}</button>` : ""}`;
    const dis = hasPresence ? "" : "disabled";
    return `<section class="card" aria-labelledby="h-presence">
        <div class="card-head"><h2 id="h-presence">${esc(this._t("presence_title"))}</h2></div>
        <div class="row">
          <span class="lead">${icon("person")}</span>
          <div class="txt"><b id="au-ps-l">${esc(this._t("presence_start"))}</b><span>${presenceDesc}</span></div>
          <button class="switch" role="switch" data-action="auto" data-key2="presence_start" aria-checked="${!!au.presence_start && hasPresence}" aria-labelledby="au-ps-l" ${dis}></button>
        </div>
        <div class="row" style="justify-content:flex-start;flex-wrap:wrap;gap:16px;padding-left:54px">
          <div class="field"><label class="lbl" for="au-from" style="color:var(--muted);font-size:13px">${esc(this._t("from"))}</label>
            <input class="text" id="au-from" type="time" value="${esc(au.presence_from)}" data-change="auto_time" data-key2="presence_from" ${dis}></div>
          <div class="field"><label class="lbl" for="au-to" style="color:var(--muted);font-size:13px">${esc(this._t("to"))}</label>
            <input class="text" id="au-to" type="time" value="${esc(au.presence_to)}" data-change="auto_time" data-key2="presence_to" ${dis}></div>
        </div>
        <div class="field" style="padding-left:54px">
          <div class="field-head"><label for="au-stop">${esc(this._t("presence_stop"))}</label><output for="au-stop">${stopMin ? esc(this._t("presence_stop_after", { m: stopMin })) : esc(this._t("never"))}</output></div>
          <input type="range" id="au-stop" min="0" max="60" step="5" value="${stopMin}" style="--p:${(stopMin / 60) * 100}%" data-input="auto_stop" ${dis}>
        </div>
      </section>
      <section class="card" aria-labelledby="h-music">
        <div class="card-head"><h2 id="h-music">${esc(this._t("music_title"))}</h2></div>
        <div class="row">
          <span class="lead">${icon("music")}</span>
          <div class="txt"><b id="au-pm-l">${esc(this._t("pause_on_music"))}</b><span>${esc(this._t("pause_desc"))}</span></div>
          <button class="switch" role="switch" data-action="auto" data-key2="pause_on_music" aria-checked="${!!au.pause_on_music}" aria-labelledby="au-pm-l"></button>
        </div>
      </section>
      <section class="card" aria-labelledby="h-autolight">
        <div class="card-head"><h2 id="h-autolight">${esc(this._t("light_title"))}</h2></div>
        <div class="row">
          <span class="lead">${icon("bulb")}</span>
          <div class="txt"><b id="au-nl-l">${esc(this._t("night_light"))}</b><span>${esc(hasLight ? this._t("night_light_desc") : this._t("no_light"))}</span></div>
          <button class="switch" role="switch" data-action="auto" data-key2="night_light_with_sound" aria-checked="${!!au.night_light_with_sound}" aria-labelledby="au-nl-l" ${hasLight ? "" : "disabled"}></button>
        </div>
      </section>`;
  }

  /* ---- Einstellungen */
  _initCfg(keepDirty = false) {
    const spot = this._spot();
    if (!spot) return;
    if (keepDirty && this._cfg && this._cfg.entry_id === spot.entry_id && this._cfg.dirty) return;
    this._cfg = {
      entry_id: spot.entry_id, name: spot.name || "", speakers: [...(spot.speakers || [])],
      lights: [...(spot.lights || [])], presence: spot.presence || null, dirty: false,
    };
  }

  async _loadEntities() {
    try {
      const res = await this._hass.callWS({ type: "dusk_dawn/entities" });
      this._entities = Array.isArray(res) ? res : (res && res.entities) || [];
    } catch (err) {
      console.warn("[dusk-dawn] entities failed", err);
      this._entities = [];
    }
    this._schedule();
  }

  _tplPicker(kind, multi) {
    const cfg = this._cfg;
    const domain = { speakers: "media_player", lights: "light", presence: "binary_sensor" }[kind];
    const all = (this._entities || []).filter((e) => (e.domain || e.entity_id.split(".")[0]) === domain);
    const q = (this._filters[kind] || "").toLowerCase();
    const sel = multi ? cfg[kind] : [cfg.presence].filter(Boolean);
    // keep selected entries visible even if the backend does not list them
    sel.forEach((id) => { if (!all.find((e) => e.entity_id === id)) all.unshift({ entity_id: id, name: this._entityName(id), domain }); });
    const shown = all.filter((e) => !q || `${e.name} ${e.entity_id}`.toLowerCase().includes(q));
    const label = this._t(kind);
    const filter = all.length > 6
      ? `<input class="text" type="search" placeholder="${esc(this._t("filter"))}" aria-label="${esc(this._t("filter_label", { x: label }))}" value="${esc(this._filters[kind] || "")}" data-input="filter" data-kind="${kind}">`
      : "";
    let rows = shown.map((e) => {
      const checked = sel.includes(e.entity_id);
      return `<label class="pick" data-key="${esc(e.entity_id)}"><input type="${multi ? "checkbox" : "radio"}" name="pick-${kind}" data-pick="${kind}" value="${esc(e.entity_id)}" ${checked ? "checked" : ""}>
        <span class="pt"><b>${esc(e.name || e.entity_id)}</b><small>${esc(e.entity_id)}${e.device_class ? ` · ${esc(e.device_class)}` : ""}</small></span></label>`;
    }).join("");
    if (!multi) {
      rows = `<label class="pick" data-key="none"><input type="radio" name="pick-${kind}" data-pick="${kind}" value="" ${cfg.presence ? "" : "checked"}><span class="pt"><b>${esc(this._t("none"))}</b></span></label>` + rows;
    }
    if (this._entities === null) rows = `<p class="hint" style="padding:10px">${esc(this._t("loading"))}</p>`;
    else if (!shown.length && multi) rows = `<p class="hint" style="padding:10px">${esc(this._t("no_entities"))}</p>`;
    const hint = { speakers: "speakers_hint", lights: "lights_hint", presence: "presence_hint" }[kind];
    const count = multi ? `<span class="hint">${esc(this._t("selected_n", { n: sel.length }))}</span>` : "";
    return `<section class="card" aria-labelledby="h-${kind}">
      <div class="card-head"><div><h2 id="h-${kind}">${esc(label)}</h2><p class="hint">${esc(this._t(hint))}</p></div>${count}</div>
      ${filter}
      <div class="picklist" role="group" aria-labelledby="h-${kind}">${rows}</div>
    </section>`;
  }

  _tplSettings(spot) {
    if (!this._cfg || this._cfg.entry_id !== spot.entry_id) this._initCfg();
    if (this._entities === null && !this._entLoading) { this._entLoading = true; this._loadEntities().then(() => { this._entLoading = false; }); }
    const cfg = this._cfg;
    return `<div class="settings-head">
        <button class="iconbtn" data-action="view" data-view="${esc(lsGet("dusk_dawn.view") || "now")}" aria-label="${esc(this._t("back"))}">${icon("back")}</button>
        <h2>${esc(this._t("settings"))} · ${esc(spot.name)}</h2>
      </div>
      <div class="settings-grid">
        <section class="card span" aria-labelledby="h-name">
          <h2 id="h-name">${esc(this._t("name"))}</h2>
          <div class="field"><label class="sr" for="cfg-name">${esc(this._t("name"))}</label>
            <input class="text" id="cfg-name" type="text" maxlength="60" autocomplete="off" value="${esc(cfg.name)}" data-input="cfg_name"></div>
          ${spot.diy_device ? `<p class="hint">${esc(this._t("diy_hint"))}</p>` : ""}
        </section>
        ${spot.diy_device ? "" : this._tplPicker("speakers", true)}
        ${this._tplPicker("lights", true)}
        <div class="span">${this._tplPicker("presence", false)}</div>
        <section class="card span">
          <div class="row wrap"><div class="txt"><b>${esc(this._t("manage"))}</b><span>${esc(this._t("add_spot_hint"))}</span></div>
          <a class="btn" href="/config/integrations/integration/dusk_dawn" data-nav="/config/integrations/integration/dusk_dawn">${icon("external")}${esc(this._t("manage"))}</a></div>
        </section>
      </div>
      <div class="savebar" ${cfg.dirty ? "" : "hidden"}>
        <span class="grow">${esc(this._t("unsaved"))}</span>
        <button class="btn ghost" data-action="cfg_reset">${esc(this._t("cancel"))}</button>
        <button class="btn primary" data-action="cfg_save" ${cfg.name.trim() ? "" : "disabled"}>${icon("check")}${esc(this._t("save"))}</button>
      </div>`;
  }

  /* ---- events */
  _onClick(e) {
    const nav = e.target.closest("[data-nav]");
    if (nav) { e.preventDefault(); this._navigate(nav.getAttribute("data-nav")); return; }
    const el = e.target.closest("[data-action]");
    if (!el || el.disabled) return;
    const a = el.dataset.action;
    const spot = this._spot();
    const st = spot?.state;
    switch (a) {
      case "menu":
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "retry": this._loadError = null; this._spots = null; this._loadSpots(); this._schedule(); break;
      case "settings":
        if (this._view === "settings") { this._setView(lsGet("dusk_dawn.view") || "now"); break; }
        this._initCfg(); this._entities = null; this._view = "settings"; this._schedule(); break;
      case "spot":
        this._flushAll();
        this._active = el.dataset.id; lsSet("dusk_dawn.spot", this._active);
        this._saveForm = null; this._confirmDel = null;
        if (this._view === "settings") this._initCfg();
        this._schedule(); break;
      case "view": this._setView(el.dataset.view); break;
      case "toggle":
        this._cmd("toggle", {}, (s) => { s.playing = !s.playing; }); break;
      case "timer": {
        const m = el.dataset.min ? Number(el.dataset.min) : null;
        this._cmd("set_timer", { minutes: m }, (s) => {
          s.timer = { minutes: m, ends_at: m && s.playing ? new Date(Date.now() + m * 60000).toISOString() : null };
        });
        break;
      }
      case "light_toggle": {
        const on = !st.light?.on;
        this._cmd("light", { on }, (s) => { s.light = { ...(s.light || {}), on }; }); break;
      }
      case "effect": {
        const eff = el.dataset.effect;
        this._cmd("light", { effect: eff }, (s) => { s.light = { ...(s.light || {}), on: eff !== "fade" ? true : s.light?.on }; })
          .then((r) => { if (r) this._toast(this._t("effect_started", { e: this._t(`eff_${eff}`) })); });
        break;
      }
      case "good_night":
        this._cmd("good_night", {}, (s) => { s.playing = true; }).then((r) => { if (r) this._toast(this._t("good_night_done")); }); break;
      case "stop_alarm":
        this._cmd("stop_alarm", {}, (s) => { s.alarm_ringing = false; }); break;
      case "preset": {
        const p = st.presets.find((x) => x.id === el.dataset.id);
        this._cmd("apply_preset", { preset_id: el.dataset.id }, (s) => {
          s.preset = el.dataset.id;
          if (p) { const lv = {}; SOUNDS.forEach((k) => { lv[k] = p.levels?.[k] || 0; }); s.levels = lv; }
        });
        break;
      }
      case "del_preset": {
        const id = el.dataset.id;
        if (this._confirmDel !== id) {
          this._confirmDel = id; this._schedule();
          clearTimeout(this._confirmT); this._confirmT = setTimeout(() => { this._confirmDel = null; this._schedule(); }, 3500);
          break;
        }
        this._confirmDel = null;
        this._cmd("delete_preset", { preset_id: id }, (s) => { s.presets = s.presets.filter((x) => x.id !== id); if (s.preset === id) s.preset = null; });
        break;
      }
      case "open_save":
        this._saveForm = { name: "", icon: "moon" }; this._focusNext = "#pname"; this._schedule(); break;
      case "cancel_preset": this._saveForm = null; this._schedule(); break;
      case "preset_icon": this._saveForm.icon = el.dataset.icon; this._schedule(); break;
      case "save_preset": {
        e.preventDefault();
        this._savePreset(); break;
      }
      case "new_alarm":
        this._openDialog(null, el); break;
      case "edit_alarm":
        this._openDialog(st.alarms.find((x) => x.id === el.dataset.id), el); break;
      case "alarm_toggle": {
        const al = st.alarms.find((x) => x.id === el.dataset.id);
        if (!al) break;
        const next = { ...al, enabled: !al.enabled };
        this._cmd("set_alarm", { alarm: next }, (s) => { s.alarms = s.alarms.map((x) => (x.id === next.id ? next : x)); });
        break;
      }
      case "ring": this._cmd("ring", {}, (s) => { s.alarm_ringing = true; }); break;
      case "dlg_scrim": if (e.target === el) this._closeDialog(); break;
      case "dlg_close": this._closeDialog(); break;
      case "dlg_day": {
        const i = Number(el.dataset.day); const ds = this._dlg.alarm.days;
        this._dlg.alarm.days = ds.includes(i) ? ds.filter((x) => x !== i) : [...ds, i].sort((x, y) => x - y);
        this._schedule(); break;
      }
      case "dlg_tone": this._dlg.alarm.tone = el.dataset.tone; this._schedule(); break;
      case "dlg_preview":
        this._cmd("preview_tone", { tone: this._dlg.alarm.tone }).then((r) => { if (r) this._toast(this._t("previewing", { t: this._tone(this._dlg?.alarm.tone || "bells") })); });
        break;
      case "dlg_enabled": this._dlg.alarm.enabled = !this._dlg.alarm.enabled; this._schedule(); break;
      case "dlg_sunrise": this._dlg.alarm.sunrise = !this._dlg.alarm.sunrise; this._schedule(); break;
      case "dlg_save": {
        const al = clone(this._dlg.alarm);
        this._closeDialog();
        this._cmd("set_alarm", { alarm: al }, (s) => {
          const i = (s.alarms ||= []).findIndex((x) => x.id === al.id);
          if (i >= 0) s.alarms[i] = al; else s.alarms.push(al);
        }).then((r) => { if (r) this._toast(this._t("alarm_saved")); });
        break;
      }
      case "dlg_delete": {
        const id = this._dlg.alarm.id;
        this._closeDialog();
        this._cmd("delete_alarm", { alarm_id: id }, (s) => { s.alarms = (s.alarms || []).filter((x) => x.id !== id); })
          .then((r) => { if (r) this._toast(this._t("alarm_deleted")); });
        break;
      }
      case "auto": {
        const key = el.dataset.key2;
        const auto = { ...(st.auto || {}), [key]: !st.auto?.[key] };
        this._cmd("set_auto", { auto }, (s) => { s.auto = auto; }); break;
      }
      case "cfg_reset": this._initCfg(); this._schedule(); break;
      case "cfg_save": this._saveCfg(); break;
      default: break;
    }
  }

  _onInput(e) {
    const el = e.target;
    const kind = el.dataset?.input;
    if (!kind) return;
    const spot = this._spot();
    const v = Number(el.value);
    if (el.type === "range") el.style.setProperty("--p", `${((v - Number(el.min)) / (Number(el.max) - Number(el.min))) * 100}%`);
    switch (kind) {
      case "volume": {
        const vol = v / 100;
        spot.state.volume = vol; this._setOv("volume", vol);
        this._debounce("volume", () => this._cmd("set_volume", { volume: vol }));
        break;
      }
      case "level": {
        const s = el.dataset.sound; const lv = v / 100;
        (spot.state.levels ||= {})[s] = lv; this._setOv(`levels.${s}`, lv);
        spot.state.preset = null; this._setOv("preset", null);
        this._debounce(`level.${s}`, () => this._cmd("set_level", { sound: s, level: lv }));
        break;
      }
      case "brightness": {
        const b = Math.round((v / 100) * 255);
        spot.state.light = { ...(spot.state.light || {}), brightness: b, on: true };
        this._setOv("light.brightness", b); this._setOv("light.on", true);
        this._debounce("brightness", () => this._cmd("light", { on: true, brightness: b }));
        break;
      }
      case "kelvin": {
        spot.state.light = { ...(spot.state.light || {}), kelvin: v };
        this._setOv("light.kelvin", v);
        this._debounce("kelvin", () => this._cmd("light", { kelvin: v }));
        break;
      }
      case "auto_stop": {
        const auto = { ...(spot.state.auto || {}), presence_stop_min: v };
        spot.state.auto = auto; this._setOv("auto.presence_stop_min", v);
        this._debounce("auto_stop", () => this._cmd("set_auto", { auto: { ...(this._spot()?.state.auto || auto) } }));
        break;
      }
      case "preset_name": this._saveForm.name = el.value; break;
      case "dlg_time": this._dlg.alarm.time = el.value; break;
      case "dlg_dur": this._dlg.alarm.duration_min = v; break;
      case "dlg_vol": this._dlg.alarm.volume = v / 100; break;
      case "dlg_sun": this._dlg.alarm.sunrise_min = v; break;
      case "cfg_name": this._cfg.name = el.value; this._cfg.dirty = true; break;
      case "filter": this._filters[el.dataset.kind] = el.value; break;
      default: break;
    }
    this._schedule();
  }

  _onChange(e) {
    const el = e.target;
    const kind = el.dataset?.input;
    if (kind === "volume") this._flush("volume");
    else if (kind === "level") this._flush(`level.${el.dataset.sound}`);
    else if (kind === "brightness" || kind === "kelvin" || kind === "auto_stop") this._flush(kind);
    if (el.dataset?.change === "auto_time") {
      const spot = this._spot();
      if (!/^\d{2}:\d{2}$/.test(el.value)) return;
      const auto = { ...(spot.state.auto || {}), [el.dataset.key2]: el.value };
      this._cmd("set_auto", { auto }, (s) => { s.auto = auto; });
    }
    const pick = el.dataset?.pick;
    if (pick) {
      const cfg = this._cfg;
      if (pick === "presence") cfg.presence = el.value || null;
      else {
        const set = new Set(cfg[pick]);
        if (el.checked) set.add(el.value); else set.delete(el.value);
        cfg[pick] = [...set];
      }
      cfg.dirty = true;
      this._schedule();
    }
  }

  _onKey(e) {
    // Esc closes dialog / save form
    if (e.key === "Escape") {
      if (this._dlg) { e.preventDefault(); this._closeDialog(); return; }
      if (this._saveForm) { this._saveForm = null; this._schedule(); return; }
    }
    // Enter in the preset name field saves
    if (e.key === "Enter" && e.target?.dataset?.input === "preset_name") { e.preventDefault(); this._savePreset(); return; }
    // focus trap in dialog
    if (e.key === "Tab" && this._dlg) {
      const dlg = this.shadowRoot.querySelector(".dialog");
      const f = [...dlg.querySelectorAll("button:not([disabled]),input:not([disabled])")];
      if (!f.length) return;
      const first = f[0]; const last = f[f.length - 1];
      const act = this.shadowRoot.activeElement;
      if (e.shiftKey && act === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && act === last) { e.preventDefault(); first.focus(); }
      return;
    }
    // arrow keys in tablists
    const tab = e.target.closest?.('[role="tab"]');
    if (tab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
      const tabs = [...tab.parentElement.querySelectorAll('[role="tab"]')];
      let i = tabs.indexOf(tab);
      if (e.key === "ArrowLeft") i = (i - 1 + tabs.length) % tabs.length;
      else if (e.key === "ArrowRight") i = (i + 1) % tabs.length;
      else if (e.key === "Home") i = 0; else i = tabs.length - 1;
      e.preventDefault();
      tabs[i].click();
      const sel = tabs[i].dataset.view ? `[data-view="${tabs[i].dataset.view}"][role="tab"]` : `[data-id="${CSS.escape(tabs[i].dataset.id)}"][role="tab"]`;
      this._focusNext = sel;
    }
  }

  _savePreset() {
    const f = this._saveForm;
    if (!f || !f.name.trim()) return;
    const name = f.name.trim();
    const iconName = ICON_TO_MDI[f.icon] || f.icon;
    this._saveForm = null;
    this._cmd("save_preset", { name, icon: iconName }).then((r) => { if (r) this._toast(this._t("preset_saved", { n: name })); });
    this._schedule();
  }

  _openDialog(alarm, opener) {
    this._dlgReturn = opener;
    this._dlg = alarm
      ? { isNew: false, alarm: { days: [], ...clone(alarm) } }
      : {
          isNew: true,
          alarm: {
            id: `a${Date.now().toString(36)}`, enabled: true, time: "07:00", days: [0, 1, 2, 3, 4], tone: "bells",
            duration_min: 10, volume: 0.6, sunrise: !!((this._spot()?.lights || []).length || this._spot()?.diy_device), sunrise_min: 30,
          },
        };
    this._focusNext = "#dlg-time";
    this._schedule();
  }

  _closeDialog() {
    this._dlg = null;
    const ret = this._dlgReturn;
    this._dlgReturn = null;
    this._schedule();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (ret && ret.isConnected) ret.focus();
      else this.shadowRoot.querySelector('[data-action="new_alarm"]')?.focus();
    }));
  }

  async _saveCfg() {
    const cfg = this._cfg;
    const spot = this._spot();
    if (!cfg || !spot) return;
    const msg = { type: "dusk_dawn/config", entry_id: cfg.entry_id, name: cfg.name.trim(), lights: cfg.lights, presence: cfg.presence };
    if (!spot.diy_device) msg.speakers = cfg.speakers;
    try {
      await this._hass.callWS(msg);
      Object.assign(spot, { name: msg.name, lights: msg.lights, presence: msg.presence }, msg.speakers ? { speakers: msg.speakers } : {});
      cfg.dirty = false;
      this._toast(this._t("saved"));
      this._loadSpots();
    } catch (err) {
      this._toast(`${this._t("err_cmd")}${err && err.message ? `: ${err.message}` : ""}`, true);
    }
    this._schedule();
  }
}

if (!customElements.get("dusk-dawn-panel")) {
  customElements.define("dusk-dawn-panel", DuskDawnPanel);
  console.info(`%c Dusk & Dawn panel ${VERSION} `, "background:#141b31;color:#e3b062;border-radius:4px");
}
