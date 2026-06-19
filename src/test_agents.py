from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config
from memory_store import UserProfileStore


def make_config(tmp_path: Path):
    """Student TODO: build an isolated config for tests."""

    # Hint:
    # - point `state_dir` into tmp_path
    # - reduce compact threshold so compaction happens quickly in tests
    config = load_config(Path(__file__).resolve().parent.parent)
    config.state_dir = tmp_path / "state"
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.compact_threshold_tokens = 80
    config.compact_keep_messages = 4
    return config


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Student TODO: verify `User.md` can be created, updated, and edited."""

    store = UserProfileStore(tmp_path / "profiles")
    assert store.read_text("user-1").startswith("# User Profile")

    path = store.write_text("user-1", "# User Profile\n\n- name: Linh\n")
    assert path.exists()
    assert "Linh" in store.read_text("user-1")

    changed = store.edit_text("user-1", "Linh", "Khanh Linh")
    assert changed is True
    assert "Khanh Linh" in store.read_text("user-1")
    assert store.file_size("user-1") > 0


def test_compact_trigger(tmp_path: Path) -> None:
    """Student TODO: verify long threads trigger compaction."""

    config = make_config(tmp_path)
    agent = AdvancedAgent(config, force_offline=True)

    for index in range(12):
        agent.reply(
            "user-1",
            "thread-long",
            f"Đây là một tin nhắn dài số {index} về Python, AI, MLOps và benchmark memory.",
        )

    assert agent.compaction_count("thread-long") > 0


def test_cross_session_recall(tmp_path: Path) -> None:
    """Student TODO: verify advanced remembers across sessions and baseline does not."""

    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    baseline.reply("user-1", "thread-a", "Mình tên là Linh và đang làm MLOps engineer.")
    advanced.reply("user-1", "thread-a", "Mình tên là Linh và đang làm MLOps engineer.")

    baseline_answer = baseline.reply("user-1", "thread-b", "Mình tên gì và làm nghề gì?")["answer"]
    advanced_answer = advanced.reply("user-1", "thread-b", "Mình tên gì và làm nghề gì?")["answer"]

    assert "MLOps engineer" not in baseline_answer
    assert "MLOps engineer" in advanced_answer


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Student TODO: compare prompt load of baseline vs advanced on a long thread."""

    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    for index in range(20):
        message = (
            f"Tin nhắn dài {index}: mình đang kiểm thử compact memory với nhiều context "
            "về Python, AI agent, benchmark, token cost và long-context stress."
        )
        baseline.reply("user-1", "thread-long", message)
        advanced.reply("user-1", "thread-long", message)

    assert advanced.compaction_count("thread-long") > 0
    assert advanced.prompt_token_usage("thread-long") < baseline.prompt_token_usage("thread-long")
