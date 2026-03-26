"""JSON 파일 기반 데이터 CRUD 서비스."""

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = BASE_DIR / "images"

PRODUCTS_FILE = DATA_DIR / "products.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"
PREORDERS_FILE = DATA_DIR / "preorders.json"
STAGING_FILE = DATA_DIR / "staging.json"


def _ensure_dirs():
    """필요한 디렉토리 생성."""
    DATA_DIR.mkdir(exist_ok=True)
    (IMAGES_DIR / "invoices").mkdir(parents=True, exist_ok=True)
    (IMAGES_DIR / "labels").mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> list | dict:
    if not path.exists():
        return [] if path != SETTINGS_FILE else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data):
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Products ──


def load_products() -> list[dict]:
    return _read_json(PRODUCTS_FILE)


def save_products(products: list[dict]):
    _write_json(PRODUCTS_FILE, products)


def save_product(product: dict):
    """단일 제품 추가 또는 업데이트 (id 기준)."""
    products = load_products()
    for i, p in enumerate(products):
        if p["id"] == product["id"]:
            products[i] = product
            save_products(products)
            return
    products.append(product)
    save_products(products)


def save_products_bulk(new_products: list[dict]):
    """여러 제품을 한꺼번에 추가."""
    products = load_products()
    existing_ids = {p["id"] for p in products}
    for p in new_products:
        if p["id"] in existing_ids:
            for i, ep in enumerate(products):
                if ep["id"] == p["id"]:
                    products[i] = p
                    break
        else:
            products.append(p)
    save_products(products)


def delete_product(product_id: str):
    products = load_products()
    products = [p for p in products if p["id"] != product_id]
    save_products(products)


def new_product(
    name: str,
    grade: str = "normal",
    intake_date: str | None = None,
    expiry_date: str | None = None,
    status: str = "incomplete",
    invoice_image: str | None = None,
    label_image: str | None = None,
    binder_location: str | None = None,
    registered_by: str = "manual",
    task_id: str | None = None,
    origin: str | None = None,
    restaurant: str = "",
    no_expiry: bool = False,
) -> dict:
    """새 제품 딕셔너리 생성."""
    now = datetime.now().isoformat(timespec="seconds")
    if no_expiry:
        status = "complete"
        expiry_date = None
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "grade": grade,
        "intake_date": intake_date or datetime.now().strftime("%Y-%m-%d"),
        "expiry_date": expiry_date,
        "status": status,
        "no_expiry": no_expiry,
        "origin": origin,
        "restaurant": restaurant,
        "invoice_image": invoice_image,
        "label_image": label_image,
        "binder_location": binder_location,
        "registered_by": registered_by,
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
    }


def update_product_by_task_id(
    task_id: str,
    name: str | None = None,
    expiry_date: str | None = None,
    origin: str | None = None,
) -> str | None:
    """task_id로 제품을 찾아 이름·소비기한 자동 업데이트.

    Returns:
        업데이트된 제품의 name (이력 기록용). 없으면 None.
    """
    products = load_products()
    for p in products:
        if p.get("task_id") == task_id:
            if name and not name.startswith("분석중_"):
                p["name"] = name
            if expiry_date:
                p["expiry_date"] = expiry_date
                p["status"] = "complete"
            if origin:
                p["origin"] = origin
            p["updated_at"] = datetime.now().isoformat(timespec="seconds")
            save_products(products)
            return p["name"]
    return None


# ── Settings ──


def load_settings() -> dict:
    defaults = {
        "api_key": "",
        "model": "gemini-2.5-flash-lite",
        "restaurants": [],
        "update_action": "ask",  # "ask" | "delete" | "keep"
    }
    stored = _read_json(SETTINGS_FILE)
    if isinstance(stored, dict):
        defaults.update(stored)
    return defaults


