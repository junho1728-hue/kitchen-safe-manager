"""설정 페이지: API Key, 모델 선택, 데이터 관리."""

import streamlit as st
from services.data_service import load_settings, save_settings, load_products, IMAGES_DIR

st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
st.markdown("<p class='page-header'><span class='material-symbols-outlined'>settings</span> 설정</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="settings_back"):
    st.switch_page(st.session_state["_home_pg"])

st.markdown("---")

# ── 현재 설정 로드 ──
settings = load_settings()

# ── API Key ──
st.subheader("Google API Key")
api_key = st.text_input(
    "API Key",
    value=settings.get("api_key", ""),
    type="password",
    placeholder="AIza...",
    help="Google AI Studio에서 발급받은 API Key를 입력하세요.",
)

# ── 모델 선택 ──
st.subheader("AI 모델 선택")
model_options = {
    "gemini-2.5-flash-lite": "⚡ Flash-Lite (빠름, 기본)",
    "gemini-2.5-pro": "🧠 Pro (정교함)",
}
current_model = settings.get("model", "gemini-2.5-flash-lite")
model = st.selectbox(
    "모델",
    options=list(model_options.keys()),
    format_func=lambda x: model_options[x],
    index=list(model_options.keys()).index(current_model) if current_model in model_options else 0,
)

st.caption("Flash-Lite: 빠른 응답, 일반적인 명세서/라벨 인식에 적합")
st.caption("Pro: 정교한 분석, 복잡하거나 흐릿한 이미지에 적합")

# ── 소비기한 업데이트 동작 설정 ──
st.subheader("🔄 소비기한 업데이트 시 기존 기록 처리")
st.caption("기존 레코드를 삭제하면 새 입고로 교체되고, 유지하면 날짜만 수정됩니다.")
update_action_options = {
    "ask": "매번 선택 (업데이트할 때마다 물어봄)",
    "delete": "항상 삭제 (기존 레코드 삭제 후 새 입고로 등록)",
    "keep": "항상 유지 (날짜만 수정)",
}
current_update_action = settings.get("update_action", "ask")
update_action = st.radio(
    "기본 동작",
    options=list(update_action_options.keys()),
    format_func=lambda x: update_action_options[x],
    index=list(update_action_options.keys()).index(current_update_action)
        if current_update_action in update_action_options else 0,
    key="update_action_radio",
    label_visibility="collapsed",
)

# ── 저장 버튼 ──
if st.button("💾 설정 저장", use_container_width=True, type="primary"):
    restaurants = settings.get("restaurants", [])
    save_settings({"api_key": api_key, "model": model, "restaurants": restaurants, "update_action": update_action})
    st.success("설정이 저장되었습니다!")
    st.rerun()

# ── 데이터 현황 ──
st.markdown("---")
st.subheader("📊 데이터 현황")
products = load_products()
total = len(products)
incomplete = sum(1 for p in products if p.get("status") == "incomplete")
a_grade = sum(1 for p in products if p.get("grade") == "A")

col1, col2, col3 = st.columns(3)
col1.metric("전체 품목", f"{total}건")
col2.metric("미완료", f"{incomplete}건")
col3.metric("A등급", f"{a_grade}건")

# ── 라벨 사진 수 ──
label_dir = IMAGES_DIR / "labels"
label_count = len(list(label_dir.glob("*"))) if label_dir.exists() else 0
st.info(f"📸 보관된 라벨 사진: {label_count}장")

# ── 데이터 내보내기 ──
st.markdown("---")
st.subheader("데이터 관리")

if products:
    import json
    st.download_button(
        "📥 품목 데이터 다운로드 (JSON)",
        data=json.dumps(products, ensure_ascii=False, indent=2),
        file_name="products_export.json",
        mime="application/json",
        use_container_width=True,
    )

# ── 음식점/코너 관리 ──
st.markdown("---")
st.subheader("🏪 음식점/코너 관리")
st.caption("소비기한 관리 탭에서 코너별로 식자재를 분류할 수 있습니다.")

restaurants = settings.get("restaurants", [])

col_input, col_btn = st.columns([3, 1])
with col_input:
    new_restaurant = st.text_input(
        "음식점/코너명",
        placeholder="예: 여의반상, 청진동순두부, 곡분...",
        label_visibility="collapsed",
        key="new_restaurant_input",
    )
with col_btn:
    if st.button("➕ 추가", use_container_width=True):
        name_stripped = new_restaurant.strip()
        if name_stripped and name_stripped not in restaurants:
            restaurants.append(name_stripped)
            settings["restaurants"] = restaurants
            save_settings(settings)
            st.success(f"'{name_stripped}' 추가 완료!")
            st.rerun()
        elif name_stripped in restaurants:
            st.warning("이미 등록된 이름입니다.")

if restaurants:
    for r in restaurants:
        col_r, col_del = st.columns([4, 1])
        with col_r:
            st.markdown(f"🏷️ **{r}**")
        with col_del:
            if st.button("삭제", key=f"del_rest_{r}"):
                restaurants.remove(r)
                settings["restaurants"] = restaurants
                save_settings(settings)
                st.rerun()
else:
    st.info("등록된 음식점/코너가 없습니다. 위에서 추가해주세요.")

# ── 데이터 초기화 ──
with st.expander("⚠️ 데이터 초기화 (위험)"):
    st.warning("모든 품목 데이터와 이력이 삭제됩니다. 이 작업은 되돌릴 수 없습니다.")
    if st.button("🗑️ 전체 데이터 초기화", type="secondary"):
        from services.data_service import save_products, _write_json, HISTORY_FILE
        save_products([])
        _write_json(HISTORY_FILE, [])
        st.success("데이터가 초기화되었습니다.")
        st.rerun()
