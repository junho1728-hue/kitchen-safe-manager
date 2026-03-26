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
        label_image_path: str = "",
        bundle_image_paths: list = None,
    ) -> None:
        """사진을 큐에 추가. 즉시 반환 (블로킹 없음)."""
        task = {
            "task_id": task_id,
            "image_path": image_path,
            "task_type": task_type,
            "product_name": product_name,
            "api_key": api_key,
            "model": model,
            "label_image_path": label_image_path,
            "bundle_image_paths": bundle_image_paths or [],
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
        from services.gemini_service import (
            extract_date_from_label,
            extract_product_name_from_front,
        )

        image_path = Path(task["image_path"])
        if not image_path.exists():
            return {"error": "이미지 파일 없음", "product_name": task.get("product_name", "")}

        image_bytes = image_path.read_bytes()

        # ── 기존: 라벨에서 날짜만 추출 ──
        if task["task_type"] == "label_ocr":
            detected_date = extract_date_from_label(
                task["api_key"], task["model"], image_bytes
            )
            # 즉시 DB 업데이트
            if detected_date:
                from services.data_service import update_product_by_task_id
                update_product_by_task_id(
                    task["task_id"],
                    expiry_date=detected_date,
                )
            return {
                "date": detected_date,
                "product_name": task.get("product_name", ""),
                "image_path": task["image_path"],
            }

        # ── 신규: 전면(제품명) + 라벨(날짜) 동시 분석 ──
        if task["task_type"] == "product_front_label":
            names = extract_product_name_from_front(
                task["api_key"], task["model"], image_bytes
            )
            product_name = names[0] if names else "인식불가"

            detected_date = None
            label_path = task.get("label_image_path", "")
            if label_path:
                lp = Path(label_path)
                if lp.exists():
                    label_bytes = lp.read_bytes()
                    detected_date = extract_date_from_label(
                        task["api_key"], task["model"], label_bytes
                    )

            # 즉시 DB 업데이트
            from services.data_service import update_product_by_task_id
            update_product_by_task_id(
                task["task_id"],
                name=product_name,
                expiry_date=detected_date,
            )
            return {
                "product_name": product_name,
                "date": detected_date,
                "image_path": task["image_path"],
                "label_image_path": label_path,
            }

        # ── 명세서 일괄 처리 (Snap & Go) → 대기함으로 저장 ──
        if task["task_type"] == "invoice_batch":
            from services.gemini_service import extract_invoice_items, analyze_products_comprehensive
            from services.classification import classify_product
            from services.data_service import add_staging_batch
            import uuid as _uuid

            invoice_result = extract_invoice_items(task["api_key"], task["model"], image_bytes)
            items = invoice_result.get("items", [])
            corner = invoice_result.get("corner", "")
            if not items:
                return {"error": "품목 추출 실패", "count": 0}

            try:
                analyzed = analyze_products_comprehensive(task["api_key"], task["model"], items)
            except Exception:
                analyzed = []

            ai_map = {a["name"]: a for a in analyzed}
            staging_items = []
            for name in items:
                ai = ai_map.get(name, {})
                grade = ai.get("grade") or classify_product(name)
                staging_items.append({
                    "id": str(_uuid.uuid4()),
                    "name": name,
                    "grade": grade,
                    "storage": ai.get("storage", ""),
                    "ai_reason": ai.get("reason", ""),
                    "expiry_date": None,
                    "origin": None,
                    "no_expiry": bool(ai.get("no_expiry", False)),
                    "selected": grade != "exclude",
                })

            batch = add_staging_batch(
                source="invoice",
                image_path=task["image_path"],
                restaurant=corner,
                items=staging_items,
            )

            return {
                "count": len(staging_items),
                "batch_id": batch["id"],
                "corner": corner,
                "product_names": [i["name"] for i in staging_items],
            }

        # ── 번들 분석 (PIL 보정 + 3필드 추출) → 대기함으로 저장 ──
        if task["task_type"] == "product_bundle":
            from services.gemini_service import verify_and_analyze_bundle
            from services.data_service import add_staging_batch, delete_product
            from services.classification import classify_product
            import uuid as _uuid

            bundle_paths = task.get("bundle_image_paths") or [task["image_path"]]
            image_bytes_list = []
            for bp in bundle_paths:
                p = Path(bp)
                if not p.exists():
                    continue
                raw = p.read_bytes()
                # PIL 선명도 보정 (백그라운드에서만 실행)
                try:
                    from PIL import Image, ImageFilter, ImageEnhance
                    import io as _io
                    img = Image.open(_io.BytesIO(raw))
                    img = img.filter(ImageFilter.SHARPEN)
                    img = ImageEnhance.Sharpness(img).enhance(1.8)
                    buf = _io.BytesIO()
                    img.save(buf, format="JPEG", quality=92)
                    image_bytes_list.append(buf.getvalue())
                except Exception:
                    image_bytes_list.append(raw)

            if not image_bytes_list:
                return {"error": "번들 이미지 없음", "product_name": ""}

            result = verify_and_analyze_bundle(
                task["api_key"], task["model"], image_bytes_list
            )

            # 기존 플레이스홀더 제품 삭제 (staging으로 대체)
            try:
                delete_product(task["task_id"])
            except Exception:
                pass

            p_name = result.get("product_name", "") or "인식불가"
            grade = classify_product(p_name)

            staging_items = [{
                "id": str(_uuid.uuid4()),
                "name": p_name,
                "grade": grade if grade != "exclude" else "normal",
                "storage": "",
                "ai_reason": result.get("reason", ""),
                "expiry_date": result.get("expiry_date"),
                "origin": result.get("origin"),
                "selected": True,
            }]

            batch = add_staging_batch(
                source="bundle",
                image_path=bundle_paths[0] if bundle_paths else None,
                items=staging_items,
            )

            return {
                "status": result.get("status", "ok"),
                "batch_id": batch["id"],
                "product_name": p_name,
                "date": result.get("expiry_date"),
                "origin": result.get("origin"),
                "reason": result.get("reason", ""),
                "bundle_image_paths": bundle_paths,
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
