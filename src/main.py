"""MiniDevin 애플리케이션의 진입점을 정의하는 모듈."""

import asyncio
import argparse
import logging
from typing import Any, Dict, List
from modules.llm_client import LLMClient
from modules.prompt_interface import PromptInterface
from modules.planner import Planner
from modules.auto_repair import AutoRepairLoop


LOGGER = logging.getLogger(__name__)


class MiniDevin:
    """MiniDevin 실행 로직을 담는 핵심 클래스."""

    def __init__(
        self,
        llm_base_url: str = "http://localhost:11434",
        llm_model: str = "phi3:mini",
        api_type: str = "ollama",
        max_retries: int = 3,
    ) -> None:
        """MiniDevin 인스턴스를 초기화한다.

        Args:
            llm_base_url: LLM 서버의 기본 URL.
            llm_model: 사용할 모델 이름.
            api_type: 사용할 API 타입(ollama 또는 openai).
            max_retries: 자동 수정 루프에서 단계별로 허용할 최대 재시도 횟수.
        """

        # LLM과 통신하는 클라이언트를 생성한다.
        self.llm_client = LLMClient(llm_base_url, llm_model, api_type)
        # 사용자 입력을 해석하는 프롬프트 인터페이스를 준비한다.
        self.prompt_interface = PromptInterface()
        # 작업 계획 수립을 담당하는 플래너를 생성한다.
        self.planner = Planner(self.llm_client)
        # 실행 실패 시 자동으로 수정 시도를 반복하는 루프를 구성한다.
        self.auto_repair = AutoRepairLoop(self.llm_client, max_retries=max_retries)

    async def run(self, user_input: str) -> None:
        """사용자 입력을 받아 전체 실행 절차를 처리한다.

        Args:
            user_input: 사용자가 수행하길 원하는 작업 설명 문자열.
        """

        # 새 실행마다 LLM 요청 기록을 초기화한다.
        self.llm_client.reset_request_logs()

        self._display_banner("MiniDevin - Lightweight Autonomous Development AI")

        # 1단계: 사용자 입력을 분석하여 구조화된 작업으로 변환한다.
        print("\n[1/4] 사용자 입력 분석 중...")
        task = await self.prompt_interface.parse_user_input(user_input)
        self._display_task(task)

        # 2단계: 분석된 작업을 기반으로 실행 계획을 생성한다.
        print("\n[2/4] 실행 계획 수립 중...")
        plan = await self.planner.create_plan(task)
        LOGGER.debug("Planner returned plan status=%s", plan.get("status"))
        self._display_plan(plan)

        if plan.get("status") == "failed":
            print("\n[3/4] 자동 수정 기능과 함께 계획 실행 중...")
            print("계획 생성에 실패하여 실행을 진행할 수 없습니다.")
            self._display_plan_failure(plan)
            empty_summary = {
                "total_steps": 0,
                "completed_steps": 0,
                "failed_steps": 0,
                "results": []
            }
            self._display_summary(empty_summary)
            self._display_success_details(empty_summary)
            self._display_llm_stats()
            self._display_knowledge_stats()
            print("\n" + "=" * 80)
            print("모든 작업이 완료되었습니다!")
            print("=" * 80 + "\n")
            await self.auto_repair.close()
            return

        # 3단계: 생성된 계획을 순차적으로 실행하고 필요 시 자동 수정을 수행한다.
        print("\n[3/4] 자동 수정 기능과 함께 계획 실행 중...")
        summary = await self.auto_repair.execute_plan(plan)

        # 4단계: 실행 결과 요약을 출력하고 성공 시 코드와 테스트 결과를 보여준다.
        self._display_summary(summary)
        self._display_success_details(summary)
        self._display_llm_stats()
        self._display_knowledge_stats()

        print("\n" + "=" * 80)
        print("모든 작업이 완료되었습니다!")
        print("=" * 80 + "\n")

        await self.auto_repair.close()

    async def interactive_mode(self) -> None:
        """사용자와 실시간으로 상호작용하는 인터페이스를 실행한다."""

        self._display_banner("MiniDevin - Interactive Mode")
        print("프로그램을 종료하려면 'exit', 'quit', 'q' 중 하나를 입력하세요.\n")

        while True:
            try:
                # 사용자의 명령을 입력받는다.
                user_input = input("MiniDevin> ").strip()

                # 종료 명령이 입력되면 반복문을 탈출한다.
                if user_input.lower() in ["exit", "quit", "q"]:
                    print("안녕히 가세요!")
                    break

                # 공백 입력은 무시하고 다음 반복으로 넘어간다.
                if not user_input:
                    continue

                await self.run(user_input)

            except KeyboardInterrupt:
                # 사용자가 Ctrl+C로 인터럽트한 경우 우아하게 종료한다.
                print("\n\n사용자 인터럽트로 종료합니다. 안녕히 가세요!")
                break
            except Exception as exc:  # pylint: disable=broad-except
                # 예상치 못한 예외를 포착하여 디버깅을 돕는다.
                print(f"\n오류가 발생했습니다: {exc}")
                import traceback

                traceback.print_exc()

        await self.auto_repair.close()

    def _display_banner(self, title: str) -> None:
        """콘솔에 공통 헤더 배너를 출력한다."""

        print("\n" + "=" * 80)
        print(title)
        print("=" * 80)

    @staticmethod
    def _display_task(task: dict) -> None:
        """분석된 작업 정보를 자세히 출력한다."""

        print(f"작업 유형: {task['task_type']}")
        print(f"원본 설명: {task['raw_input']}")

    @staticmethod
    def _display_plan(plan: dict) -> None:
        """생성된 실행 계획을 단계별로 출력한다."""

        if plan.get("status") == "failed":
            print("계획 생성에 실패했습니다.")
            return

        steps = plan.get("steps", [])
        print(f"총 {len(steps)}개의 단계를 생성했습니다:")
        for index, step in enumerate(steps, start=1):
            print(f"  {index}. {step['description']}")

    def _display_summary(self, summary: dict) -> None:
        """계획 실행 결과를 요약하여 출력한다."""

        print("\n[4/4] 실행 결과 요약")
        print("=" * 80)
        total_steps = summary.get("total_steps", 0)
        completed_steps = summary.get("completed_steps", 0)
        failed_steps = summary.get("failed_steps", 0)
        success_rate = self._calculate_success_rate(completed_steps, total_steps)

        print(f"총 단계 수: {total_steps}")
        print(f"완료된 단계: {completed_steps}")
        print(f"실패한 단계: {failed_steps}")
        print(f"성공률: {success_rate:.1f}%")

    @staticmethod
    def _display_success_details(summary: dict) -> None:
        """성공적으로 실행된 코드와 테스트 결과를 출력한다."""

        successful_results = [result for result in summary.get("results", []) if result.get("success")]

        if not successful_results:
            print("\n성공한 단계가 없어 코드와 테스트 결과를 표시할 수 없습니다.")
            return

        final_result = successful_results[-1]
        code = (final_result.get("code") or "").rstrip()
        output = (final_result.get("output") or "").rstrip()

        print("\n성공한 코드")
        print("-" * 80)
        print(code if code else "(코드가 비어 있습니다)")
        print("-" * 80)

        print("테스트/실행 결과")
        print("-" * 80)
        print(output if output else "(출력 결과가 없습니다)")
        print("-" * 80)

    def _display_llm_stats(self) -> None:
        """LLM 요청 통계를 표 형태로 출력한다."""

        logs = self.llm_client.get_request_logs()

        print("\nLLM 요청 통계:")
        if not logs:
            print("  기록된 요청이 없습니다.")
            return

        print(f"  총 요청 수: {len(logs)}")

        table_columns = [
            ("No.", 5, lambda idx, entry: str(idx)),
            ("API", 10, lambda _idx, entry: entry.get("api_type", "")),
            ("모델", 18, lambda _idx, entry: entry.get("model", "")),
            ("시간(s)", 12, lambda _idx, entry: f"{entry.get('duration', 0.0):.3f}"),
            ("성공", 8, lambda _idx, entry: "True" if entry.get("success") else "False"),
        ]

        header = "".join(f"{name:<{width}}" for name, width, _ in table_columns) + "프롬프트 요약"
        separator = "-" * len(header)
        print(separator)
        print(header)
        print(separator)

        for index, entry in enumerate(logs, start=1):
            prompt_preview = entry.get("prompt", "").replace("\n", " ").strip()
            if len(prompt_preview) > 80:
                prompt_preview = prompt_preview[:77] + "..."

            row = "".join(
                f"{formatter(index, entry):<{width}}"
                for _name, width, formatter in table_columns
            )
            print(f"{row}{prompt_preview}")

        print(separator)

        self._display_llm_prompt_details(logs)

    @staticmethod
    def _display_llm_prompt_details(logs: List[Dict[str, Any]]) -> None:
        """각 LLM 요청의 전체 프롬프트와 관련 정보를 출력한다."""

        print("\n상세 프롬프트:")
        print("=" * 80)
        for index, entry in enumerate(logs, start=1):
            prompt_body = entry.get("prompt", "").rstrip() or "(프롬프트가 비어 있습니다)"
            response_preview = entry.get("response_preview", "").rstrip()

            print(
                f"{index}. API={entry.get('api_type', '')} 모델={entry.get('model', '')} "
                f"온도={entry.get('temperature', '')} 최대토큰={entry.get('max_tokens', '')}"
            )
            print("프롬프트:")
            print(prompt_body)
            if response_preview:
                print("\n응답 미리보기:")
                print(response_preview)
            if index != len(logs):
                print("-" * 80)

    def _display_knowledge_stats(self) -> None:
        """자동 수정 루프에서 활용한 지식 캐시 통계를 출력한다."""

        if not self.auto_repair.knowledge_cache:
            return

        stats = self.auto_repair.knowledge_cache.get_stats()
        print("\n지식 캐시 통계:")
        print(f"  검색 기록 수: {stats.get('search_entries', 0)}")
        print(f"  해결책 기록 수: {stats.get('solution_entries', 0)}")
        print(f"  캐시 조회 성공 횟수: {stats.get('cache_hits', 0)}")

    @staticmethod
    def _display_plan_failure(plan: dict) -> None:
        """계획 생성 실패 사유를 출력한다."""

        error_message = plan.get("error", "알 수 없는 오류가 발생했습니다.")
        print("\n계획 생성 오류")
        print("-" * 80)
        print(error_message)
        print("-" * 80)

    @staticmethod
    def _calculate_success_rate(completed_steps: int, total_steps: int) -> float:
        """성공률(%)을 계산한다.

        total_steps가 0일 경우 0으로 나누는 오류를 방지하기 위해 0을 반환한다.
        """

        if total_steps == 0:
            return 0.0
        return (completed_steps / total_steps) * 100