def save_settings(settings: dict):
    settings["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(SETTINGS_FILE, settings)


# ── History (자동 추론용) ──


def load_history() -> list[dict]:
    return _read_json(HISTORY_FILE)


def record_history(product_name: str, intake_date: str, expiry_date: str):
    """완료된 등록 이력 추가."""
    history = load_history()
    history.append(
        {
            "product_name": product_name,
            "intake_date": intake_date,
            "expiry_date": expiry_date,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _write_json(HISTORY_FILE, history)


# ── Images ──


def save_image(image_bytes: bytes, category: str, filename: str) -> str:
    """이미지를 images/{category}/{filename}에 저장하고 상대 경로 반환."""
    _ensure_dirs()
    dest = IMAGES_DIR / category / filename
    with open(dest, "wb") as f:
        f.write(image_bytes)
    return str(dest.relative_to(BASE_DIR))


# ── Preorders (전날 발주표) ──


def load_preorders() -> list[dict]:
    return _read_json(PREORDERS_FILE)


def save_preorders(preorders: list[dict]):
    _write_json(PREORDERS_FILE, preorders)


def add_preorder(
    name: str,
    grade: str = "normal",
    expected_intake_date: str | None = None,
    storage: str = "냉장",
    ai_reason: str = "",
) -> dict:
    """발주 항목 추가."""
    now = datetime.now().isoformat(timespec="seconds")
    preorder = {
        "id": str(uuid.uuid4()),
        "name": name,
        "grade": grade,
        "storage": storage,
        "ai_reason": ai_reason,
        "expected_intake_date": expected_intake_date or (
            datetime.now().strftime("%Y-%m-%d")
        ),
        "status": "pending",
        "created_at": now,
    }
    preorders = load_preorders()
    preorders.append(preorder)
    save_preorders(preorders)
    return preorder


def add_preorders_bulk(items: list[dict]) -> list[dict]:
    """발주 항목 대량 추가."""
    now = datetime.now().isoformat(timespec="seconds")
    new_preorders = []
    for item in items:
        preorder = {
            "id": str(uuid.uuid4()),
            "name": item.get("name", ""),
            "grade": item.get("grade", "normal"),
            "storage": item.get("storage", "냉장"),
            "ai_reason": item.get("ai_reason", ""),
            "expected_intake_date": item.get("expected_intake_date", ""),
            "restaurant": item.get("restaurant", ""),
            "status": "pending",
            "created_at": now,
        }
        new_preorders.append(preorder)
    preorders = load_preorders()
    preorders.extend(new_preorders)
    save_preorders(preorders)
    return new_preorders


def complete_preorder(preorder_id: str):
    """발주 항목을 완료 처리."""
    preorders = load_preorders()
    for p in preorders:
        if p["id"] == preorder_id:
            p["status"] = "completed"
            break
    save_preorders(preorders)


def delete_preorder(preorder_id: str):
    preorders = load_preorders()
    save_preorders([p for p in preorders if p["id"] != preorder_id])


# ── Staging (대기함) ──


def load_staging() -> list[dict]:
    """대기함 배치 목록 로드."""
    return _read_json(STAGING_FILE)


def save_staging(batches: list[dict]):
    _write_json(STAGING_FILE, batches)


def add_staging_batch(
    source: str,
    image_path: str | None = None,
    restaurant: str = "",
    items: list[dict] | None = None,
) -> dict:
    """대기함에 새 배치 추가. source: 'invoice' | 'bundle' | 'manual'"""
    now = datetime.now().isoformat(timespec="seconds")
    batch = {
        "id": str(uuid.uuid4()),
        "created_at": now,
        "source": source,
        "image_path": image_path,
        "restaurant": restaurant,
        "items": items or [],
        "status": "ready",
    }
    batches = load_staging()
    batches.append(batch)
    save_staging(batches)
    return batch


def get_staging_batch(batch_id: str) -> dict | None:
    for b in load_staging():
        if b["id"] == batch_id:
            return b
    return None


def update_staging_batch(batch_id: str, updates: dict):
    batches = load_staging()
    for b in batches:
        if b["id"] == batch_id:
            b.update(updates)
            break
    save_staging(batches)


def remove_staging_batch(batch_id: str):
    batches = load_staging()
    save_staging([b for b in batches if b["id"] != batch_id])


def register_staging_batch(batch_id: str, restaurant: str = "") -> list[dict]:
    """대기함 배치를 정식 등록 (products.json으로 이동).

    Returns: 등록된 product 리스트.
    """
    batch = get_staging_batch(batch_id)
    if not batch:
        return []

    products = []
    for item in batch.get("items", []):
        if not item.get("selected", True):
            continue
        is_no_expiry = bool(item.get("no_expiry", False))
        p = new_product(
            name=item.get("name", "미확인"),
            grade=item.get("grade", "normal"),
            expiry_date=item.get("expiry_date"),
            status="complete" if item.get("expiry_date") or is_no_expiry else "incomplete",
            origin=item.get("origin"),
            restaurant=restaurant or batch.get("restaurant", ""),
            invoice_image=batch.get("image_path"),
            registered_by=f"staging_{batch.get('source', 'unknown')}",
            no_expiry=is_no_expiry,
        )
        products.append(p)

    if products:
        save_products_bulk(products)
    remove_staging_batch(batch_id)
    return products
