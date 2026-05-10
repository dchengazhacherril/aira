import os
import re
import signal
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv

from sms import configure_inbound_sms_webhook


LOCAL_ENV_PATH = os.path.join(".local", ".env")
CLOUDFLARED_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


load_dotenv(LOCAL_ENV_PATH)


def start_process(command):
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def stop_process(process):
    if process and process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()


def wait_for_tunnel_url(process, timeout_seconds=45):
    started_at = time.time()

    while time.time() - started_at < timeout_seconds:
        line = process.stdout.readline()

        if line:
            print(line.rstrip(), flush=True)
            match = CLOUDFLARED_URL_PATTERN.search(line)
            if match:
                return match.group(0)

        if process.poll() is not None:
            raise RuntimeError("cloudflared exited before creating a tunnel URL.")

    raise TimeoutError("Timed out waiting for cloudflared to create a tunnel URL.")


def stream_process_output(process, label):
    for line in process.stdout:
        print(f"[{label}] {line.rstrip()}", flush=True)


def main():
    port = os.getenv("SMS_WEBHOOK_PORT", "8000")
    webhook_process = None
    tunnel_process = None

    try:
        print("Starting Aira SMS webhook...", flush=True)
        webhook_process = start_process([sys.executable, "sms_webhook.py"])
        time.sleep(1)

        if webhook_process.poll() is not None:
            stream_process_output(webhook_process, "webhook")
            raise RuntimeError("SMS webhook failed to start.")

        print("Starting Cloudflare tunnel...", flush=True)
        tunnel_process = start_process(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
        )
        tunnel_url = wait_for_tunnel_url(tunnel_process)
        webhook_url = f"{tunnel_url}/sms/reply"

        print(f"Configuring Twilio inbound webhook: {webhook_url}", flush=True)
        twilio_result = configure_inbound_sms_webhook(webhook_url)
        print(
            "Twilio webhook configured "
            f"service={twilio_result['messaging_service_sid']} "
            f"method={twilio_result['inbound_method']}",
            flush=True,
        )
        print("Reply server is ready. Press Ctrl-C to stop.", flush=True)

        threading.Thread(
            target=stream_process_output,
            args=(webhook_process, "webhook"),
            daemon=True,
        ).start()
        threading.Thread(
            target=stream_process_output,
            args=(tunnel_process, "cloudflared"),
            daemon=True,
        ).start()

        while True:
            if webhook_process.poll() is not None:
                raise RuntimeError("SMS webhook process exited.")

            if tunnel_process.poll() is not None:
                raise RuntimeError("cloudflared process exited.")

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping reply server...", flush=True)
    finally:
        stop_process(tunnel_process)
        stop_process(webhook_process)


if __name__ == "__main__":
    main()
