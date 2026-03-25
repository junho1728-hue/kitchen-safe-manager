"""Gemini API 연동 서비스.

명세서 OCR, 라벨 날짜 인식, 종합 등급 분석 등을 수행.
SDK: google-genai (새 통합 SDK)
"""

import json
import re

from google import genai
from google.genai import types

# ── 프롬프트 상수 ──

INVOICE_EXTRACTION_PROMPT = """이 이미지는 식자재 거래명세서(납품서/발주서)입니다.
문서에 행(row)으로 나열된 납품 품목명만 추출하세요.

절대 하지 말 것:
- 제품 포장지나 라벨의 원재료명(소금, 설탕, 유화제 등)을 품목으로 추출하지 마세요.
- 영양성분, 첨가물, 알레르기 정보를 품목으로 추출하지 마세요.
- 제조사명, 주소, 연락처를 품목으로 추출하지 마세요.
- 수량, 단가, 금액 등 숫자 정보는 제외하세요.

반드시 할 것:
- 명세서에 독립 행(줄)으로 나열된 납품 상품명만 추출하세요.
- 예: "돼지고기 삼겹살", "계란 30구", "두부 500g", "참치캔"
- 반드시 JSON 배열 형식으로만 반환하세요.

예시 출력:
["돼지고기 앞다리", "계란 30구", "두부", "고등어", "참치캔"]
"""

COMPREHENSIVE_GRADE_PROMPT = """아래 식자재 품목명 목록을 분석하여 각 제품의 위생 관리 등급을 결정하세요.

등급 기준:
- A등급 (집중관리): 냉장 보관 필수, 단기 소비기한. 고기류(돼지/소/닭/오리), 수산물(생선/새우/조개/오징어), 계란, 두부, 생유제품(우유/생크림), 신선 가공육
- B등급 (일반관리): 중간 위험. 가공식품, 소스류, 냉장 보관 조리식품, 냉장 반찬류
- C등급 (저위험): 냉동 제품(기한이 길어 위급도 낮음), 건조식품, 통조림, 장기 보관 식품
- exclude (관리제외): 채소류(양파/마늘/감자/당근/배추/무/대파 등 모든 채소)는 무조건 제외

중요: 냉동 제품은 고위험 재료라도 C등급으로 낮춤 (기한이 길어 즉각적 위험 낮음).

입력 품목명 목록:
{product_names}

반드시 아래 JSON 형식으로만 반환하세요:
[
  {{
    "name": "원본 품목명",
    "storage": "냉장|냉동|실온",
    "grade": "A|B|C|exclude",
    "reason": "한 줄 이유"
  }}
]"""

DATE_EXTRACTION_PROMPT = """이 식품 라벨/포장 이미지에서 소비기한 또는 유통기한 날짜를 찾아주세요.

규칙:
1. 날짜를 YYYY-MM-DD 형식으로만 반환하세요.
2. 여러 날짜가 있으면 소비기한(또는 유통기한)을 우선하세요.
3. 날짜를 찾을 수 없으면 정확히 "NOT_FOUND"만 반환하세요.
4. 다른 설명 없이 날짜 문자열만 반환하세요.
5. 단축 연도 형식도 처리하세요:
   - "27.07" → 2027-07-01 (연도.월 형식, 일은 01로 처리)
   - "27.07.15" → 2027-07-15
   - "27/07" → 2027-07-01
6. 날짜 뒤에 붙은 로트 코드(예: /+DF, -A, LOT 등)는 무시하세요.
"""

BUNDLE_ANALYSIS_PROMPT = """You are a food label analyst for a Korean restaurant kitchen.

Analyze the provided food product photo(s) and extract ONLY these 3 fields:

1. product_name:
   - Extract ONLY the brand name + product name (commercial name on the label).
   - DO NOT include any of the following in product_name:
     * Ingredients or additives (e.g., 정제소금, 탄산칼슘, 유화제, 맥아, 대두)
     * Allergen warnings
     * Nutritional information (단백질, 지방, 탄수화물)
     * Weight or volume (30g, 1L, 500ml)
     * Manufacturer or distributor info
   - CORRECT: "강냉이 초코"
   - WRONG: "강냉이 초코 (맥아(옥수수 100%) 36%, 준초콜릿 7.1%...)"

2. expiry_date:
   - Expiry date or best-before date in YYYY-MM-DD format.
   - Handle short formats: "27.07" = 2027-07-01, "27.07.15" = 2027-07-15.
   - Ignore lot codes or suffixes after the date (e.g., "/+DF", "-A", " LOT123").
   - Return "NOT_FOUND" if not visible.

3. origin:
   - Country/region of origin as printed (원산지). e.g., "국내산", "미국산", "호주산"
   - Return "NOT_FOUND" if not labeled.

4. status:
   - "ok" if all photos show the same product.
   - "mismatch" if photos clearly show different products.
   - On mismatch, still attempt to extract product_name from the first photo.

Return ONLY valid JSON, no extra text:
{
  "status": "ok",
  "product_name": "brand + product name only — no ingredients",
  "expiry_date": "YYYY-MM-DD or NOT_FOUND",
  "origin": "원산지 or NOT_FOUND",
  "reason": "one-line summary"
}
"""

