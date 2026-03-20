"""소비기한 업데이트 페이지: 기존 제품의 소비기한을 빠르게 갱신."""

import streamlit as st
from datetime import datetime, date, timedelta
from services.data_service import (
    load_products, save_product, load_settings, save_image,
    record_history, load_history,
)
from services.gemini_service import extract_date_from_label
from services.suggestion import suggest_expiry_days

st.markdown("<p class='page-header'>📷 소비기한 업데이트</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="update_back"):
    st.switch_page(st.session_state["_home_pg"])

settings = load_settings()
products = load_products()

if not products:
    st.info("등록된 품목이 없습니다. 먼저 식자재를 입고 등록하세요.")
    if st.button("📋 입고 등록하러 가기", use_container_width=True):
        st.switch_page("pages/invoice_register.py")
    st.stop()

# ── 탭: 개별 업데이트 / 일괄 업데이트 ──
tab_single, tab_bulk = st.tabs(["📌 개별 업데이트", "📋 미완료 일괄 업데이트"])

# ═══════════════════════════════════════════
# TAB 1: 개별 업데이트
# ═══════════════════════════════════════════
with tab_single:
    # 제품 선택
    product_names = [f"{p['name']} ({'소비기한: ' + p['expiry_date'] if p.get('expiry_date') else '미등록'})" for p in products]
    selected_idx = st.selectbox(
        "품목 선택", range(len(products)),
        format_func=lambda i: product_names[i],
        key="update_select",
    )

    if selected_idx is not None:
        product = products[selected_idx]
        st.markdown(f"**현재 소비기한:** {product.get('expiry_date', '미등록')}")

        # 자동 추론 제안
        history = load_history()
        suggested_days = suggest_expiry_days(product["name"], history)
        if suggested_days:
            suggested_date = (date.today() + timedelta(days=suggested_days)).isoformat()
            st.info(f"💡 이 제품은 보통 입고 후 **{suggested_days}일**입니다.")
            if st.button("제안 날짜 적용", key="apply_suggest"):
                product["expiry_date"] = suggested_date
                product["status"] = "complete"
                product["registered_by"] = "suggested"
                product["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_product(product)
                record_history(product["name"], product["intake_date"], suggested_date)
                st.success(f"✅ {product['name']}의 소비기한이 {suggested_date}로 업데이트되었습니다.")
                st.rerun()

        st.markdown("---")
        method = st.radio(
            "업데이트 방법", ["📷 라벨 촬영", "✏️ 직접 입력"],
            horizontal=True, key="update_method",
        )

        if method == "📷 라벨 촬영":
            if not settings.get("api_key"):
                st.error("⚠️ API Key가 필요합니다. 설정에서 입력하세요.")
            else:
                photo = st.camera_input("라벨 촬영", key="update_camera")
                if photo is not None:
                    img_bytes = photo.getvalue()

                    # 이미지 저장
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    label_path = save_image(img_bytes, "labels", f"{product['name']}_{ts}.jpg")

                    with st.spinner("AI가 날짜를 인식 중..."):
                        try:
                            detected = extract_date_from_label(
                                settings["api_key"], settings["model"], img_bytes
                            )
                            if detected:
                                st.success(f"인식된 날짜: **{detected}**")
                                if st.button("✅ 이 날짜로 업데이트", type="primary", key="confirm_ocr"):
                                    product["expiry_date"] = detected
                                    product["status"] = "complete"
                                    product["registered_by"] = "auto"
                                    product["label_image"] = label_path
                                    product["updated_at"] = datetime.now().isoformat(timespec="seconds")
                                    save_product(product)
                                    record_history(product["name"], product["intake_date"], detected)
                                    st.success("업데이트 완료!")
                                    st.rerun()
                            else:
                                st.warning("날짜를 인식하지 못했습니다. 직접 입력해 주세요.")
                        except Exception as e:
                            st.error(f"AI 오류: {e}")

        else:  # 직접 입력
            current = None
            if product.get("expiry_date"):
                try:
                    current = datetime.strptime(product["expiry_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            new_date = st.date_input(
                "새 소비기한",
                value=current or (date.today() + timedelta(days=7)),
                key="update_date_input",
            )

            if st.button("✅ 업데이트", use_container_width=True, type="primary", key="save_manual_update"):
                product["expiry_date"] = new_date.isoformat()
                product["status"] = "complete"
                product["registered_by"] = "manual"
                product["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_product(product)
                record_history(product["name"], product["intake_date"], new_date.isoformat())
                st.success(f"✅ {product['name']}의 소비기한이 {new_date}로 업데이트되었습니다.")
                st.rerun()

# ═══════════════════════════════════════════
# TAB 2: 미완료 일괄 업데이트
# ═══════════════════════════════════════════
with tab_bulk:
    incomplete = [p for p in products if p.get("status") == "incomplete"]

    if not incomplete:
        st.success("🎉 미완료 항목이 없습니다! 모든 제품의 소비기한이 등록되어 있습니다.")
    else:
        st.write(f"**미완료 항목: {len(incomplete)}건**")
        st.caption("각 항목의 소비기한을 빠르게 입력하세요.")

        for i, p in enumerate(incomplete):
            with st.container(border=True):
                grade_text = "🔴 A등급" if p.get("grade") == "A" else ""
                st.markdown(f"**{p['name']}** {grade_text}")
                st.caption(f"입고일: {p.get('intake_date', '-')}")

                # 자동 추론
                suggested_days = suggest_expiry_days(p["name"], history)
                default_date = date.today() + timedelta(days=suggested_days or 7)
                if suggested_days:
                    st.caption(f"💡 추천: 입고 후 {suggested_days}일")

                col_date, col_save = st.columns([3, 1])
                with col_date:
                    new_exp = st.date_input(
                        "소비기한",
                        value=default_date,
                        key=f"bulk_date_{p['id']}",
                        label_visibility="collapsed",
                    )
                with col_save:
                    if st.button("저장", key=f"bulk_save_{p['id']}", use_container_width=True):
                        p["expiry_date"] = new_exp.isoformat()
                        p["status"] = "complete"
                        p["registered_by"] = "manual"
                        p["updated_at"] = datetime.now().isoformat(timespec="seconds")
                        save_product(p)
                        record_history(p["name"], p["intake_date"], new_exp.isoformat())
                        st.success(f"✅ {p['name']} 저장 완료")
                        st.rerun()
