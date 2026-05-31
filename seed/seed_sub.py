import random
from faker import Faker

from seed.constants import SOLUTIONS, SUBMISSION_FILES
from seed.settings import SUBMISSIONS_PER_PARTICIPATION_MAX, SUBMISSIONS_PER_PARTICIPATION_MIN


async def seed_submissions(
    inserter,
    fake: Faker,
    min_per_participation: int = SUBMISSIONS_PER_PARTICIPATION_MIN,
    max_per_participation: int = SUBMISSIONS_PER_PARTICIPATION_MAX,
) -> int:
    return await inserter.seed(
        table='submission',
        query=(
            'INSERT INTO submission (participation_id, status_id, file_path, attempt_number, metric_value, is_valid, error_log, source_code, language, solution_description)\n'
            'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)\n'
            'ON CONFLICT (participation_id, attempt_number) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            random.choice(deps['status']),
            f"submissions/{random.choice(SUBMISSION_FILES)}",
            deps.get('current_ordinal'),
            round(random.uniform(0.0, 1.0), 6),
            random.choice([True, True, True, False]),
            None,
            'def solve():\n    return 42\n',
            random.choice(['python', 'cpp', 'java']),
            random.choice(SOLUTIONS),
        ),
        dependencies={
            'participation': (
                'SELECT p.participation_id\n'
                'FROM participation p\n'
                'LEFT JOIN submission s ON s.participation_id = p.participation_id\n'
                'WHERE s.participation_id IS NULL\n'
                'ORDER BY p.participation_id'
            ),
            'status': 'SELECT status_id FROM submission_status',
        },
        per_dependency='participation',
        min_per_dependency=min_per_participation,
        max_per_dependency=max_per_participation,
    )


async def seed_participation_scores(conn) -> int:
    row = await conn.fetchrow(
        """
        WITH ranked AS (
            SELECT
                p.participation_id,
                MAX(s.metric_value) AS best_score,
                ROW_NUMBER() OVER (
                    ORDER BY MAX(s.metric_value) DESC NULLS LAST, p.participation_id
                ) AS rank
            FROM participation p
            LEFT JOIN submission s ON s.participation_id = p.participation_id
            GROUP BY p.participation_id
        ), updated AS (
            UPDATE participation p
            SET best_score = ranked.best_score,
                rank = ranked.rank
            FROM ranked
            WHERE p.participation_id = ranked.participation_id
            RETURNING 1
        )
        SELECT COUNT(*)::int AS updated_count FROM updated
        """
    )
    return int(row[0]) if row else 0


async def run_level3(inserter, fake: Faker) -> None:
    await seed_submissions(inserter, fake)
    await seed_participation_scores(inserter.conn)
