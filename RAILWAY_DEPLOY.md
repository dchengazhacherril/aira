# Railway Deployment

This is the intended production-ish MVP shape:

- Web service: receives Twilio inbound SMS replies.
- Cron service: checks Gmail on a schedule and sends outbound SMS messages.
- Postgres: shared state for pending replies and learned host memory.

## 1. Prepare Gmail JSON

Railway cannot use the local OAuth browser flow. Use the local token you already created and paste it into Railway as `GMAIL_TOKEN_JSON`.

On your machine, the token is usually:

```bash
.local/token-david_getaira.host.json
```

Copy the full JSON content into the Railway variable value.

If you also want Railway to have the OAuth client config available, copy the full content of `.local/credentials.json` into `GMAIL_CREDENTIALS_JSON`.

## 2. Create Railway Project

1. Create a new Railway project.
2. Connect this GitHub repo.
3. Add a Postgres service.
4. Add one repo service for the webhook.
5. Add one repo service for the checker cron.

Railway will provide `DATABASE_URL` from the Postgres service.

## 3. Webhook Service

Use this start command:

```bash
python -m aira.sms_webhook
```

Add these variables:

```bash
GMAIL_ACCOUNT_EMAIL=david@getaira.host
GMAIL_SEND_AS_EMAIL=aira.cohost@gmail.com
GMAIL_TOKEN_JSON=<full token JSON>
GMAIL_CREDENTIALS_JSON=<full credentials JSON>

TWILIO_ACCOUNT_SID=<twilio account sid>
TWILIO_AUTH_TOKEN=<twilio auth token>
TWILIO_MESSAGING_SERVICE_SID=<twilio messaging service sid>
MY_PHONE_NUMBER=<your phone number>
TWILIO_VALIDATE_REQUESTS=true
AIRA_PUBLIC_WEBHOOK_URL=https://<railway-webhook-domain>/sms/reply

AIRA_HOST_ID=david
HOST_PROFILE_JSON=<profile JSON>
HOST_PREFERENCES_JSON=<preferences JSON>
HOST_PLAYBOOKS_JSON=<playbooks JSON>

DATABASE_URL=<railway postgres database url>
```

Railway sets `PORT` automatically. The webhook listens on that port.

## 4. Checker Cron Service

Use this command:

```bash
python -m scripts.check_airbnb_email --no-reply-server
```

Use this cron schedule:

```text
*/5 * * * *
```

Use the same environment variables as the webhook service. The checker and webhook must share the same `DATABASE_URL`.

## 5. Twilio

In the Twilio Messaging Service inbound settings, set:

```text
https://<railway-webhook-domain>/sms/reply
```

Method:

```text
POST
```

## 6. Health Check

Open the Railway service URL in a browser. The root path should return:

```text
Aira SMS webhook is running.
```

## Local Development

Local development still works with:

```bash
.venv/bin/python -m scripts.check_airbnb_email
```

If `DATABASE_URL` is unset, Aira uses `.local/pending_replies.json` and `.local/hosts/...` files as before.
