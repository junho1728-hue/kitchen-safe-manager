"""Snap & Go 백그라운드 워커.

사진 촬영 즉시 로컬 저장 후 다음 촬영으로 넘어가고,
Gemini API 분석은 백그라운드 스레드에서 처리한다.
"""

import json
import threading
import queue
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_FILE = BASE_DIR / "data" / "pending_queue.json"


class BackgroundWorker:
    """모듈 수준 싱글톤 — Streamlit 재실행 간에도 유지."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._task_queue: queue.Queue = queue.Queue()
        self._results: dict = {}
        self._results_lock = threading.Lock()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self._restore_queue()

    # ── 공개 API ──

    def enqueue(
        self,
        task_id: str,
        image_path: str,
        task_type: str,
        product_name: str = "",
        api_key: str = "",
        model: str = "",
    ) -> None:
        """사진을 큐에 추가. 즉시 반환 (블로킹 없음)."""
        task = {
            "task_id": task_id,
            "image_path": image_path,
            "task_type": task_type,
            "product_name": product_name,
            "api_key": api_key,
            "model": model,
            "enqueued_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_to_queue_file(task)
        self._task_queue.put(task)

    def pending_count(self) -> int:
        """현재 처리 대기 중인 작업 수 (알림 배지용)."""
        return self._task_queue.qsize()

    def get_result(self, task_id: str) -> dict | None:
        """완료된 결과 가져오기. 없으면 None. 한 번 가져오면 삭제."""
        with self._results_lock:
            return self._results.pop(task_id, None)

    def get_all_results(self) -> dict:
        """완료된 모든 결과를 가져와 초기화."""
        with self._results_lock:
            r = dict(self._results)
            self._results.clear()
            return r

    # ── 내부 처리 ──

    def _worker_loop(self):
        while True:
            task = self._task_queue.get()
            try:
                result = self._process_task(task)
            except Exception as e:
                result = {"error": str(e), "product_name": task.get("product_name", "")}
            finally:
                with self._results_lock:
                    self._results[task["task_id"]] = result
                self._remove_from_queue_file(task["task_id"])

    def _process_task(self, task: dict) -> dict:
        from services.gemini_service import extract_date_from_label

        image_path = Path(task["image_path"])
        if not image_path.exists():
            return {"error": "이미지 파일 없음", "product_name": task.get("product_name", "")}

        image_bytes = image_path.read_bytes()

        if task["task_type"] == "label_ocr":
            detected_date = extract_date_from_label(
                task["api_key"], task["model"], image_bytes
            )
            return {
                "date": detected_date,
                "product_name": task.get("product_name", ""),
                "image_path": task["image_path"],
            }

        return {"error": f"알 수 없는 작업 유형: {task['task_type']}"}

    # ── 큐 영속화 (앱 재시작 복원) ──

    def _save_to_queue_file(self, task: dict):
        tasks = self._read_queue_file()
        tasks.append(task)
        self._write_queue_file(tasks)

    def _remove_from_queue_file(self, task_id: str):
        tasks = [t for t in self._read_queue_file() if t.get("task_id") != task_id]
        self._write_queue_file(tasks)

    def _restore_queue(self):
        for task in self._read_queue_file():
            self._task_queue.put(task)

    def _read_queue_file(self) -> list:
        if not QUEUE_FILE.exists():
            return []
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write_queue_file(self, tasks: list):
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)


def get_worker() -> BackgroundWorker:
    """싱글톤 워커 반환."""
    return BackgroundWorker()
