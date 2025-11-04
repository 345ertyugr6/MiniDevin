"""MiniDevin 프로토타입 CLI.

복잡한 자동화 대신, 사용자가 직접 단계를 정의하면서 진행할 수 있는
아주 가벼운 인터페이스를 제공합니다.
"""

from __future__ import annotations

from textwrap import dedent

from prototype import DevelopmentSession


INTRO = dedent(
    """
    ================================================
    MiniDevin Prototype
    ================================================
    - 목표를 입력하고, 필요한 작업 단계를 직접 추가하세요.
    - 각 단계에는 선택적으로 실행하려는 명령을 함께 기록할 수 있습니다.
    - 빈 줄을 입력하면 단계 추가를 종료합니다.
    """
)


def prompt_goal() -> str:
    print(INTRO)
    return input("이번 세션의 목표를 적어주세요: ").strip()


def prompt_steps(session: DevelopmentSession) -> None:
    print("\n단계를 추가합니다. (그만하려면 그냥 Enter)")
    while True:
        description = input("- 단계 설명: ").strip()
        if not description:
            break
        command = input("  ↳ 연관된 명령(없으면 Enter): ").strip()
        command_value = command if command else None
        session.add_step(description, command_value)
        print("  단계가 추가되었습니다!\n")


def main() -> None:
    goal = prompt_goal()
    session = DevelopmentSession(goal)
    prompt_steps(session)
    print("\n요약:\n")
    print(session.render_summary())


if __name__ == "__main__":
    main()
