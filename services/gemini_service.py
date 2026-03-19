"""Gemini API 연동 서비스.

명세서 OCR, 라벨 날짜 인식 등을 수행.
SDK: google-genai (새 통합 SDK)
"""

import json
import re

from google import genai
from google.genai import types

# ── 프롬프트 상수 ──

INVOICE_EXTRACTION_PROMPT = """이 거래명세서/송장 이미지에서 모든 식자재 품목명을 추출하세요.

규칙:
1. 품목명만 추출하세요 (수량, 단가, 금액 등은 제외).
2. 한 품목당 하나의 문자열로 정리하세요.
3. 반드시 JSON 배열 형식으로만 반환하세요.

예시 출력:
["돼지고기 앞다리", "계란 30구", "두부", "양파"]
"""

DATE_EXTRACTION_PROMPT = """이 식품 라벨/포장 이미지에서 소비기한 또는 유통기한 날짜를 찾아주세요.

규칙:
1. 날짜를 YYYY-MM-DD 형식으로만 반환하세요.
2. 여러 날짜가 있으면 소비기한(또는 유통기한)을 우선하세요.
3. 날짜를 찾을 수 없으면 정확히 "NOT_FOUND"만 반환하세요.
4. 다른 설명 없이 날짜 문자열만 반환하세요.
"""


def _create_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def _parse_json_array(text: str) -> list[str]:
    """Gemini 응답에서 JSON 배열 추출. 마크다운 코드펜스 처리."""
    # 코드펜스 제거
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.strip()

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [str(item).strip() for item in result if str(item).strip()]
    except json.JSONDecodeError:
        pass

    # 폴백: 줄 단위 파싱
    lines = []
    for line in text.split("\n"):
        line = line.strip().strip("-•·").strip('"').strip("'").strip(",").strip()
        if line and not line.startswith("[") and not line.startswith("]"):
            lines.append(line)
    return lines


def _parse_date(text: str) -> str | None:
    """Gemini 응답에서 날짜 추출. YYYY-MM-DD 형식."""
    text = text.strip()
    if "NOT_FOUND" in text.upper():
        return None
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return match.group(0)
    # YYYY.MM.DD 또는 YYYY/MM/DD 패턴도 처리
    match = re.search(r"(\d{4})[./](\d{2})[./](\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def extract_invoice_items(api_key: str, model: str, image_bytes: bytes) -> list[str]:
    """명세서 이미지에서 품목 리스트 추출.

    Returns:
        품목명 리스트. 실패 시 빈 리스트.

    Raises:
        Exception: API 호출 실패 시.
    """
    client = _create_client(api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            INVOICE_EXTRACTION_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ],
    )
    return _parse_json_array(response.text)


def extract_date_from_label(api_key: str, model: str, image_bytes: bytes) -> str | None:
    """라벨 이미지에서 소비기한/유통기한 날짜 추출.

    Returns:
        "YYYY-MM-DD" 문자열 또는 None.
    """
    client = _create_client(api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            DATE_EXTRACTION_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ],
    )
    return _parse_date(response.text)