PRODUCT_FRONT_PROMPT = """Extract the product name from this food packaging image.

Rules:
- Return ONLY the brand name + product name (e.g., "강냉이 초코", "풀무원 국산 콩 두부").
- The largest, boldest text on the front is the product name.
- DO NOT include ingredients, additives, allergens, nutritional facts, weight, or manufacturer info.
- Return as a JSON array with one string.

Examples:
["강냉이 초코"]
["청정원 순창 고추장"]
["풀무원 국산 콩 두부"]
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
    """Gemini 응답에서 날짜 추출. YYYY-MM-DD 형식으로 정규화."""
    text = text.strip()
    if "NOT_FOUND" in text.upper():
        return None

    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)

    # YYYY.MM.DD 또는 YYYY/MM/DD
    m = re.search(r"(\d{4})[./](\d{2})[./](\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # YY.MM.DD 또는 YY/MM/DD (일본식 단축 연도, 예: 27.07.01)
    m = re.search(r"\b(\d{2})[./](\d{2})[./](\d{2})\b", text)
    if m:
        year = int(m.group(1))
        return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}" if year >= 20 else f"19{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # YY.MM 또는 YY/MM (일/월 없는 단축형, 예: 27.07 → 2027-07-01)
    m = re.search(r"\b(\d{2})[./](\d{2})\b", text)
    if m:
        year = int(m.group(1))
        if 20 <= year <= 40:  # 2020~2040년 범위만 날짜로 인식
            return f"20{m.group(1)}-{m.group(2)}-01"

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


def extract_product_name_from_front(api_key: str, model: str, image_bytes: bytes) -> list[str]:
    """제품 전면 사진에서 제품명 추출 (원재료명·알레르기 정보 무시).

    Returns:
        제품명 리스트 (보통 1개). 실패 시 빈 리스트.
    """
    client = _create_client(api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            PRODUCT_FRONT_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ],
    )
    return _parse_json_array(response.text)


def verify_and_analyze_bundle(
    api_key: str, model: str, image_bytes_list: list
) -> dict:
    """묶음 사진 검증 + 제품명/소비기한/원산지 통합 분석 (3개 필드만 추출).

    Returns:
        {"status": str, "product_name": str,
         "expiry_date": str|None, "origin": str|None, "reason": str}
    """
    if not image_bytes_list:
        return {"status": "error", "product_name": "", "expiry_date": None,
                "origin": None, "reason": "이미지 없음"}

    client = _create_client(api_key)
    contents: list = [BUNDLE_ANALYSIS_PROMPT]
    for img_bytes in image_bytes_list:
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    response = client.models.generate_content(model=model, contents=contents)
    text = re.sub(r"```(?:json)?\s*", "", response.text).strip()

    try:
        result = json.loads(text)
        result["expiry_date"] = _parse_date(result.get("expiry_date", "NOT_FOUND"))
        raw_origin = result.get("origin", "NOT_FOUND")
        result["origin"] = None if raw_origin == "NOT_FOUND" else raw_origin
        return result
    except json.JSONDecodeError:
        if "MISMATCH" in text.upper():
            return {"status": "mismatch", "product_name": "", "expiry_date": None,
                    "origin": None, "reason": "제품 불일치"}
        return {"status": "ok", "product_name": "", "expiry_date": None,
                "origin": None, "reason": "파싱 실패"}


def analyze_products_comprehensive(
    api_key: str, model: str, product_names: list[str]
) -> list[dict]:
    """품목명 목록을 AI로 종합 분석하여 A/B/C 등급 반환.

    Returns:
        [{"name": str, "storage": str, "grade": str, "reason": str}, ...]
        실패 시 빈 리스트.
    """
    if not product_names:
        return []

    names_text = "\n".join(f"- {name}" for name in product_names)
    prompt = COMPREHENSIVE_GRADE_PROMPT.format(product_names=names_text)

    client = _create_client(api_key)
    response = client.models.generate_content(model=model, contents=[prompt])

    text = re.sub(r"```(?:json)?\s*", "", response.text).strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    return []
