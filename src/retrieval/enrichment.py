"""LLM-based schema enrichment for Text-to-SQL.

Generates natural-language descriptions for tables and columns using
database DDL and sampled values. Based on findings from:
  - "Synthetic SQL Column Descriptions" (NeurIPS 2024)
  - "Automatic Database Description Generation" (2025)
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

_SYSTEM = """\
You are a database documentation specialist generating schema descriptions for a Text-to-SQL system.

Your descriptions help an LLM understand what each table and column actually stores,
enabling it to write accurate SQL queries without guessing column semantics.

Rules:
- Describe the DOMAIN MEANING, not just the column name
- Decode coded values if samples reveal them (e.g. 'M'/'F' → gender, 'Y'/'N' → yes/no flag)
- Note value formats when non-obvious (date as YYYYMMDD, units, encodings)
- Mention FK role when the column name suggests it (e.g. "References the stadium table")
- Keep descriptions concise: 1 sentence per column, 1-2 sentences per table
- Respond with valid JSON only — no markdown, no extra text
"""

_FEW_SHOTS = """\
=== EXAMPLE 1 ===

DDL:
CREATE TABLE singer (
    Singer_ID   INTEGER PRIMARY KEY,
    Name        TEXT,
    Country     TEXT,
    Song_Name   TEXT,
    Song_release_year TEXT,
    Age         INTEGER,
    Is_male     TEXT
)

Sample values:
Singer_ID: [1, 2, 3]
Name: ["Joe Sharp", "Timbaland", "Enrique Iglesias"]
Country: ["Netherlands", "United States", "Spain"]
Song_Name: ["You Raise Me Up", "Apologize", "Hero"]
Song_release_year: ["2003", "2006", "2001"]
Age: [52, 34, 37]
Is_male: ["F", "M", "M"]

Response:
{
  "table_description": "Professional singers with their nationality, a representative song, and basic demographics.",
  "columns": {
    "Singer_ID":         "Unique numeric identifier for each singer record.",
    "Name":              "Full stage or real name of the singer.",
    "Country":           "Country of origin or nationality of the singer.",
    "Song_Name":         "Title of the singer's representative or best-known song.",
    "Song_release_year": "Year the representative song was released, stored as a 4-digit string (e.g. '2006').",
    "Age":               "Current age of the singer in years.",
    "Is_male":           "Gender flag: 'M' for male, 'F' for female."
  }
}

=== EXAMPLE 2 ===

DDL:
CREATE TABLE trip (
    id          INTEGER PRIMARY KEY,
    duration    INTEGER,
    start_date  TEXT,
    start_station_name TEXT,
    start_station_id   INTEGER,
    end_station_name   TEXT,
    end_station_id     INTEGER,
    bike_id     INTEGER,
    subscription_type  TEXT,
    zip_code    TEXT
)

Sample values:
id: [913460, 913461, 913462]
duration: [765, 1036, 307]
start_date: ["8/31/2015 23:26", "8/31/2015 23:30", "8/31/2015 23:57"]
start_station_name: ["Harry Bridges Plaza (Ferry Building)", "San Antonio Shopping Center", "Post at Kearney"]
start_station_id: [50, 31, 47]
end_station_name: ["San Francisco Caltrain (Townsend at 4th)", "South Van Ness at Market", "2nd at South Park"]
end_station_id: [70, 66, 64]
bike_id: [288, 35, 468]
subscription_type: ["Subscriber", "Subscriber", "Customer"]
zip_code: ["94133", "94107", NULL]

Response:
{
  "table_description": "Individual bike-share trips recording origin, destination, duration, and rider type.",
  "columns": {
    "id":                 "Unique identifier for each bike trip.",
    "duration":           "Trip duration in seconds.",
    "start_date":         "Trip start timestamp in M/D/YYYY HH:MM format.",
    "start_station_name": "Human-readable name of the departure station.",
    "start_station_id":   "Numeric ID of the departure station — references the station table.",
    "end_station_name":   "Human-readable name of the arrival station.",
    "end_station_id":     "Numeric ID of the arrival station — references the station table.",
    "bike_id":            "Identifier of the specific bicycle used for the trip.",
    "subscription_type":  "Rider account type: 'Subscriber' (annual member) or 'Customer' (casual/day pass).",
    "zip_code":           "Home zip code of the rider (NULL for anonymous customers)."
  }
}

