# Standing orders — every Candidate job applications run

These rules apply on **every** run of this automation (cron or follow-up), even if
chat history is empty. Do not wait for the owner to repeat them.

The canonical apply runner is **`cloud_apply.py`**. Older scripts
(`browser_apply*.py`, `headed_apply.py`, `apply_now.py` as a full Firefox run,
`amazon_apply.py`, `apply_parallel.py`, `firefox_real.py`) are **not** the daily
path.

## Every run must

1. Apply to leftover matching Hyderabad / Remote-India jobs. Do not only discover
   or tailor. Queue first (`apply_now.queue()`), then discover more if the
   career-portal queue is empty.
2. Run headed Chrome on `DISPLAY=:1`:
   `python3 cloud_apply.py --headed --wait 360 --limit 80`
3. After each **SUBMITTED** application, tell the owner in **this agent chat**
   (company, title, URL). Also append `data/applications/SUBMITTED.md`.
4. If a CAPTCHA / 2FA puzzle appears, **notify the owner in this agent chat**
   immediately (company, title, URL, what to solve). Leave Chrome on that tab
   and wait. The owner will solve it in **Desktop / Take control**. Do not skip
   the job. After it is solved, keep filling this same application and submit.
5. After filling everything the runner can, if leftover fields still need a
   human (**notify in this agent chat**): list the fields, leave Chrome on that
   tab, and wait. Same for identity codes if Gmail is already open — otherwise
   ask the owner. Do not silently sit on a blocked form.
6. **One application at a time.** Open a single job tab. Do not open another until
   that application is **SUBMITTED**. Then close the tab and move to the next.
   Close the tab and open the next leftover when the posting is **404/closed**, or
   when **Sign In / Create Account rejects every portal password** (wrong password
   or locked account). Do not sit on a locked login. CAPTCHA and leftover fields
   still wait on the same tab.

## Chrome (always)

- Profile email: `rafi.success@gmail.com` only. Never a throwaway profile.
- Binary: `/opt/google/chrome/chrome` — **never** `/usr/local/bin/google-chrome`
  (that wrapper forces `~/.config/google-chrome` and `--test-type`).
- Profile dir: `data/chrome_profile` (Default), CDP `http://127.0.0.1:9222`.
- Apply in **one new tab**. Never more than one application tab. Do not navigate or close Google / Gmail tabs. After a successful submit, a closed/404 posting, or a locked/rejected portal login, close that apply tab and open the next leftover.
- Google password lives in gitignored `.env` (`GOOGLE_PASSWORD`) and automation
  memory `secrets.md`. Load via `google_auth.py`. Never commit it. Never put it
  in `field_memory.json` or `DAILY_REPORT.md`. 2FA: Nothing Phone (3).
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

- Career portals first (Greenhouse, Lever, Workday, Phenom, SmartRecruiters,
  Oracle Cloud, iCIMS). Naukri / LinkedIn / Indeed / Cutshort / Foundit /
  Instahyre are other automations.
- Career portals are **not** capped per company. Aggregator boards stay at 3 per
  company. Skip Salesforce/SAP/PEGA, Java-mandatory, DevOps-primary, and
  out-of-scope titles already in `apply_now.py`.
- Do **not** invent skills on the resume. Persist submitted, closed-404, and
  locked/rejected-login jobs in `data/applied_ids.json` so they are never reopened.

## Code map (this is the apply stack)

| File | Role |
|---|---|
| `cloud_apply.py` | Headed Chrome apply + Copilot + wait-for-CAPTCHA + submit notify |
| `simplify_copilot.py` | Autofill this page / Continue; skip Tailor Resume |
| `google_auth.py` | Sign in rafi.success Chrome from `.env` |
| `apply_now.py` | Queue, scoring, persist applied |
| `form_memory.py` | Learned answers on later forms |
| `tailor_resume.py` | Per-job `.docx` (truthful keywords only) |
