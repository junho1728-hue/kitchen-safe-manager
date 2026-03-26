"""대기함 페이지: AI 분석 완료된 식자재를 사진별로 확인/수정 후 최종 등록."""

import streamlit as st
from datetime import date, datetime
from pathlib import Path
from services.data_service import (
    load_staging, update_staging_batch, remove_staging_batch,
    register_staging_batch, load_settings, save_settings,
    BASE_DIR, save_image,
)

# ── CSS ──
st.markdown(
    """
<style>
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.65; }
}
.batch-card {
    background: #1e293b;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 1rem;
    padding: 1rem;
    margin-bottom: 1rem;
}
.batch-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 0.75rem;
}
.batch-time {
    color: #64748b; font-size: 0.85rem;
}
.item-row {
    background: rgba(255,255,255,0.03);
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    margin: 0.25rem 0;
    display: flex; align-items: center; gap: 0.5rem;
}
.grade-a { color: #ef4444; font-weight: 700; }
.grade-b { color: #f59e0b; font-weight: 700; }
.grade-c { color: #22c55e; font-weight: 700; }
.corner-new {
    background: #1e3a5f; border: 1px dashed #3b82f6;
    border-radius: 0.75rem; padding: 0.75rem;
    margin-bottom: 0.75rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── 헤더 ──
st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
st.markdown("<p class='page-header'>📦 대기함</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="staging_back"):
    st.switch_page(st.session_state["_home_pg"])

# ── 데이터 로드 ──
batches = load_staging()
settings = load_settings()
restaurants = settings.get("restaurants", [])

if not batches:
    st.info("대기 중인 항목이 없습니다.\n\n식자재 입고 등록에서 명세서를 촬영하면 AI 분석 후 여기에 표시됩니다.")
    st.stop()

st.markdown(f"**{len(batches)}건**의 배치가 대기 중입니다.")
st.markdown("---")

# ── 배치별 표시 ──
for batch_idx, batch in enumerate(batches):
    batch_id = batch["id"]
    source_label = {"invoice": "📋 명세서", "bundle": "📷 제품 촬영", "manual": "✏️ 수동"}.get(
        batch.get("source", ""), "📋"
    )
    created = batch.get("created_at", "")[:16].replace("T", " ")

    st.markdown(
        f"<div class='batch-card'>"
        f"<div class='batch-header'>"
        f"<span style='font-size:1.1rem;font-weight:700;'>{source_label} 배치 #{batch_idx + 1}</span>"
        f"<span class='batch-time'>{created}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── 사진 썸네일 ──
    img_path = batch.get("image_path")
    if img_path:
        full_path = BASE_DIR / img_path
        if full_path.exists():
            st.image(str(full_path), caption="원본 사진", width=200)

    # ── 코너/음식점 지정 ──
    detected_corner = batch.get("restaurant", "")
    corner_options = ["(미분류)"] + restaurants

    # AI가 감지한 코너가 기존 목록에 없는 경우
    if detected_corner and detected_corner not in restaurants:
        st.markdown(
            f"<div class='corner-new'>"
            f"🔍 AI가 감지한 코너: <strong>{detected_corner}</strong>"
            f"<br><span style='color:#94a3b8;font-size:0.85rem;'>"
            f"기존 목록에 없는 코너입니다.</span></div>",
            unsafe_allow_html=True,
        )
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button(
                f"✅ '{detected_corner}' 새로 추가",
                key=f"add_corner_{batch_id}",
                use_container_width=True,
                type="primary",
            ):
                restaurants.append(detected_corner)
                settings["restaurants"] = restaurants
                save_settings(settings)
                st.success(f"'{detected_corner}' 코너가 추가되었습니다!")
                st.rerun()
        with col_no:
            if st.button(
                "❌ 무시",
                key=f"ignore_corner_{batch_id}",
                use_container_width=True,
            ):
                update_staging_batch(batch_id, {"restaurant": ""})
                st.rerun()
        corner_options = ["(미분류)"] + restaurants

    # 코너 선택 드롭다운
    if detected_corner and detected_corner in restaurants:
        default_idx = corner_options.index(detected_corner)
    else:
        default_idx = 0

    selected_corner = st.selectbox(
        "🏪 코너/음식점 지정",
        corner_options,
        index=default_idx,
        key=f"corner_{batch_id}",
    )

    st.markdown("---")

    # ── 품목 리스트 ──
    items = batch.get("items", [])
    if not items:
        st.warning("품목이 없습니다.")
        if st.button("🗑️ 배치 삭제", key=f"del_batch_{batch_id}", use_container_width=True):
            remove_staging_batch(batch_id)
            st.rerun()
        continue

    st.markdown("**품목 목록**")

    updated_items = []
    for item_idx, item in enumerate(items):
        grade = item.get("grade", "normal")
        grade_class = {"A": "grade-a", "B": "grade-b", "C": "grade-c"}.get(grade, "")
        grade_label = {"A": "A 집중", "B": "B 일반", "C": "C 저위험", "exclude": "제외"}.get(grade, "일반")

        with st.container():
            col_check, col_name = st.columns([1, 5])
            with col_check:
                selected = st.checkbox(
                    "선택",
                    value=item.get("selected", True),
                    key=f"sel_{batch_id}_{item_idx}",
                    label_visibility="collapsed",
                )
            with col_name:
                new_name = st.text_input(
                    "품목명",
                    value=item.get("name", ""),
                    key=f"name_{batch_id}_{item_idx}",
                    label_visibility="collapsed",
                )

            # 등급 + 소비기한 표시
            col_grade, col_expiry = st.columns([1, 2])
            with col_grade:
                st.markdown(
                    f"<span class='{grade_class}'>{grade_label}</span>"
                    f" <span style='color:#64748b;font-size:0.8rem;'>"
                    f"{item.get('storage', '')}</span>",
                    unsafe_allow_html=True,
                )
            with col_expiry:
                # 소비기한 입력 방식: 직접 입력 / 사진 촬영
                expiry_tab1, expiry_tab2 = st.tabs(["📅 직접 입력", "📷 사진 촬영"])

                with expiry_tab1:
                    cur_exp = None
                    if item.get("expiry_date"):
                        try:
                            cur_exp = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
                        except ValueError:
                            pass
                    new_exp = st.date_input(
                        "소비기한",
                        value=cur_exp or date.today(),
                        key=f"exp_{batch_id}_{item_idx}",
                        label_visibility="collapsed",
                    )
                    expiry_str = new_exp.isoformat() if new_exp else item.get("expiry_date")

                with expiry_tab2:
                    uploaded = st.file_uploader(
                        "라벨 사진",
                        type=["jpg", "jpeg", "png", "heic"],
                        key=f"label_upload_{batch_id}_{item_idx}",
                        label_visibility="collapsed",
                    )
                    if uploaded:
                        api_key = settings.get("api_key", "")
                        model = settings.get("model", "gemini-2.5-flash-lite")
                        if api_key:
                            with st.spinner("AI 소비기한 추출 중..."):
                                try:
                                    from services.gemini_service import extract_date_from_label
                                    img_bytes = uploaded.read()
                                    detected = extract_date_from_label(api_key, model, img_bytes)
                                    if detected:
                                        expiry_str = detected
                                        st.success(f"소비기한 감지: {detected}")
                                        # 이미지 저장
                                        fname = f"label_{batch_id[:8]}_{item_idx}.jpg"
                                        save_image(img_bytes, "labels", fname)
                                    else:
                                        st.warning("소비기한을 찾을 수 없습니다.")
                                except Exception as e:
                                    st.error(f"AI 분석 실패: {e}")
                        else:
                            st.warning("설정에서 API 키를 등록해주세요.")

            updated_items.append({
                **item,
                "name": new_name,
                "selected": selected,
                "expiry_date": expiry_str if "expiry_str" in dir() else item.get("expiry_date"),
            })
            # expiry_str 초기화
            if "expiry_str" in dir():
                del expiry_str

    st.markdown("---")

    # ── 액션 버튼 ──
    col_register, col_delete = st.columns(2)
    with col_register:
        selected_count = sum(1 for it in updated_items if it.get("selected", True))
        if st.button(
            f"✅ {selected_count}건 등록",
            key=f"register_{batch_id}",
            use_container_width=True,
            type="primary",
            disabled=selected_count == 0,
        ):
            # 대기함 업데이트 후 등록
            actual_corner = "" if selected_corner == "(미분류)" else selected_corner
            update_staging_batch(batch_id, {"items": updated_items, "restaurant": actual_corner})
            products = register_staging_batch(batch_id, restaurant=actual_corner)
            st.success(f"✅ {len(products)}건이 소비기한 관리에 등록되었습니다!")
            st.rerun()

    with col_delete:
        if st.button(
            "🗑️ 전체 삭제",
            key=f"del_{batch_id}",
            use_container_width=True,
        ):
            remove_staging_batch(batch_id)
            st.toast("배치가 삭제되었습니다.")
            st.rerun()

    st.markdown("<hr style='border-color:rgba(255,255,255,0.05);'>", unsafe_allow_html=True)
