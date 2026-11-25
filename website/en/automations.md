# Automations

For your own automations, scripts and dashboards Dusk & Dawn creates entities and actions **per sleep spot**. You do not need them for everyday use, that is what the [sidebar](usage.md) is for.

## Entities

| Entity | Type | Meaning |
| --- | --- | --- |
| Sounds | switch | sounds on/off |
| Alarms | switch | all alarms of the sleep spot on/off |
| Sound | select | active scene; the options are the names of your scenes |
| Sleep timer | select | Off, 15, 30, 45, 60 or 90 minutes |
| Volume | number | 0 to 100 % |
| Rain, Ocean waves, Wind, Thunder, Fan, White/Pink/Brown noise | number | level of each built-in sound, 0 to 100 %. Only rain, ocean waves and brown noise are enabled by default, the others can be enabled in the entity settings. |
| Next alarm | sensor | time of the next alarm |
| Alarm time | time | time of the first alarm; setting it creates an alarm if none exists yet |
| Alarm ringing | binary sensor | on while an alarm is ringing |
| Good night | button | starts "Good night" |
| Stop alarm | button | stops a ringing alarm |

## Actions

All actions belong to the `dusk_dawn` domain. As target, pick an entity or device of the sleep spot. **Without a target the action applies to all sleep spots.**

| Action | Fields | Effect |
| --- | --- | --- |
| `dusk_dawn.play` | `preset` (name or ID of the scene, optional), `volume` (0 to 1), `timer` (minutes, 0 to 240; 0 turns the timer off) | starts the sleep sounds |
| `dusk_dawn.stop` | | stops the sleep sounds |
| `dusk_dawn.good_night` | | starts the good-night sound with sleep timer and dims the light |
| `dusk_dawn.ring` | `tone` (`bells` or `classic`), `duration` (1 to 60 minutes) | rings the alarm now |
| `dusk_dawn.stop_alarm` | | stops a ringing alarm |

## Example

Start rain with a 30-minute sleep timer when a certain button is pressed (adjust button and scene name):

```yaml
automation:
  - alias: "Fall asleep to rain"
    triggers:
      - trigger: state
        entity_id: input_button.bed    # your button
    actions:
      - action: dusk_dawn.play
        data:
          preset: Regen                # name of your scene
          volume: 0.4
          timer: 30
```

Without a `target` this starts on all sleep spots. For one room, add a `target` with an entity or the device of that sleep spot.
