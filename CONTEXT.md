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
Learned facts from edited host replies should be saved back into `profile.json`. Keep `preferences.json` for style and behavior only.
For now, host profiles are created manually. Do not build automatic host detection or onboarding sync from Airbnb account metadata.

## Current Reply Loop

Current MVP behavior:

- `SEND` means use the suggested reply
- `SKIP` means do nothing
- `EDIT <message>` means send the custom edited reply
- any other reply text is sent as the host's reply for the newest pending message

Aira saves pending replies at `.local/pending_replies.json` after sending outbound SMS messages. Reply IDs are internal only; host-facing SMS messages should not include them. Commands target the newest pending reply.

If a reply needs manual review, `SEND` should not be accepted. The host can reply with the message they want to send, or `SKIP`.

When an edited reply answers a learnable topic, such as trash, Aira should save the answer to `profile.json` and use it for future suggested replies.

The `aira.sms_webhook` module receives Twilio inbound SMS webhooks, resolves the host command, sends through Gmail on the original Airbnb thread, and clears that reply ID when it sends or skips. Local Cloudflare quick-tunnel runs disable Twilio request signature validation because the signed public URL can differ from the forwarded local request. Production should use a stable public URL and re-enable validation.

For normal local testing, use `python -m scripts.check_airbnb_email`. It starts `aira.sms_webhook`, starts a temporary Cloudflare Tunnel, updates the Twilio Messaging Service inbound webhook URL, checks Gmail, sends a host SMS when relevant, and then waits for the pending SMS reply to be sent or skipped. After that reply is resolved, or after the local timeout, it stops the webhook and tunnel processes automatically.

Use `python -m scripts.run_reply_server` only when you want the lower-level inbound reply server by itself.

For Railway, run `python -m scripts.railway_entrypoint` for both services. The entrypoint starts the webhook by default and runs the checker once when the Railway service name contains `checker` or `AIRA_RAILWAY_ROLE=checker` is set. Set `DATABASE_URL` so pending replies and host memory are shared by both processes. Set `GMAIL_TOKEN_JSON` so the deployed services do not depend on local OAuth token files.

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
