# Maritime & Conflict Disruption Tracker

Production-ready single-page dashboard for maritime disruption monitoring with global trade-flow visualization, right-panel analytics, and source-backed asset layers.

## Live Deployment

- GitHub Pages: https://vamsvamshi.github.io/maritime-disruption-tracker/

## Runtime

- Static app entry: `index.html`
- Incident feed: `data/incidents.json`
- Analytics feed: `data/analytics_dashboard.json`

## Key Production Controls

- Resilient feed loading with timeout + retry (incidents and analytics)
- Feed health indicator in top subheader (`FEEDS HEALTHY`, `ANALYTICS STALE`, `ANALYTICS OUTDATED`)
- Smart date presets (`7d`, `15d`, `1m`, `3m`, `6m`, `since Feb 28`, `custom`)
- Source-backed 12 analytics modules
- Map layers with toggles and symbolic markers:
  - Client exposure (`🏢`)
  - Key ports (`⚓`)
  - LNG terminals (`⛽`)
- Validation gate for analytics schema:
  - `scripts/validate_analytics.js`
  - Enforced in GitHub Actions workflow

## Local Run

```powershell
npx --yes http-server . -p 5500 -a 127.0.0.1
```

Open `http://127.0.0.1:5500`.

## Data Update Workflow

1. Workflow file: `.github/workflows/update-incidents.yml`.
2. Latest incident data is fetched first and saved to `data/incidents.json`.
3. Analytics is then refreshed on top of the latest incidents by `scripts/update_analytics_feed.js`.
4. Updated analytics is written to `data/analytics_dashboard.json`.
5. Validation runs via `scripts/validate_analytics.js` before commit/push.

Manual refresh + validate:

```powershell
node scripts/update_analytics_feed.js
node scripts/validate_analytics.js
```

Manual validate:

```powershell
node scripts/validate_analytics.js
```

## Governance Guidance

- Keep `meta.last_updated` current in `data/analytics_dashboard.json`.
- Keep all `source_refs` fields populated with credible-source labels.
- Use directional wording where data is estimated/speculated.
- Avoid publishing uncited values.

## Recommended Next Hardening

- Add CI check to block PRs when `source_refs` are empty.
- Add end-to-end smoke test for map + analytics panel rendering.
