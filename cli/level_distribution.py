from __future__ import annotations

from seed.settings import LEVEL_COEFFICIENTS

ALL_LEVEL_RATIOS: dict[str, float] = {
    "level1": 0.42,
    "level2": 0.40,
    "level3": 0.18,
}


def distribute_total(total_count: int, ratios: dict[str, float]) -> dict[str, int]:
    if total_count <= 0:
        raise ValueError("total_count must be greater than 0")
    if not ratios:
        raise ValueError("ratios must not be empty")

    ratio_sum = sum(ratios.values())
    if ratio_sum <= 0:
        raise ValueError("sum of ratios must be greater than 0")

    normalized = {key: value / ratio_sum for key, value in ratios.items()}

    base: dict[str, int] = {}
    fractions: list[tuple[float, str]] = []
    allocated = 0

    for key, ratio in normalized.items():
        raw = total_count * ratio
        integer = int(raw)
        base[key] = integer
        allocated += integer
        fractions.append((raw - integer, key))

    remainder = total_count - allocated
    for _fraction, key in sorted(fractions, reverse=True)[:remainder]:
        base[key] += 1

    return base


def level_counts(level: str, total_count: int) -> dict[str, int]:
    if level not in LEVEL_COEFFICIENTS:
        raise ValueError(f"Unknown level: {level}")
    return distribute_total(total_count, LEVEL_COEFFICIENTS[level])
