# Variable-Driven Monitor Reactivation Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the previous monitor target with 5 October 2026, Belgrave to Lakeside return, for eight adults, and reactivate hourly checks.

**Architecture:** Add strict adult and child count environment overrides alongside the existing date and route overrides. Keep `config.json` synchronized as the safe local fallback, then set all four GitHub Variables and verify a manual production run before enabling the schedule.

**Tech Stack:** Python 3 standard library, `unittest`, GitHub Actions.

---

### Task 1: Add passenger variable overrides

**Files:**
- Modify: `check_ticket.py`
- Modify: `tests/test_notifications.py`

**Step 1: Write failing tests**

Verify `ADULT_COUNT=8` and `CHILD_COUNT=0` replace the configured passenger
counts. Verify negative, fractional, and non-numeric values return an error
before any website request.

**Step 2: Run tests**

Run: `python3 -m unittest discover -s tests -v`

Expected: FAIL because passenger variables are not read.

**Step 3: Implement strict overrides**

Parse each configured environment variable with decimal integer syntax and
reject values below zero. Require at least one passenger after overrides.

**Step 4: Run tests**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add check_ticket.py tests/test_notifications.py
git commit -m "feat: configure passenger counts from Actions variables"
```

### Task 2: Replace the active target everywhere

**Files:**
- Modify: `config.json`
- Modify: `.github/workflows/ticket_monitor.yml`
- Modify: `README.md`

**Step 1: Replace local fallback**

Set:

```json
"target_dates": ["05/10/2026"],
"route_code": "BEL-LAK",
"passengers": {"adult": 8, "child": 0}
```

**Step 2: Map repository variables**

Add `ADULT_COUNT` and `CHILD_COUNT` to the workflow environment.

**Step 3: Update documentation**

Replace all old target references and document that each new request replaces
the prior target.

**Step 4: Validate**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile monitor.py check_ticket.py
```

Expected: all checks pass.

**Step 5: Commit**

```bash
git add config.json .github/workflows/ticket_monitor.yml README.md
git commit -m "config: monitor October return tickets for eight adults"
```

### Task 3: Configure and reactivate GitHub Actions

**Files:**
- No repository files.

**Step 1: Set repository variables**

Set:

```text
TARGET_DATES=05/10/2026
ROUTE_CODE=BEL-LAK
ADULT_COUNT=8
CHILD_COUNT=0
```

**Step 2: Push implementation**

Push all commits using the personal GitHub account.

**Step 3: Run one manual check**

Trigger `ticket_monitor.yml` and inspect the log for the target, route, and
passenger-aware result.

**Step 4: Enable scheduling**

Enable the workflow only after the manual run succeeds.

**Step 5: Confirm state**

Verify the personal workflow is active and the obsolete enterprise workflow
remains disabled.
