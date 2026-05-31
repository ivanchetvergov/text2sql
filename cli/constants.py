from __future__ import annotations

from seed.settings import (
    COMPETITION_DATASETS_MAX,
    COMPETITION_DATASETS_MIN,
    DATASET_FILES_MAX,
    DATASET_FILES_MIN,
    DEFAULT_COMPETITIONS_COUNT,
    DEFAULT_DATASETS_COUNT,
    DEFAULT_USERS_COUNT,
    SUBMISSIONS_PER_PARTICIPATION_MAX,
    SUBMISSIONS_PER_PARTICIPATION_MIN,
    TEAM_COMPETITIONS_MAX,
    TEAM_COMPETITIONS_MIN,
    TEAM_MEMBERS_MAX,
    TEAM_MEMBERS_MIN,
    TEAMS_PER_COMPETITION_MAX,
    TEAMS_PER_COMPETITION_MIN,
)


DEFAULT_LLM_URL = "http://localhost:8000/generate"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-120b:free"
DEFAULT_LLM_TIMEOUT_SECONDS = 20.0

MAX_PARAM_FIELDS = 4

MENU: dict[str, list[tuple[str, str]]] = {
    "main": [
        ("1. Fill dictionaries", "dict"),
        ("2. Base", "base"),
        ("3. Core", "core"),
        ("4. Sub", "sub"),
        ("5. Full seed", "all"),
        ("6. Table counts", "table_counts"),
        ("7. Clear all data", "clear_all_data"),
        ("8. Ask LLM", "llm_query"),
    ],
    "base": [
        ("Run base level", "level1"),
        ("Users", "users"),
        ("Datasets", "datasets"),
        ("Dataset files", "dataset_files"),
        ("Competitions", "competitions"),
        ("Back", "main"),
    ],
    "core": [
        ("Run core level", "level2"),
        ("Configurations", "configurations"),
        ("Competition datasets", "competition_datasets"),
        ("Teams", "teams"),
        ("Team members", "team_members"),
        ("Team competitions", "team_competitions"),
        ("Participations", "participations"),
        ("Back", "main"),
    ],
    "sub": [
        ("Run sub level", "level3"),
        ("Submissions", "submissions"),
        ("Back", "main"),
    ],
}

BINDINGS = [
    ("up", "menu_up", "Up"),
    ("down", "menu_down", "Down"),
    ("enter", "menu_select", "Select"),
    ("ctrl+r", "run_action", "Run"),
    ("ctrl+l", "clear_logs", "Clear logs"),
    ("escape", "go_back", "Back"),
    ("ctrl+c", "quit", "Quit"),
]

ACTION_SPECS = {
    "all": {"defaults": {"total_count": 3000}},
    "dict": {"defaults": {}},
    "table_counts": {"defaults": {}},
    "clear_all_data": {"defaults": {"confirm": "NO"}},
    "llm_query": {
        "defaults": {
            "prompt": "",
        }
    },
    "level1": {"defaults": {"total_count": 1000}},
    "level2": {"defaults": {"total_count": 1000}},
    "level3": {"defaults": {"total_count": 1000}},
    "users": {"defaults": {"count": DEFAULT_USERS_COUNT}},
    "datasets": {"defaults": {"count": DEFAULT_DATASETS_COUNT}},
    "dataset_files": {
        "defaults": {"min_per_dataset": DATASET_FILES_MIN, "max_per_dataset": DATASET_FILES_MAX}
    },
    "competitions": {"defaults": {"count": DEFAULT_COMPETITIONS_COUNT}},
    "configurations": {"defaults": {}},
    "competition_datasets": {
        "defaults": {
            "min_per_competition": COMPETITION_DATASETS_MIN,
            "max_per_competition": COMPETITION_DATASETS_MAX,
        }
    },
    "teams": {
        "defaults": {
            "min_per_competition": TEAMS_PER_COMPETITION_MIN,
            "max_per_competition": TEAMS_PER_COMPETITION_MAX,
        }
    },
    "team_members": {
        "defaults": {"min_per_team": TEAM_MEMBERS_MIN, "max_per_team": TEAM_MEMBERS_MAX}
    },
    "team_competitions": {
        "defaults": {
            "min_per_team": TEAM_COMPETITIONS_MIN,
            "max_per_team": TEAM_COMPETITIONS_MAX,
        }
    },
    "participations": {"defaults": {"count": 50}},
    "submissions": {
        "defaults": {
            "min_per_participation": SUBMISSIONS_PER_PARTICIPATION_MIN,
            "max_per_participation": SUBMISSIONS_PER_PARTICIPATION_MAX,
        }
    },
    "participation_scores": {"defaults": {}},
}
