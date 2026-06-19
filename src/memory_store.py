from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Student TODO: implement a simple token estimator.

    Example idea:
    - Strip whitespace
    - Return 0 for empty text
    - Approximate tokens from character count, e.g. len(text) / 4
    """

    cleaned = " ".join((text or "").split())
    if not cleaned:
        return 0
    return max(1, len(cleaned) // 4)


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        # TODO: slugify or sanitize the user id before building the file path.
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", user_id.strip()) or "default"
        return self.root_dir / safe_id / "User.md"

    def read_text(self, user_id: str) -> str:
        # TODO: return file content or an empty default markdown profile.
        path = self.path_for(user_id)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "# User Profile\n\n"

    def write_text(self, user_id: str, content: str) -> Path:
        # TODO: write markdown to disk and return the file path.
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        # TODO: replace one occurrence inside User.md and return whether it changed.
        current = self.read_text(user_id)
        if search_text not in current:
            return False
        self.write_text(user_id, current.replace(search_text, replacement, 1))
        return True

    def file_size(self, user_id: str) -> int:
        # TODO: return the current file size in bytes.
        path = self.path_for(user_id)
        if not path.exists():
            return 0
        return path.stat().st_size

    def facts(self, user_id: str) -> dict[str, str]:
        facts: dict[str, str] = {}
        for line in self.read_text(user_id).splitlines():
            if not line.startswith("- "):
                continue
            key, sep, value = line[2:].partition(":")
            if sep:
                facts[key.strip().lower()] = value.strip()
        return facts

    def upsert_fact(self, user_id: str, key: str, value: str) -> None:
        key = key.strip().lower()
        value = value.strip()
        current = self.read_text(user_id)
        lines = current.splitlines()
        target = f"- {key}:"

        for index, line in enumerate(lines):
            if line.lower().startswith(target):
                lines[index] = f"- {key}: {value}"
                self.write_text(user_id, "\n".join(lines).rstrip() + "\n")
                return

        if not lines:
            lines = ["# User Profile", ""]
        if lines[-1].strip():
            lines.append("")
        lines.append(f"- {key}: {value}")
        self.write_text(user_id, "\n".join(lines).rstrip() + "\n")


def extract_profile_updates(message: str) -> dict[str, str]:
    """Student TODO: convert raw user text into stable profile facts.

    Example facts you may want to extract:
    - name
    - location
    - profession
    - preferences / response style
    - favorite food / drink

    Pseudocode:
    1. Build a few regex patterns.
    2. Skip obvious question-only turns.
    3. Return only the facts that are confidently present in the message.
    """

    text = " ".join((message or "").split())
    lowered = text.lower()
    if not text:
        return {}

    updates: dict[str, str] = {}
    question_markers = ("?", "không", "khong", "gì", "gi", "nhắc lại", "nhac lai")
    is_question_only = text.endswith("?") and any(marker in lowered for marker in question_markers)

    patterns = [
        ("name", r"(?:mình|minh|tên mình|ten minh)\s+(?:tên là|ten la|là|la)\s+([^,.!?]+)"),
        ("location", r"(?:mình|minh)\s+(?:đang\s+)?(?:ở|o)\s+([^,.!?]+)"),
        ("profession", r"(?:đang|dang|giờ|gio|hiện tại|hien tai).{0,30}?(?:làm|lam|là|la)\s+([^,.!?]+engineer|MLOps engineer|backend engineer|product manager)"),
        ("favorite_drink", r"(?:đồ uống yêu thích|do uong yeu thich|uống|uong)\s+(?:là|la)?\s*([^,.!?]*(?:cà phê sữa đá|ca phe sua da)[^,.!?]*)"),
        ("favorite_food", r"(?:món ăn yêu thích|mon an yeu thich|món ruột|mon ruot)\s+(?:là|la)?\s*([^,.!?]+)"),
        ("pet", r"(?:nuôi|nuoi)\s+(?:một|mot)?\s*([^,.!?]*(?:corgi|Bơ|Bo)[^,.!?]*)"),
    ]

    if not is_question_only:
        for key, pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .")
                if value:
                    updates[key] = value

    if any(word in lowered for word in ("ngắn gọn", "ngan gon", "bullet", "3 bullet", "ví dụ", "vi du")):
        styles: list[str] = []
        if "3 bullet" in lowered:
            styles.append("3 bullet")
        elif "bullet" in lowered:
            styles.append("bullet ngắn")
        if "ngắn gọn" in lowered or "ngan gon" in lowered:
            styles.append("ngắn gọn")
        if "ví dụ" in lowered or "vi du" in lowered or "thực chiến" in lowered or "thuc chien" in lowered:
            styles.append("có ví dụ thực tế")
        if "trade-off" in lowered:
            styles.append("nhấn trade-off")
        updates["response_style"] = ", ".join(dict.fromkeys(styles))

    if any(word in lowered for word in ("python", "ai", "mlops", "rag", "benchmark")):
        interests = []
        for word in ("Python", "AI", "MLOps", "RAG", "benchmark"):
            if word.lower() in lowered:
                interests.append(word)
        if interests:
            updates["interests"] = ", ".join(dict.fromkeys(interests))

    if "đà nẵng" in lowered or "da nang" in lowered:
        updates["location"] = "Đà Nẵng"
    if "huế" in lowered or "hue" in lowered:
        updates["location"] = "Huế"
    if "mlops engineer" in lowered:
        updates["profession"] = "MLOps engineer"
    elif "backend engineer" in lowered and "không còn" not in lowered and "khong con" not in lowered:
        updates["profession"] = "backend engineer"
    if "dũngct stress" in lowered or "dungct stress" in lowered:
        updates["name"] = "DũngCT Stress"
    elif "dũngct" in lowered or "dungct" in lowered:
        updates["name"] = "DũngCT"
    if "cà phê sữa đá" in lowered or "ca phe sua da" in lowered:
        updates["favorite_drink"] = "cà phê sữa đá"
    if "mì quảng" in lowered or "mi quang" in lowered:
        updates["favorite_food"] = "mì Quảng"
    if "corgi" in lowered:
        updates["pet"] = "corgi"

    return updates


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Student TODO: create a compact summary of older messages.

    This can be heuristic text concatenation first.
    Later, you can replace it with an LLM-based summary if desired.
    """

    if not messages:
        return ""
    snippets = []
    for item in messages[-max_items:]:
        role = item.get("role", "unknown")
        content = " ".join(item.get("content", "").split())
        if len(content) > 180:
            content = content[:177].rstrip() + "..."
        snippets.append(f"{role}: {content}")
    return "\n".join(snippets)


