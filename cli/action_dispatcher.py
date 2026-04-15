from __future__ import annotations

from faker import Faker

from cli import bootstrap  # noqa: F401
from cli.level_distribution import ALL_LEVEL_RATIOS, distribute_total, level_counts
from inserter import Inserter
from seed_base import (
    seed_competitions,
    seed_dataset_files,
    seed_datasets,
    seed_users,
)
from seed_core import (
    seed_competition_datasets,
    seed_configurations,
    seed_participations,
    seed_team_competitions,
    seed_team_members,
    seed_teams,
)
from seed_dict import run_all_dictionaries
from seed_sub import (
    seed_evaluations,
    seed_leaderboard_entries,
    seed_solution_codes,
    seed_submissions,
)

ACTION_SPECS = {
    "all": {"defaults": {"total_count": 3000}},
    "dict": {"defaults": {}},
    "table_counts": {"defaults": {}},
    "clear_all_data": {"defaults": {"confirm": "NO"}},
    "llm_query": {
        "defaults": {
            "prompt": "",
            "url": "http://localhost:8000/generate",
            "timeout": 180,
        }
    },
    "level1": {"defaults": {"total_count": 1000}},
    "level2": {"defaults": {"total_count": 1000}},
    "level3": {"defaults": {"total_count": 1000}},
    "users": {"defaults": {"count": 50}},
    "datasets": {"defaults": {"count": 10}},
    "dataset_files": {"defaults": {"min_per_dataset": 3, "max_per_dataset": 5}},
    "competitions": {"defaults": {"count": 10}},
    "configurations": {"defaults": {"count": 10}},
    "competition_datasets": {
        "defaults": {"min_per_competition": 1, "max_per_competition": 3}
    },
    "teams": {"defaults": {"count": 20}},
    "team_members": {"defaults": {"min_per_team": 2, "max_per_team": 5}},
    "team_competitions": {"defaults": {"min_per_team": 1, "max_per_team": 2}},
    "participations": {"defaults": {"count": 50}},
    "submissions": {
        "defaults": {"min_per_participation": 1, "max_per_participation": 3}
    },
    "solution_codes": {"defaults": {}},
    "evaluations": {"defaults": {}},
    "leaderboard_entries": {"defaults": {}},
}


async def _table_count(conn, table: str) -> int:
    safe_table = table.replace('"', '""')
    return int(await conn.fetchval(f'SELECT COUNT(*)::bigint FROM "{safe_table}"'))


def _bounds_for_target(target_total: int, parent_total: int) -> tuple[int, int]:
    if target_total <= 0 or parent_total <= 0:
        return 0, 0

    exact = target_total / parent_total
    base = int(exact)
    if base <= 0:
        return 0, 1
    if float(base) == exact:
        return base, base
    return base, base + 1


async def run_level1_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    counts = level_counts("level1", total_count)

    # Track initial counts
    initial_counts = {
        "user": await _table_count(conn, "user"),
        "dataset": await _table_count(conn, "dataset"),
        "dataset_file": await _table_count(conn, "dataset_file"),
        "competition": await _table_count(conn, "competition"),
    }

    await seed_users(inserter, fake, count=counts["users"])
    await seed_datasets(inserter, fake, count=counts["datasets"])
    datasets_total = await _table_count(conn, "dataset")
    files_min, files_max = _bounds_for_target(counts["dataset_files"], datasets_total)
    await seed_dataset_files(
        inserter,
        fake,
        min_per_dataset=files_min,
        max_per_dataset=files_max,
    )
    await seed_competitions(inserter, fake, count=counts["competitions"])

    # Report added counts
    print("\nLevel 1 - Records added:")
    final_counts = {
        "user": await _table_count(conn, "user"),
        "dataset": await _table_count(conn, "dataset"),
        "dataset_file": await _table_count(conn, "dataset_file"),
        "competition": await _table_count(conn, "competition"),
    }
    for table, final in final_counts.items():
        added = final - initial_counts[table]
        print(f"- {table}: +{added}")


async def run_level2_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    counts = level_counts("level2", total_count)

    # Track initial counts
    initial_counts = {
        "configuration": await _table_count(conn, "configuration"),
        "competition_dataset": await _table_count(conn, "competition_dataset"),
        "team": await _table_count(conn, "team"),
        "team_member": await _table_count(conn, "team_member"),
        "team_competition": await _table_count(conn, "team_competition"),
        "participation": await _table_count(conn, "participation"),
    }

    await seed_configurations(inserter, count=counts["configurations"])

    competitions_total = await _table_count(conn, "competition")
    comp_data_min, comp_data_max = _bounds_for_target(
        counts["competition_datasets"],
        competitions_total,
    )
    await seed_competition_datasets(
        inserter,
        min_per_competition=comp_data_min,
        max_per_competition=comp_data_max,
    )

    await seed_teams(inserter, fake, count=counts["teams"])

    teams_total = await _table_count(conn, "team")
    team_members_min, team_members_max = _bounds_for_target(
        counts["team_members"],
        teams_total,
    )
    await seed_team_members(
        inserter,
        min_per_team=team_members_min,
        max_per_team=team_members_max,
    )

    team_comp_min, team_comp_max = _bounds_for_target(
        counts["team_competitions"],
        teams_total,
    )
    await seed_team_competitions(
        inserter,
        min_per_team=team_comp_min,
        max_per_team=team_comp_max,
    )

    await seed_participations(inserter, count=counts["participations"])

    # Report added counts
    print("\nLevel 2 - Records added:")
    final_counts = {
        "configuration": await _table_count(conn, "configuration"),
        "competition_dataset": await _table_count(conn, "competition_dataset"),
        "team": await _table_count(conn, "team"),
        "team_member": await _table_count(conn, "team_member"),
        "team_competition": await _table_count(conn, "team_competition"),
        "participation": await _table_count(conn, "participation"),
    }
    for table, final in final_counts.items():
        added = final - initial_counts[table]
        print(f"- {table}: +{added}")


