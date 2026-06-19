from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}

        # TODO: optionally initialize a real LangChain/LangGraph agent.
        self.langchain_agent = None

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: route between offline mode and live mode."""

        return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement the deterministic advanced path.

        Pseudocode:
        1. Extract stable profile facts from the incoming message.
        2. Persist those facts into `User.md`.
        3. Append the message into compact memory.
        4. Estimate prompt-context load from `User.md` + summary + recent messages.
        5. Generate a response that can answer long-term recall questions.
        6. Append the assistant reply and update token counters.
        """

        updates = extract_profile_updates(message)
        for key, value in updates.items():
            self.profile_store.upsert_fact(user_id, key, value)

        self.compact_memory.append(thread_id, "user", message)
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens

        answer = self._offline_response(user_id, thread_id, message)
        self.compact_memory.append(thread_id, "assistant", answer)

        output_tokens = estimate_tokens(answer)
        self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + output_tokens

        return {
            "answer": answer,
            "content": answer,
            "thread_id": thread_id,
            "agent_tokens": output_tokens,
            "prompt_tokens": prompt_tokens,
            "memory_path": str(self.profile_store.path_for(user_id)),
            "profile_updates": updates,
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Student TODO: estimate the context carried into one turn.

        Hint:
        - Include `User.md`
        - Include compact summary text
        - Include recent kept messages
        """

        profile = self.profile_store.read_text(user_id)
        context = self.compact_memory.context(thread_id)
        messages = context.get("messages", [])
        summary = str(context.get("summary", ""))
        recent_text = "\n".join(
            item.get("content", "") for item in messages if isinstance(item, dict)
        )
        return estimate_tokens(profile) + estimate_tokens(summary) + estimate_tokens(recent_text)

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Student TODO: return a deterministic answer using persisted memory.

        Make sure the advanced agent can answer questions like:
        - "Mình tên gì?"
        - "Hiện tại mình làm nghề gì?"
        - "Nhắc lại style trả lời mình thích"
        - questions in the long stress dataset
        """

        facts = self.profile_store.facts(user_id)
        lowered = message.lower()

        def get(key: str, fallback: str = "chưa rõ") -> str:
            return facts.get(key, fallback)

        wants_recall = any(
            marker in lowered
            for marker in (
                "tên",
                "ten",
                "nghề",
                "nghe",
                "ở đâu",
                "o dau",
                "hiện tại",
                "hien tai",
                "style",
                "đồ uống",
                "do uong",
                "món ăn",
                "mon an",
                "nuôi",
                "nuoi",
                "tóm tắt",
                "tom tat",
                "biết",
                "biet",
            )
        )

        if wants_recall:
            parts = []
            if "name" in facts:
                parts.append(f"tên {facts['name']}")
            if "profession" in facts:
                parts.append(f"nghề hiện tại {facts['profession']}")
            if "location" in facts:
                parts.append(f"đang ở {facts['location']}")
            if "favorite_drink" in facts:
                parts.append(f"đồ uống yêu thích {facts['favorite_drink']}")
            if "favorite_food" in facts:
                parts.append(f"món ăn yêu thích {facts['favorite_food']}")
            if "pet" in facts:
                parts.append(f"nuôi {facts['pet']}")
            if "response_style" in facts:
                parts.append(f"style trả lời {facts['response_style']}")
            if "interests" in facts:
                parts.append(f"quan tâm {facts['interests']}")
            if parts:
                return "Mình nhớ: " + "; ".join(parts) + "."
            return "Mình chưa có đủ thông tin ổn định trong User.md để nhắc lại chính xác."

        updates = extract_profile_updates(message)
        if updates:
            remembered = ", ".join(f"{key}={value}" for key, value in updates.items())
            return f"Mình đã lưu vào User.md: {remembered}."

        style = get("response_style", "ngắn gọn")
        return f"Mình đã ghi nhận. Mình sẽ trả lời theo hướng {style} khi phù hợp."

    def _maybe_build_langchain_agent(self):
        """Student TODO: wire a live agent with tools and compact middleware.

        High-level design:
        - `build_chat_model(self.config.model)` for the selected provider
        - `InMemorySaver` for short-term thread state
        - tool to read `User.md`
        - tool to write/edit `User.md`
        - dynamic prompt that injects profile memory
        - summarization middleware for long threads
        """

        if self.force_offline:
            return None
        try:
            return build_chat_model(self.config.model)
        except Exception:
            return None