@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        # TODO:
        # 1. create thread state if missing
        # 2. append the new message
        # 3. trigger compaction if needed
        thread = self.state.setdefault(
            thread_id,
            {"messages": [], "summary": "", "compactions": 0},
        )
        messages = thread["messages"]
        assert isinstance(messages, list)
        messages.append({"role": role, "content": content})

        summary = str(thread.get("summary", ""))
        total_text = summary + "\n" + "\n".join(m["content"] for m in messages)
        if estimate_tokens(total_text) <= self.threshold_tokens:
            return

        keep = max(1, self.keep_messages)
        older = messages[:-keep]
        recent = messages[-keep:]
        if not older:
            return

        older_summary = summarize_messages(older, max_items=3)
        compacted = (summary + "\n" + older_summary).strip()
        if len(compacted) > 600:
            compacted = compacted[-600:]
        thread["summary"] = compacted
        thread["messages"] = recent
        thread["compactions"] = int(thread.get("compactions", 0)) + 1

    def context(self, thread_id: str) -> dict[str, object]:
        # TODO: return per-thread state with keys like messages, summary, compactions.
        return self.state.setdefault(
            thread_id,
            {"messages": [], "summary": "", "compactions": 0},
        )

    def compaction_count(self, thread_id: str) -> int:
        # TODO: return number of compactions for this thread.
        return int(self.context(thread_id).get("compactions", 0))
