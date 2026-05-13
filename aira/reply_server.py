import os
import re
import signal
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv

from aira.sms import configure_inbound_sms_webhook


LOCAL_ENV_PATH = os.path.join(".local", ".env")
CLOUDFLARED_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


load_dotenv(LOCAL_ENV_PATH)


def start_process(command, env=None):
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
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


class ReplyServer:
    def __init__(self, port=None):
        self.port = port or os.getenv("SMS_WEBHOOK_PORT", "8000")
        self.webhook_process = None
        self.tunnel_process = None
        self.webhook_url = ""

    def start(self):
        print("Starting Cloudflare tunnel...", flush=True)
        self.tunnel_process = start_process(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{self.port}"]
        )
        tunnel_url = wait_for_tunnel_url(self.tunnel_process)
        self.webhook_url = f"{tunnel_url}/sms/reply"

        print("Starting Aira SMS webhook...", flush=True)
        webhook_env = os.environ.copy()
        webhook_env["AIRA_PUBLIC_WEBHOOK_URL"] = self.webhook_url
        webhook_env["TWILIO_VALIDATE_REQUESTS"] = "false"
        self.webhook_process = start_process(
            [sys.executable, "-m", "aira.sms_webhook"],
            env=webhook_env,
        )
        time.sleep(1)

        if self.webhook_process.poll() is not None:
            stream_process_output(self.webhook_process, "webhook")
            raise RuntimeError("SMS webhook failed to start.")

        print(f"Configuring Twilio inbound webhook: {self.webhook_url}", flush=True)
        twilio_result = configure_inbound_sms_webhook(self.webhook_url)
        print(
            "Twilio webhook configured "
            f"service={twilio_result['messaging_service_sid']} "
            f"method={twilio_result['inbound_method']}",
            flush=True,
        )

        threading.Thread(
            target=stream_process_output,
            args=(self.webhook_process, "webhook"),
            daemon=True,
        ).start()
        threading.Thread(
            target=stream_process_output,
            args=(self.tunnel_process, "cloudflared"),
            daemon=True,
        ).start()

        print("Reply server is ready.", flush=True)

    def monitor(self):
        while True:
            if self.webhook_process.poll() is not None:
                raise RuntimeError("SMS webhook process exited.")

            if self.tunnel_process.poll() is not None:
                raise RuntimeError("cloudflared process exited.")

            time.sleep(0.2)

    def stop(self):
        stop_process(self.tunnel_process)
        stop_process(self.webhook_process)
