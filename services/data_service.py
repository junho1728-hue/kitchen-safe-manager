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
) -> dict:
    """새 제품 딕셔너리 생성."""
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "grade": grade,
        "intake_date": intake_date or datetime.now().strftime("%Y-%m-%d"),
        "expiry_date": expiry_date,
        "status": status,
        "invoice_image": invoice_image,
        "label_image": label_image,
        "binder_location": binder_location,
        "registered_by": registered_by,
        "created_at": now,
        "updated_at": now,
    }


# ── Settings ──


def load_settings() -> dict:
    defaults = {"api_key": "", "model": "gemini-2.5-flash-lite"}
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
