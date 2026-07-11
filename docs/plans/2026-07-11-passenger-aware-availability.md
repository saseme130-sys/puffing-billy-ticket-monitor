# Passenger-Aware Availability Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Alert only when 29 August BEL-LAK can accommodate two adults and one child.

**Architecture:** Reuse one fresh booking token and cookie for fare quantity updates and the final availability query. Convert configured passenger counts into the same `updateBookingFareQty` requests used by the website, then evaluate the returned route data with existing logic.

**Tech Stack:** Python 3 standard library, `unittest`, GitHub Actions.

---

### Task 1: Specify passenger session setup

**Files:**
- Create: `tests/test_availability.py`
- Modify: `monitor.py:27-112`

**Step 1: Write failing tests**

Patch `monitor.http` and verify `fetch_availability(token, passengers)` sends:

```text
fare=2867_2810 twice
fare=2867_2812 once
updateAvailability last
```

Verify every call uses the same `oidToken` cookie and a rejected fare update
raises `RuntimeError`.

**Step 2: Run the tests**

Run: `python3 -m unittest tests.test_availability -v`

Expected: FAIL because `fetch_availability` does not accept passengers.

**Step 3: Implement session setup**

Add one fare mapping:

```python
PASSENGER_FARES = {
    "adult": "2867_2810",
    "child": "2867_2812",
}
```

Create a shared booking POST helper that applies the token cookie. For each
configured count, call `updateBookingFareQty` with `increment=1`, require
`result == "OK"`, then call `updateAvailability`.

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_availability -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add monitor.py tests/test_availability.py
git commit -m "fix: check availability for configured passengers"
```

### Task 2: Pass passenger configuration through every entry point

**Files:**
- Modify: `monitor.py:265-267`
- Modify: `check_ticket.py:62-64`
- Modify: `tests/test_availability.py`

**Step 1: Add failing entry-point tests**

Verify local `check_once` and cloud `main` pass `cfg["passengers"]` into
`fetch_availability`.

**Step 2: Run tests**

Run: `python3 -m unittest discover -s tests -v`

Expected: FAIL until both entry points pass passenger data.

**Step 3: Wire the configuration**

Call:

```python
fetch_availability(token, cfg.get("passengers", {}))
```

Reject configurations with no positive supported passenger counts rather than
falling back to the inaccurate empty-session query.

**Step 4: Run full validation**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile monitor.py check_ticket.py
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add monitor.py check_ticket.py tests/test_availability.py
git commit -m "fix: require passenger-aware cloud checks"
```

### Task 3: Validate production and restore scheduling

**Files:**
- Modify: `README.md`

**Step 1: Document exact-party behavior**

State that availability is checked after selecting two adults and one child,
not from the empty-session calendar overview.

**Step 2: Push changes**

Run: `env -u GH_TOKEN git push`

**Step 3: Run a one-off production check**

Run:

```bash
env -u GH_TOKEN gh workflow enable ticket_monitor.yml \
  -R saseme130-sys/puffing-billy-ticket-monitor
env -u GH_TOKEN gh workflow run ticket_monitor.yml \
  -R saseme130-sys/puffing-billy-ticket-monitor
```

Expected log:

```text
29/08/2026 | 车次:Sold out | 整体:Sold out | 可订:False
目标日期暂无可订票，本次静默。
```

**Step 4: Confirm schedule state**

Verify the workflow is active and the test run succeeded without a ServerChan
availability alert.

**Step 5: Commit documentation**

```bash
git add README.md
git commit -m "docs: explain exact-party availability checks"
git push
```
