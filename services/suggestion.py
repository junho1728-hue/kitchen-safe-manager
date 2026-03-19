"""소비기한 자동 추론 서비스.

과거 등록 이력을 분석하여 입고일 대비 소비기한 일수를 제안.
"""

import re
from datetime import datetime
from statistics import median, mode


def _normalize(name: str) -> str:
    """품목명 정규화: 공백·수량·원산지 등 제거."""
    name = name.strip()
    # 수량 패턴 제거 (예: "30구", "1kg", "500g")
    name = re.sub(r"\d+\s*(구|kg|g|ml|l|개|팩|봉|마리|근)\b", "", name, flags=re.IGNORECASE)
    # 원산지/등급 제거
    for tag in ["국내산", "수입산", "수입", "냉동", "냉장", "신선", "특", "상", "중"]:
        name = name.replace(tag, "")
    return name.strip()


def suggest_expiry_days(product_name: str, history: list[dict]) -> int | None:
    """과거 데이터 기반으로 입고~소비기한 일수를 추론.

    Args:
        product_name: 현재 등록하려는 제품명.
        history: data_service.load_history() 결과.

    Returns:
        추천 일수 (int) 또는 데이터 부족 시 None.
    """
    target = _normalize(product_name)
    if not target:
        return None

    deltas: list[int] = []
    for entry in history:
        stored = _normalize(entry.get("product_name", ""))
        # 부분 문자열 매칭 (양방향)
        if not stored or (target not in stored and stored not in target):
            continue
        try:
            intake = datetime.fromisoformat(entry["intake_date"])
            expiry = datetime.fromisoformat(entry["expiry_date"])
            delta = (expiry - intake).days
            if delta > 0:
                deltas.append(delta)
        except (KeyError, ValueError):
            continue

    # 최소 2건 이상 있어야 제안
    if len(deltas) < 2:
        return None

    # 최빈값 우선, 동률이면 중앙값
    try:
        return mode(deltas)
    except Exception:
        return int(median(deltas))
