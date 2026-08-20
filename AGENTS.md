# AGENTS

## Cursor Cloud specific instructions

This repo is a collection of standalone Python 3 scripts (no package, no build step) that
discover Hyderabad/Remote-India jobs, filter/score them, tailor a resume per job, and — on a
real desktop — auto-fill/submit applications via a browser. State lives in `data/*.json`.

### Services / how things run
There is no long-running service and no test suite. You run scripts directly with `python3 <script>.py`.
Key entry points:
- `cloud_apply.py` — headed Chrome apply for this automation. **One application
  at a time**; next job only after a successful submit. See `APPLY.md`.
- `tailor_resume.py` — loads discovered jobs, builds the queue, and writes tailored `.docx` +
  cover letters to `data/resume/tailored/` (and `data/resume/Rafi_Resume_Latest.docx`). Good
  no-browser smoke test of core logic.
- `daily_cloud.py` — cloud pipeline: discovery + resume tailoring only, writes `DAILY_REPORT.md`.
  Explicitly avoids opening a browser. Note: `discover_hyd_gcc.main()` fetches many external job
  boards, so it needs network egress and can be slow/partial when egress is restricted.
- `apply_now.py` (`load_all_discovered()`, `queue()`) — dependency-free queue/scoring built from
  the committed `data/*.json` discovery files; works fully offline.

### Browser-based apply scripts — do NOT run in cloud
`apply_now.py` (as a full run), `browser_apply*.py`, `headed_apply.py`, `amazon_apply.py`,
`apply_parallel.py`, `firefox_real.py`, etc. drive a real Firefox/Chromium profile, depend on
logged-in sessions, and SUBMIT REAL JOB APPLICATIONS. Never execute these in an automated/cloud
context — they have real side effects and need an interactive display + human CAPTCHA solving.

### Lint / test / build
- No configured linter, formatter, or tests. Use `python3 -m py_compile *.py` as a syntax check.
- No build step (pure scripts).

### Pull requests
The owner asked agents to **merge PRs automatically every time** after work is complete
(do not leave them sitting as drafts for a human merge). Mark the PR ready, then merge
into `main` (fast-forward `git push origin HEAD:main` when that is allowed). Browser-apply
scripts are still never run in cloud.

### Gotchas
- Playwright needs its browser binary: `python3 -m playwright install chromium` (the update
  script does this). The `playwright` CLI installs to `~/.local/bin`; prefer `python3 -m playwright`.
- All paths are resolved relative to the repo root via `Path(__file__).resolve().parent`, so run
  scripts from anywhere but keep the `data/` tree intact.
