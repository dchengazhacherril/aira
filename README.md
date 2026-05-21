# Aira

## Overview

Aira is an SMS-first copilot for Airbnb hosts. It is designed to help hosts manage important Airbnb activity from their phone instead of logging into Airbnb or separate property management software.

The core value proposition is simple: when something important happens, Aira should text the host, make the situation clear, and help them respond quickly.

## Core Magic

Aira should make a host feel like they can run their Airbnb from their phone.

## Product Vision

Aira should feel like a lightweight assistant that texts hosts when something important happens.

Over time, it should help with:

- Guest communication
- Host alerts
- Listing optimization

## Current Stage

Aira is in a very early MVP stage.

The current goal is narrow: allow a host to respond to relevant Airbnb messages from SMS or iMessage instead of logging into Airbnb.

We are building step by step and simulating parts of the workflow before adding real integrations.

## MVP Scope

The MVP is:

- Read Airbnb emails from email
- Parse the relevant message
- Identify whether the message belongs to a listing you host or co-host
- Send the message to the host via SMS
- Let the host respond by SMS
- Send the response back through email on the correct thread
- Track Airbnb reservations from notification emails
- Send high-value reservation alerts such as same-day turnover and check-in context

If a feature does not directly support this loop, it is not part of the MVP.

## Roadmap

- MVP: send texts that allow a host to respond to relevant Airbnb messages for listings they host or co-host
- V1: AI-generated suggested replies with host review, edit, and send
- V2: battery alerts and other low-risk host notifications
- V3: listing optimization suggestions based on guest message patterns

## Current MVP Rule

For now, Aira should only process Airbnb messages that appear to belong to listings you host or co-host.

Simple heuristic:

- If the Airbnb email clearly belongs to the host-side inbox, it is relevant
- If the sender is a guest or co-host, it is relevant
- If the sender matches the `hosted by ...` name, it is likely a host-originated message and Aira should ignore it
- If you are only the guest on the reservation, Aira should ignore it

## Host Memory

Each host should have a small structured memory folder so Aira can stay organized as more hosts onboard.

Current structure:

- `.local/hosts/<host_id>/profile.json`: listing facts like Wi-Fi, check-in time, parking, trash location, and listing name
- `.local/hosts/<host_id>/preferences.json`: learned host style like tone and sign-off
- `.local/hosts/<host_id>/playbooks.json`: simple handling rules for common situations like parking, Wi-Fi, check-in, check-out, or lockout

For now, Aira uses this memory to classify messages and generate simple suggested replies. When a host edits a reply for a learnable topic, Aira saves that fact back to `profile.json` so future suggestions can use it.

For the MVP, create these host folders manually. Aira does not automatically create or rename host folders.

## Reply Loop

The current reply loop is intentionally simple:

- Aira reads the newest unread Airbnb email
- Aira classifies the message
- Aira generates a suggested reply when grounded host facts exist
- Aira marks low-confidence cases for manual review
- Aira sends the message summary to the host by SMS
- The host can reply with:
  - `SEND` to use the suggested reply
  - `SKIP` to do nothing
  - `EDIT <message>` to send a custom edited reply
  - any other text to send that text as the reply for the newest pending message

When Aira sends the outbound SMS, it saves the pending Gmail thread in `.local/pending_replies.json`. The inbound SMS webhook reads the newest pending reply context and sends the final reply through Gmail on the same Airbnb thread.

If Aira marks a message as needing manual review, `SEND` is blocked. The host can reply with the message they want to send, or `SKIP`.

If more than one Airbnb reply is pending and the host sends a reply without a hidden reply ID, Aira asks which pending guest/message the reply belongs to before sending anything. Reply with the number, guest name, or `CANCEL`. Clarification prompts expire after 6 hours.

When the host sends a custom reply for a learnable topic such as trash, Aira stores that answer in the host profile and can suggest it next time.

## Gmail Setup

This project now includes the first Gmail integration step: read the newest unread Airbnb email from Gmail, parse it, and send relevant host-side messages to your phone with Twilio.

### 1. Create Google Cloud credentials

Follow Google's Gmail API Python quickstart for a desktop app:

- Create or choose a Google Cloud project
- Enable the Gmail API
- Configure the OAuth consent screen
- Create an OAuth client for a Desktop app
- Download the OAuth client file as `credentials.json`
- Put `credentials.json` in `.local/credentials.json`

The operational Airbnb cohost identity for the MVP is:

`aira.cohost@gmail.com`

