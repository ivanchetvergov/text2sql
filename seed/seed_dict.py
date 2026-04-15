import asyncio
import asyncpg
import sys
from pathlib import Path

from config import *

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from infra.db_config import get_pg_connect_kwargs


async def seed_roles(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO role (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        ROLES,
    )
    print('- Table role: handled.')
    return len(ROLES)

async def seed_dataset_purposes(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO dataset_purpose (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        DATASET_PURPOSES,
    )
    print('- Table dataset_purpose: handled.')
    return len(DATASET_PURPOSES)


async def seed_team_roles(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO team_role (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        TEAM_ROLES,
    )
    print('- Table team_role: handled.')
    return len(TEAM_ROLES)

async def seed_task_types(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO task_type (code, description, answer_format)\n'
            'VALUES ($1, $2, $3)\n'
            'ON CONFLICT (code) DO NOTHING'
        ),
        TASK_TYPES,
    )
    print('- Table task_type: handled.')
    return len(TASK_TYPES)

async def seed_metrics(conn) -> int:
    metrics_data = [(metric[0], metric[1], metric[2], metric[0]) for metric in METRICS]
    await conn.executemany(
        (
            'INSERT INTO metric (name, description, optimization_dir, formula)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        metrics_data,
    )
    print('- Table metric: handled.')
    return len(METRICS)

async def seed_competition_statuses(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO competition_status (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        COMPETITION_STATUSES,
    )
    print('- Table competition_status: handled.')
    return len(COMPETITION_STATUSES)

async def seed_team_statuses(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO team_status (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        TEAM_STATUSES,
    )
    print('- Table team_status: handled.')
    return len(TEAM_STATUSES)

async def seed_participation_statuses(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO participation_status (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        PARTICIPATION_STATUSES,
    )
    print('- Table participation_status: handled.')
    return len(PARTICIPATION_STATUSES)

async def seed_submission_statuses(conn) -> int:
    await conn.executemany(
        (
            'INSERT INTO submission_status (name, description)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        SUBMISSION_STATUSES,
    )
    print('- Table submission_status: handled.')
    return len(SUBMISSION_STATUSES)

async def run_all_dictionaries(conn):
    total = 0
    total += await seed_roles(conn)
    total += await seed_dataset_purposes(conn)
    total += await seed_team_roles(conn)
    total += await seed_task_types(conn)
    total += await seed_metrics(conn)
    total += await seed_competition_statuses(conn)
    total += await seed_team_statuses(conn)
    total += await seed_participation_statuses(conn)
    total += await seed_submission_statuses(conn)
    print(f"\nTotal dictionary entries handled: {total}")

