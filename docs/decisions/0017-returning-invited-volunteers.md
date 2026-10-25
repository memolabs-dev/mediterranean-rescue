# ADR 0017 — Returning invited volunteers without email delivery

Date: 25 October 2026
Status: interim decision, self-service recovery not yet shipped

## Problem

Volunteers who accept a one-time invitation receive an account with an unusable password.
The invitation expires after 72 hours and can only be used once. Following sign-out or
expiry of the browser session, an ordinary password login does not work for that account.
The former sign-in guidance only explained the first invitation and could mislead a
returning volunteer.

No outgoing email provider or verified delivery monitoring is configured in this
deployment. Claiming that a passwordless self-service email flow works would be unsafe.

## What works now

A staff coordinator with invitation permission can create a fresh one-time link for the
volunteer's existing email address. The backend checks the account again when the new
link is accepted; the original link stays spent, the same account is reused, and staff,
superusers, publishers and coordinators are protected by the existing takeover rules.
A coordinator without staff status cannot open an existing account by invitation.
No email is sent automatically: the authorized coordinator delivers the link through a
channel agreed with the volunteer.

The sign-in page must accurately tell both first-time and returning volunteers to ask
their coordinator for a new link when they have no password. The regression test proves
that a second invitation can reopen an ordinary existing volunteer without creating a
duplicate account, and that both links remain single-use.

## Follow-up needed to close issue #16

Provide reliable, monitored email delivery or a reviewed account-credential setup flow.
Only ship self-service recovery with explicit password validation or hashed, single-use,
short-lived tokens; CSRF, replay protection, per-address/IP rate limits, generic responses
that never enumerate accounts, audit events and staff/publisher/coordinator exclusions.
Test invitation reuse, revocation, concurrent requests, fresh device, sign-out,
language, keyboard accessibility and mobile. Keep all test identities fictitious.

**Do not represent coordinator-assisted return as self-service recovery.**
