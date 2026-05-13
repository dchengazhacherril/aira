def remove_reply_id(host_reply_text, reply_id):
    if not reply_id:
        return host_reply_text

    words = host_reply_text.strip().split()
    filtered_words = [
        word for word in words if word.strip(".,:;()[]{}").upper() != reply_id.upper()
    ]
    return " ".join(filtered_words)


def parse_host_reply(
    host_reply_text,
    suggested_reply,
    needs_manual_review=False,
    reply_id="",
):
    host_reply_text = remove_reply_id(host_reply_text, reply_id)
    normalized_reply = host_reply_text.strip()
    command = normalized_reply.lower()

    if not normalized_reply:
        return {
            "action": "error",
            "reply_text": "",
            "message": "Reply with SEND, SKIP, or EDIT followed by your reply.",
        }

    if command == "send":
        if needs_manual_review:
            return {
                "action": "error",
                "reply_text": "",
                "message": "Review needed. Reply with EDIT followed by the exact message to send, or SKIP.",
            }

        return {
            "action": "send",
            "reply_text": suggested_reply,
            "message": "Sending the suggested reply.",
        }

    if command == "skip":
        return {
            "action": "skip",
            "reply_text": "",
            "message": "Skipped. No Airbnb reply was sent.",
        }

    if command == "edit":
        return {
            "action": "error",
            "reply_text": "",
            "message": "Reply with EDIT followed by the exact message you want to send.",
        }

    if command.startswith("edit "):
        edited_reply = normalized_reply[5:].strip()
        if not edited_reply:
            return {
                "action": "error",
                "reply_text": "",
                "message": "Reply with EDIT followed by the exact message you want to send.",
            }

        return {
            "action": "edit",
            "reply_text": edited_reply,
            "message": "Sending your edited reply.",
        }

    return {
        "action": "edit",
        "reply_text": normalized_reply,
        "message": "Sending your edited reply.",
    }
