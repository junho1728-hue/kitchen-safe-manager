"""소비기한 관리 페이지: 등록 제품을 소비기한 임박순으로 표시."""

import streamlit as st
from datetime import datetime, date
from services.data_service import load_products, save_product, IMAGES_DIR, BASE_DIR

# ── 긴급 알림 CSS ──
st.markdown(
    """
<style>
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.65; }
}
.card-red {
    background: linear-gradient(135deg, #b71c1c, #d32f2f) !important;
    border-radius: 12px; padding: 12px; margin: 4px 0;
    animation: pulse 1.5s infinite;
}
.card-yellow {
    background: linear-gradient(135deg, #e65100, #f57c00) !important;
    border-radius: 12px; padding: 12px; margin: 4px 0;
}
.card-normal {
    background: #16213e !important;
    border-radius: 12px; padding: 12px; margin: 4px 0;
}
.card-expired {
    background: linear-gradient(135deg, #4a0000, #7f0000) !important;
    border-radius: 12px; padding: 12px; margin: 4px 0;
    animation: pulse 0.8s infinite;
}
.grade-badge-a {
    background: #d32f2f; color: #fff; padding: 2px 8px; border-radius: 8px;
    font-size: 0.85rem; font-weight: 700;
}
.grade-badge-b {
    background: #f57c00; color: #fff; padding: 2px 8px; border-radius: 8px;
    font-size: 0.85rem; font-weight: 700;
}
.grade-badge-c {
    background: #388e3c; color: #fff; padding: 2px 8px; border-radius: 8px;
    font-size: 0.85rem;
}
.grade-badge-normal {
    background: #555; color: #ccc; padding: 2px 8px; border-radius: 8px;
    font-size: 0.85rem;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown("<p class='page-header'>🔍 소비기한 관리</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="expiry_back"):
    st.switch_page(st.session_state["_home_pg"])

# ── 필터 ──
col_search, col_filter = st.columns([2, 1])
with col_search:
    search = st.text_input("🔎 품목 검색", placeholder="품목명 입력...", label_visibility="collapsed")
with col_filter:
    filter_opt = st.selectbox(
        "필터", ["전체", "A등급만", "기한 임박 (7일 이내)", "미완료"],
        label_visibility="collapsed",
    )

# ── 데이터 로드 & 정렬 ──
products = load_products()
today = date.today()
today_str = today.isoformat()


def days_remaining(p: dict) -> int:
    """소비기한까지 남은 일수. 미등록이면 9999."""
    exp = p.get("expiry_date")
    if not exp:
        return 9999
    try:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
        return (exp_date - today).days
    except ValueError:
        return 9999


# 필터 적용
filtered = products
if search:
    filtered = [p for p in filtered if search in p.get("name", "")]
if filter_opt == "A등급만":
    filtered = [p for p in filtered if p.get("grade") == "A"]
elif filter_opt == "기한 임박 (7일 이내)":
    filtered = [p for p in filtered if 0 < days_remaining(p) <= 7]
elif filter_opt == "미완료":
    filtered = [p for p in filtered if p.get("status") == "incomplete"]

# 소비기한 임박순 정렬
filtered.sort(key=lambda p: days_remaining(p))

# ── 통계 ──
total = len(products)
urgent = sum(1 for p in products if 0 < days_remaining(p) <= 3)
warning = sum(1 for p in products if 3 < days_remaining(p) <= 7)
expired = sum(1 for p in products if days_remaining(p) < 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("전체", f"{total}")
c2.metric("🔴 긴급 (3일↓)", f"{urgent}")
c3.metric("🟡 주의 (7일↓)", f"{warning}")
c4.metric("⛔ 기한 경과", f"{expired}")

st.markdown("---")

# ── 제품 카드 렌더링 ──
if not filtered:
    st.info("표시할 품목이 없습니다.")
else:
    for p in filtered:
        remaining = days_remaining(p)
        name = p.get("name", "알 수 없음")
        grade = p.get("grade", "normal")
        expiry = p.get("expiry_date", "미등록")
        status = p.get("status", "incomplete")
        binder = p.get("binder_location", "")

        # 카드 스타일 결정
        if remaining < 0:
            card_class = "card-expired"
            status_text = f"⛔ {abs(remaining)}일 경과"
        elif remaining <= 3:
            card_class = "card-red"
            status_text = f"🔴 {remaining}일 남음"
        elif remaining <= 7:
            card_class = "card-yellow"
            status_text = f"🟡 {remaining}일 남음"
        elif remaining == 9999:
            card_class = "card-normal"
            status_text = "📋 소비기한 미등록"
        else:
            card_class = "card-normal"
            status_text = f"✅ {remaining}일 남음"

        grade_map = {
            "A": ("grade-badge-a", "A 집중관리"),
            "B": ("grade-badge-b", "B 일반관리"),
            "C": ("grade-badge-c", "C 저위험"),
        }
        grade_badge, grade_label = grade_map.get(grade, ("grade-badge-normal", "일반"))

        st.markdown(
            f"""
<div class="{card_class}">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <span style="font-size:1.3rem; font-weight:700;">{name}</span>
            <span class="{grade_badge}" style="margin-left:8px;">{grade_label}</span>
        </div>
        <div style="text-align:right;">
            <div style="font-size:1.1rem; font-weight:600;">{status_text}</div>
            <div style="font-size:0.85rem; color:#bbb;">소비기한: {expiry}</div>
        </div>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:0.85rem; color:#999;">
        <span>입고: {p.get('intake_date', '-')}</span>
        <span>{'📁 ' + binder if binder else ''}</span>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # 라벨 사진 보기 + 삭제 (expander)
        with st.expander(f"📋 {name} 상세", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                label_img = p.get("label_image")
                if label_img:
                    img_path = BASE_DIR / label_img
                    if img_path.exists():
                        st.image(str(img_path), caption="라벨 사진", width=300)
                    else:
                        st.caption("라벨 사진 파일 없음")
                else:
                    st.caption("라벨 사진 미등록")
            with col_b:
                st.write(f"**등록 방법:** {p.get('registered_by', '-')}")
                st.write(f"**등록일:** {p.get('created_at', '-')[:10]}")
                if binder:
                    st.write(f"**바인더 위치:** {binder}")

                # 바인더 위치 수정
                new_binder = st.text_input(
                    "바인더 위치 수정",
                    value=binder or "",
                    key=f"binder_{p['id']}",
                    placeholder="예: A-01",
                )
                if new_binder != (binder or ""):
                    p["binder_location"] = new_binder
                    p["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    save_product(p)
                    st.success("바인더 위치가 업데이트되었습니다.")
                    st.rerun()
