import random
from faker import Faker

from seed.constants import (
    COMPETITION_DESCRIPTIONS,
    COMPETITION_TITLES,
    DATASET_FILE_NAMES,
    DATASET_NAMES,
    USER_NAMES,
)
from seed.settings import DATASET_FILES_MAX, DATASET_FILES_MIN

# === уровни: 2, 3 ===

async def seed_users(inserter, fake: Faker, count: int = 50) -> int:
    return await inserter.seed(
        table='"user"',
        query=(
            'INSERT INTO "user" (role_id, username, email, password_hash)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT DO NOTHING'
        ),
        generator=lambda deps: (
            random.choice(deps['role']),
            f"{random.choice(USER_NAMES)}{random.randint(1, 9999)}"[:20],
            f"{random.choice(USER_NAMES)}{random.randint(1, 9999)}@example.com"[:40],
            fake.sha256(),
        ),
        count=count,
        dependencies={'role': 'SELECT role_id FROM role'},
    )

async def seed_datasets(inserter, fake: Faker, count: int = 10) -> int:
    return await inserter.seed(
        table='dataset',
        query=(
            'INSERT INTO dataset (name, purpose_id, is_hidden, version)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (name, version) DO NOTHING'
        ),
        generator=lambda deps: (
            f"{random.choice(DATASET_NAMES)}_{random.randint(1, 99)}"[:30],
            random.choice(deps['purpose']),
            random.choice([True, False]),
            random.randint(1, 5),
        ),
        count=count,
        dependencies={'purpose': 'SELECT purpose_id FROM dataset_purpose'},
    )

async def seed_dataset_files(
    inserter,
    fake: Faker,
    min_per_dataset: int = DATASET_FILES_MIN,
    max_per_dataset: int = DATASET_FILES_MAX,
) -> int:
    return await inserter.seed(
        table='dataset_file',
        query=(
            'INSERT INTO dataset_file (dataset_id, filename, storage_path, size_bytes, checksum)\n'
            'VALUES ($1, $2, $3, $4, $5)'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            random.choice(DATASET_FILE_NAMES)[:50],
            f"datasets/{random.choice(DATASET_NAMES)}/{random.choice(DATASET_FILE_NAMES)}"[:100],
            random.randint(1024, 10485760),
            fake.sha256()[:64],
        ),
        dependencies={'dataset': 'SELECT dataset_id FROM dataset'},
        per_dependency='dataset',
        min_per_dependency=min_per_dataset,
        max_per_dependency=max_per_dataset,
    )

async def seed_competitions(inserter, fake: Faker, count: int = 10) -> int:
    return await inserter.seed(
        table='competition',
        query=(
            'INSERT INTO competition (organizer_id, status_id, title, description, ends_at)\n'
            'VALUES ($1, $2, $3, $4, $5)\n'
            'ON CONFLICT (title) DO NOTHING'
        ),
        generator=lambda deps: (
            random.choice(deps['organizers']),
            random.choice(deps['status']),
            f"{random.choice(COMPETITION_TITLES)} #{random.randint(1, 999)}"[:50],
            random.choice(COMPETITION_DESCRIPTIONS)[:200],
            fake.date_time_between(start_date='+1d', end_date='+30d'),
        ),
        dependencies={
            'organizers': (
                'SELECT user_id FROM "user" WHERE role_id IN '
                '(SELECT role_id FROM role WHERE name IN (\'organizer\', \'организатор\'))'
            ),
            'status': 'SELECT status_id FROM competition_status',
        },
        count=count,
    )


async def run_level1(inserter, fake: Faker) -> None:
    await seed_users(inserter, fake)
    await seed_datasets(inserter, fake)
    await seed_dataset_files(inserter, fake)
    await seed_competitions(inserter, fake)
