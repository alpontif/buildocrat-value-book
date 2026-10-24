# Weekly refresh

**Normally nothing to do.** The *Weekly refresh* workflow runs every Monday at 06:17 Nigeria time: it crawls, rebuilds, checks and publishes. Check the Actions tab on Monday morning for a green tick.

## If the run is red

Open the run and look at the last lines of the failing step.

| What you see | What it means | What to do |
|---|---|---|
| `KEEPING last run` for a source | That site blocked or changed; last week's listings were reused | Fine for a week or two. If it repeats, do the chat refresh below. |
| `SANITY CHECK FAILED` | The new numbers looked wrong, so nothing was published | Read the listed reasons. Re-run with *crawl* ticked; if it fails again, do the chat refresh. |
| Push rejected | Someone pushed at the same time | Re-run the workflow. |

## Chat refresh (needed while the sites block GitHub)

Since October 2026 Nigeria Property Centre and Jiji refuse requests from GitHub's servers, so the Monday job only updates the exchange rate and build rate (it keeps last week's listings and does not start a new edition). To refresh the listings, ask Claude:

> Refresh the Land Value Book for this week.

What Claude does (first done 24 Oct 2026, about 45 minutes):
1. In the browser pane on Kola's computer (Nigerian connection), opens jiji.ng and nigeriapropertycentre.com and runs the same collection as `pipeline/crawl.py` inside those pages:
   - Jiji: 4 categories per state, land up to 200 pages for Lagos/Abuja, 90 for Rivers/Ogun/Oyo, 60 elsewhere; houses and rents up to 120 / 60.
   - NPC land: up to the site's 50-page limit per state, then area by area (Lekki, Ajah, Ikorodu, Apo, Guzape...) for states that hit it.
   - NPC market-trend averages only when NPC has published a new month.
2. Saves the results to Downloads, copies them to `C:\Users\user\Claude\lvb-weekly\` (the copy tool refuses the browser's own download file) and stages them into `pipeline/raw/`.
3. Runs `python pipeline/refresh.py --no-crawl`, checks the site locally, commits and pushes. GitHub Pages publishes within a couple of minutes.

## Changing things

- Exchange rate and build rate come from the live Rate Book each week (`rate-data.json` and the bungalow cost guide); the fallbacks are in `site-config.json`.
- Crawl depth per state is in `site-config.json` → `crawl`.
- Keys (Mapbox, NIPOST) live in `site-config.json`; rebuild so `docs/config.js` updates.
