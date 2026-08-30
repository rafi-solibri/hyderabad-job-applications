# Standing orders — every Candidate job applications run

These rules apply on **every** run of this automation (cron or follow-up), even if
chat history is empty. Do not wait for the owner to repeat them.

The canonical apply runner is **`cloud_apply.py`**. Older scripts
(`browser_apply*.py`, `headed_apply.py`, `apply_now.py` as a full Firefox run,
`amazon_apply.py`, `apply_parallel.py`, `firefox_real.py`) are **not** the daily
path.

Profile on every form: current CTC **52 LPA**, expected CTC **60 LPA**
(INR 6000000), notice immediate, Hyderabad. Do not fill 65 LPA.

## Every run must

1. Apply to leftover matching Hyderabad / Remote-India jobs. Do not only discover
   or tailor. Queue first (`apply_now.queue()`), then discover more if the
   career-portal queue is empty.
2. Run headed Chrome on `DISPLAY=:1`:
   `python3 cloud_apply.py --headed --wait 360 --limit 80`
   Naukri / LinkedIn / Indeed / Cutshort / Foundit / Instahyre run in the same
   loop (3 other-board jobs per 1 career portal). One Chrome profile —
   do not attach a second Playwright to CDP 9222.
3. After each **SUBMITTED** application, tell the owner in **this agent chat**
   (company, title, URL). Also append `data/applications/SUBMITTED.md`.
4. **Google 2FA number in this chat — do not wait to be asked.** As soon as
   Chrome shows 2-Step Verification, post the tap number here immediately,
   as its own line: `Google 2FA number: NN`. Tell the owner to tap **Yes**
   on Nothing Phone (3) / OnePlus 7 Pro, then tap **NN**. The runner writes
   `data/applications/GOOGLE_2FA.md` and prints `GOOGLE_2FA_NUMBER=NN`.
   Read that file (or the apply log) and post the number before other status.
   Re-post if the number changes. Keep the 2FA tab open. Session-skip
   Naukri / LinkedIn / Indeed / Instahyre while 2FA is up.
5. If a CAPTCHA / 2FA puzzle appears, **notify the owner in this agent chat**
   immediately (company, title, URL, what to solve). **Keep that CAPTCHA tab
   open.** Do not wait idle for hours. Open a **new tab** and start the next
   leftover. When the owner is back they solve parked CAPTCHAs in
   **Desktop / Take control**; then continue those same applications.
6. After filling everything the runner can, if leftover fields still need a
   human: try to fill them. If the owner is away, **do not wait** — move to the
   next leftover. If the owner is present (`--owner-present`), notify in this
   agent chat, list the fields, **learn answers they type**, and **wait on that
   tab** (`NEED_INPUT`). Do not start another leftover until they finish or
   ask. `--watch-open` continues the already-open tab only (no new leftovers,
   do not reset Chrome tabs). Same for identity codes if Gmail is already open.
7. **One live application at a time**, except parked CAPTCHA tabs stay open.
   Close the current apply tab and open the next leftover after **SUBMITTED**,
   **404/closed**, or **Sign In / Create Account rejects every portal password**.
   Do not sit on a locked login.
