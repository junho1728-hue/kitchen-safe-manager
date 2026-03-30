"""소비기한 업데이트 페이지: 기존 제품의 소비기한을 빠르게 갱신."""

import streamlit as st
from datetime import datetime, date, timedelta
from services.data_service import (
    load_products, save_product, load_settings, save_image,
    record_history, new_product, save_products_bulk, delete_product,
)
from services.gemini_service import extract_date_from_label


# ── 페이지 전용 CSS ──
st.markdown("""
<style>
/* ── 코너 칩 버튼 ── */
.corner-chip button {
    min-height: 52px !important;
    padding: 0 1.5rem !important;
    border-radius: 9999px !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
}
/* 선택된 코너 칩 */
.corner-chip-active button {
    background: #3b82f6 !important;
    color: #ffffff !important;
    border: none !important;
}
/* 비선택 코너 칩 */
.corner-chip-inactive button {
    background: #1e293b !important;
    color: #94a3b8 !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
}

/* ── 현재 아이템 카드 ── */
.item-card {
    background: rgba(30,41,59,0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 2rem;
    padding: 1.75rem 2rem;
    margin: 1rem 0;
    position: relative;
    overflow: hidden;
}
.item-card::before {
    content: '';
    position: absolute;
    top: -3rem;
    right: -3rem;
    width: 8rem;
    height: 8rem;
    background: rgba(59,130,246,0.1);
    border-radius: 50%;
    filter: blur(2rem);
}
.item-card .badge-label {
    display: inline-block;
    background: rgba(59,130,246,0.2);
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.75rem;
}
.item-card .item-name {
    font-family: 'Lexend', sans-serif;
    font-size: 28px;
    font-weight: 900;
    color: #f8fafc;
    margin: 0 0 0.25rem 0;
    line-height: 1.2;
}
.item-card .item-expiry {
    font-size: 16px;
    color: #94a3b8;
    margin: 0;
}

/* ── 업데이트 방식 버튼 ── */
.method-btn button {
    min-height: 72px !important;
    border-radius: 1rem !important;
    font-size: 20px !important;
    font-weight: 700 !important;
}
.method-btn-active button {
    background: #3d4d63 !important;
    border: 2px solid #3b82f6 !important;
    color: #3b82f6 !important;
}
.method-btn-inactive button {
    background: #1e293b !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    color: #94a3b8 !important;
    opacity: 0.7 !important;
}

/* ── 날짜 입력 큰 표시 ── */
.date-display-box {
    background: #0b111e;
    border: 2px solid rgba(255,255,255,0.05);
    border-radius: 2rem;
    padding: 2rem;
    text-align: center;
    margin: 0.5rem 0 1rem 0;
    transition: border-color 0.2s;
}
.date-display-box:hover { border-color: rgba(59,130,246,0.4); }
.date-display-box .date-hint {
    color: #699cff;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.date-display-box .date-value {
    font-family: 'Lexend', sans-serif;
    font-size: 42px;
    font-weight: 900;
    color: #f8fafc;
    letter-spacing: -0.03em;
    line-height: 1;
}

/* ── 기록 처리 카드 ── */
.action-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.25rem;
    border-radius: 1rem;
    margin-bottom: 0.75rem;
    cursor: pointer;
    transition: background 0.15s;
}
.action-card-keep {
    background: #334155;
    border: 2px solid #3b82f6;
    box-shadow: 0 4px 20px rgba(59,130,246,0.08);
}
.action-card-delete {
    background: #1e293b;
    border: 1px solid rgba(255,255,255,0.05);
}
.action-icon-box {
    width: 3rem; height: 3rem;
    border-radius: 0.75rem;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.action-icon-keep { background: rgba(59,130,246,0.1); }
.action-icon-delete { background: rgba(239,68,68,0.1); }
.action-card-title { font-weight: 700; font-size: 18px; color: #f8fafc; margin: 0; }
.action-card-desc  { font-size: 13px; color: #94a3b8; margin: 0; }
.action-radio-dot {
    width: 1.5rem; height: 1.5rem; border-radius: 50%;
    margin-left: auto; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
}
.action-radio-selected { background: #3b82f6; border: 2px solid #3b82f6; }
.action-radio-selected::after { content: ''; display: block; width: 0.6rem; height: 0.6rem; background: #fff; border-radius: 50%; }
.action-radio-empty { border: 2px solid #475569; }

/* ── 섹션 라벨 ── */
.section-label {
    font-family: 'Lexend', sans-serif;
    font-size: 13px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 1.5rem 0 0.75rem 0;
}

/* ── 미완료 아이템 카드 ── */
.bulk-item-card {
    background: #1e293b;
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 1.25rem;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# 헬퍼 함수
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


# ═══════════════════════════════════════════
# 페이지 헤더
# ═══════════════════════════════════════════
st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
st.markdown(
    "<p class='page-header'>"
    "<span class='material-symbols-outlined'>update</span>"
    " 소비기한 업데이트</p>",
    unsafe_allow_html=True,
)
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
# 코너 선택 칩
# ═══════════════════════════════════════════
if restaurants:
    st.markdown("<p class='section-label'>코너 선택</p>", unsafe_allow_html=True)

    if "update_selected_restaurant" not in st.session_state:
        st.session_state["update_selected_restaurant"] = "전체"

    btn_labels = ["전체"] + restaurants
    # 한 줄에 최대 4개씩 배치 (가로 스크롤 근사치)
    row_size = min(len(btn_labels), 4)
    cols = st.columns(row_size)
    for i, label in enumerate(btn_labels):
        col = cols[i % row_size]
        is_active = st.session_state["update_selected_restaurant"] == label
        css_cls = "corner-chip corner-chip-active" if is_active else "corner-chip corner-chip-inactive"
        col.markdown(f"<div class='{css_cls}'>", unsafe_allow_html=True)
        if col.button(label, key=f"upd_rest_{label}", use_container_width=True):
            st.session_state["update_selected_restaurant"] = label
            st.session_state.pop("detected_date", None)
            st.rerun()
        col.markdown("</div>", unsafe_allow_html=True)

    selected_rest = st.session_state["update_selected_restaurant"]
    products = all_products if selected_rest == "전체" else [
        p for p in all_products if p.get("restaurant", "") == selected_rest
    ]

    if not products:
        st.info(f"'{selected_rest}' 코너에 등록된 품목이 없습니다.")
        st.stop()
else:
    products = all_products


# 업데이트 성공 메시지
if msg := st.session_state.pop("_update_success", None):
    st.toast(msg, icon="✅")


# ═══════════════════════════════════════════
# 탭: 개별 업데이트 / 미완료 일괄 업데이트
# ═══════════════════════════════════════════
tab_single, tab_bulk = st.tabs(["📌 개별 업데이트", "📋 미완료 일괄"])

# ──────────────────────────────────────────
# TAB 1: 개별 업데이트
# ──────────────────────────────────────────
with tab_single:

    # ── 품목 선택 드롭다운 ──
    st.markdown("<p class='section-label'>품목 선택</p>", unsafe_allow_html=True)
    product_names = [
        f"{p['name']}  ({'기한: ' + p['expiry_date'] if p.get('expiry_date') else '소비기한 미등록'})"
        for p in products
    ]
    selected_idx = st.selectbox(
        "품목 선택",
        range(len(products)),
        format_func=lambda i: product_names[i],
        key="update_select",
        label_visibility="collapsed",
    )

    if selected_idx is not None:
        product = products[selected_idx]
        exp_text = product.get("expiry_date", "미등록")
        rest_text = f" · {product['restaurant']}" if product.get("restaurant") else ""

        # ── 현재 아이템 카드 ──
        st.markdown(
            f"""<div class='item-card'>
              <div class='badge-label'>현재 품목</div>
              <p class='item-name'>{product['name']}</p>
              <p class='item-expiry'>소비기한 {exp_text}{rest_text}</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── 업데이트 방식 선택 ──
        st.markdown("<p class='section-label'>업데이트 방식</p>", unsafe_allow_html=True)

        if "update_method_sel" not in st.session_state:
            st.session_state["update_method_sel"] = "manual"

        col_m1, col_m2 = st.columns(2)
        is_manual = st.session_state["update_method_sel"] == "manual"
        is_photo  = st.session_state["update_method_sel"] == "photo"

        with col_m1:
            st.markdown(
                f"<div class='method-btn {'method-btn-active' if is_manual else 'method-btn-inactive'}'>",
                unsafe_allow_html=True,
            )
            if st.button("✏️  직접 입력", use_container_width=True, key="meth_manual"):
                st.session_state["update_method_sel"] = "manual"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_m2:
            st.markdown(
                f"<div class='method-btn {'method-btn-active' if is_photo else 'method-btn-inactive'}'>",
                unsafe_allow_html=True,
            )
            if st.button("📷  사진 촬영", use_container_width=True, key="meth_photo"):
                st.session_state["update_method_sel"] = "photo"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # ─────────────────────────
        # 직접 입력 방식
        # ─────────────────────────
        if st.session_state["update_method_sel"] == "manual":
            current = None
            if product.get("expiry_date"):
                try:
                    current = datetime.strptime(product["expiry_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            st.markdown("<p class='section-label'>새 소비기한</p>", unsafe_allow_html=True)

            new_date = st.date_input(
                "새 소비기한",
                value=current or (date.today() + timedelta(days=7)),
                key="update_date_input",
                label_visibility="collapsed",
            )

            # 큰 날짜 표시
            st.markdown(
                f"""<div class='date-display-box'>
                  <p class='date-hint'>날짜를 터치하여 수정</p>
                  <div class='date-value'>{new_date.strftime('%Y/%m/%d')}</div>
                </div>""",
                unsafe_allow_html=True,
            )

            # ── 기록 처리 카드 (ask일 때만) ──
            if update_action == "ask":
                st.markdown(
                    "<p class='section-label'>"
                    "<span class='material-symbols-outlined' style='font-size:16px;vertical-align:middle;margin-right:6px;'>history</span>"
                    "기존 기록을 어떻게 처리할까요?</p>",
                    unsafe_allow_html=True,
                )
                if "action_choice" not in st.session_state:
                    st.session_state["action_choice"] = "keep"

                col_k, col_d = st.columns(2)
                with col_k:
                    if st.button(
                        "✏️ 유지 (날짜만 수정)\n기록은 남기고 기한 정보만 변경",
                        use_container_width=True,
                        key="action_keep_btn",
                        type="primary" if st.session_state["action_choice"] == "keep" else "secondary",
                    ):
                        st.session_state["action_choice"] = "keep"
                        st.rerun()
                with col_d:
                    if st.button(
                        "🗑️ 삭제 (새 입고로 교체)\n기존 데이터를 무시하고 새로 설정",
                        use_container_width=True,
                        key="action_delete_btn",
                        type="primary" if st.session_state["action_choice"] == "delete" else "secondary",
                    ):
                        st.session_state["action_choice"] = "delete"
                        st.rerun()
                chosen_action = st.session_state["action_choice"]
            else:
                chosen_action = update_action

            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            if st.button(
                "✅  업데이트",
                use_container_width=True,
                type="primary",
                key="save_manual_update",
            ):
                try:
                    _do_update(product, new_date.isoformat(), None, chosen_action)
                except Exception as e:
                    st.error(f"저장 오류: {e}")
                else:
                    st.session_state["_update_success"] = f"✅ {product['name']} → {new_date} 업데이트 완료!"
                    st.rerun()

        # ─────────────────────────
        # 사진 촬영 방식
        # ─────────────────────────
        else:
            if not settings.get("api_key"):
                st.error("⚠️ API Key가 필요합니다. 설정에서 입력하세요.")
            else:
                st.markdown("<p class='section-label'>라벨 사진 업로드</p>", unsafe_allow_html=True)
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

                    st.image(img_bytes, width="stretch",
                             caption="업로드된 라벨 — 날짜가 잘 보이면 분석 시작")

                    if st.button("🔍 날짜 인식 시작", use_container_width=True,
                                 type="primary", key="start_ocr"):
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        label_path = save_image(img_bytes, "labels", f"{product['name']}_{ts}.jpg")
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

                # OCR 결과 표시
                if st.session_state.get("detected_date"):
                    detected = st.session_state["detected_date"]
                    label_path = st.session_state.get("detected_label_path")

                    st.markdown("<p class='section-label'>인식된 소비기한</p>", unsafe_allow_html=True)
                    st.markdown(
                        f"""<div class='date-display-box'>
                          <p class='date-hint'>AI가 인식한 날짜</p>
                          <div class='date-value'>{detected.replace('-','/')}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                    if update_action == "ask":
                        if "action_choice_ocr" not in st.session_state:
                            st.session_state["action_choice_ocr"] = "keep"
                        col_k2, col_d2 = st.columns(2)
                        with col_k2:
                            if st.button(
                                "✏️ 유지",
                                use_container_width=True, key="action_keep_ocr",
                                type="primary" if st.session_state["action_choice_ocr"] == "keep" else "secondary",
                            ):
                                st.session_state["action_choice_ocr"] = "keep"
                                st.rerun()
                        with col_d2:
                            if st.button(
                                "🗑️ 삭제",
                                use_container_width=True, key="action_del_ocr",
                                type="primary" if st.session_state["action_choice_ocr"] == "delete" else "secondary",
                            ):
                                st.session_state["action_choice_ocr"] = "delete"
                                st.rerun()
                        chosen_action_ocr = st.session_state["action_choice_ocr"]
                    else:
                        chosen_action_ocr = update_action

                    if st.button("✅  이 날짜로 업데이트", type="primary",
                                 use_container_width=True, key="confirm_ocr"):
                        try:
                            _do_update(product, detected, label_path, chosen_action_ocr)
                        except Exception as e:
                            st.error(f"저장 오류: {e}")
                        else:
                            st.session_state.pop("detected_date", None)
                            st.session_state.pop("detected_label_path", None)
                            st.session_state["_update_success"] = f"✅ {product['name']} 업데이트 완료!"
                            st.rerun()


# ──────────────────────────────────────────
# TAB 2: 미완료 일괄 업데이트
# ──────────────────────────────────────────
with tab_bulk:
    incomplete = [p for p in products if p.get("status") == "incomplete"]

    if not incomplete:
        st.markdown(
            "<div style='text-align:center;padding:3rem 0;'>"
            "<div style='font-size:3rem;margin-bottom:1rem;'>🎉</div>"
            "<p style='font-size:22px;font-weight:700;color:#f8fafc;'>모든 소비기한 등록 완료!</p>"
            "<p style='font-size:16px;color:#64748b;'>미완료 항목이 없습니다.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<p style='font-size:20px;font-weight:700;color:#f8fafc;margin-bottom:1rem;'>"
            f"미완료 항목: <span style='color:#ef4444;'>{len(incomplete)}건</span></p>",
            unsafe_allow_html=True,
        )

        for i, p in enumerate(incomplete):
            grade_label = {"A": "🔴 A등급", "B": "🟡 B등급", "C": "🟢 C등급"}.get(p.get("grade", ""), "")
            rest_label = f"  ·  🏷️ {p['restaurant']}" if p.get("restaurant") else ""

            st.markdown(
                f"<div class='bulk-item-card'>"
                f"<p style='font-size:20px;font-weight:800;color:#f8fafc;margin:0 0 0.25rem;'>"
                f"{p['name']} <span style='font-size:14px;font-weight:600;color:#94a3b8;'>{grade_label}{rest_label}</span></p>"
                f"<p style='font-size:14px;color:#64748b;margin:0;'>입고일: {p.get('intake_date', '-')}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

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
                if st.button("저장 ✅", key=f"bulk_save_{p['id']}", use_container_width=True):
                    _do_update(p, new_exp.isoformat(), None, update_action if update_action != "ask" else "keep")
                    st.toast(f"✅ {p['name']} 저장 완료", icon="✅")
                    st.rerun()
