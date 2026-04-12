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
- `.local/token.json`
- `.local/.env`

### 3. Run the app

```bash
.venv/bin/python main.py
```

The first run will open a browser window for Google OAuth. After you sign in and approve Gmail read-only access, Google will create a local `token.json` file so later runs do not need a new login.

### 4. What the app reads

The app currently looks for the newest unread inbox email from:

`express@airbnb.com`

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

## Local Development

This repo is currently a local prototype focused on validating the workflow, not productionizing infrastructure.

A simple landing page and waitlist may be built separately, but that is not the focus of this codebase.
