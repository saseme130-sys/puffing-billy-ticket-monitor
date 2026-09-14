# High-Frequency Azure Ticket Monitor Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detect eight adult BEL-LAK return tickets for 5 October 2026 within about two minutes and send three rounds of WeChat and QQ email alerts.

**Architecture:** Azure Functions runs a two-stage monitor every two minutes: a lightweight overview check gates the existing exact eight-adult booking check. Azure Blob Storage coordinates state, reminder timing, and backoff; the personal GitHub Actions workflow runs the same core every thirty minutes as a fallback.

**Tech Stack:** Python 3.11, Azure Functions v2 model, Azure Blob Storage, ServerChan, QQ SMTP, GitHub Actions.

---

### Task 1: Add two-stage availability checking

**Files:**
- Modify: `monitor.py`
- Create: `tests/test_two_stage_monitor.py`

**Steps:**
1. Write tests proving an unavailable overview skips the eight-adult sequence.
2. Write tests proving a positive BEL-LAK overview triggers the exact-party sequence.
3. Add `fetch_overview_availability()` and a shared two-stage evaluator.
4. Run `python3 -m unittest discover -s tests -v`.
5. Commit: `feat: add two-stage ticket availability checks`.

### Task 2: Add persistent alert state

**Files:**
- Create: `high_frequency_monitor.py`
- Create: `tests/test_high_frequency_monitor.py`
- Modify: `requirements.txt`

**Steps:**
1. Write state-machine tests for unavailable reset, immediate first alert, reminders
   at +5 and +10 minutes, and no fourth alert.
2. Write tests for per-channel retry so a successful channel is not duplicated when
   the other channel fails.
3. Implement Azure Blob JSON state with conditional writes.
4. Add 429/403 backoff and one retry for transient network/5xx errors.
5. Run the focused and full tests.
6. Commit: `feat: persist high-frequency alert state`.

### Task 3: Add QQ email notification

**Files:**
- Modify: `monitor.py`
- Modify: `high_frequency_monitor.py`
- Create: `tests/test_email_notifications.py`

**Steps:**
1. Test SMTP SSL configuration, UTF-8 subject/body, and missing-secret handling.
2. Implement QQ SMTP using `QQ_SMTP_USER`, `QQ_SMTP_AUTH_CODE`, and
   `ALERT_EMAIL_TO`.
3. Keep credentials out of logs and repository files.
4. Run notification and full tests.
5. Commit: `feat: send ticket alerts by QQ email`.

### Task 4: Add Azure and GitHub entry points

**Files:**
- Create: `function_app.py`
- Modify: `requirements.txt`
- Modify: `.github/workflows/ticket_monitor.yml`
- Modify: `README.md`

**Steps:**
1. Add an Azure Timer Trigger with schedule `0 */2 * * * *`.
2. Change the personal GitHub schedule to every thirty minutes and run
   `high_frequency_monitor.py`.
3. Map Blob, ServerChan, and QQ SMTP secrets into both environments.
4. Document the two-stage behavior and replacement semantics.
5. Run tests and Python compilation.
6. Commit: `deploy: add Azure high-frequency ticket monitor`.

### Task 5: Provision and verify production

**Files:**
- No source files unless deployment metadata is required.

**Steps:**
1. Create a dedicated resource group, storage account, and Python Function App in
   Australia East.
2. Configure target date, `BEL-LAK`, eight adults, ServerChan, QQ SMTP, and Blob
   settings as Azure application settings.
3. Configure the same state and notification secrets in the personal GitHub
   repository only.
4. Deploy the Function App.
5. Run one Azure invocation and one GitHub fallback invocation.
6. Confirm the current sold-out result sends no availability alert.
7. Confirm Azure is scheduled every two minutes, personal GitHub every thirty
   minutes, and the enterprise workflow remains disabled.
