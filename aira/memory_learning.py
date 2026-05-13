from aira.host_memory import update_host_profile
from aira.reply_engine import classify_message


LEARNED_PROFILE_FIELDS = {
    "trash": "trash_notes",
}


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

    updated_profile = update_host_profile({profile_field: reply_text})

    return {
        "message_type": message_type,
        "profile_field": profile_field,
        "profile_value": updated_profile.get(profile_field, ""),
    }
