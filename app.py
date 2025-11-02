import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Generator, List, Optional
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
LOG_DIR = BASE_DIR / "logs"


class EventManager:
    """간단한 SSE 이벤트 브로드캐스터."""

    def __init__(self) -> None:
        self._events: List[Dict[str, object]] = []
        self._condition = threading.Condition()
        self._next_id = 1

    def clear(self) -> None:
        with self._condition:
            self._events.clear()
            self._next_id = 1
            self._condition.notify_all()

    def publish(self, data: Dict[str, object], event_type: Optional[str] = None) -> Dict[str, object]:
        event_type = event_type or str(data.get("type", "message"))
        with self._condition:
            event = {
                "id": self._next_id,
                "type": event_type,
                "data": data,
            }
            self._events.append(event)
            self._next_id += 1
            self._condition.notify_all()
        return event

    def listen(self, last_event_id: int = 0) -> Generator[Dict[str, object], None, None]:
        index = 0
        with self._condition:
            if last_event_id:
                for i, event in enumerate(self._events):
                    if event["id"] > last_event_id:
                        index = i
                        break
                else:
                    index = len(self._events)
        while True:
            with self._condition:
                keep_alive = False
                while index >= len(self._events):
                    notified = self._condition.wait(timeout=15)
                    if not notified:
                        keep_alive = True
                        break
                if keep_alive:
                    event = {"comment": "keep-alive"}
                else:
                    event = self._events[index]
                    index += 1
            yield event


