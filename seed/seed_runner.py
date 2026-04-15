import asyncio
import random
from pathlib import Path
import sys

import asyncpg
from faker import Faker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from infra.db_config import get_pg_connect_kwargs
from inserter import Inserter
from seed_dict import run_all_dictionaries
from seed_base import run_level1
from seed_core import run_level2
from seed_sub import run_level3


async def seed_all(
    conn,
    *,
    inserter: Inserter | None = None,
    rng: random.Random | None = None,
    fake: Faker | None = None,
) -> None:
    fake = fake or Faker()
    inserter = inserter or Inserter(conn, rng=rng)

    await run_all_dictionaries(conn)
    await run_level1(inserter, fake)
    await run_level2(inserter, fake)
    await run_level3(inserter, fake)


async def main() -> None:
    conn = await asyncpg.connect(**get_pg_connect_kwargs())
    try:
        await seed_all(conn)
        print("\nFull seed completed.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
