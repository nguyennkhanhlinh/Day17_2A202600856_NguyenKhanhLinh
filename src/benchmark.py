from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Student TODO: read JSON conversations from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def recall_points(answer: str, expected: list[str]) -> float:
    """Student TODO: return 0 / 0.5 / 1 depending on how many expected facts appear."""

    if not expected:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for item in expected if item.lower() in answer_lower)
    return hits / len(expected)


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Student TODO: add a lightweight quality score for offline mode."""

    if not answer.strip():
        return 0.0
    recall = recall_points(answer, expected)
    length_bonus = 1.0 if 20 <= len(answer) <= 600 else 0.7
    return round((recall * 0.8) + (length_bonus * 0.2), 3)


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    """Student TODO: evaluate one agent over many conversations.

    Pseudocode:
    1. Feed all turns to the agent.
    2. Track `agent tokens only`.
    3. Track `prompt tokens processed`.
    4. Ask recall questions in a fresh thread.
    5. Compute average recall and quality.
    6. Record memory file growth and compaction count.
    """

    user_ids = {conv["user_id"] for conv in conversations}
    before_sizes = {
        user_id: getattr(agent, "memory_file_size", lambda _user_id: 0)(user_id)
        for user_id in user_ids
    }

    recall_scores: list[float] = []
    quality_scores: list[float] = []
    thread_ids: list[str] = []

    for conv in conversations:
        user_id = conv["user_id"]
        thread_id = f"{conv['id']}-{agent_name}-train"
        thread_ids.append(thread_id)
        for turn in conv.get("turns", []):
            agent.reply(user_id, thread_id, turn)

        for index, question in enumerate(conv.get("recall_questions", [])):
            recall_thread = f"{conv['id']}-{agent_name}-recall-{index}"
            thread_ids.append(recall_thread)
            result = agent.reply(user_id, recall_thread, question["question"])
            answer = result.get("answer") or result.get("content") or ""
            expected = question.get("expected_contains", [])
            recall_scores.append(recall_points(answer, expected))
            quality_scores.append(heuristic_quality(answer, expected))

    after_sizes = {
        user_id: getattr(agent, "memory_file_size", lambda _user_id: 0)(user_id)
        for user_id in user_ids
    }

    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=sum(agent.token_usage(thread_id) for thread_id in thread_ids),
        prompt_tokens_processed=sum(agent.prompt_token_usage(thread_id) for thread_id in thread_ids),
        recall_score=round(sum(recall_scores) / len(recall_scores), 3) if recall_scores else 0.0,
        response_quality=round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else 0.0,
        memory_growth_bytes=sum(after_sizes[user_id] - before_sizes[user_id] for user_id in user_ids),
        compactions=sum(agent.compaction_count(thread_id) for thread_id in thread_ids),
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Student TODO: print a markdown table or tabulated output."""

    headers = [
        "Agent",
        "Agent tokens only",
        "Prompt tokens processed",
        "Cross-session recall",
        "Response quality",
        "Memory growth (bytes)",
        "Compactions",
    ]
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        table.append(
            "| "
            + " | ".join(
                [
                    row.agent_name,
                    str(row.agent_tokens_only),
                    str(row.prompt_tokens_processed),
                    f"{row.recall_score:.3f}",
                    f"{row.response_quality:.3f}",
                    str(row.memory_growth_bytes),
                    str(row.compactions),
                ]
            )
            + " |"
        )
    return "\n".join(table)


def main() -> None:
    """Student TODO: run both benchmark suites.

    Required benchmark sections:
    - Standard benchmark from `data/conversations.json`
    - Long-context stress benchmark from `data/advanced_long_context.json`

    Compare:
    - Baseline
    - Advanced

    Keep the same output columns as the solved lab:
    - Agent tokens only
    - Prompt tokens processed
    - Cross-session recall
    - Response quality
    - Memory growth (bytes)
    - Compactions
    """

    config = load_config(Path(__file__).resolve().parent.parent)

    standard = load_conversations(config.data_dir / "conversations.json")
    stress = load_conversations(config.data_dir / "advanced_long_context.json")

    print("## Standard Benchmark")
    print(
        format_rows(
            [
                run_agent_benchmark("Baseline", BaselineAgent(config, force_offline=True), standard, config),
                run_agent_benchmark("Advanced", AdvancedAgent(config, force_offline=True), standard, config),
            ]
        )
    )

    print("\n## Long-Context Stress Benchmark")
    print(
        format_rows(
            [
                run_agent_benchmark("Baseline", BaselineAgent(config, force_offline=True), stress, config),
                run_agent_benchmark("Advanced", AdvancedAgent(config, force_offline=True), stress, config),
            ]
        )
    )


if __name__ == "__main__":
    main()
