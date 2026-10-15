# Buildocrat Nigeria Land Value Book

Land values, rents and house prices for every Nigerian state, all 774 LGAs and about 293,000 towns, villages and neighbourhoods, on a Mapbox satellite map with live NIPOST postcodes. Sister site of the [Construction Rate Book](https://rates.buildocrat.store/).

Live at **https://value.buildocrat.store/** (served by GitHub Pages from `docs/`).

## How it fits together

| Folder / file | What it is |
|---|---|
| `docs/` | The website. `index.html` + `app.js` (map, tables, estimator), `config.js` (public keys), `data/` (model output), one static page per state and LGA, `sitemap.xml`. |
| `pipeline/crawl.py` | Weekly crawl: Nigeria Property Centre land listings and market-trend medians, Jiji land/house/rent/commercial listings, FX and build rate from the Rate Book. Writes `pipeline/raw/`. A source that fails keeps last week's file. |
| `pipeline/build.py` | Places (GRID3 settlements + OSM) and geocoded market evidence. |
| `pipeline/run_model.py` | Spatial hedonic model: residential land surface, then commercial, industrial, farmland, rents and sale prices. |
| `pipeline/export.py` | Writes `docs/data/` (LGAs, places, evidence). |
| `pipeline/sanity.py` | Stops a bad week from going live (wrong counts, implausible values, big jumps against last week). |
| `pipeline/pages.py` | 812 static pages (37 states, 774 LGAs) + sitemap, robots, CNAME. |
| `pipeline/refresh.py` | Runs all of the above in order. |
| `pipeline/static/` | Fixed reference data: GRID3 settlement register, OSM places, LGA and state boundaries (geoBoundaries/GRID3). |
| `.github/workflows/weekly-refresh.yml` | Runs the refresh every Monday 06:17 Nigeria time, commits, pushes, pings IndexNow. |
| `site-config.json` | Domain, Mapbox token, NIPOST publishable key, crawl limits, fallbacks. |

## One-time setup

1. **Repository.** Create a public GitHub repo (e.g. `alpontif/buildocrat-land-book`) and push this folder to `main`.
2. **GitHub Pages.** Settings → Pages → Source: *Deploy from a branch* → `main` / `/docs`. Tick *Enforce HTTPS* once the certificate is issued.
3. **Actions permissions.** Settings → Actions → General → Workflow permissions: *Read and write*.
4. **Domain.** At your DNS host for `buildocrat.store`, add `CNAME  value  →  alpontif.github.io` (same as `rates`). `docs/CNAME` already says `value.buildocrat.store`; change `domain` in `site-config.json` if you pick another name, then run `python pipeline/pages.py`.
5. **Mapbox.** Create a free account at mapbox.com → Tokens → *Create a token*: public scopes only, URL restrictions `https://value.buildocrat.store` (add `http://localhost:8765` for local testing). Paste the `pk.…` token into `mapbox_token`. Free tier: 50,000 map loads a month.
6. **NIPOST.** At dashboard.postcode.gov.ng create the organisation, complete KYB, then Settings → API Keys → *Publishable*: scopes `search` (and `lookup` for postcode checks), allowed origin `https://value.buildocrat.store`. Paste the `nipost_pk_live_…` key into `nipost_publishable_key`. Reverse lookups (`/v1/search/reverse`) and level-1 postcode checks are free.
7. Run `python pipeline/refresh.py --no-crawl` (or the workflow with *crawl* unticked) so `docs/config.js` picks up the keys, then commit.

Without a Mapbox token the site still works with the built-in plain map; without a NIPOST key it shows the state prefix and links to postcode.gov.ng.

## Run locally

```bash
pip install -r requirements.txt
python pipeline/refresh.py --no-crawl     # rebuild from the files in pipeline/raw (≈1 minute)
python pipeline/refresh.py                # crawl first (≈1 to 1.5 hours, polite delays)
cd docs && python -m http.server 8765     # open http://localhost:8765
```

Deep links: `/#state=LA`, `/#lga=LA/ikeja`, `/#at=6.4281,3.4225`, `/#postcode=LA-05-E12-VI-07`.

## Data and licences

Listings: Nigeria Property Centre, Jiji (asking prices, read weekly). Settlements and boundaries: GRID3 / geoBoundaries (CC BY 4.0). Places: © OpenStreetMap contributors (ODbL). Imagery: © Mapbox, © Maxar. Postcodes: NIPOST, postcode.gov.ng. Values are indicative asking prices, not valuation reports.
