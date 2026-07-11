# Passenger-aware availability design

## Problem

The public availability endpoint returns route-level availability for an empty
booking session. On 11 July it reported BEL-LAK as available for 29 August,
while the real booking calendar reported sold out after selecting two adults
and one child. This caused a false alert.

## Design

Reproduce the website's booking sequence in one token/cookie session:

1. Fetch a fresh `oidToken`.
2. Call `updateBookingFareQty` once per passenger, using the site's fare IDs.
3. Call `updateAvailability` with the same token and cookie.
4. Alert only when the resulting date and BEL-LAK route are available.

The passenger configuration remains `adult` and `child` counts. Fare IDs are
kept in one mapping close to the booking API code so a future site change is
easy to diagnose and update.

## Failure behavior

Any rejected fare update, malformed response, or availability request failure
must fail the GitHub Actions run and must not send an availability alert.
The workflow remains disabled until the passenger-aware production check
reports 29 August as sold out.

## Validation

- Unit tests verify two adult updates and one child update occur before the
  availability request.
- Tests verify all calls share the same token/cookie session and API errors are
  surfaced.
- A real one-off workflow run must report 29 August BEL-LAK as sold out and
  remain silent before the hourly schedule is re-enabled.
