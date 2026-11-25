# FAQ

## Brauche ich eigene Hardware?

Nein. Dusk & Dawn läuft mit jedem Lautsprecher, der in Home Assistant als Media Player erscheint, und jeder Lampe. Die [Soundlampe](sound-lamp.md) ist nur ein optionales Gerät.

## Welche Lautsprecher funktionieren?

Alle, die in Home Assistant als Media Player erscheinen und einen Stream abspielen können, zum Beispiel Sonos, Google/Nest, Music Assistant, Squeezebox oder AirPlay. Echo/Alexa-Lautsprecher spielen keine eigenen Streams ab und funktionieren deshalb nicht.

## Warum reagiert mein Lautsprecher verzögert auf die Regler?

Home Assistant schickt die Klänge als MP3-Stream, den der Lautsprecher wie ein Internetradio puffert. Bei Sonos- und Google-Lautsprechern dauert eine Änderung deshalb 2 bis 10 Sekunden. Die Soundlampe rechnet selbst und hat diese Verzögerung nicht.

## Warum sind die Klänge leiser als meine Musik?

Absichtlich. Der Regler ganz oben entspricht −18 dB, bei 50 % sind es etwa −38 dB. Der Wecker ist zusätzlich um 12 dB gedämpft. Siehe [Lautstärke](usage.md#lautstarke).

## Laufen die Klänge nach einem Neustart von Home Assistant weiter?

Nein. Nach einem Neustart von Home Assistant laufen die Geräusche nicht automatisch weiter.

## Klingelt der Wecker, wenn Home Assistant oder das WLAN ausfällt?

Mit einem normalen Lautsprecher nicht, denn der Klang kommt von Home Assistant. Die [Soundlampe](sound-lamp.md) speichert die Weckzeiten selbst und klingelt auch ohne Home Assistant und WLAN.

## Warum flackert die Kerze auf meiner Lampe so langsam?

Damit das Zigbee-Netz nicht überlastet wird, läuft das Kerzenflackern auf normalen Lampen nur als sanftes Schwanken mit höchstens einem Befehl pro Sekunde.

## Wie viel Rechenleistung braucht das?

Der Klangkern in Rust braucht für vier Klänge etwa 0,5 % eines CPU-Kerns. Er liegt für x86_64 und aarch64 fertig bei. Auf anderen Systemen nutzt die Integration eine langsamere Python-Version mit gleichem Klang.

## Werden meine eigenen Aufnahmen gesichert?

Nicht mit dem Backup der Integration. Sie liegen im Home-Assistant-Ordner `dusk_dawn_sounds/`, den du selbst mitsichern solltest. Siehe [Eigene Klänge](own-sounds.md).

## Kann ich mehrere Zimmer steuern?

Ja. Jeder Schlafplatz hat eigene Lautsprecher, Lampen und Einstellungen. Für jedes Zimmer die Integration einfach noch einmal hinzufügen.

## Wo sind Feuer, Vögel und Bach geblieben?

Diese Klänge sind nicht mehr eingebaut. Wer sie möchte, lädt eine eigene Aufnahme hoch, siehe [Eigene Klänge](own-sounds.md).

## Unter welcher Lizenz steht das Projekt?

[MIT-Lizenz](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/LICENSE).
