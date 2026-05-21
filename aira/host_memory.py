import json
import os


HOSTS_DIR = os.path.join(".local", "hosts")
DEFAULT_HOST_ID = "david"


def should_use_database_storage():
    return bool(os.getenv("DATABASE_URL", "").strip())


def load_json_env(name, default=None):
    value = os.getenv(name, "").strip()
    if not value:
        return default if default is not None else {}

    return json.loads(value)


def get_database_connection():
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "DATABASE_URL is set, but psycopg is not installed. "
            "Run pip install -r requirements.txt."
        ) from error

    return psycopg.connect(os.environ["DATABASE_URL"])


def ensure_host_memory_table(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS host_memory (
                host_id TEXT PRIMARY KEY,
                profile JSONB NOT NULL,
                preferences JSONB NOT NULL,
                playbooks JSONB NOT NULL
            )
            """
        )
    connection.commit()


def parse_database_json(value):
    if isinstance(value, str):
        return json.loads(value)

    return value


def merge_missing_fields(current, defaults):
    merged = dict(current or {})
    changed = False

    for key, value in (defaults or {}).items():
        if key not in merged and value not in ("", None):
            merged[key] = value
            changed = True

    return merged, changed


def get_default_host_memory(host_id):
    return {
        "host_id": host_id,
        "profile": load_json_env("HOST_PROFILE_JSON", {}),
        "preferences": load_json_env("HOST_PREFERENCES_JSON", {}),
        "playbooks": load_json_env("HOST_PLAYBOOKS_JSON", {}),
    }


def load_host_memory_from_database(host_id):
    from psycopg.types.json import Jsonb

    default_memory = get_default_host_memory(host_id)

    with get_database_connection() as connection:
        ensure_host_memory_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT profile, preferences, playbooks
                FROM host_memory
                WHERE host_id = %s
                """,
                (host_id,),
            )
            row = cursor.fetchone()

            if not row:
                cursor.execute(
                    """
                    INSERT INTO host_memory (
                        host_id,
                        profile,
                        preferences,
                        playbooks
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        host_id,
                        Jsonb(default_memory["profile"]),
                        Jsonb(default_memory["preferences"]),
                        Jsonb(default_memory["playbooks"]),
                    ),
                )
                connection.commit()
                return default_memory

    profile, preferences, playbooks = row
    profile = parse_database_json(profile)
    preferences = parse_database_json(preferences)
    playbooks = parse_database_json(playbooks)

    profile, profile_changed = merge_missing_fields(
        profile,
        default_memory["profile"],
    )
    preferences, preferences_changed = merge_missing_fields(
        preferences,
        default_memory["preferences"],
    )
    playbooks, playbooks_changed = merge_missing_fields(
        playbooks,
        default_memory["playbooks"],
    )

    if profile_changed or preferences_changed or playbooks_changed:
        with get_database_connection() as connection:
            ensure_host_memory_table(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE host_memory
                    SET profile = %s,
                        preferences = %s,
                        playbooks = %s
                    WHERE host_id = %s
                    """,
                    (
                        Jsonb(profile),
                        Jsonb(preferences),
                        Jsonb(playbooks),
                        host_id,
                    ),
                )
            connection.commit()

    return {
        "host_id": host_id,
        "profile": profile,
        "preferences": preferences,
        "playbooks": playbooks,
    }


def update_host_profile_in_database(fields, host_id):
    from psycopg.types.json import Jsonb

    host_memory = load_host_memory_from_database(host_id)
    profile = host_memory["profile"]

    for key, value in fields.items():
        if isinstance(value, str) and value.strip():
            profile[key] = value.strip()

    with get_database_connection() as connection:
        ensure_host_memory_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO host_memory (
                    host_id,
                    profile,
                    preferences,
                    playbooks
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (host_id)
                DO UPDATE SET profile = EXCLUDED.profile
                """,
                (
                    host_id,
                    Jsonb(profile),
                    Jsonb(host_memory["preferences"]),
                    Jsonb(host_memory["playbooks"]),
                ),
            )
        connection.commit()

    return profile


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def get_current_host_id():
    configured_host_id = os.getenv("AIRA_HOST_ID", "").strip()
    if configured_host_id:
        return configured_host_id

    if should_use_database_storage():
        return DEFAULT_HOST_ID

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

    if should_use_database_storage():
        return load_host_memory_from_database(host_id)

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

    if should_use_database_storage():
        return update_host_profile_in_database(fields, host_id)

    host_dir = os.path.join(HOSTS_DIR, host_id)
    os.makedirs(host_dir, exist_ok=True)
    profile_path = os.path.join(host_dir, "profile.json")
    profile = load_json_file(profile_path)

    for key, value in fields.items():
        if isinstance(value, str) and value.strip():
            profile[key] = value.strip()

    save_json_file(profile_path, profile)
    return profile
