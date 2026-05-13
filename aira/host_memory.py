import json
import os


HOSTS_DIR = os.path.join(".local", "hosts")
DEFAULT_HOST_ID = "david"


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def get_current_host_id():
    os.makedirs(HOSTS_DIR, exist_ok=True)
    host_dirs = []
    for entry in os.listdir(HOSTS_DIR):
        entry_path = os.path.join(HOSTS_DIR, entry)
        if os.path.isdir(entry_path):
            host_dirs.append(entry)

    if host_dirs:
        return sorted(host_dirs)[0]

    return DEFAULT_HOST_ID


def load_host_memory(host_id=DEFAULT_HOST_ID):
    if host_id == DEFAULT_HOST_ID:
        host_id = get_current_host_id()

    host_dir = os.path.join(HOSTS_DIR, host_id)

    return {
        "host_id": host_id,
        "profile": load_json_file(os.path.join(host_dir, "profile.json")),
        "preferences": load_json_file(os.path.join(host_dir, "preferences.json")),
        "playbooks": load_json_file(os.path.join(host_dir, "playbooks.json")),
    }


def update_host_profile(fields, host_id=DEFAULT_HOST_ID):
    if host_id == DEFAULT_HOST_ID:
        host_id = get_current_host_id()

    host_dir = os.path.join(HOSTS_DIR, host_id)
    os.makedirs(host_dir, exist_ok=True)
    profile_path = os.path.join(host_dir, "profile.json")
    profile = load_json_file(profile_path)

    for key, value in fields.items():
        if isinstance(value, str) and value.strip():
            profile[key] = value.strip()

    save_json_file(profile_path, profile)
    return profile