7. When the daily apply finishes, email **rafi.success@gmail.com** the same way
   the other daily automations do: submitted / blocked / leftover. Runner:
   `python3 notify_daily_email.py` (also called at the end of every
   `cloud_apply.py` run, and on process exit if that call was skipped). Prefer
   `RESEND_API_KEY` (Resend, same as Notification Job; set it on this
   environment's Secrets tab). Else Gmail app password SMTP
   (`GMAIL_APP_PASSWORD`). Else Gmail compose in the already-open
   rafi.success Chrome. Never commit keys. The Gmail *account* password
   cannot SMTP (2FA).

## Chrome (always)

- Profile email: `rafi.success@gmail.com` only. Never a throwaway profile.
- Binary: `/opt/google/chrome/chrome` — **never** `/usr/local/bin/google-chrome`
  (that wrapper forces `~/.config/google-chrome` and `--test-type`).
- Profile dir: `data/chrome_profile` (Default), CDP `http://127.0.0.1:9222`.
- Apply in **one new tab** for the live job. Parked CAPTCHA tabs stay open.
  Do not navigate or close Google / Gmail tabs. After a successful submit,
  a closed/404 posting, or a locked/rejected portal login, close that apply
  tab and open the next leftover.
- Google password lives in gitignored `.env` (`GOOGLE_PASSWORD`) and automation
  memory `secrets.md`. Load via `google_auth.py`. Never commit it. Never put it
  in `field_memory.json` or `DAILY_REPORT.md`. 2FA: Nothing Phone (3) and
  OnePlus 7 Pro. Every headed run must print and chat-post the tap number
  (`google_auth.announce_2fa_number` → `GOOGLE_2FA.md`). Never create a
  Google password.
- Career-site **Create Account / Sign In** (Workday, Oracle, Greenhouse, etc.)
  uses gitignored `.env` `APPLY_ACCOUNT_PASSWORD`, then
  `APPLY_ACCOUNT_PASSWORD_FALLBACKS`. Fill them on every create-account / sign-in
  form. Never commit them. Never store them in `field_memory.json`.

## Simplify Copilot (always)

- Load Simplify Copilot (`data/tools/simplify-ext`, store id
  `pbanhockgagggenencehbnadejlgchfc`).
- Click Copilot **Start Application** / **Apply Now** on the **right** panel
  (`#start-application-button`) immediately. Do not sit idle waiting. Never
  **Tailor Resume** / **Resume Builder**.

## What to click on ATS pages

Prefer, in order: **Apply Manually**, **Autofill with Resume**, **Start Application**,
**Apply for this job**, **Apply Now**, **I'm interested**, then exact **Apply**.
Never click **Apply with Indeed**, LinkedIn intercepts, Share, or Talent Network.
Walk shadow DOM (Workday modals). Do not use CSS `a[href*="apply" i]` (the `i`
flag throws and disables every Apply click).

Guest apply URLs (`/apply/email`, Lever `/apply`) are real forms — fill them.
Do not treat a checkbox reCAPTCHA as a skip. Only a visible puzzle
("drag the shape", large hCaptcha challenge) needs the owner.

Check terms/privacy boxes (including hidden `#legal-disclaimer-checkbox`).
Leave honeypot fields empty.

## Queue / matching

- Career portals and other boards in the same loop (3:1, or 2 other + 1 LinkedIn
  + 1 career when LinkedIn is open). Naukri / LinkedIn / Indeed / Cutshort /
  Foundit / Instahyre are Easy Apply — start them immediately; do not hold
  them behind slow Workday forms.
- **LinkedIn (do not get restricted again):** LinkedIn blamed high-volume
  *profile data* access via a third-party tool. Until the stated lift time in
  `data/linkedin_guard.json` (30 Aug 2026 7:43 PM PDT / 31 Aug 02:43 UTC),
  session-skip LinkedIn only — do **not** persist-skip leftovers. After it
  lifts: apply **12 Easy Applies per run** (15/day max), **90s** between them,
  **no Simplify Copilot** on LinkedIn, never open `/in/` or Recruiter profiles,
  Easy Apply on `jobs/view` only. If a restriction or checkpoint page appears,
  stop LinkedIn for the rest of the run. Do not scrape Voyager people APIs.
- No per-company application cap. Duplicate company+title listings are still
  collapsed. Skip Salesforce/SAP/PEGA, Java-mandatory, DevOps-primary, and
  out-of-scope titles already in `apply_now.py`.
- Prefer companies in **RMZ Nexity / Futura / Spire, Knowledge City,
  Knowledge Park, and Raheja Mindspace** (Madhapur / HITEC City commute).
  List + score boost: `data/preferred_campuses.json` and
  `apply_now.is_preferred_campus_job()`. Those leftovers go first within
  career portals and within other boards.
- Resume base for every apply is
  `data/resume/Mohammed_Abdul_Rafi_Ahmed_Resume.docx` (owner upload).
  `tailor_resume.require_for_job()` copies that file and overlays headline /
  summary / competency order from the JD only. **Every application must use
  that tailored file.** If tailoring fails, skip the job — never upload the
  untailored base or `Rafi_Resume_Technical_Architect.docx` (old XML stub).
  Do **not** invent skills.
  Persist submitted, closed-404, and locked/rejected-login jobs in
  `data/applied_ids.json` so they are never reopened.
- After each apply-runner code fix, commit, push the feature branch, and
  **merge into `main`** (`git push origin HEAD:main`). Do not leave PRs sitting.

## Code map (this is the apply stack)

| File | Role |
|---|---|
| `cloud_apply.py` | Headed Chrome apply + Copilot + wait-for-CAPTCHA + submit notify |
| `ats_fill.py` | Open-source ATS dropdown / React-input / Phenom ack / ATS Submit (skip Copilot overlay) |
| `simplify_copilot.py` | Autofill this page / Continue; skip Tailor Resume |
| `google_auth.py` | Sign in rafi.success Chrome from `.env` |
| `apply_now.py` | Queue, scoring, persist applied |
| `discover_preferred_campuses.py` | Live search of RMZ / Knowledge City / Raheja tenants; leftovers first |
| `linkedin_guard.py` | LinkedIn restriction window, 12/run Easy Apply cap, no Copilot |
| `form_memory.py` | Learned answers on later forms |
| `tailor_resume.py` | Copy uploaded base resume + overlay truthful JD keywords |
| `notify_daily_email.py` | Email rafi.success@gmail.com when the daily apply finishes |
