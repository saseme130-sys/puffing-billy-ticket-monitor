# High-frequency Azure ticket monitor design

## Goal

Detect eight available adult return tickets for 5 October 2026 from Belgrave
to Lakeside within approximately two minutes, without continuously running
the expensive exact-party booking sequence.

## Architecture

Azure Functions is the primary scheduler and runs every two minutes. Each run
uses two stages:

1. Fetch the lightweight empty-session availability overview.
2. Only when the overview indicates that `BEL-LAK` may be available, create a
   fresh booking session, add eight adults, and query exact-party availability.

GitHub Actions remains a lower-frequency 30-minute fallback. Both execution
paths use the same monitor logic and Azure Blob state.

## Notifications

When exact-party availability changes from unavailable to available:

- Send a ServerChan WeChat notification immediately.
- Send an email to `244823781@qq.com` immediately through QQ SMTP.
- Repeat both notifications five minutes later.
- Repeat both notifications once more after another five minutes.
- Stop repeating after three total notification rounds.

A later unavailable result resets the cycle. A future transition back to
available starts a new three-notification cycle.

QQ SMTP uses the mailbox's generated authorization code, never the mailbox
password. The authorization code and ServerChan key are stored only as Azure
application secrets and GitHub Actions secrets.

## State

Azure Blob Storage records:

- last exact availability state;
- notification cycle identifier;
- number of completed notification rounds;
- next reminder time;
- consecutive request failures;
- backoff-until time.

Blob updates use optimistic concurrency so overlapping Azure and GitHub runs
cannot both send the same reminder.

## Rate-limit safety

The site publishes no numeric rate-limit threshold. Normal two-minute runs use
only the lightweight overview request sequence. The eight-adult sequence runs
only after a positive overview signal.

HTTP 429 and 403 responses trigger backoff instead of immediate retries.
Transient network and 5xx errors receive at most one short retry. Operational
failures do not produce availability alerts.

## Validation

- Unit tests cover two-stage gating, exact eight-adult confirmation, reminder
  timing, state reset, and rate-limit backoff.
- A deployment smoke run must show the current target as sold out without
  sending an availability alert.
- Azure runs every two minutes; the personal GitHub workflow runs every thirty
  minutes. The enterprise workflow remains disabled.
