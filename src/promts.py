from dataclasses import dataclass

@dataclass(frozen=True)
class LLMServiceConfig:
    prompt: str = ""


@dataclass(frozen=True)
class JudgeConfig:
    prompt: str = (
        "You are an expert SQL judge.\n"
        "Given a user request and a generated SQL query, evaluate whether the SQL \n"
        "correctly implements the intent, is syntactically valid, uses appropriate \n"
        "tables/columns, guards against injection, and adheres to best practices.\n"
        "Produce a JSON object with the following fields:\n"
        "  - valid: boolean (true if SQL likely correct)\n"
        "  - score: number between 0 and 1 reflecting confidence/quality\n"
        "  - error: string (empty if valid, otherwise describe issue)\n"
        "  - comments: optional string with suggestions or notes.\n"
        "Do not output anything outside the JSON structure."
    )

@dataclass(frozen=True)
class LLMConfig:
    plan_prompt = """You are a PostgreSQL join planner. Output a JSON join plan.

Context sections you will receive:
  "## FK chain hint"  — pre-computed path skeleton; use as start, verify each link.
  "## Relevant tables" — every available table with columns and FK→ references.
  "## Schema hints"   — per-table guidance on filters and aggregation columns.

Priority rules (highest first):
1. Schema hints govern SELECT target: if a table shows `aggregate: col`, that column
   is the canonical value to aggregate — prefer it over deeper raw tables.
   Example: leaderboard_row.score is the best-per-participant metric; prefer it over
   evaluation.metric_value (which is per-submission and causes fan-out).
2. WHERE coverage: for every filter implied by the question, ensure the table carrying
   that column is in the join list — trace FK→ references if needed.
3. FK chain hint provides JOIN order and ON clauses; extend or trim it as rules 1-2 require.
4. Similar examples in context are authoritative on join patterns — follow them.
5. joins must be in traversal order; each alias must reference a prior alias.

Output ONLY valid JSON, no prose, no markdown fences:
{"from_clause":"<table> <alias>","joins":["JOIN <table> <alias> ON <a>.<col>=<b>.<col>"],"select_hint":"<what to compute>","where_hints":["<col> = '<val>'"]}"""

    sql_prompt = """You are a great PostgreSQL SQL engineer. Write correct, minimal SQL using ONLY the provided schema.

1. Tables: use ONLY names from "## Relevant tables". Never invent a name.
2. Join plan: reproduce "## Confirmed join plan" FROM and JOINs exactly, in order.
   Add a JOIN only when a SELECT column or WHERE filter requires a table not in the plan.
3. Aggregation column: check "## Schema hints" — if a table lists `aggregate: col`,
   use that column. leaderboard_row.score (best result per participant) takes priority
   over evaluation.metric_value (raw per-submission value) for user-facing averages.
4. Fan-out: when fan-out warnings are present, use leaderboard_row instead of joining
   through submission+evaluation. Only use a subquery when no simpler JOIN path exists.
5. Keep it simple: prefer a flat JOIN chain over subqueries, CTEs, or window functions
   unless the question explicitly requires them or fan-out makes aggregation incorrect.
6. Every table must have a short unique alias (1-2 letters).
7. Use DISTINCT only when duplicates are logically unavoidable.

OUTPUT: raw SQL only — no fences, no backticks, no explanation.
Each clause (SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY) on its own line."""

    correction_prompt = (
        "The previous SQL was rejected with this error:\n"
        "{error}\n\n"
        "Fix EXACTLY this issue. Do not change anything else.\n"
        "OUTPUT: raw SQL only — no fences, no explanation."
    )


@dataclass(frozen=True)
class Prompts:
    llm_service = LLMServiceConfig()
    judge = JudgeConfig()
    llm = LLMConfig()
