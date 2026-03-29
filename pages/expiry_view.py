"""소비기한 관리 페이지: 등록 제품을 소비기한 임박순으로 표시."""

import streamlit as st
from datetime import datetime, date
from services.data_service import (
    load_products, save_product, delete_product,
    load_settings, IMAGES_DIR, BASE_DIR,
)

# ──────────────────────────────────────────
# 음식점 원산지 표시 의무 품목
# 근거: 농수산물의 원산지 표시에 관한 법률
# (2025년 현행 기준, 시행 중)
# ──────────────────────────────────────────
ORIGIN_REQUIRED_ITEMS = [
    # 축산물
    (["소고기", "쇠고기", "한우", "육우", "갈비", "스테이크", "등심", "안심", "채끝"],
     "🥩 소고기 — 원산지 표시 의무 (국내산/수입산 + 등급 표시)"),
    (["돼지고기", "삼겹살", "목살", "항정살", "돈육", "돈까스"],
     "🐷 돼지고기 — 원산지 표시 의무"),
    (["닭고기", "닭발", "닭갈비", "치킨", "닭볶음"],
     "🐔 닭고기 — 원산지 표시 의무"),
    (["오리고기", "오리"],
     "🦆 오리고기 — 원산지 표시 의무"),
    (["양고기", "양갈비", "램"],
     "🐑 양고기 — 원산지 표시 의무"),
    (["염소"],
     "🐐 염소고기 — 원산지 표시 의무"),
    # 농산물
    (["배추김치", "김치"],
     "🥬 배추·고춧가루(김치용) — 원산지 표시 의무"),
    (["두부", "순두부", "콩국수", "두유"],
     "🫘 콩(두부·두유류) — 원산지 표시 의무"),
    (["고춧가루"],
     "🌶 고춧가루(김치용) — 원산지 표시 의무"),
    # 수산물
    (["넙치", "광어"],
     "🐟 광어(넙치) — 원산지 표시 의무"),
    (["우럭", "조피볼락"],
     "🐟 우럭(조피볼락) — 원산지 표시 의무"),
    (["참돔"],
     "🐟 참돔 — 원산지 표시 의무"),
    (["미꾸라지"],
     "🐟 미꾸라지 — 원산지 표시 의무"),
    (["뱀장어", "장어"],
     "🐟 장어(뱀장어) — 원산지 표시 의무"),
    (["낙지"],
     "🐙 낙지 — 원산지 표시 의무"),
    (["명태", "동태", "황태", "코다리", "노가리"],
     "🐟 명태(동태·황태·코다리 포함) — 원산지 표시 의무"),
    (["고등어"],
     "🐟 고등어 — 원산지 표시 의무"),
    (["갈치"],
     "🐟 갈치 — 원산지 표시 의무"),
    (["오징어"],
     "🦑 오징어 — 원산지 표시 의무"),
    (["꽃게"],
     "🦀 꽃게 — 원산지 표시 의무"),
    (["참조기", "조기"],
     "🐟 참조기(조기) — 원산지 표시 의무"),
    (["다랑어", "참치"],
     "🐟 다랑어(참치) — 원산지 표시 의무"),
    (["아귀"],
     "🐟 아귀 — 원산지 표시 의무"),
    (["쭈꾸미"],
     "🐙 쭈꾸미 — 원산지 표시 의무"),
]


def check_origin_required(product_name: str) -> list[str]:
    """제품명에서 원산지 표시 의무 품목 확인. 해당 항목 목록 반환."""
    # 가공 조미료·양념류 제외 (파우더, 소스, 믹스 등은 원산지 표시 대상 아님)
    EXCLUDE_SUFFIXES = [
        "파우더", "소스", "시즈닝", "믹스", "분말", "엑기스",
        "농축액", "맛", "향", "스톡", "다시", "육수", "조미료",
        "드레싱", "오일", "식초", "젓갈", "진액", "즙", "절임",
    ]
    if any(ex in product_name for ex in EXCLUDE_SUFFIXES):
        return []

    matched = []
    for keywords, label in ORIGIN_REQUIRED_ITEMS:
        if any(kw in product_name for kw in keywords):
            matched.append(label)
    return matched


