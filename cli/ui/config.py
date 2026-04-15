MENU = {
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
        ("Solution codes", "solution_codes"),
        ("Evaluations", "evaluations"),
        ("Leaderboard entries", "leaderboard_entries"),
        ("Back", "main"),
    ],
}

MAX_PARAM_FIELDS = 4

BINDINGS = [
    ("up", "menu_up", "Up"),
    ("down", "menu_down", "Down"),
    ("enter", "menu_select", "Select"),
    ("ctrl+r", "run_action", "Run"),
    ("ctrl+l", "clear_logs", "Clear logs"),
    ("escape", "go_back", "Back"),
    ("ctrl+c", "quit", "Quit"),
]
