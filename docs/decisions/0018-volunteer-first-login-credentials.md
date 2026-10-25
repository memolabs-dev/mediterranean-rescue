# ADR 0018 — Volunteer credentials after one-time invitation

Date: 25 October 2026
Status: implemented on feature branch; release requires full green CI

## Why

The app sends no email. A one-use invitation signs in a volunteer who otherwise has
no usable password. Without setting a password during an active session, the person
must ask an authorized coordinator for a fresh one-time link after a sign-out.

## Decision

Offer an optional credential setup panel on the signed-in volunteer dashboard.
Only active, ordinary accounts with a completed invitation and no usable password
can write credentials. Staff, superusers, publishers and coordinators are excluded
regardless of whether privileges came from roles or individual permissions.

The JSON endpoint is authenticated by Django session and protected by CSRF.
Password length is 12 to 128 characters and Django's standard validators apply.
The user must type the same value twice. Backend errors never echo credential
input. Django hashes the value with the configured hasher and rotates the active
session after changing it; other sessions are invalidated. The setup is one-time
and its database transition is guarded by a transaction and row lock. Status and
errors are private and non-cacheable. POST is rate limited by the existing sign-in
bucket.

No invitation token is reused or delivered automatically. Nothing alters roles,
publication rules or data privacy. Test users and records are fictitious.

## Limitations

A person who ignores the setup and later loses their authenticated session still
needs a new invitation. A forgotten password cannot yet be reset without a
reviewed recovery mechanism; adding an unverified email provider would not help.
The app must not promise self-service password recovery or send account emails
until delivery, monitoring, privacy and throttling are verified.
