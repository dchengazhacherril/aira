import json
import os
import re


HOSTS_DIR = os.path.join(".local", "hosts")
DEFAULT_HOST_ID = "aira_cohost"


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def slugify_host_name(host_name):
    slug = host_name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or DEFAULT_HOST_ID


def get_current_host_id():
    os.makedirs(HOSTS_DIR, exist_ok=True)
    default_path = os.path.join(HOSTS_DIR, DEFAULT_HOST_ID)
    if os.path.exists(default_path):
        return DEFAULT_HOST_ID

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


def rename_host_folder(host_name, current_host_id=DEFAULT_HOST_ID):
    if not host_name.strip():
        return get_current_host_id()

    if current_host_id == DEFAULT_HOST_ID:
        current_host_id = get_current_host_id()

    new_host_id = slugify_host_name(host_name)
    current_path = os.path.join(HOSTS_DIR, current_host_id)
    new_path = os.path.join(HOSTS_DIR, new_host_id)

    if current_host_id == new_host_id:
        return new_host_id

    if not os.path.exists(current_path):
        return current_host_id

    if os.path.exists(new_path):
        return new_host_id

    os.rename(current_path, new_path)
    return new_host_id
