# Variable-driven monitor reactivation design

## Goal

Reactivate the monitor for one current request only:

- Date: 05/10/2026
- Route: Belgrave to Lakeside (Return), code `BEL-LAK`
- Party: 8 adults, 0 children

Each future request replaces the prior date, route, and passenger counts. It
does not append another target.

## Configuration

GitHub Actions repository variables are the production source:

- `TARGET_DATES`
- `ROUTE_CODE`
- `ADULT_COUNT`
- `CHILD_COUNT`

`config.json` is updated to the same values so local checks and production
checks cannot fall back to an obsolete party.

## Runtime behavior

`check_ticket.py` reads all four variables and validates passenger counts as
non-negative integers. It then uses the existing passenger-aware booking flow,
which creates an eight-adult booking session before querying availability.

Invalid variables fail the workflow without sending an availability alert.
After a successful manual check, the hourly schedule is re-enabled.
