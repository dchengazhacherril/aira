from aira.host_memory import update_host_profile
from aira.reply_engine import classify_message


LEARNED_PROFILE_FIELDS = {
    "trash": "trash_notes",
    "baby_gear": "baby_gear_notes",
}


def extract_baby_gear_notes(reply_text):
    text = reply_text.lower()
    has_travel_crib = "travel crib" in text or "crib" in text
    has_high_chair = "high chair" in text or "highchair" in text

    if has_travel_crib and has_high_chair:
        return "Travel crib and high chair are available."
    if has_travel_crib:
        return "Travel crib is available."
    if has_high_chair:
        return "High chair is available."

    return reply_text


def get_learnable_message_type(pending_reply):
    reply_plan = pending_reply.get("reply_plan", {})
    message_type = reply_plan.get("message_type", "other")

    if message_type != "other":
        return message_type

    parsed_email = pending_reply.get("parsed_email", {})
    message_body = parsed_email.get("guest_message_body", "")
    return classify_message(message_body)


def learn_from_edited_reply(pending_reply, reply_text):
    message_type = get_learnable_message_type(pending_reply)
    profile_field = LEARNED_PROFILE_FIELDS.get(message_type)

    if not profile_field:
        return {}

    if message_type == "baby_gear":
        reply_text = extract_baby_gear_notes(reply_text)

    updated_profile = update_host_profile({profile_field: reply_text})

    return {
        "message_type": message_type,
        "profile_field": profile_field,
        "profile_value": updated_profile.get(profile_field, ""),
    }
