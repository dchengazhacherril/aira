from aira.host_memory import load_host_memory, update_host_profile
from aira.reply_engine import classify_message


LEARNED_PROFILE_FIELDS = {
    "amenity": "amenity_notes",
    "amenity_unknown": "amenity_notes",
    "trash": "trash_notes",
    "baby_gear": "baby_gear_notes",
}
CORRECTION_NOTES_FIELD = "reply_correction_notes"


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


def append_unique_note(existing_notes, new_note):
    existing_notes = (existing_notes or "").strip()
    new_note = (new_note or "").strip()

    if not existing_notes:
        return new_note

    if new_note.lower() in existing_notes.lower():
        return existing_notes

    return f"{existing_notes}\n{new_note}"


def build_correction_note(pending_reply, reply_text):
    parsed_email = pending_reply.get("parsed_email", {})
    guest_message = " ".join(
        parsed_email.get("guest_message_body", "").split()
    )
    reply_text = " ".join(reply_text.split())

    if guest_message:
        return f"Guest asked: {guest_message}\nHost replied: {reply_text}"

    return f"Host replied: {reply_text}"


def build_correction_notes(pending_reply, reply_text):
    correction_note = build_correction_note(pending_reply, reply_text)

    try:
        host_memory = load_host_memory()
        existing_notes = host_memory.get("profile", {}).get(CORRECTION_NOTES_FIELD, "")
    except Exception:
        existing_notes = ""

    return append_unique_note(existing_notes, correction_note)


def build_amenity_notes(reply_text):
    text = " ".join(reply_text.split())
    if not text:
        return ""

    try:
        host_memory = load_host_memory()
        existing_notes = host_memory.get("profile", {}).get("amenity_notes", "")
    except Exception:
        existing_notes = ""

    return append_unique_note(existing_notes, text)


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
    profile_updates = {
        CORRECTION_NOTES_FIELD: build_correction_notes(pending_reply, reply_text),
    }

    if profile_field:
        if message_type == "baby_gear":
            reply_text = extract_baby_gear_notes(reply_text)
        elif profile_field == "amenity_notes":
            reply_text = build_amenity_notes(reply_text)

        profile_updates[profile_field] = reply_text

    updated_profile = update_host_profile(profile_updates)

    return {
        "message_type": message_type,
        "profile_field": profile_field or CORRECTION_NOTES_FIELD,
        "profile_fields": list(profile_updates),
        "profile_value": updated_profile.get(
            profile_field or CORRECTION_NOTES_FIELD,
            "",
        ),
    }
