"""전날 발주표 미리 등록 페이지.

입고 전날 발주 목록을 미리 등록해두고,
입고 당일 식자재 입고 등록 화면에서 발주표를 불러와
터치 한 번으로 소비기한 촬영 모드로 진입한다.
"""

import streamlit as st
from datetime import date, timedelta
from services.data_service import (
    load_settings,
    load_preorders,
    add_preorders_bulk,
    delete_preorder,
    save_preorders,
)
from services.gemini_service import extract_invoice_items, analyze_products_comprehensive
from services.classification import classify_product

st.markdown("<p class='page-header'>📦 발주표 미리 등록</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="pre_back"):
    st.switch_page("app.py")

settings = load_settings()
st.markdown("---")

# ── 탭 구성 ──
tab_new, tab_list = st.tabs(["➕ 새 발주표 등록", "📋 등록된 발주표"])

# ══════════════════════════════════════════════════
# TAB 1: 새 발주표 등록
# ══════════════════════════════════════════════════
with tab_new:
    st.subheader("입고 예정일 설정")
    tomorrow = date.today() + timedelta(days=1)
    intake_date = st.date_input(
        "입고 예정일",
        value=tomorrow,
        min_value=date.today(),
        key="pre_intake_date",
    )

    st.markdown("---")
    st.subheader("품목 입력 방법 선택")

    input_method = st.radio(
        "입력 방법",
        ["✏️ 직접 입력", "📸 명세서/발주서 촬영"],
        horizontal=True,
        key="pre_input_method",
        label_visibility="collapsed",
    )

    if input_method == "✏️ 직접 입력":
        st.caption("품목명을 한 줄에 하나씩 입력하세요.")
        text_input = st.text_area(
            "품목 목록",
            placeholder="돼지고기 앞다리\n계란 30구\n두부\n고등어",
            height=180,
            key="pre_text_input",
        )

        if st.button("📊 AI 등급 분석 후 등록", use_container_width=True, type="primary", key="pre_analyze"):
            if not settings.get("api_key"):
                st.error("⚠️ API Key가 설정되지 않았습니다.")
            else:
                lines = [l.strip() for l in text_input.strip().split("\n") if l.strip()]
                if not lines:
                    st.warning("품목을 입력하세요.")
                else:
                    with st.spinner("AI가 등급을 분석 중..."):
                        try:
                            analyzed = analyze_products_comprehensive(
                                settings["api_key"], settings["model"], lines
                            )
                            # AI 결과가 없으면 키워드 분류로 폴백
                            if not analyzed:
                                analyzed = [
                                    {"name": n, "storage": "냉장", "grade": classify_product(n), "reason": "키워드 분류"}
                                    for n in lines
                                ]
                        except Exception as e:
                            st.warning(f"AI 분석 실패, 키워드 분류 사용: {e}")
                            analyzed = [
                                {"name": n, "storage": "냉장", "grade": classify_product(n), "reason": "키워드 분류"}
                                for n in lines
                            ]

                    st.session_state["pre_analyzed"] = analyzed
                    st.session_state["pre_intake_date_val"] = intake_date.isoformat()
                    st.rerun()

    else:  # 명세서 촬영
        if not settings.get("api_key"):
            st.error("⚠️ API Key가 설정되지 않았습니다. 설정 페이지에서 먼저 입력하세요.")
        else:
            photo = st.camera_input("발주서/명세서 촬영", key="pre_invoice_camera")
            if photo is not None:
                image_bytes = photo.getvalue()
                with st.spinner("AI가 품목을 추출 중..."):
                    try:
                        items = extract_invoice_items(
                            settings["api_key"], settings["model"], image_bytes
                        )
                        if items:
                            analyzed = analyze_products_comprehensive(
                                settings["api_key"], settings["model"], items
                            )
                            if not analyzed:
                                analyzed = [
                                    {"name": n, "storage": "냉장", "grade": classify_product(n), "reason": "키워드 분류"}
                                    for n in items
                                ]
                            st.session_state["pre_analyzed"] = analyzed
                            st.session_state["pre_intake_date_val"] = intake_date.isoformat()
                            st.rerun()
                        else:
                            st.warning("품목을 추출하지 못했습니다. 다시 촬영해 주세요.")
                    except Exception as e:
                        st.error(f"AI 오류: {e}")

    # ── 분석 결과 확인 및 저장 ──
    if "pre_analyzed" in st.session_state and st.session_state["pre_analyzed"]:
        analyzed = st.session_state["pre_analyzed"]
        intake_str = st.session_state.get("pre_intake_date_val", intake_date.isoformat())

        st.markdown("---")
        st.subheader(f"AI 분석 결과 — 입고 예정: {intake_str}")

        GRADE_COLORS = {"A": "#d32f2f", "B": "#f57c00", "C": "#388e3c", "exclude": "#555"}
        GRADE_LABELS = {"A": "A 집중관리", "B": "B 일반관리", "C": "C 저위험", "exclude": "관리제외"}
        STORAGE_ICONS = {"냉장": "🧊", "냉동": "❄️", "실온": "🌡️"}

        exclude_items = [it for it in analyzed if it.get("grade") == "exclude"]
        manage_items = [it for it in analyzed if it.get("grade") != "exclude"]

        if manage_items:
            for it in manage_items:
                grade = it.get("grade", "B")
                color = GRADE_COLORS.get(grade, "#555")
                label = GRADE_LABELS.get(grade, grade)
                storage = it.get("storage", "냉장")
                icon = STORAGE_ICONS.get(storage, "")
                reason = it.get("reason", "")

                st.markdown(
                    f'<div style="background:#1e1e2e; border-left:4px solid {color}; '
                    f'padding:10px 14px; border-radius:8px; margin-bottom:6px;">'
                    f'<span style="font-size:1.1rem; font-weight:700;">{it["name"]}</span> '
                    f'{icon} <span style="color:{color}; font-weight:600;">{label}</span>'
                    f'<br><span style="color:#888; font-size:0.85rem;">{reason}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if exclude_items:
            with st.expander(f"관리 제외 ({len(exclude_items)}건) — 채소류"):
                for it in exclude_items:
                    st.write(f"- {it['name']}")

        st.markdown("---")
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("💾 발주표 저장", use_container_width=True, type="primary", key="pre_save"):
                items_to_save = [
                    {
                        "name": it["name"],
                        "grade": it.get("grade", "B"),
                        "storage": it.get("storage", "냉장"),
                        "ai_reason": it.get("reason", ""),
                        "expected_intake_date": intake_str,
                    }
                    for it in manage_items
                ]
                add_preorders_bulk(items_to_save)
                st.success(f"✅ {len(items_to_save)}건이 발주표에 등록되었습니다!")
                del st.session_state["pre_analyzed"]
                st.rerun()
        with col_cancel:
            if st.button("✕ 취소", use_container_width=True, key="pre_cancel"):
                del st.session_state["pre_analyzed"]
                st.rerun()


# ══════════════════════════════════════════════════
# TAB 2: 등록된 발주표 목록
# ══════════════════════════════════════════════════
with tab_list:
    preorders = load_preorders()

    if not preorders:
        st.info("등록된 발주표가 없습니다.")
    else:
        # 상태 필터
        filter_status = st.radio(
            "상태 필터",
            ["전체", "대기 중", "완료"],
            horizontal=True,
            key="pre_filter",
        )

        filtered = preorders
        if filter_status == "대기 중":
            filtered = [p for p in preorders if p["status"] == "pending"]
        elif filter_status == "완료":
            filtered = [p for p in preorders if p["status"] == "completed"]

        # 날짜별 그룹핑
        dates = sorted({p["expected_intake_date"] for p in filtered}, reverse=True)

        GRADE_COLORS = {"A": "#d32f2f", "B": "#f57c00", "C": "#388e3c", "exclude": "#555", "normal": "#555"}

        for d in dates:
            day_items = [p for p in filtered if p["expected_intake_date"] == d]
            pending = sum(1 for p in day_items if p["status"] == "pending")
            st.markdown(f"#### 📅 {d} — 대기 {pending}건")

            for p in day_items:
                grade = p.get("grade", "B")
                color = GRADE_COLORS.get(grade, "#555")
                status_icon = "⏳" if p["status"] == "pending" else "✅"
                storage_icon = {"냉장": "🧊", "냉동": "❄️", "실온": "🌡️"}.get(p.get("storage", "냉장"), "")

                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f'<div style="background:#1e1e2e; border-left:3px solid {color}; '
                        f'padding:8px 12px; border-radius:6px; margin-bottom:4px;">'
                        f'{status_icon} <strong>{p["name"]}</strong> {storage_icon} '
                        f'<span style="color:{color}; font-size:0.85rem;">{grade}등급</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_del:
                    if st.button("🗑", key=f"del_pre_{p['id']}", help="삭제"):
                        delete_preorder(p["id"])
                        st.rerun()

        # 완료된 항목 일괄 삭제
        completed = [p for p in preorders if p["status"] == "completed"]
        if completed:
            st.markdown("---")
            if st.button(f"🗑 완료된 항목 {len(completed)}건 삭제", key="del_completed"):
                save_preorders([p for p in preorders if p["status"] != "completed"])
                st.rerun()
