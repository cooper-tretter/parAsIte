# ParAsIte — Project Instructions for Claude Code

## Deployment Reminders

After ANY changes to the dashboard or seed script are pushed:

1. **If database schema changed** (new columns, new tables, altered types):
   - Remind the user to set `FORCE_RESEED=true` in Render environment variables before deploying
   - After the first successful deploy with the new schema, remind them to remove `FORCE_RESEED=true`

2. **If affect scoring logic changed** (AFFECT_PATTERNS, regex patterns, scoring weights):
   - Remind the user to set `FORCE_RESEED=true` so `compute_and_store_affect_scores()` re-runs

3. **If correlation logic changed** (PRE_PARASITIC_INDICATORS, tag_pre_parasitic_content, correlation computation):
   - Remind the user to set `FORCE_RESEED=true` so `compute_and_cache_correlation()` re-runs

4. **For CSS/layout-only changes**: No `FORCE_RESEED` needed — just push and Render will redeploy automatically.

## Architecture Notes

- **Hosting**: Render.com (web service)
- **Start sequence**: `seed_render_db.py --quick-check` runs before gunicorn starts (see Procfile / render.yaml)
- **seed_render_db.py**: Creates tables, imports data from CSV, pre-computes affect scores and correlation cache. With `--quick-check`, skips everything if tables already have data.
- **dashboard.py**: Single-file Dash/Plotly app (~2900 lines). Loads data at module level. Uses clientside callback for loading screen dismiss.
- **assets/**: Dash auto-serves CSS/JS from this directory (loading.css, responsive.css)
- **Theme**: Cream/papyrus background (#f5f0e6) with indigo/purple accents — "ancient mystical knowledge meets cutting-edge tech"
