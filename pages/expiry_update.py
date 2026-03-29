"""소비기한 업데이트 페이지: 기존 제품의 소비기한을 빠르게 갱신."""

import streamlit as st
from datetime import datetime, date, timedelta
from services.data_service import (
    load_products, save_product, load_settings, save_image,
    record_history, new_product, save_products_bulk, delete_product,
)
from services.gemini_service import extract_date_from_label


# ═══════════════════════════════════════════
# 헬퍼 함수 (탭 섹션보다 먼저 정의)
# ═══════════════════════════════════════════

def _do_update(product: dict, new_date: str, label_path: str | None, action: str):
    """실제 저장 처리 (삭제 or 유지)."""
    if action == "delete":
        delete_product(product["id"])
        new_p = new_product(
            name=product["name"],
            grade=product.get("grade", "normal"),
            intake_date=date.today().isoformat(),
            expiry_date=new_date,
            status="complete",
            label_image=label_path,
            registered_by="updated",
            restaurant=product.get("restaurant", ""),
        )
        save_products_bulk([new_p])
    else:  # keep
        product["expiry_date"] = new_date
        product["status"] = "complete"
        product["registered_by"] = "updated"
        if label_path:
            product["label_image"] = label_path
        product["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_product(product)
    record_history(product["name"], product.get("intake_date", date.today().isoformat()), new_date)


def _render_action_ui(key_suffix: str, update_action: str) -> str:
    """update_action 설정에 따라 삭제/유지 라디오를 표시하고 선택값 반환."""
    if update_action == "ask":
        action = st.radio(
            "기존 기록을 어떻게 처리할까요?",
            options=["keep", "delete"],
            format_func=lambda x: "✏️ 유지 (날짜만 수정)" if x == "keep" else "🗑️ 삭제 (새 입고로 교체)",
            horizontal=True,
            key=f"action_radio_{key_suffix}",
        )
        return action
    return update_action  # "delete" or "keep"


# ═══════════════════════════════════════════
# 페이지 헤더
# ═══════════════════════════════════════════

st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
st.markdown("<p class='page-header'><span class='material-symbols-outlined'>photo_camera</span> 소비기한 업데이트</p>", unsafe_allow_html=True)

if st.button("← 홈으로", key="update_back"):
    st.switch_page(st.session_state["_home_pg"])

settings = load_settings()
update_action = settings.get("update_action", "ask")
restaurants = settings.get("restaurants", [])
all_products = load_products()

if not all_products:
    st.info("등록된 품목이 없습니다. 먼저 식자재를 입고 등록하세요.")
    if st.button("📋 입고 등록하러 가기", use_container_width=True):
        st.switch_page("pages/invoice_register.py")
    st.stop()

# ═══════════════════════════════════════════
# 코너 필터 버튼
# ═══════════════════════════════════════════
if restaurants:
    st.markdown("**코너 선택**")
    btn_labels = ["전체"] + restaurants
    if "update_selected_restaurant" not in st.session_state:
        st.session_state["update_selected_restaurant"] = "전체"

    cols = st.columns(len(btn_labels))
    for col, label in zip(cols, btn_labels):
        selected = st.session_state["update_selected_restaurant"] == label
        btn_type = "primary" if selected else "secondary"
        if col.button(label, key=f"upd_rest_{label}", type=btn_type, use_container_width=True):
            st.session_state["update_selected_restaurant"] = label
            st.session_state.pop("detected_date", None)
            st.rerun()

    selected_rest = st.session_state["update_selected_restaurant"]
    if selected_rest == "전체":
        products = all_products
    else:
        products = [p for p in all_products if p.get("restaurant", "") == selected_rest]

    if not products:
        st.info(f"'{selected_rest}' 코너에 등록된 품목이 없습니다.")
        st.stop()
else:
    products = all_products

st.markdown("---")

# 업데이트 성공 메시지 (rerun 후 표시)
if msg := st.session_state.pop("_update_success", None):
    st.success(msg)
    st.balloons()

# ═══════════════════════════════════════════
# 탭: 개별 업데이트 / 미완료 일괄 업데이트
# ═══════════════════════════════════════════
tab_single, tab_bulk = st.tabs(["📌 개별 업데이트", "📋 미완료 일괄 업데이트"])

# ═══════════════════════════════════════════
# TAB 1: 개별 업데이트
# ═══════════════════════════════════════════
with tab_single:
    product_names = [
        f"{p['name']} ({'소비기한: ' + p['expiry_date'] if p.get('expiry_date') else '미등록'})"
        for p in products
    ]
    selected_idx = st.selectbox(
        "품목 선택", range(len(products)),
        format_func=lambda i: product_names[i],
        key="update_select",
    )

    if selected_idx is not None:
        product = products[selected_idx]
        st.markdown(f"**현재 소비기한:** {product.get('expiry_date', '미등록')}")
        st.markdown("---")

        method = st.radio(
            "업데이트 방법", ["📷 라벨 촬영", "✏️ 직접 입력"],
            horizontal=True, key="update_method",
        )

        # ── 라벨 촬영 ──
        if method == "📷 라벨 촬영":
            if not settings.get("api_key"):
                st.error("⚠️ API Key가 필요합니다. 설정에서 입력하세요.")
            else:
                label_file = st.file_uploader(
                    "📷 라벨 사진 찍기 / 업로드",
                    type=["jpg", "jpeg", "png", "heic", "webp"],
                    key=f"update_uploader_{selected_idx}",
                    help="순정 카메라 앱 또는 사진첩에서 선택",
                )

                if label_file is not None:
                    raw_bytes = label_file.read()
                    try:
                        from PIL import Image, ImageFilter, ImageEnhance
                        import io as _io
                        img = Image.open(_io.BytesIO(raw_bytes))
                        img = img.filter(ImageFilter.SHARPEN)
                        img = ImageEnhance.Sharpness(img).enhance(1.8)
                        buf = _io.BytesIO()
                        img.save(buf, format="JPEG", quality=92)
                        img_bytes = buf.getvalue()
                    except Exception:
                        img_bytes = raw_bytes

                    st.image(img_bytes, width='stretch',
                             caption="업로드된 라벨 — 날짜가 잘 보이면 분석 시작")
                    st.markdown("---")

                    if st.button("🔍 날짜 인식 시작", use_container_width=True,
                                 type="primary", key="start_ocr"):
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        label_path = save_image(
                            img_bytes, "labels", f"{product['name']}_{ts}.jpg"
                        )
                        with st.spinner("AI가 날짜를 인식 중..."):
                            try:
                                detected = extract_date_from_label(
                                    settings["api_key"], settings["model"], img_bytes
                                )
                            except Exception as e:
                                detected = None
                                st.error(f"AI 오류: {e}")

                        if detected:
                            st.session_state["detected_date"] = detected
                            st.session_state["detected_label_path"] = label_path
                        else:
                            st.session_state.pop("detected_date", None)
                            st.warning("날짜를 인식하지 못했습니다. 더 선명하게 다시 찍어주세요.")

                # ── OCR 결과 표시 (spinner 밖) ──
                if st.session_state.get("detected_date"):
                    detected = st.session_state["detected_date"]
                    label_path = st.session_state.get("detected_label_path")
                    st.success(f"✅ 인식된 날짜: **{detected}**")
                    chosen_action = _render_action_ui("ocr", update_action)
                    if st.button("✅ 이 날짜로 업데이트", type="primary",
                                 use_container_width=True, key="confirm_ocr"):
                        try:
                            _do_update(product, detected, label_path, chosen_action)
                        except Exception as e:
                            st.error(f"저장 오류: {e}")
                        else:
                            st.session_state.pop("detected_date", None)
                            st.session_state.pop("detected_label_path", None)
                            st.session_state["_update_success"] = f"✅ {product['name']} 업데이트 완료!"
                            st.rerun()

        # ── 직접 입력 ──
        else:
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
            chosen_action = _render_action_ui("manual", update_action)
            if st.button("✅ 업데이트", use_container_width=True,
                         type="primary", key="save_manual_update"):
                try:
                    _do_update(product, new_date.isoformat(), None, chosen_action)
                except Exception as e:
                    st.error(f"저장 오류: {e}")
                else:
                    st.session_state["_update_success"] = f"✅ {product['name']} → {new_date} 업데이트 완료!"
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
                rest_text = f" | 🏷️ {p['restaurant']}" if p.get("restaurant") else ""
                st.markdown(f"**{p['name']}** {grade_text}{rest_text}")
                st.caption(f"입고일: {p.get('intake_date', '-')}")

                default_date = date.today() + timedelta(days=7)
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
                        _do_update(p, new_exp.isoformat(), None, update_action if update_action != "ask" else "keep")
                        st.success(f"✅ {p['name']} 저장 완료")
                        st.rerun()
