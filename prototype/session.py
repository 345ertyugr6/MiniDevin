"""프로토타입 개발 세션 로직."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SessionStep:
    """사용자가 정의한 개발 단계 정보를 보관합니다."""

    description: str
    command: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def format_for_display(self, index: int) -> str:
        parts = [f"[{index}] {self.description}"]
        if self.command:
            parts.append(f"  └─ $ {self.command}")
        parts.append(f"  (작성 시각: {self.created_at.isoformat()} UTC)")
        return "\n".join(parts)


class DevelopmentSession:
    """매우 단순한 MiniDevin 협업 프로토타입."""

    def __init__(self, goal: str) -> None:
        self.goal = goal.strip()
        self._steps: List[SessionStep] = []

    def add_step(self, description: str, command: Optional[str] = None) -> SessionStep:
        """세션에 새로운 단계를 추가합니다."""

        normalized = description.strip()
        if not normalized:
            raise ValueError("단계 설명은 비어 있을 수 없습니다.")

        step = SessionStep(description=normalized, command=command.strip() if command else None)
        self._steps.append(step)
        return step

    def steps(self) -> List[SessionStep]:
        """현재까지 누적된 단계를 순서대로 반환합니다."""

        return list(self._steps)

    def render_summary(self) -> str:
        """목표와 함께 단계 요약을 문자열로 반환합니다."""

        header = ["================ MiniDevin Prototype ================", f"목표: {self.goal or '미정'}", ""]
        if not self._steps:
            header.append("아직 추가된 단계가 없습니다. 대화를 통해 단계를 쌓아보세요!")
            return "\n".join(header)

        lines = header
        for index, step in enumerate(self._steps, start=1):
            lines.append(step.format_for_display(index))
            lines.append("")
        return "\n".join(lines).rstrip()