async def run_level3_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    counts = level_counts("level3", total_count)

    # Track initial counts
    initial_counts = {
        "submission": await _table_count(conn, "submission"),
        "solution_code": await _table_count(conn, "solution_code"),
        "evaluation": await _table_count(conn, "evaluation"),
        "leaderboard_entry": await _table_count(conn, "leaderboard_entry"),
    }

    participations_total = await _table_count(conn, "participation")
    submissions_min, submissions_max = _bounds_for_target(
        counts["submissions"],
        participations_total,
    )
    await seed_submissions(
        inserter,
        fake,
        min_per_participation=submissions_min,
        max_per_participation=submissions_max,
    )

    if counts["solution_codes"] > 0:
        await seed_solution_codes(inserter, fake)
    if counts["evaluations"] > 0:
        await seed_evaluations(inserter)
    if counts["leaderboard_entries"] > 0:
        await seed_leaderboard_entries(inserter)

    # Report added counts
    print("\nLevel 3 - Records added:")
    final_counts = {
        "submission": await _table_count(conn, "submission"),
        "solution_code": await _table_count(conn, "solution_code"),
        "evaluation": await _table_count(conn, "evaluation"),
        "leaderboard_entry": await _table_count(conn, "leaderboard_entry"),
    }
    for table, final in final_counts.items():
        added = final - initial_counts[table]
        print(f"- {table}: +{added}")


async def run_all_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    level_totals = distribute_total(
        total_count,
        ratios=ALL_LEVEL_RATIOS,
    )

    await run_all_dictionaries(conn)
    await run_level1_from_total(conn, inserter, fake, level_totals["level1"])
    await run_level2_from_total(conn, inserter, fake, level_totals["level2"])
    await run_level3_from_total(conn, inserter, fake, level_totals["level3"])


async def print_table_counts(conn) -> None:
    rows = await conn.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )

    if not rows:
        print("No tables found in public schema.")
        return

    print("Table row counts:")
    table_counts = []
    for row in rows:
        table = row["table_name"]
        safe_table = table.replace('"', '""')
        count = await conn.fetchval(f'SELECT COUNT(*)::bigint FROM "{safe_table}"')
        table_counts.append((table, count))

    # Sort by count in descending order
    table_counts.sort(key=lambda x: x[1], reverse=True)

    total_count = 0
    for table, count in table_counts:
        print(f"- {table}: {count}")
        total_count += count

    print(f"\nTotal records: {total_count}")


async def clear_all_data(conn, *, confirm: str = "NO") -> None:
    if confirm.upper() != "YES":
        raise ValueError("Set confirm=YES to clear all data")

    rows = await conn.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )

    if not rows:
        print("No tables found in public schema.")
        return

    counts: list[tuple[str, int]] = []
    for row in rows:
        table = row["table_name"]
        safe_table = table.replace('"', '""')
        count = int(await conn.fetchval(f'SELECT COUNT(*)::bigint FROM "{safe_table}"'))
        counts.append((table, count))

    quoted_tables = []
    for table, _ in counts:
        quoted_tables.append('"' + table.replace('"', '""') + '"')
    table_list = ", ".join(quoted_tables)
    await conn.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")

    total_deleted = sum(count for _, count in counts)
    print("Data cleared for public schema tables:")
    for table, count in counts:
        print(f"- {table}: removed {count}")
    print(f"Total removed rows: {total_deleted}")


async def execute_action(
    action: str,
    *,
    conn,
    inserter: Inserter,
    fake: Faker,
    **kwargs,
) -> int | None:
    if action == "all":
        await run_all_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "dict":
        await run_all_dictionaries(conn)
        return None
    if action == "table_counts":
        await print_table_counts(conn)
        return None
    if action == "clear_all_data":
        await clear_all_data(conn, **kwargs)
        return None
    if action == "level1":
        await run_level1_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "level2":
        await run_level2_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "level3":
        await run_level3_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "users":
        return await seed_users(inserter, fake, **kwargs)
    if action == "datasets":
        return await seed_datasets(inserter, fake, **kwargs)
    if action == "dataset_files":
        return await seed_dataset_files(inserter, fake, **kwargs)
    if action == "competitions":
        return await seed_competitions(inserter, fake, **kwargs)
    if action == "configurations":
        return await seed_configurations(inserter, **kwargs)
    if action == "competition_datasets":
        return await seed_competition_datasets(inserter, **kwargs)
    if action == "teams":
        return await seed_teams(inserter, fake, **kwargs)
    if action == "team_members":
        return await seed_team_members(inserter, **kwargs)
    if action == "team_competitions":
        return await seed_team_competitions(inserter, **kwargs)
    if action == "participations":
        return await seed_participations(inserter, **kwargs)
    if action == "submissions":
        return await seed_submissions(inserter, fake, **kwargs)
    if action == "solution_codes":
        return await seed_solution_codes(inserter, fake)
    if action == "evaluations":
        return await seed_evaluations(inserter)
    if action == "leaderboard_entries":
        return await seed_leaderboard_entries(inserter)

    raise ValueError(f"Unknown action: {action}")
