# Aira Context

## Product

Aira is an SMS-first copilot for Airbnb hosts.

Near-term goal: let a host handle Airbnb guest communication from SMS or iMessage instead of logging into Airbnb.

Long-term direction:

- Guest communication
- Host alerts
- Listing optimization

## Current MVP Scope

Build only this loop:

- Read Airbnb emails from email
- Parse the relevant message
- Identify whether the message belongs to a listing you host or co-host
- Send the message to the host via SMS
- Let the host respond by SMS
- Send the response back through email on the correct thread

## Roadmap

- MVP: Airbnb message relay and reply loop over SMS for listings you host or co-host
- V1: AI-suggested replies with host review and editing
- V2: battery alerts and other low-risk host notifications
- V3: listing optimization suggestions based on guest message patterns

## Non-Goals

Do not build yet:

- Dashboard
- Web app product
- Complex auth
- Property management system features
- Calendar sync
- Booking.com support
- Listing optimization features
- Battery alerts
- Autopilot sending unless explicitly added later

## Coding Principles

- Keep code simple and beginner-friendly
- Prefer minimal, readable Python
- Use small modules
- Avoid overengineering
- Build and test one layer at a time
- Simulate first, then add real integrations
- Explain changes clearly

## Preferred Stack And Style

- Python for core logic
- Plain scripts and small modules
- JSON files for per-host memory
- Environment variables via `.env`
- Minimal dependencies
- No frameworks unless there is a strong reason
- Clear function names and straightforward control flow

## Current Priorities

Build in this order:

1. Reliable email ingestion
2. SMS sending
3. Connect email ingestion to SMS delivery
4. Simple message classification and suggested replies
5. Simple host reply loop
6. SMS reply handling
7. Email reply sending on the correct thread

## Host Memory Structure

Each onboarded host should have:

- `profile.json` for static facts
- `preferences.json` for tone and behavior
- `playbooks.json` for situation handling rules

Keep this structure simple and local-first.
For now, host profiles are created manually. Do not build automatic host detection or onboarding sync from `automated@airbnb.com`.

## Current Reply Loop

Current MVP behavior:

- `SEND` means use the suggested reply
- `SKIP` means do nothing
- `EDIT <message>` means send the custom edited reply
- any other reply text is also treated as the host's edited reply

Aira saves one pending reply at `.local/pending_reply.json` after sending the outbound SMS. The `sms_webhook.py` process receives Twilio inbound SMS webhooks, resolves the host command, sends through Gmail on the original Airbnb thread, and clears the pending reply when it sends or skips.

For local testing, use `run_reply_server.py`. It starts `sms_webhook.py`, starts a temporary Cloudflare Tunnel, updates the Twilio Messaging Service inbound webhook URL, and streams reply logs.

## Current Relevance Rule

For now, process only Airbnb messages that appear relevant to your host-side workflow.

Current heuristic:

- Relevant if the Airbnb email is clearly tied to the host inbox
- Relevant if the sender is a guest or co-host
- Ignore if the sender matches the `hosted by ...` name
- Ignore if you are only the guest on the reservation

## Working Rules For Future Codex Sessions

- Optimize for the MVP loop, not a full host operations platform
- Reject features that expand scope too early
- Prefer the simplest working implementation
- Keep the repo easy to read and easy to modify
