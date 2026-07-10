# ServerChan notification design

## Goal

Deliver Puffing Billy availability alerts to WeChat reliably through ServerChan,
while keeping the SendKey out of the public repository.

## Architecture

- Keep ticket fetching and route-level availability evaluation unchanged.
- Add a ServerChan notification adapter to `monitor.py`.
- Read `SERVERCHAN_KEY` from a local ignored secrets file or the environment.
- Store the production key only as the `SERVERCHAN_KEY` GitHub Actions Secret.
- Make ServerChan the primary cloud notification channel. Keep existing channels
  available for local use, but do not inject the unreliable WxPusher SPT into
  the cloud workflow.

## Data flow

1. GitHub Actions runs `check_ticket.py` every hour.
2. The script fetches and evaluates the configured date and route.
3. Sold-out or unavailable results remain silent.
4. A bookable result is formatted once and sent through ServerChan.
5. ServerChan posts the alert to the user's bound WeChat account.

The manual workflow gains a `test_notification` input. When enabled,
`check_ticket.py` sends a test message without requiring tickets to be
available.

## Error handling

- Missing ServerChan configuration is reported explicitly.
- HTTP errors, invalid JSON, non-success response codes, and rejected sends are
  treated as notification failures.
- Cloud notification failures return a non-zero exit code so GitHub Actions
  surfaces the problem instead of recording a false success.
- Secrets are never printed in logs or committed.

## Validation

- Unit tests cover successful, rejected, malformed, and missing-key ServerChan
  responses.
- Existing availability evaluation remains covered by an end-to-end manual run.
- A manual `test_notification` run confirms actual WeChat delivery before the
  hourly schedule is considered operational.
