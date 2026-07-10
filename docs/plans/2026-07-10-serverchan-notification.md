# ServerChan Ticket Alerts Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Send bookable-ticket and manual test alerts to WeChat through ServerChan without exposing the SendKey.

**Architecture:** Add a standard-library ServerChan adapter to the shared notification module and load its key through the existing secret override path. Make the cloud entry point fail when no configured notification channel succeeds, and add a workflow input that sends a test notification without querying ticket availability.

**Tech Stack:** Python 3.12 standard library, `unittest`, GitHub Actions, ServerChan HTTP API.

---

### Task 1: Specify ServerChan response handling

**Files:**
- Create: `tests/test_notifications.py`
- Modify: `monitor.py:149-239`

**Step 1: Write the failing tests**

Create tests that patch `monitor.http` and verify:

```python
import json
import unittest
from unittest.mock import patch

import monitor


class ServerChanTests(unittest.TestCase):
    def test_successful_send(self):
        cfg = {"notify": {"serverchan_key": "SCT_test"}}
        response = json.dumps({"code": 0, "message": "SUCCESS", "data": {"pushid": "1"}})
        with patch("monitor.http", return_value=response):
            self.assertEqual(
                monitor.notify_serverchan(cfg, "Ticket alert", "Available"),
                (True, "SUCCESS"),
            )

    def test_rejected_send(self):
        cfg = {"notify": {"serverchan_key": "SCT_test"}}
        response = json.dumps({"code": 40001, "message": "bad sendkey"})
        with patch("monitor.http", return_value=response):
            self.assertEqual(
                monitor.notify_serverchan(cfg, "Ticket alert", "Available"),
                (False, "bad sendkey"),
            )

    def test_missing_key_is_skipped(self):
        self.assertIsNone(monitor.notify_serverchan({"notify": {}}, "title", "body"))
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_notifications -v`

Expected: FAIL because `notify_serverchan` does not exist.

**Step 3: Implement the minimal adapter**

In `monitor.py`, URL-encode a form body with `title` and `desp`, POST it to:

```python
"https://sctapi.ftqq.com/{}.send".format(key)
```

Parse JSON and accept only `code == 0`. Return `None` when the key is absent and
`(False, error)` for HTTP, JSON, or API failures. Never log or return the key.

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_notifications -v`

Expected: all ServerChan tests PASS.

**Step 5: Commit**

```bash
git add monitor.py tests/test_notifications.py
git commit -m "feat: add ServerChan notification adapter"
```

### Task 2: Wire configuration and delivery failures

**Files:**
- Modify: `monitor.py:217-239,318-331`
- Modify: `check_ticket.py:20-67`
- Modify: `tests/test_notifications.py`

**Step 1: Write failing orchestration tests**

Add tests verifying:

- `SERVERCHAN_KEY` overrides `notify.serverchan_key`.
- `send_all` tries ServerChan before legacy channels.
- `send_all` returns `True` after the first successful remote channel.
- `send_all` returns `False` when every configured remote channel fails.
- A cloud bookable result returns a non-zero exit code if delivery fails.

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_notifications -v`

Expected: FAIL because the environment override and boolean result are absent.

**Step 3: Implement configuration and orchestration**

Extend `apply_secret_overrides` with:

```python
if os.getenv("SERVERCHAN_KEY", "").strip():
    cfg["notify"]["serverchan_key"] = os.getenv("SERVERCHAN_KEY").strip()
```

Also allow `serverchan_key` in `secrets.local.json`. Update `send_all` to return
whether at least one configured remote channel succeeded. In `check_ticket.py`,
track delivery failures and return `3` when a bookable alert could not be sent.

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_notifications -v`

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add monitor.py check_ticket.py tests/test_notifications.py
git commit -m "fix: surface ticket alert delivery failures"
```

### Task 3: Add an explicit cloud test mode

**Files:**
- Modify: `check_ticket.py:1-71`
- Modify: `tests/test_notifications.py`

**Step 1: Write failing test-mode tests**

Patch `monitor.send_all`, set `TEST_NOTIFICATION=true`, and verify `main()`:

- sends a recognizable test title;
- skips `fetch_oid_token` and `fetch_availability`;
- returns `0` after delivery and `3` after failed delivery.

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_notifications -v`

Expected: FAIL because test mode is not implemented.

**Step 3: Implement test mode**

Before ticket fetching, read:

```python
test_notification = os.getenv("TEST_NOTIFICATION", "").lower() == "true"
```

When enabled, build a short diagnostic message, call `send_all`, and return
`0` or `3` based on actual delivery.

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_notifications -v`

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add check_ticket.py tests/test_notifications.py
git commit -m "feat: add cloud notification test mode"
```

### Task 4: Configure GitHub Actions and documentation

**Files:**
- Modify: `.github/workflows/ticket_monitor.yml:3-33`
- Modify: `README.md`

**Step 1: Add the workflow input**

Define a boolean `workflow_dispatch.inputs.test_notification` with default
`false`, then inject:

```yaml
SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
TEST_NOTIFICATION: ${{ inputs.test_notification || 'false' }}
```

Remove `WXPUSHER_SPT` and `PUSHPLUS_TOKEN` from the cloud job so ServerChan is
the only production cloud channel.

**Step 2: Update documentation**

Document ServerChan as the active WeChat channel, the `SERVERCHAN_KEY` Secret,
and the manual test input. Remove claims that WxPusher currently provides the
active WeChat path.

**Step 3: Validate syntax and tests**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile monitor.py check_ticket.py
```

Expected: tests PASS and compilation exits zero.

**Step 4: Commit**

```bash
git add .github/workflows/ticket_monitor.yml README.md
git commit -m "ci: use ServerChan for ticket alerts"
```

### Task 5: Store the secret and verify real delivery

**Files:**
- No repository files.

**Step 1: Store the SendKey**

Run `gh secret set SERVERCHAN_KEY` using standard input so the value does not
appear in shell history or command output.

**Step 2: Push implementation commits**

Run: `env -u GH_TOKEN git push`

Expected: the personal repository accepts all commits.

**Step 3: Trigger a test notification**

Run:

```bash
env -u GH_TOKEN gh workflow run ticket_monitor.yml \
  -f test_notification=true \
  -R saseme130-sys/puffing-billy-ticket-monitor
```

**Step 4: Verify the workflow**

Wait for the run and inspect its log.

Expected: the job succeeds and reports ServerChan delivery success without
printing the SendKey.

**Step 5: Confirm persistence**

Verify the hourly workflow remains enabled and `SERVERCHAN_KEY` appears in the
repository Secret list.
