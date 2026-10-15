# Weekly refresh

**Normally nothing to do.** The *Weekly refresh* workflow runs every Monday at 06:17 Nigeria time: it crawls, rebuilds, checks and publishes. Check the Actions tab on Monday morning for a green tick.

## If the run is red

Open the run and look at the last lines of the failing step.

| What you see | What it means | What to do |
|---|---|---|
| `KEEPING last run` for a source | That site blocked or changed; last week's listings were reused | Fine for a week or two. If it repeats, do the chat refresh below. |
| `SANITY CHECK FAILED` | The new numbers looked wrong, so nothing was published | Read the listed reasons. Re-run with *crawl* ticked; if it fails again, do the chat refresh. |
| Push rejected | Someone pushed at the same time | Re-run the workflow. |

## Chat refresh (fallback, like the Rate Book)

If the crawl keeps getting blocked from GitHub's servers, ask Claude on Monday:

> Refresh the Land Value Book for this week.

Claude then: attaches `alpontif/buildocrat-value-book` with push access → collects the week's listings through its browser (the same sources as `pipeline/crawl.py`) into `pipeline/raw/` → runs `python pipeline/refresh.py --no-crawl` → checks the site locally → commits and pushes. GitHub Pages publishes within a couple of minutes.

## Changing things

- Exchange rate and build rate come from the live Rate Book each week (`rate-data.json` and the bungalow cost guide); the fallbacks are in `site-config.json`.
- Crawl depth per state is in `site-config.json` → `crawl`.
- Keys (Mapbox, NIPOST) live in `site-config.json`; rebuild so `docs/config.js` updates.