# ── CSS ──
st.markdown(
    """
<style>
/* 소비기한 관리 — 스타일은 전역 CSS에서 관리 */
.section-label {
    text-transform: uppercase; letter-spacing: 0.15em;
    font-weight: 700; font-size: 0.8rem; color: #94a3b8;
}
</style>
""",
    unsafe_allow_html=True,
)

# 제목 잘림 방지 여백
st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
st.markdown("<p class='page-header'><span class='material-symbols-outlined'>hourglass_bottom</span> 소비기한 관리</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="expiry_back"):
    st.switch_page(st.session_state["_home_pg"])

# ── 설정 로드 ──
settings = load_settings()
restaurants = settings.get("restaurants", [])

if "selected_restaurant" not in st.session_state:
    st.session_state.selected_restaurant = "전체"

# ── 검색 + 필터 ──
col_search, col_filter = st.columns([2, 1])
with col_search:
    search = st.text_input("🔎 품목 검색", placeholder="품목명 입력...", label_visibility="collapsed")
with col_filter:
    filter_opt = st.selectbox(
        "필터", ["전체", "A등급만", "기한 임박 (7일 이내)", "미완료"],
        label_visibility="collapsed",
    )

# ── 데이터 로드 ──
products = load_products()
today = date.today()


def days_remaining(p: dict) -> int:
    if p.get("no_expiry"):
        return 99999  # 소비기한 없음 → 맨 뒤로
    exp = p.get("expiry_date")
    if not exp:
        return 9999
    try:
        return (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
    except ValueError:
        return 9999


# ── 통계 (전체 합산, no_expiry 제외) ──
total = len(products)
no_expiry_count = sum(1 for p in products if p.get("no_expiry"))
urgent = sum(1 for p in products if not p.get("no_expiry") and 0 < days_remaining(p) <= 3)
warning = sum(1 for p in products if not p.get("no_expiry") and 3 < days_remaining(p) <= 7)
expired = sum(1 for p in products if not p.get("no_expiry") and days_remaining(p) < 0)

st.markdown(f"""<div class="summary-grid">
<div class="summary-card summary-all">
<div class="summary-top"><span class="material-symbols-outlined summary-icon">inventory_2</span><span class="summary-number">{total:02d}</span></div>
<p class="summary-label">전체</p>
</div>
<div class="summary-card summary-urgent">
<div class="summary-top"><span class="material-symbols-outlined summary-icon" style="font-variation-settings:'FILL' 1;">emergency_home</span><span class="summary-number">{urgent:02d}</span></div>
<p class="summary-label">긴급 (3일 이내)</p>
</div>
<div class="summary-card summary-warning">
<div class="summary-top"><span class="material-symbols-outlined summary-icon">warning</span><span class="summary-number">{warning:02d}</span></div>
<p class="summary-label">주의 (7일 이내)</p>
</div>
<div class="summary-card summary-expired">
<div class="summary-top"><span class="material-symbols-outlined summary-icon" style="font-variation-settings:'FILL' 1;">timer_off</span><span class="summary-number">{expired:02d}</span></div>
<p class="summary-label">기한 경과</p>
</div>
</div>""", unsafe_allow_html=True)

# ── 음식점 필터 버튼 ──
if restaurants:
    st.markdown("---")
    btn_labels = ["전체"] + restaurants
    cols = st.columns(len(btn_labels))
    for i, label in enumerate(btn_labels):
        with cols[i]:
            btn_type = "primary" if st.session_state.selected_restaurant == label else "secondary"
            if st.button(label, key=f"rest_filter_{label}", use_container_width=True, type=btn_type):
                st.session_state.selected_restaurant = label
                st.rerun()

st.markdown("---")

# ── 필터 적용 ──
filtered = list(products)

if st.session_state.selected_restaurant != "전체":
    filtered = [p for p in filtered if p.get("restaurant", "") == st.session_state.selected_restaurant]

if search:
    filtered = [p for p in filtered if search in p.get("name", "")]

if st.session_state.selected_restaurant == "전체":
    if filter_opt == "A등급만":
        filtered = [p for p in filtered if p.get("grade") == "A"]
    elif filter_opt == "기한 임박 (7일 이내)":
        filtered = [p for p in filtered if 0 < days_remaining(p) <= 7]
    elif filter_opt == "미완료":
        filtered = [p for p in filtered if p.get("status") == "incomplete"]

filtered.sort(key=lambda p: days_remaining(p))

# ── 제품 카드 ──
if not filtered:
    st.info("표시할 품목이 없습니다.")
else:
    for p in filtered:
        remaining = days_remaining(p)
        name = p.get("name", "알 수 없음")
        grade = p.get("grade", "normal")
        expiry = p.get("expiry_date", "미등록")

        # ── 카드 스타일 변수 ──
        grade_map = {
            "A": ("grade-chip-a", "A 집중"),
            "B": ("grade-chip-b", "B 일반"),
            "C": ("grade-chip-c", "C 저위험"),
        }
        grade_chip, grade_label = grade_map.get(grade, ("grade-chip-normal", "일반"))
        thumb_icon = {"A": "local_fire_department", "B": "kitchen", "C": "ac_unit"}.get(grade, "category")

        rest_tag = p.get("restaurant", "")
        rest_display = f" · {rest_tag}" if rest_tag else ""

        # 원산지 표시 의무 확인
        origin_reqs = check_origin_required(name)
        origin_badge = '<span style="display:inline-block;background:#1565c0;color:#fff;padding:2px 7px;border-radius:0.5rem;font-size:0.7rem;font-weight:600;margin-left:0.5rem;">원산지 의무</span>' if origin_reqs else ''

        if p.get("no_expiry"):
            card_variant = ""
            thumb_class = "product-thumb-noexpiry"
            d_day_class = "d-day-noexpiry"
            d_day_text = "&#8734;"
            status_class = "product-status-normal"
            status_icon = "all_inclusive"
            status_label = "소비기한 없음"
            expiry = "해당 없음"
        elif remaining < 0:
            card_variant = "product-card-expired"
            thumb_class = "product-thumb-expired"
            d_day_class = "d-day-expired"
            d_day_text = f"D+{abs(remaining)}"
            status_class = "product-status-expired"
            status_icon = "error"
            status_label = "소비기한 만료"
        elif remaining <= 3:
            card_variant = "product-card-urgent"
            thumb_class = "product-thumb-urgent"
            d_day_class = "d-day-urgent"
            d_day_text = f"D-{remaining}"
            status_class = "product-status-urgent"
            status_icon = "error"
            status_label = f"{remaining}일 남음"
        elif remaining <= 7:
            card_variant = "product-card-warning"
            thumb_class = "product-thumb-warning"
            d_day_class = "d-day-warning"
            d_day_text = f"D-{remaining}"
            status_class = "product-status-warning"
            status_icon = "schedule"
            status_label = f"{remaining}일 남음"
        elif remaining == 9999:
            card_variant = ""
            thumb_class = "product-thumb-normal"
            d_day_class = "d-day-normal"
            d_day_text = "---"
            status_class = "product-status-normal"
            status_icon = "event_busy"
            status_label = "소비기한 미등록"
        else:
            card_variant = ""
            thumb_class = "product-thumb-normal"
            d_day_class = "d-day-normal"
            d_day_text = f"D-{remaining}"
            status_class = "product-status-normal"
            status_icon = "schedule"
            status_label = f"{expiry} 까지"

        card_html = (
            f'<div class="product-card {card_variant}">'
            f'<div class="product-thumb {thumb_class}">'
            f'<span class="material-symbols-outlined" style="font-size:2rem;">{thumb_icon}</span>'
            f'</div>'
            f'<div class="product-info">'
            f'<div class="product-header">'
            f'<div><span class="product-name">{name}</span>'
            f'<span class="grade-chip {grade_chip}">{grade_label}</span>'
            f'{origin_badge}</div>'
            f'<span class="d-day {d_day_class}">{d_day_text}</span>'
            f'</div>'
            f'<div class="product-status {status_class}">'
            f'<span class="material-symbols-outlined" style="font-size:1.1rem;">{status_icon}</span> '
            f'{status_label}</div>'
            f'<div class="product-meta">입고: {p.get("intake_date", "-")}{rest_display}</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        with st.expander("✏️ 수정 · 상세보기", expanded=False):

            # ── 원산지 표시 의무 안내 ──
            if origin_reqs:
                with st.container():
                    st.warning(
                        "**📋 음식점 원산지 표시 의무 품목입니다** (농수산물 원산지 표시법)\n\n"
                        + "\n".join(f"- {r}" for r in origin_reqs)
                        + "\n\n메뉴판·원산지 표시판에 반드시 원산지를 표기하세요.",
                        icon="⚖️",
                    )

            # ── 품목명 수정 ──
            new_name = st.text_input("품목명 수정", value=name, key=f"name_{p['id']}")

            # ── 소비기한 없음 토글 ──
            new_no_expiry = st.checkbox(
                "소비기한 없음 (설탕, 쌀, 소금 등)",
                value=p.get("no_expiry", False),
                key=f"noexp_{p['id']}",
            )

            # ── 소비기한 수정 ──
            new_exp = None
            if not new_no_expiry:
                try:
                    cur_exp = (
                        datetime.strptime(expiry, "%Y-%m-%d").date()
                        if expiry and expiry not in ("미등록", "해당 없음")
                        else date.today()
                    )
                except ValueError:
                    cur_exp = date.today()
                new_exp = st.date_input("소비기한 수정", value=cur_exp, key=f"exp_{p['id']}")

            # ── 음식점/코너 지정 ──
            if restaurants:
                rest_options = ["(미분류)"] + restaurants
                cur_rest = p.get("restaurant", "")
                rest_idx = rest_options.index(cur_rest) if cur_rest in rest_options else 0
                new_rest = st.selectbox(
                    "🏪 음식점/코너", rest_options, index=rest_idx, key=f"rest_{p['id']}"
                )
            else:
                new_rest = "(미분류)"

            # ── 저장 버튼 ──
            if st.button("저장", key=f"save_{p['id']}", type="primary", use_container_width=True):
                changed = False
                if new_name != name:
                    p["name"] = new_name
                    changed = True
                # no_expiry 변경
                if new_no_expiry != p.get("no_expiry", False):
                    p["no_expiry"] = new_no_expiry
                    if new_no_expiry:
                        p["expiry_date"] = None
                        p["status"] = "complete"
                    changed = True
                # 소비기한 변경 (no_expiry가 아닐 때만)
                if not new_no_expiry and new_exp:
                    if new_exp.isoformat() != (expiry if expiry not in ("미등록", "해당 없음") else ""):
                        p["expiry_date"] = new_exp.isoformat()
                        p["status"] = "complete"
                        changed = True
                actual_rest = "" if new_rest == "(미분류)" else new_rest
                if actual_rest != p.get("restaurant", ""):
                    p["restaurant"] = actual_rest
                    changed = True
                if changed:
                    p["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    save_product(p)
                    st.toast(f"✅ '{p['name']}' 저장 완료!", icon="💾")
                    st.rerun()

            # ── 삭제 버튼 ──
            if st.button("삭제", key=f"del_{p['id']}", type="secondary", use_container_width=True):
                deleted_name = p.get("name", "항목")
                delete_product(p["id"])
                st.toast(f"🗑️ '{deleted_name}' 삭제 완료!", icon="🗑️")
                st.rerun()

            st.markdown("---")

            # ── 라벨 사진 (썸네일 + 크게 보기) ──
            label_img = p.get("label_image")
            if label_img:
                img_path = BASE_DIR / label_img
                if img_path.exists():
                    enlarged_key = f"img_enlarged_{p['id']}"
                    if enlarged_key not in st.session_state:
                        st.session_state[enlarged_key] = False

                    if st.session_state[enlarged_key]:
                        # 크게 보기 모드
                        st.image(str(img_path), caption="라벨 사진 (크게 보기)", width="stretch")
                        if st.button("🔼 접기", key=f"shrink_{p['id']}", use_container_width=True):
                            st.session_state[enlarged_key] = False
                            st.rerun()
                    else:
                        # 썸네일 모드
                        st.image(str(img_path), caption="라벨 사진", width=160)
                        if st.button("🔍 크게 보기", key=f"enlarge_{p['id']}", use_container_width=True):
                            st.session_state[enlarged_key] = True
                            st.rerun()
                else:
                    st.caption("라벨 사진 파일 없음")
            else:
                st.caption("라벨 사진 미등록")

            # ── 등록일 + 원산지 ──
            st.caption(f"등록일: {p.get('created_at', '-')[:10]}")
            origin = p.get("origin", "")
            if origin and origin != "NOT_FOUND":
                st.caption(f"원산지: {origin}")
