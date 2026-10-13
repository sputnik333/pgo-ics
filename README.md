# pgo-ics

Auto-updating iCalendar feed of the Pokémon GO calendar from
[vivific/pgocalendar](https://vivific.github.io/pgocalendar/).

**Feed URL:** `https://sputnik333.github.io/pgo-ics/calendar.ics`

- `build_ics.py` downloads `calendar_events.json` and converts it to `calendar.ics` (all-day events).
- `.github/workflows/build.yml` runs it every 6 hours and commits the file when the calendar changes.
- GitHub Pages serves `calendar.ics` at the URL above.

Run manually: Actions → *Build calendar.ics* → *Run workflow*.