def _configure_logging(debug_enabled: bool) -> None:
    """애플리케이션 전체에서 사용할 로깅 출력을 설정한다."""

    log_level = logging.DEBUG if debug_enabled else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 디버그 모드에서도 과도한 외부 라이브러리 로그는 억제한다.
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def main():
    """애플리케이션의 메인 진입점."""
    parser = argparse.ArgumentParser(
        description="MiniDevin - Lightweight Autonomous Development AI"
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Task description (if not provided, enters interactive mode)"
    )
    parser.add_argument(
        "--llm-url",
        default="http://localhost:11434",
        help="LLM API base URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--model",
        default="phi3:mini",
        help="LLM model name (default: phi3:mini)"
    )
    parser.add_argument(
        "--api-type",
        choices=["ollama", "openai"],
        default="ollama",
        help="API type (default: ollama)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum repair attempts per step (default: 3)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging"
    )
    
    # 명령행 인자를 해석하여 실행 설정을 로드한다.
    args = parser.parse_args()
    
    _configure_logging(args.debug)
    
    mini_devin = MiniDevin(
        llm_base_url=args.llm_url,
        llm_model=args.model,
        api_type=args.api_type,
        max_retries=args.max_retries,
    )
    
    if args.task:
        # 공백으로 구분된 문자열을 하나의 작업 설명으로 합친다.
        task_description = " ".join(args.task)
        await mini_devin.run(task_description)
    else:
        # 작업 설명이 없으면 대화형 모드로 진입한다.
        await mini_devin.interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
