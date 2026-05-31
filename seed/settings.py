from __future__ import annotations

DATASET_FILES_MIN = 3
DATASET_FILES_MAX = 10

COMPETITION_DATASETS_MIN = 1
COMPETITION_DATASETS_MAX = 3

TEAMS_PER_COMPETITION_MIN = 3
TEAMS_PER_COMPETITION_MAX = 10

TEAM_MEMBERS_MIN = 1
TEAM_MEMBERS_MAX = 5

TEAM_COMPETITIONS_MIN = 1
TEAM_COMPETITIONS_MAX = 5

SUBMISSIONS_PER_PARTICIPATION_MIN = 1
SUBMISSIONS_PER_PARTICIPATION_MAX = 3


DEFAULT_USERS_COUNT = 50
DEFAULT_DATASETS_COUNT = 6
DEFAULT_COMPETITIONS_COUNT = 10


LEVEL_COEFFICIENTS: dict[str, dict[str, float]] = {
    "level1": {
        "users": 0.66,
        "datasets": 0.02,
        "dataset_files": 0.03,
        "competitions": 0.29,
    },
    "level2": {
        "configurations": 0.06,
        "competition_datasets": 0.15,
        "teams": 0.25,
        "team_members": 0.39,
        "participations": 0.15,
    },
    "level3": {
        "submissions": 1.0,
    },
}
