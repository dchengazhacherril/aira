import os
import sys

from aira.sms_webhook import main as run_webhook
from scripts.check_airbnb_email import main as run_checker


def get_service_role():
    configured_role = os.getenv("AIRA_RAILWAY_ROLE", "").strip().lower()
    if configured_role:
        return configured_role

    service_name = os.getenv("RAILWAY_SERVICE_NAME", "").strip().lower()
    if "checker" in service_name:
        return "checker"

    return "webhook"


def main():
    role = get_service_role()

    if role == "checker":
        sys.argv = ["check_airbnb_email", "--no-reply-server"]
        run_checker()
        return

    run_webhook()


if __name__ == "__main__":
    main()