Airbnb should send host-side notification emails to that address, and Aira should send all Airbnb email replies from that address. In this local setup, Google may authenticate the mailbox as the upgraded account `david@getaira.host`, while `aira.cohost@gmail.com` remains the working Gmail send-as identity for Airbnb.

### 2. Install dependencies

It is safest to use a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Put your local secrets in a local-only folder:

```bash
mkdir -p .local
```

Examples:

- `.local/credentials.json`
- `.local/token-david_getaira.host.json`
- `.local/.env`
- `.local/hosts/`

Set the Gmail account and outbound Airbnb identity in `.local/.env`:

```bash
GMAIL_ACCOUNT_EMAIL=david@getaira.host
GMAIL_SEND_AS_EMAIL=aira.cohost@gmail.com
TWILIO_VALIDATE_REQUESTS=true
```

### 3. Run the app

```bash
.venv/bin/python -m scripts.check_airbnb_email
```

This starts the inbound SMS reply server, opens a temporary Cloudflare Tunnel, updates the Twilio inbound webhook, checks Gmail for the newest unread Airbnb message, sends a text if the message is relevant, and then waits for your SMS reply. After the pending reply is sent, skipped, or the local wait times out, the script stops the local webhook and tunnel processes.

The default local wait is 15 minutes. To change it:

```bash
.venv/bin/python -m scripts.check_airbnb_email --reply-timeout-seconds 600
```

The first run will open a browser window for Google OAuth. Sign in to the Google account whose canonical email is `david@getaira.host`. Aira will still send Airbnb replies using the configured send-as address `aira.cohost@gmail.com`.

If you previously authenticated a different mailbox, this setup will prompt for a fresh OAuth login because Aira stores the token by Gmail account.

### 4. What the app reads

The app currently looks for the newest unread inbox email from:

`express@airbnb.com`

Emails from `automated@airbnb.com` are ignored by the active reply loop because Airbnb does not accept normal email replies for those notifications.

It prints:

- Subject
- From
- Date
- Snippet
- Plain text body, if available
- Parsed sender name
- Parsed sender role
- Parsed listing name when available

If the message looks relevant to a listing you host or co-host, the app also sends it to your phone with Twilio.

## Reservation Alerts

Aira also has a separate reservation checker:

```bash
.venv/bin/python -m scripts.check_reservations
```

This reads reservation-related emails from `automated@airbnb.com` and `express@airbnb.com`, stores reservation details, and sends only high-value host alerts:

- Same-day turnover alert at noon the day before
- Check-in alert at noon on check-in day
- Checkout alert at noon only if the next guest arrives within 7 days

Reservation emails update the ledger only. Aira does not reply to `automated@airbnb.com`.

## SMS Reply Webhook

The normal email-check command now runs the full local reply flow:

```bash
.venv/bin/python -m scripts.check_airbnb_email
```

This local runner exits automatically after your reply is handled, or after the configured timeout. Use the lower-level reply server command only when you intentionally want the webhook and tunnel to keep running.

After the email checker texts you an Airbnb message, reply to that text with:

- `SEND` to send the suggested reply
- `SKIP` to clear the pending reply without sending
- `EDIT Thanks, that works for us.` to send the edited message
- Or just type the exact message you want to send for the newest pending message

The local reply server disables Twilio request signature validation for Cloudflare quick-tunnel testing. A production deployment should turn validation back on with a stable public URL.

Lower-level manual commands are still available:

```bash
.venv/bin/python -m scripts.run_reply_server
```

```bash
.venv/bin/python -m aira.sms_webhook
```

If you use the manual webhook, expose port `8000` yourself and configure the Twilio Messaging Service inbound webhook to:

```text
https://<your-public-domain>/sms/reply
```

Use HTTP `POST`.

## Local Development

This repo is currently a local prototype focused on validating the workflow, not productionizing infrastructure.

Project layout:

- `aira/`: application modules for Gmail, Airbnb parsing, Twilio SMS, reply state, and reply generation
- `scripts/`: runnable local commands
- `tests/`: unit tests for parser, reply flow, reply state, and webhook behavior
- `.local/`: ignored local secrets, Gmail tokens, host memory, and pending reply state

## Railway Deployment

For an always-on MVP, deploy Aira as:

- A Railway web service running `python -m scripts.railway_entrypoint`
- A Railway cron service running `python -m scripts.railway_entrypoint`
- A Railway cron service named `aira-reservations` running `python -m scripts.railway_entrypoint`
- A Railway Postgres database shared by both services

See `RAILWAY_DEPLOY.md` for the step-by-step setup and required environment variables.

A simple landing page and waitlist may be built separately, but that is not the focus of this codebase.