=== EXAMPLE 3 ===

DDL:
CREATE TABLE trans (
    trans_id    INTEGER PRIMARY KEY,
    account_id  INTEGER,
    date        TEXT,
    type        TEXT,
    operation   TEXT,
    amount      REAL,
    balance     REAL,
    k_symbol    TEXT,
    bank        TEXT,
    account     TEXT
)

Sample values:
trans_id: [1, 5, 6]
account_id: [1, 1, 1]
date: ["930101", "930101", "930101"]
type: ["PRIJEM", "VYDAJ", "VYDAJ"]
operation: ["VKLAD", "PREVOD NA UCET", "PREVOD Z UCTU"]
amount: [1000.0, 500.0, 900.0]
balance: [1000.0, 500.0, 1400.0]
k_symbol: [NULL, "POJISTNE", "DUCHOD"]
bank: [NULL, "AB", NULL]
account: [NULL, "41403269", NULL]

Response:
{
  "table_description": "Bank account transactions in a Czech financial system, recording credits, debits, amounts, and symbolic payment categories.",
  "columns": {
    "trans_id":   "Unique identifier for each transaction record.",
    "account_id": "References the account this transaction belongs to.",
    "date":       "Transaction date in YYYYMMDD format (e.g. '930101' = 1993-01-01).",
    "type":       "Transaction direction: 'PRIJEM' (credit / incoming money) or 'VYDAJ' (debit / outgoing money).",
    "operation":  "Payment method: 'VKLAD' (cash deposit), 'PREVOD NA UCET' (outgoing wire transfer), 'PREVOD Z UCTU' (incoming wire transfer), 'VYBER' (cash withdrawal), 'VYBER KARTOU' (card withdrawal).",
    "amount":     "Monetary amount of the transaction in Czech Korunas.",
    "balance":    "Account balance after this transaction was applied.",
    "k_symbol":   "Payment purpose code: 'POJISTNE' (insurance payment), 'DUCHOD' (pension/retirement income), 'UROK' (interest earned), 'SIPO' (household utility payment), NULL if not applicable.",
    "bank":       "Two-letter code of the partner bank for wire transfers (NULL for cash transactions).",
    "account":    "Account number at the partner bank for wire transfers (NULL for cash transactions)."
  }
}
"""

_USER_TEMPLATE = """\
{few_shots}

=== YOUR TASK ===

DDL:
{ddl}

Sample values:
{samples_text}

Response:
"""


def _format_samples(samples: dict[str, list[Any]]) -> str:
    lines = []
    for col, vals in samples.items():
        rendered = []
        for v in vals:
            rendered.append("NULL" if v is None else repr(v))
        lines.append(f"{col}: [{', '.join(rendered)}]")
    return "\n".join(lines)


def sample_values(db_path: Path, table: str, columns: list[str], n: int = 5) -> dict[str, list[Any]]:
    """Sample up to n non-null values per column from a SQLite table."""
    result: dict[str, list[Any]] = {}
    try:
        conn = sqlite3.connect(str(db_path))
        for col in columns:
            try:
                rows = conn.execute(
                    f'SELECT "{col}" FROM "{table}" LIMIT {n}'
                ).fetchall()
                result[col] = [r[0] for r in rows]
            except Exception:
                result[col] = []
        conn.close()
    except Exception:
        pass
    return result


class SchemaEnricher:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def enrich_table(
        self,
        table: str,
        ddl: str,
        samples: dict[str, list[Any]],
    ) -> dict[str, Any]:
        """Call LLM to generate table + column descriptions. Returns enrichment dict."""
        user_prompt = _USER_TEMPLATE.format(
            few_shots=_FEW_SHOTS,
            ddl=ddl,
            samples_text=_format_samples(samples),
        )
        try:
            raw = self._llm.call(
                system_prompt=_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=1200,
            )
            # strip markdown fences if model added them
            raw = re.sub(r"^```[a-z]*\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw.strip())
            return json.loads(raw)
        except Exception as exc:
            return {"table_description": "", "columns": {}, "_error": str(exc)}
