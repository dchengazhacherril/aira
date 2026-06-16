import json
import os
from pathlib import Path


DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
CONFIDENCE_VALUES = {"high", "medium", "low"}
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "response_agent.md"


def should_use_response_agent():
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return False

    value = os.getenv("AIRA_USE_RESPONSE_AGENT", "true").strip().lower()
    return value not in {"0", "false", "no"}


def get_openai_model():
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def load_agent_instructions():
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def compact_json(value):
    return json.dumps(value or {}, ensure_ascii=True, sort_keys=True)


def build_agent_prompt(parsed_email, host_memory, fallback_plan):
    payload = {
        "guest": {
            "name": parsed_email.get("guest_name", ""),
            "role": parsed_email.get("sender_role", ""),
            "message": parsed_email.get("guest_message_body", ""),
        },
        "listing": {
            "name": parsed_email.get("listing_name", ""),
        },
        "host_memory": {
            "profile": host_memory.get("profile", {}),
            "preferences": host_memory.get("preferences", {}),
            "playbooks": host_memory.get("playbooks", {}),
        },
        "fallback_plan": fallback_plan,
    }

    return (
        "Draft the best Airbnb guest reply for this input.\n"
        f"{compact_json(payload)}"
    )


def parse_agent_json_output(raw_output):
    if isinstance(raw_output, dict):
        data = raw_output
    else:
        text = str(raw_output or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)

    suggested_reply = str(data.get("suggested_reply", "")).strip()
    confidence = str(data.get("confidence", "low")).strip().lower()
    if confidence not in CONFIDENCE_VALUES:
        confidence = "low"

    message_type = str(data.get("message_type", "")).strip().lower() or "other"
    reason = str(data.get("reason", "")).strip()
    memory_candidates = data.get("memory_candidates", [])
    if not isinstance(memory_candidates, list):
        memory_candidates = []

    return {
        "message_type": message_type,
        "suggested_reply": suggested_reply,
        "confidence": confidence,
        "needs_manual_review": confidence == "low" or not suggested_reply,
        "reason": reason,
        "memory_candidates": memory_candidates,
        "source": "response_agent",
    }


def run_response_agent(prompt, model):
    from agents import Agent, Runner

    agent = Agent(
        name="AiraResponseAgent",
        instructions=load_agent_instructions(),
        model=model,
    )
    result = Runner.run_sync(agent, prompt)
    return result.final_output


def generate_response_agent_plan(parsed_email, host_memory, fallback_plan):
    if not should_use_response_agent():
        return None

    prompt = build_agent_prompt(parsed_email, host_memory, fallback_plan)
    raw_output = run_response_agent(prompt, get_openai_model())
    plan = parse_agent_json_output(raw_output)

    if not plan["suggested_reply"]:
        return None

    return plan
