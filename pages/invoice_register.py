"""식자재 입고 등록 페이지: 4단계 상태머신 워크플로.

Step 1 (capture): 명세서 촬영 → Gemini OCR → 품목 리스트 추출
Step 2 (review_list): 추출 리스트 확인, A등급 자동 분류, 편집
Step 3 (date_entry): 선택 품목별 날짜 등록 (촬영/직접입력/건너뛰기)
Step 4 (complete): 라벨 보관 위치 입력 → 저장 완료
"""

import streamlit as st
from datetime import datetime, date, timedelta
from services.data_service import (
    load_settings, new_product, save_products_bulk, save_image,
    record_history, load_history,
)
from services.classification import classify_product
from services.gemini_service import extract_invoice_items, extract_date_from_label
from services.suggestion import suggest_expiry_days

# ── 세션 상태 초기화 ──
if "reg_step" not in st.session_state:
    st.session_state.reg_step = "capture"
if "reg_items" not in st.session_state:
    st.session_state.reg_items = []
if "reg_selected" not in st.session_state:
    st.session_state.reg_selected = []
if "reg_item_idx" not in st.session_state:
    st.session_state.reg_item_idx = 0
if "reg_invoice_path" not in st.session_state:
    st.session_state.reg_invoice_path = None
if "reg_date_mode" not in st.session_state:
    st.session_state.reg_date_mode = None


def reset_workflow():
    """워크플로 상태 초기화."""
    st.session_state.reg_step = "capture"
    st.session_state.reg_items = []
    st.session_state.reg_selected = []
    st.session_state.reg_item_idx = 0
    st.session_state.reg_invoice_path = None
    st.session_state.reg_date_mode = None


st.markdown("<p class='page-header'>📋 식자재 입고 등록</p>", unsafe_allow_html=True)

# 홈/초기화 버튼
col_back, col_reset = st.columns([1, 1])
with col_back:
    if st.button("← 홈으로", key="reg_back"):
        reset_workflow()
        st.switch_page("app.py")
with col_reset:
    if st.session_state.reg_step != "capture":
        if st.button("🔄 처음부터", key="reg_reset"):
            reset_workflow()
            st.rerun()

# 진행 표시
steps = ["① 촬영", "② 확인", "③ 날짜등록", "④ 완료"]
step_idx = ["capture", "review_list", "date_entry", "complete"].index(st.session_state.reg_step)
st.progress((step_idx + 1) / len(steps), text=steps[step_idx])

settings = load_settings()
st.markdown("---")

# ══════════════════════════════════════════════════
# STEP 1: 명세서 촬영
# ══════════════════════════════════════════════════
if st.session_state.reg_step == "capture":
    st.subheader("📸 거래명세서를 촬영하세요")
    st.caption("명세서/송장을 카메라로 찍으면 AI가 품목을 자동 추출합니다.")

    if not settings.get("api_key"):
        st.error("⚠️ API Key가 설정되지 않았습니다. 설정 페이지에서 먼저 입력하세요.")
        if st.button("설정으로 이동"):
            st.switch_page("pages/settings.py")
    else:
        photo = st.camera_input("명세서 촬영", key="invoice_camera")

        if photo is not None:
            image_bytes = photo.getvalue()

            # 이미지 저장
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            invoice_path = save_image(image_bytes, "invoices", f"{ts}.jpg")
            st.session_state.reg_invoice_path = invoice_path

            # Gemini OCR
            with st.spinner("AI가 품목을 추출 중입니다..."):
                try:
                    items = extract_invoice_items(
                        settings["api_key"], settings["model"], image_bytes
                    )
                    if items:
                        # 자동 분류 적용
                        classified = []
                        for name in items:
                            grade = classify_product(name)
                            classified.append({"name": name, "grade": grade})
                        st.session_state.reg_items = classified
                        st.session_state.reg_step = "review_list"
                        st.rerun()
                    else:
                        st.warning("품목을 추출하지 못했습니다. 다시 촬영해 주세요.")
                except Exception as e:
                    st.error(f"AI 오류: {e}")


