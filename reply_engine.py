import re


def classify_message(message_text):
    text = message_text.lower()

    pattern_map = [
        ("parking", [r"\bparking\b", r"\bgarage\b", r"\bpark\b"]),
        ("wifi", [r"\bwifi\b", r"\bwi-fi\b", r"\binternet\b", r"\bpassword\b"]),
        ("check_in", [r"\bcheck in\b", r"\bcheck-in\b", r"\barrival\b", r"\barrive\b"]),
        ("check_out", [r"\bcheck out\b", r"\bcheck-out\b", r"\bcheckout\b"]),
        ("lockout", [r"\blocked out\b", r"\block out\b", r"\bcant get in\b", r"\bcan't get in\b", r"\bdoor code\b"]),
    ]

    for label, patterns in pattern_map:
        for pattern in patterns:
            if re.search(pattern, text):
                return label

    return "other"


def get_confidence(message_type, suggested_reply):
    if message_type == "other":
        return "low"

    if not suggested_reply:
        return "low"

    return "high"


def has_required_fields(required_fields, profile):
    for field_name in required_fields:
        field_value = profile.get(field_name, "")
        if not isinstance(field_value, str) or not field_value.strip():
            return False
    return True


def build_reply_from_playbook(message_type, host_memory):
    playbook = host_memory["playbooks"].get(message_type)
    profile = host_memory["profile"]
    preferences = host_memory["preferences"]

    if not playbook:
        return ""

    required_fields = playbook.get("required_profile_fields", [])
    if not has_required_fields(required_fields, profile):
        return ""

    sign_off = preferences.get("sign_off", "")
    opening = playbook.get("opening", "")
    response_template = playbook.get("response_template", "")
    reply_lines = []

    if opening:
        reply_lines.append(f"Hi! {opening}".strip())

    if response_template:
        reply_lines.append(response_template.format(**profile))

    if sign_off:
        reply_lines.append(sign_off)

    reply = " ".join(line.strip() for line in reply_lines if line.strip())

    return reply


def build_manual_review_response():
    return "I’m not fully confident here, please review."


def generate_reply_plan(parsed_email, host_memory):
    message_text = parsed_email["guest_message_body"]
    message_type = classify_message(message_text)
    suggested_reply = build_reply_from_playbook(message_type, host_memory)
    confidence = get_confidence(message_type, suggested_reply)

    if confidence == "low":
        suggested_reply = build_manual_review_response()

    return {
        "message_type": message_type,
        "suggested_reply": suggested_reply,
        "confidence": confidence,
        "needs_manual_review": confidence == "low",
    }