class RunState:
    """현재 MiniDevin 실행 상태를 관리한다."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.status: str = "idle"
        self.prompt: str = ""
        self.start_time: Optional[datetime] = None
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.log_path: Optional[Path] = None
        self.summary: Dict[str, object] = {}
        self.code: str = ""
        self.test_output: str = ""
        self.llm_entries: Dict[int, Dict[str, object]] = {}
        self.llm_total_requests: int = 0
        self.stop_requested: bool = False
        self.error_message: Optional[str] = None

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            entries = [
                dict(entry)
                for _, entry in sorted(self.llm_entries.items())
            ]
            return {
                "status": self.status,
                "prompt": self.prompt,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "log_path": str(self.log_path.relative_to(BASE_DIR)) if self.log_path else None,
                "summary": dict(self.summary),
                "code": self.code,
                "test_output": self.test_output,
                "llm_entries": entries,
                "llm_total_requests": self.llm_total_requests,
                "error": self.error_message,
            }


class MiniDevinOutputParser:
    """MiniDevin CLI 출력에서 구조화된 정보를 추출한다."""

    def __init__(self) -> None:
        self.summary: Dict[str, object] = {}
        self._section: Optional[str] = None
        self._code_lines: List[str] = []
        self._output_lines: List[str] = []
        self._llm_phase: Optional[str] = None
        self._llm_entries: Dict[int, Dict[str, object]] = {}
        self._current_prompt_index: Optional[int] = None
        self._current_prompt_lines: List[str] = []

    def process_line(self, line: str) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        stripped = line.strip()

        summary_event = self._parse_summary_line(stripped)
        if summary_event:
            events.append(summary_event)

        code_event = self._handle_code_sections(line, stripped)
        if code_event:
            events.append(code_event)

        output_event = self._handle_output_sections(line, stripped)
        if output_event:
            events.append(output_event)

        llm_events = self._handle_llm_sections(line, stripped)
        events.extend(llm_events)

        if stripped == "성공한 단계가 없어 코드와 테스트 결과를 표시할 수 없습니다.":
            events.append({
                "type": "notice",
                "message": stripped,
            })

        return events

    def finalize(self) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        if self._current_prompt_index is not None:
            prompt_text = "\n".join(self._current_prompt_lines).rstrip()
            stored = self._llm_entries.get(self._current_prompt_index, {"index": self._current_prompt_index})
            stored["prompt_full"] = prompt_text
            self._llm_entries[self._current_prompt_index] = stored
            events.append({
                "type": "llm_entry",
                "entry": dict(stored),
            })
            self._current_prompt_index = None
            self._current_prompt_lines = []
        return events

    def _parse_summary_line(self, stripped: str) -> Optional[Dict[str, object]]:
        if stripped.startswith("총 단계 수:"):
            value = self._extract_int(stripped)
            if value is not None:
                self.summary["total_steps"] = value
        elif stripped.startswith("완료된 단계:"):
            value = self._extract_int(stripped)
            if value is not None:
                self.summary["completed_steps"] = value
        elif stripped.startswith("실패한 단계:"):
            value = self._extract_int(stripped)
            if value is not None:
                self.summary["failed_steps"] = value
        elif stripped.startswith("성공률:"):
            try:
                percentage = stripped.split(":", 1)[1].strip().rstrip("%")
                self.summary["success_rate"] = float(percentage)
            except (IndexError, ValueError):
                pass
        else:
            return None

        return {
            "type": "summary",
            "summary": dict(self.summary),
        }

    def _handle_code_sections(self, line: str, stripped: str) -> Optional[Dict[str, object]]:
        if stripped == "성공한 코드":
            self._section = "code_wait"
            self._code_lines.clear()
            return None

        if self._section == "code_wait" and self._is_separator(stripped):
            self._section = "code"
            return None

        if self._section == "code" and self._is_separator(stripped):
            code_text = "\n".join(self._code_lines).rstrip()
            self._section = None
            return {
                "type": "code",
                "code": code_text,
            }

        if self._section == "code":
            self._code_lines.append(line)
        return None

    def _handle_output_sections(self, line: str, stripped: str) -> Optional[Dict[str, object]]:
        if stripped == "테스트/실행 결과":
            self._section = "output_wait"
            self._output_lines.clear()
            return None

        if self._section == "output_wait" and self._is_separator(stripped):
            self._section = "output"
            return None

        if self._section == "output" and self._is_separator(stripped):
            output_text = "\n".join(self._output_lines).rstrip()
            self._section = None
            return {
                "type": "test_output",
                "output": output_text,
            }

        if self._section == "output":
            self._output_lines.append(line)
        return None

    def _handle_llm_sections(self, line: str, stripped: str) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        if stripped == "LLM 요청 통계:":
            self._llm_phase = "stats"
            return events

        if self._llm_phase == "stats" and stripped.startswith("총 요청 수:"):
            total = self._extract_int(stripped)
            events.append({
                "type": "llm_total",
                "total_requests": total if total is not None else 0,
            })
            self._llm_phase = "stats_header"
            return events

        if self._llm_phase == "stats_header" and self._is_separator(stripped):
            return events

        if self._llm_phase == "stats_header" and stripped.startswith("No."):
            self._llm_phase = "table"
            return events

        if self._llm_phase == "table":
            if self._is_separator(stripped):
                self._llm_phase = "after_table"
                return events
            if not stripped:
                return events
            entry = self._parse_llm_entry(line)
            if entry:
                index = entry["index"]
                stored = self._llm_entries.get(index, {})
                stored.update(entry)
                self._llm_entries[index] = stored
                events.append({
                    "type": "llm_entry",
                    "entry": dict(stored),
                })
            return events

        if stripped == "LLM 프롬프트 전문:":
            self._llm_phase = "prompts_wait"
            return events

        if self._llm_phase == "prompts_wait" and self._is_separator(stripped):
            self._llm_phase = "prompt_meta"
            return events

        if self._llm_phase == "prompt_meta" and stripped.startswith("[") and "]" in stripped:
            if self._current_prompt_index is not None:
                prompt_text = "\n".join(self._current_prompt_lines).rstrip()
                stored = self._llm_entries.get(self._current_prompt_index, {"index": self._current_prompt_index})
                stored["prompt_full"] = prompt_text
                self._llm_entries[self._current_prompt_index] = stored
                events.append({
                    "type": "llm_entry",
                    "entry": dict(stored),
                })
            try:
                index_str = stripped[1:stripped.index("]")]
                self._current_prompt_index = int(index_str)
            except ValueError:
                self._current_prompt_index = None
            meta = stripped[stripped.index("]") + 1 :].strip()
            if self._current_prompt_index is not None:
                stored = self._llm_entries.get(self._current_prompt_index, {"index": self._current_prompt_index})
                stored["meta"] = meta
                self._llm_entries[self._current_prompt_index] = stored
                events.append({
                    "type": "llm_entry",
                    "entry": dict(stored),
                })
            self._current_prompt_lines = []
            self._llm_phase = "prompt_collect"
            return events

        if self._llm_phase == "prompt_collect":
            if self._is_separator(stripped):
                if self._current_prompt_index is not None:
                    prompt_text = "\n".join(self._current_prompt_lines).rstrip()
                    stored = self._llm_entries.get(self._current_prompt_index, {"index": self._current_prompt_index})
                    stored["prompt_full"] = prompt_text
                    self._llm_entries[self._current_prompt_index] = stored
                    events.append({
                        "type": "llm_entry",
                        "entry": dict(stored),
                    })
                self._current_prompt_index = None
                self._current_prompt_lines = []
                self._llm_phase = "prompt_meta"
                return events
            if self._current_prompt_index is not None:
                self._current_prompt_lines.append(line)
            return events

        return events

    @staticmethod
    def _extract_int(text: str) -> Optional[int]:
        try:
            return int(text.split(":", 1)[1].strip())
        except (IndexError, ValueError):
            return None

    @staticmethod
    def _is_separator(text: str) -> bool:
        if not text:
            return False
        return set(text) == {"-"}

    @staticmethod
    def _parse_llm_entry(line: str) -> Optional[Dict[str, object]]:
        if len(line) < 50:
            return None
        no_part = line[:5].strip()
        api_part = line[5:15].strip()
        model_part = line[15:33].strip()
        duration_part = line[33:45].strip()
        success_part = line[45:53].strip()
        preview_part = line[53:].strip()
        try:
            index = int(no_part)
        except ValueError:
            return None
        try:
            duration = float(duration_part)
        except ValueError:
            duration = None
        success = success_part.lower() in {"true", "성공", "yes"}
        entry = {
            "index": index,
            "api": api_part,
            "model": model_part,
            "duration": duration,
            "success": success,
            "prompt_preview": preview_part,
        }
        return entry


event_manager = EventManager()
run_state = RunState()


def ensure_directories() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def start_run(prompt: str) -> Dict[str, object]:
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("프롬프트가 비어 있습니다.")

    with run_state.lock:
        if run_state.status in {"running", "stopping"}:
            raise RuntimeError("이미 실행 중인 작업이 있습니다.")
        run_state.status = "running"
        run_state.prompt = prompt
        run_state.start_time = datetime.now()
        run_state.summary = {}
        run_state.code = ""
        run_state.test_output = ""
        run_state.llm_entries = {}
        run_state.llm_total_requests = 0
        run_state.stop_requested = False
        run_state.error_message = None
        timestamp = run_state.start_time.strftime("%Y%m%d_%H%M%S")
        run_state.log_path = LOG_DIR / f"{timestamp}.txt"

    event_manager.clear()
    event_manager.publish({"type": "reset"})
    event_manager.publish({
        "type": "run_started",
        "prompt": prompt,
        "timestamp": run_state.start_time.isoformat(),
        "log_path": str(run_state.log_path.relative_to(BASE_DIR)),
    })
    event_manager.publish({
        "type": "status",
        "status": "running",
        "prompt": prompt,
        "timestamp": run_state.start_time.isoformat(),
    })

    thread = threading.Thread(target=_run_minidevin_process, args=(prompt,), daemon=True)
    thread.start()
    with run_state.lock:
        run_state.thread = thread
    return {
        "status": "running",
        "log_path": str(run_state.log_path.relative_to(BASE_DIR)),
    }


def stop_run() -> None:
    with run_state.lock:
        process = run_state.process
        if not process or run_state.status not in {"running", "stopping"}:
            raise RuntimeError("중단할 실행이 없습니다.")
        if run_state.status != "stopping":
            run_state.status = "stopping"
            event_manager.publish({"type": "status", "status": "stopping"})
        run_state.stop_requested = True

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _run_minidevin_process(prompt: str) -> None:
    parser = MiniDevinOutputParser()
    log_path = None
    with run_state.lock:
        if run_state.log_path:
            log_path = run_state.log_path
    if log_path is None:
        log_path = LOG_DIR / f"run_{int(time.time())}.txt"
    command = [
        sys.executable,
        "-u",
        str(BASE_DIR / "src" / "main.py"),
        prompt,
    ]

    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
            )
            with run_state.lock:
                run_state.process = process

            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip("\n")
                log_file.write(raw_line)
                log_file.flush()

                event_manager.publish({"type": "log", "text": line})

                for event in parser.process_line(line):
                    event_manager.publish(event)
                    _apply_structured_event(event)

            for event in parser.finalize():
                event_manager.publish(event)
                _apply_structured_event(event)

            return_code = process.wait()
    except FileNotFoundError as exc:
        error_message = f"MiniDevin 실행 파일을 찾을 수 없습니다: {exc}"
        event_manager.publish({"type": "error", "message": error_message})
        _finalize_run(status="failed", error=error_message)
        return
    except Exception as exc:  # pylint: disable=broad-except
        error_message = f"실행 중 예외가 발생했습니다: {exc}"
        event_manager.publish({"type": "error", "message": error_message})
        _finalize_run(status="failed", error=error_message)
        return
    finally:
        with run_state.lock:
            run_state.process = None

    if return_code == 0 and not run_state.stop_requested:
        _finalize_run(status="completed")
    elif run_state.stop_requested:
        _finalize_run(status="stopped")
    else:
        _finalize_run(status="failed", error=f"MiniDevin이 종료 코드 {return_code}로 종료되었습니다.")


def _apply_structured_event(event: Dict[str, object]) -> None:
    event_type = event.get("type")
    if event_type == "summary":
        summary = event.get("summary", {})
        if isinstance(summary, dict):
            with run_state.lock:
                run_state.summary = dict(summary)
    elif event_type == "code":
        code = str(event.get("code", ""))
        with run_state.lock:
            run_state.code = code
    elif event_type == "test_output":
        output = str(event.get("output", ""))
        with run_state.lock:
            run_state.test_output = output
    elif event_type == "llm_entry":
        entry = event.get("entry")
        if isinstance(entry, dict) and "index" in entry:
            try:
                index = int(entry["index"])
            except (TypeError, ValueError):
                return
            with run_state.lock:
                stored = run_state.llm_entries.get(index, {})
                stored.update(entry)
                run_state.llm_entries[index] = stored
    elif event_type == "llm_total":
        total = event.get("total_requests")
        if isinstance(total, int):
            with run_state.lock:
                run_state.llm_total_requests = total
    elif event_type == "notice":
        message = str(event.get("message", ""))
        if message:
            event_manager.publish({"type": "log", "text": message})


def _finalize_run(status: str, error: Optional[str] = None) -> None:
    with run_state.lock:
        run_state.status = status
        if error:
            run_state.error_message = error
    summary = run_state.snapshot()["summary"]
    event_manager.publish({
        "type": "status",
        "status": status,
        "error": error,
    })
    event_manager.publish({
        "type": "run_complete",
        "status": status,
        "error": error,
        "summary": summary,
        "log_path": str(run_state.log_path.relative_to(BASE_DIR)) if run_state.log_path else None,
    })


class MiniDevinRequestHandler(BaseHTTPRequestHandler):
    server_version = "MiniDevinServer/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_index()
        elif parsed.path == "/events":
            self._serve_events()
        elif parsed.path == "/status":
            self._serve_json(run_state.snapshot())
        elif parsed.path.startswith("/static/"):
            self._serve_static(parsed.path)
        elif parsed.path.startswith("/logs/"):
            self._serve_log_file(parsed.path)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "요청한 리소스를 찾을 수 없습니다.")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/run":
            self._handle_run()
        elif parsed.path == "/stop":
            self._handle_stop()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "지원하지 않는 경로입니다.")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        sys.stderr.write("[HTTP] " + (format % args) + "\n")

    def _serve_index(self) -> None:
        index_path = TEMPLATES_DIR / "index.html"
        if not index_path.exists():
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "index.html 파일이 존재하지 않습니다.")
            return
        content = index_path.read_text(encoding="utf-8")
        encoded = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_static(self, path: str) -> None:
        relative = path[len("/static/") :]
        safe_path = os.path.normpath(relative).replace("\\", "/")
        if safe_path.startswith(".."):
            self.send_error(HTTPStatus.FORBIDDEN, "잘못된 경로입니다.")
            return
        file_path = STATIC_DIR / safe_path
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "정적 파일을 찾을 수 없습니다.")
            return
        mime = self._guess_mime_type(file_path)
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_log_file(self, path: str) -> None:
        relative = path[len("/logs/") :]
        safe_path = os.path.normpath(relative).replace("\\", "/")
        if safe_path.startswith(".."):
            self.send_error(HTTPStatus.FORBIDDEN, "잘못된 경로입니다.")
            return
        file_path = LOG_DIR / safe_path
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "로그 파일을 찾을 수 없습니다.")
            return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_events(self) -> None:
        last_id = 0
        if "Last-Event-ID" in self.headers:
            try:
                last_id = int(self.headers["Last-Event-ID"])
            except ValueError:
                last_id = 0
        query = parse_qs(urlparse(self.path).query)
        if "lastEventId" in query:
            try:
                last_id = int(query["lastEventId"][0])
            except (ValueError, IndexError):
                last_id = 0

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            for event in event_manager.listen(last_id):
                if "comment" in event:
                    payload = f": {event['comment']}\n\n".encode("utf-8")
                    self.wfile.write(payload)
                    self.wfile.flush()
                    continue
                data = event["data"]
                event_id = event["id"]
                event_type = event["type"]
                payload = json.dumps(data, ensure_ascii=False)
                message = f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"
                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError):
            return

    def _handle_run(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "JSON 형식이 잘못되었습니다.")
            return
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self.send_error(HTTPStatus.BAD_REQUEST, "프롬프트를 입력해주세요.")
            return
        try:
            result = start_run(prompt)
        except ValueError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except RuntimeError as exc:
            self.send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._serve_json(result)

    def _handle_stop(self) -> None:
        try:
            stop_run()
        except RuntimeError as exc:
            self.send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._serve_json({"status": "stopping"})

    def _serve_json(self, data: Dict[str, object]) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".js":
            return "application/javascript; charset=utf-8"
        if ext == ".css":
            return "text/css; charset=utf-8"
        if ext in {".json", ".map"}:
            return "application/json; charset=utf-8"
        if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            return f"image/{ext.lstrip('.') }"
        return "application/octet-stream"


def run_server(host: str, port: int) -> None:
    ensure_directories()
    server = ThreadingHTTPServer((host, port), MiniDevinRequestHandler)
    print(f"MiniDevin 웹 UI 서버가 http://{host}:{port} 에서 실행 중입니다. (종료: Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다...")
    finally:
        server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MiniDevin 웹 UI 서버")
    parser.add_argument("--host", default="127.0.0.1", help="바인딩할 호스트 (기본값: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="사용할 포트 (기본값: 8000)")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    event_manager.publish({"type": "status", "status": run_state.status})
    run_server(arguments.host, arguments.port)