# ══════════════════════════════════════════════════
# STEP 2: 추출 리스트 확인
# ══════════════════════════════════════════════════
elif st.session_state.reg_step == "review_list":
    st.subheader("📝 추출된 품목 확인")
    st.caption("품목명을 수정하고, 날짜 등록할 항목을 선택하세요. A등급은 자동 선택됩니다.")

    items = st.session_state.reg_items
    updated_items = []

    for i, item in enumerate(items):
        col_check, col_name, col_grade = st.columns([0.5, 3, 1])
        with col_check:
            default_checked = item["grade"] == "A"
            checked = st.checkbox(
                "선택", value=default_checked, key=f"check_{i}", label_visibility="collapsed"
            )
        with col_name:
            edited_name = st.text_input(
                "품목명", value=item["name"], key=f"name_{i}", label_visibility="collapsed"
            )
        with col_grade:
            # 이름이 변경되면 재분류
            new_grade = classify_product(edited_name)
            badge_color = "#d32f2f" if new_grade == "A" else "#555"
            badge_text = "A등급" if new_grade == "A" else "일반"
            st.markdown(
                f'<span style="background:{badge_color}; color:#fff; padding:4px 10px; '
                f'border-radius:8px; font-size:0.85rem;">{badge_text}</span>',
                unsafe_allow_html=True,
            )

        updated_items.append({
            "name": edited_name,
            "grade": new_grade,
            "selected": checked,
        })

    st.markdown("---")

    col_count, col_next = st.columns([2, 1])
    with col_count:
        selected_count = sum(1 for it in updated_items if it["selected"])
        st.write(f"**{selected_count}개** 항목이 선택됨 (날짜 등록 대상)")
    with col_next:
        if st.button("다음 →", use_container_width=True, type="primary"):
            # 선택된 항목과 비선택 항목 모두 저장
            st.session_state.reg_items = updated_items
            st.session_state.reg_selected = [
                it for it in updated_items if it["selected"]
            ]
            st.session_state.reg_item_idx = 0
            st.session_state.reg_date_mode = None

            if selected_count > 0:
                st.session_state.reg_step = "date_entry"
            else:
                st.session_state.reg_step = "complete"
            st.rerun()


# ══════════════════════════════════════════════════
# STEP 3: 날짜 등록
# ══════════════════════════════════════════════════
elif st.session_state.reg_step == "date_entry":
    selected = st.session_state.reg_selected
    idx = st.session_state.reg_item_idx

    if idx >= len(selected):
        st.session_state.reg_step = "complete"
        st.rerun()

    item = selected[idx]
    st.subheader(f"📅 날짜 등록 ({idx + 1}/{len(selected)})")

    grade_badge = "🔴 A등급" if item["grade"] == "A" else "일반"
    st.markdown(
        f"### {item['name']} {grade_badge}",
    )

    # ── 자동 추론 제안 ──
    history = load_history()
    suggested_days = suggest_expiry_days(item["name"], history)
    suggested_date = None
    if suggested_days:
        suggested_date = (date.today() + timedelta(days=suggested_days)).isoformat()
        st.info(f"💡 이 제품은 보통 입고 후 **{suggested_days}일**입니다. 맞습니까?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ 맞습니다", use_container_width=True, key=f"suggest_yes_{idx}"):
                item["expiry_date"] = suggested_date
                item["status"] = "complete"
                item["registered_by"] = "suggested"
                st.session_state.reg_item_idx = idx + 1
                st.session_state.reg_date_mode = None
                st.rerun()
        with col_no:
            if st.button("✏️ 직접 입력할게요", use_container_width=True, key=f"suggest_no_{idx}"):
                st.session_state.reg_date_mode = "choose"
                st.rerun()
        # 제안을 수락/거절하지 않은 상태면 아래 옵션 숨김
        if st.session_state.reg_date_mode is None:
            st.stop()

    # ── 날짜 입력 방법 선택 ──
    if st.session_state.reg_date_mode is None:
        st.session_state.reg_date_mode = "choose"

    if st.session_state.reg_date_mode == "choose":
        st.write("날짜 등록 방법을 선택하세요:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                '<div class="big-button">', unsafe_allow_html=True
            )
            if st.button("📷 촬영", use_container_width=True, key=f"mode_cam_{idx}"):
                st.session_state.reg_date_mode = "camera"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(
                '<div class="big-button">', unsafe_allow_html=True
            )
            if st.button("✏️ 직접 입력", use_container_width=True, key=f"mode_manual_{idx}"):
                st.session_state.reg_date_mode = "manual"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col3:
            st.markdown(
                '<div class="big-button">', unsafe_allow_html=True
            )
            if st.button("⏭️ 건너뛰기", use_container_width=True, key=f"mode_skip_{idx}"):
                item["status"] = "incomplete"
                st.session_state.reg_item_idx = idx + 1
                st.session_state.reg_date_mode = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ── 카메라 모드 ──
    elif st.session_state.reg_date_mode == "camera":
        st.write("라벨의 소비기한을 촬영하세요:")
        label_photo = st.camera_input("라벨 촬영", key=f"label_cam_{idx}")

        if label_photo is not None:
            label_bytes = label_photo.getvalue()

            # 라벨 사진 저장
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            label_path = save_image(label_bytes, "labels", f"{item['name']}_{ts}.jpg")
            item["label_image"] = label_path

            with st.spinner("AI가 날짜를 인식 중..."):
                try:
                    detected_date = extract_date_from_label(
                        settings["api_key"], settings["model"], label_bytes
                    )
                    if detected_date:
                        st.success(f"인식된 날짜: **{detected_date}**")
                        item["expiry_date"] = detected_date
                        item["status"] = "complete"
                        item["registered_by"] = "auto"
                    else:
                        st.warning("날짜를 인식하지 못했습니다. 직접 입력해 주세요.")
                        st.session_state.reg_date_mode = "manual"
                        st.rerun()
                except Exception as e:
                    st.error(f"AI 오류: {e}")
                    st.session_state.reg_date_mode = "manual"
                    st.rerun()

            if item.get("expiry_date"):
                if st.button("✅ 확인, 다음으로", use_container_width=True, type="primary", key=f"confirm_cam_{idx}"):
                    st.session_state.reg_item_idx = idx + 1
                    st.session_state.reg_date_mode = None
                    st.rerun()

        if st.button("← 뒤로", key=f"cam_back_{idx}"):
            st.session_state.reg_date_mode = "choose"
            st.rerun()

    # ── 직접 입력 모드 ──
    elif st.session_state.reg_date_mode == "manual":
        st.write("소비기한을 직접 입력하세요:")
        default_date = date.today() + timedelta(days=suggested_days or 7)
        expiry_input = st.date_input(
            "소비기한",
            value=default_date,
            min_value=date.today(),
            key=f"date_input_{idx}",
        )

        if st.button("✅ 저장", use_container_width=True, type="primary", key=f"save_manual_{idx}"):
            item["expiry_date"] = expiry_input.isoformat()
            item["status"] = "complete"
            item["registered_by"] = "manual"
            st.session_state.reg_item_idx = idx + 1
            st.session_state.reg_date_mode = None
            st.rerun()

        if st.button("← 뒤로", key=f"manual_back_{idx}"):
            st.session_state.reg_date_mode = "choose"
            st.rerun()


# ══════════════════════════════════════════════════
# STEP 4: 완료 & 바인더 위치
# ══════════════════════════════════════════════════
elif st.session_state.reg_step == "complete":
    st.subheader("✅ 입고 등록 완료")

    all_items = st.session_state.reg_items
    selected = st.session_state.reg_selected
    today_str = date.today().isoformat()

    # ── 바인더 위치 입력 ──
    st.write("라벨 실물 보관 위치를 기록하세요 (선택사항):")
    binder_loc = st.text_input(
        "바인더 위치", placeholder="예: A-01, 냉장고 위 선반", key="binder_input"
    )

    # ── 결과 요약 ──
    st.markdown("---")
    st.write("**등록 결과 요약:**")

    complete_count = 0
    incomplete_count = 0
    products_to_save = []

    for it in all_items:
        # 선택 항목에서 날짜 정보 가져오기
        matched = next(
            (s for s in selected if s["name"] == it["name"]), None
        )
        expiry = None
        status = "incomplete"
        registered_by = "manual"
        label_image = None

        if matched and matched.get("expiry_date"):
            expiry = matched["expiry_date"]
            status = "complete"
            registered_by = matched.get("registered_by", "manual")
            label_image = matched.get("label_image")
            complete_count += 1
        elif matched and matched.get("status") == "incomplete":
            incomplete_count += 1
        else:
            # 미선택 항목도 등록 (날짜 없이)
            incomplete_count += 1

        p = new_product(
            name=it["name"],
            grade=it["grade"],
            intake_date=today_str,
            expiry_date=expiry,
            status=status,
            invoice_image=st.session_state.reg_invoice_path,
            label_image=label_image,
            binder_location=binder_loc if binder_loc else None,
            registered_by=registered_by,
        )
        products_to_save.append(p)

        # 결과 표시
        icon = "✅" if status == "complete" else "⏳"
        exp_text = expiry if expiry else "미등록"
        grade_text = "🔴A" if it["grade"] == "A" else ""
        st.write(f"{icon} **{it['name']}** {grade_text} — 소비기한: {exp_text}")

    st.markdown("---")
    st.write(f"✅ 완료: {complete_count}건 | ⏳ 미완료: {incomplete_count}건")

    # ── 저장 버튼 ──
    if st.button("💾 모두 저장하고 종료", use_container_width=True, type="primary"):
        save_products_bulk(products_to_save)

        # 이력 기록 (완료된 항목만)
        for p in products_to_save:
            if p["status"] == "complete" and p.get("expiry_date"):
                record_history(p["name"], p["intake_date"], p["expiry_date"])

        st.success(f"✅ {len(products_to_save)}건이 등록되었습니다!")
        reset_workflow()
        st.balloons()

        if st.button("홈으로 돌아가기", use_container_width=True):
            st.switch_page("app.py")
