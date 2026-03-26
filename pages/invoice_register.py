"""식자재 입고 등록 페이지: 2단계 워크플로 (Snap & Go).

Step 1 (capture): 명세서 촬영/업로드 또는 직접 입력 → 품목 리스트 추출
Step 2 (review_list): 리스트 확인 → 즉시 DB 저장 → 홈 이동
(날짜 등록 단계 제거 — 소비기한은 백그라운드 AI가 자동 업데이트)
"""

import uuid
import streamlit as st
from datetime import datetime, date, timedelta
from services.data_service import (
    load_settings, new_product, save_products_bulk, save_image,
    record_history, load_history, load_preorders, complete_preorder,
    load_staging, update_staging_batch, remove_staging_batch,
    register_staging_batch, save_settings, BASE_DIR,
)
from services.classification import classify_product
from services.gemini_service import (
    extract_invoice_items, extract_date_from_label, analyze_products_comprehensive,
)
from services.suggestion import suggest_expiry_days
from services.background_worker import get_worker

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
if "reg_snap_task_ids" not in st.session_state:
    st.session_state.reg_snap_task_ids = {}  # item_name → task_id
# ── 제품 묶음 촬영 상태 ──
if "bundle_step" not in st.session_state:
    st.session_state.bundle_step = "start"      # "start" | "capturing"
if "bundle_photos" not in st.session_state:
    st.session_state.bundle_photos = []         # 현재 제품의 bytes 리스트
if "direct_items_done" not in st.session_state:
    st.session_state.direct_items_done = []     # 저장 완료된 묶음 목록
if "invoice_snap_step" not in st.session_state:
    st.session_state.invoice_snap_step = "ready"  # "ready" | "done"
if "invoice_snap_count" not in st.session_state:
    st.session_state.invoice_snap_count = 0


def reset_workflow():
    """워크플로 상태 초기화."""
    st.session_state.reg_step = "capture"
    st.session_state.reg_items = []
    st.session_state.reg_selected = []
    st.session_state.reg_item_idx = 0
    st.session_state.reg_invoice_path = None
    st.session_state.reg_date_mode = None
    st.session_state.reg_snap_task_ids = {}
    st.session_state.bundle_step = "start"
    st.session_state.bundle_photos = []
    st.session_state.direct_items_done = []
    st.session_state.invoice_snap_step = "ready"
    st.session_state.invoice_snap_count = 0


st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
st.markdown("<p class='page-header'>📋 식자재 입고 등록</p>", unsafe_allow_html=True)

# 홈/초기화 버튼
col_back, col_reset = st.columns([1, 1])
with col_back:
    if st.button("← 홈으로", key="reg_back"):
        reset_workflow()
        st.switch_page(st.session_state["_home_pg"])
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

    # ── 발주표 불러오기 (상단 고정) ──
    today_str = date.today().isoformat()
    preorders = load_preorders()
    today_preorders = [
        p for p in preorders
        if p["status"] == "pending" and p["expected_intake_date"] == today_str
    ]
    if today_preorders:
        st.info(f"📦 오늘 입고 예정 발주표 {len(today_preorders)}건이 있습니다.")
        if st.button(
            f"📦 발주표 불러오기 ({len(today_preorders)}건)",
            use_container_width=True,
            type="primary",
            key="load_preorder",
        ):
            classified = [
                {
                    "name": p["name"],
                    "grade": p.get("grade", classify_product(p["name"])),
                    "storage": p.get("storage", "냉장"),
                    "ai_reason": p.get("ai_reason", ""),
                    "preorder_id": p["id"],
                }
                for p in today_preorders
            ]
            st.session_state.reg_items = classified
            st.session_state.reg_step = "review_list"
            st.rerun()
        st.markdown("---")

    # ── 4가지 입력 방법 탭 ──
    staging_batches = load_staging()
    staging_label = f"📦 대기함 ({len(staging_batches)}건)" if staging_batches else "📦 대기함"
    tab_invoice, tab_direct, tab_manual, tab_staging = st.tabs(
        ["📸 명세서 촬영", "📷 제품 직접 촬영", "✏️ 품목명 직접 입력", staging_label]
    )

    # ─────────────────────────────────
    # TAB 1: 명세서 촬영 (기존 방식)
    # ─────────────────────────────────
    with tab_invoice:
        if not settings.get("api_key"):
            st.error("⚠️ API Key가 설정되지 않았습니다.")
            if st.button("설정으로 이동", key="inv_to_settings"):
                st.switch_page("pages/settings.py")
        else:
            isnap = st.session_state.invoice_snap_step

            # ── 완료 화면 ──
            if isnap == "done":
                st.success(f"✅ 명세서 {st.session_state.invoice_snap_count}건 접수 완료! AI가 품목을 분석 중입니다.")
                st.caption("분석 완료 후 **대기함**에서 확인하고 등록할 수 있습니다.")
                st.markdown("---")
                col_next, col_home = st.columns(2)
                with col_next:
                    if st.button("📸 다음 명세서\n등록하기", use_container_width=True,
                                 type="primary", key="inv_next"):
                        st.session_state.invoice_snap_step = "ready"
                        st.rerun()
                with col_home:
                    if st.button("🏠 홈으로\n나가기", use_container_width=True,
                                 key="inv_go_home"):
                        reset_workflow()
                        st.switch_page(st.session_state["_home_pg"])

            # ── 업로드 화면 ──
            else:
                st.caption("📄 거래명세서·납품서 전용 — 제품 사진은 [제품 직접 촬영] 탭 이용")
                uploader_key = f"invoice_uploader_{st.session_state.invoice_snap_count}"
                invoice_file = st.file_uploader(
                    "📸 명세서 사진 찍기 / 업로드",
                    type=["jpg", "jpeg", "png", "heic", "webp"],
                    key=uploader_key,
                )
                if invoice_file is not None:
                    image_bytes = invoice_file.read()
                    st.image(image_bytes, width='stretch',
                             caption="명세서가 잘 보이면 아래 버튼을 누르세요")
                    st.markdown("---")
                    if st.button("⚡ 즉시 등록 (Snap & Go)", use_container_width=True,
                                 type="primary", key="inv_snap_go"):
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        invoice_path = save_image(image_bytes, "invoices", f"inv_{ts}.jpg")
                        task_id = str(uuid.uuid4())
                        worker = get_worker()
                        worker.enqueue(
                            task_id=task_id,
                            image_path=invoice_path,
                            task_type="invoice_batch",
                            api_key=settings.get("api_key", ""),
                            model=settings.get("model", ""),
                        )
                        st.session_state.invoice_snap_count += 1
                        st.session_state.invoice_snap_step = "done"
                        st.rerun()

    # ─────────────────────────────────
    # TAB 2: 제품 묶음 업로드 (여러 장 → 하나의 제품으로 분석)
    # ─────────────────────────────────
    with tab_direct:
        if not settings.get("api_key"):
            st.error("⚠️ API Key가 설정되지 않았습니다.")
        else:
            bs = st.session_state.bundle_step
            done_items = st.session_state.direct_items_done

            if done_items:
                st.info(f"📦 저장 완료: **{len(done_items)}개 제품** (AI 백그라운드 분석 중)")

            # ── 업로드 / 미리보기 화면 ──
            if bs in ("start", "capturing"):
                st.markdown("#### 📷 제품 사진 올리기")
                st.caption("전면·라벨·옆면 등 여러 장을 한꺼번에 선택하세요. 순정 카메라 앱이 열립니다.")

                # 제출마다 key가 바뀌어 uploader 초기화
                uploader_key = f"bundle_uploader_{len(done_items)}"
                uploaded_files = st.file_uploader(
                    "📷 사진 찍기 / 사진첩에서 선택",
                    type=["jpg", "jpeg", "png", "heic", "webp"],
                    accept_multiple_files=True,
                    key=uploader_key,
                    help="iOS: '사진 찍기' 또는 '사진 보관함'  |  Android: '카메라' 또는 '갤러리'",
                )

                if uploaded_files:
                    st.markdown(f"**{len(uploaded_files)}장 선택됨 — 미리보기 확인 후 분석 시작**")
                    # 전체 너비 미리보기
                    for i, f in enumerate(uploaded_files):
                        img_bytes = f.read()
                        st.image(img_bytes, width='stretch',
                                 caption=f"사진 {i+1} / {len(uploaded_files)}")
                    st.markdown("---")
                    if st.button("⚡ 등록", use_container_width=True,
                                 type="primary", key="bundle_analyze"):
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        saved_paths = []
                        for i, f in enumerate(uploaded_files):
                            f.seek(0)
                            # 원본 바이트 즉시 저장 (PIL 보정은 백그라운드에서 처리)
                            raw_bytes = f.read()
                            path = save_image(raw_bytes, "invoices", f"bundle_{ts}_{i}.jpg")
                            saved_paths.append(path)

                        # 백그라운드 큐 등록 (Snap & Go!)
                        task_id = str(uuid.uuid4())
                        worker = get_worker()
                        worker.enqueue(
                            task_id=task_id,
                            image_path=saved_paths[0],
                            task_type="product_bundle",
                            product_name="",
                            api_key=settings.get("api_key", ""),
                            model=settings.get("model", ""),
                            bundle_image_paths=saved_paths,
                        )

                        # 대기함으로 저장 (AI 분석 후 staging.json에 추가됨)

                        st.session_state.reg_snap_task_ids[f"bundle_{ts}"] = task_id
                        st.session_state.direct_items_done.append({
                            "paths": saved_paths,
                            "task_id": task_id,
                            "ts": ts,
                            "photo_count": len(saved_paths),
                        })
                        st.session_state.bundle_photos = []
                        st.session_state.bundle_step = "next_action"
                        st.rerun()

            # ── 제품 등록 완료 → 다음 선택 ──
            elif bs == "next_action":
                total = len(done_items)
                last = done_items[-1]
                st.success(
                    f"✅ {total}번째 제품 촬영 완료! ({last['photo_count']}장 — AI 분석 중)"
                )
                st.caption("분석 완료 후 **대기함**에서 확인/등록할 수 있습니다.")
                st.markdown("---")
                col_next, col_home = st.columns(2)
                with col_next:
                    st.markdown('<div class="big-button btn-register">', unsafe_allow_html=True)
                    if st.button("📷 다음 제품\n등록하기", use_container_width=True,
                                 type="primary", key="next_product"):
                        st.session_state.bundle_step = "start"
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with col_home:
                    st.markdown('<div class="big-button btn-expiry">', unsafe_allow_html=True)
                    if st.button("🏠 홈으로\n나가기", use_container_width=True,
                                 key="bundle_go_home"):
                        st.session_state.bundle_step = "start"
                        st.session_state.bundle_photos = []
                        st.session_state.direct_items_done = []
                        reset_workflow()
                        st.switch_page(st.session_state["_home_pg"])
                    st.markdown("</div>", unsafe_allow_html=True)

    # ─────────────────────────────────
    # TAB 3: 품목명 직접 입력
    # ─────────────────────────────────
    with tab_manual:
        st.caption("제품명을 직접 입력하세요. 한 줄에 하나씩 입력하거나 쉼표로 구분합니다.")

        text_input = st.text_area(
            "품목 목록",
            placeholder="돼지고기 앞다리\n계란 30구\n두부\n고등어",
            height=180,
            key="manual_text_input",
        )

        use_ai_grade = st.checkbox(
            "AI 등급 분석 사용 (API 호출 필요)",
            value=bool(settings.get("api_key")),
            key="manual_use_ai",
        )

        if st.button("다음 →", use_container_width=True, type="primary", key="manual_next"):
            # 줄 또는 쉼표로 분리
            raw = text_input.replace(",", "\n").replace("，", "\n")
            names = [l.strip() for l in raw.split("\n") if l.strip()]

            if not names:
                st.warning("품목을 입력하세요.")
            elif use_ai_grade and settings.get("api_key"):
                with st.spinner("AI가 등급을 분석 중..."):
                    try:
                        analyzed = analyze_products_comprehensive(
                            settings["api_key"], settings["model"], names
                        )
                    except Exception:
                        analyzed = []
                ai_map = {a["name"]: a for a in analyzed}
                classified = []
                for name in names:
                    ai = ai_map.get(name, {})
                    grade = ai.get("grade") or classify_product(name)
                    if grade == "exclude":
                        continue
                    classified.append({
                        "name": name,
                        "grade": grade,
                        "storage": ai.get("storage", "냉장"),
                        "ai_reason": ai.get("reason", ""),
                    })
                st.session_state.reg_items = classified
                st.session_state.reg_step = "review_list"
                st.rerun()
            else:
                # 키워드 분류만 사용
                classified = []
                for name in names:
                    grade = classify_product(name)
                    if grade != "exclude":
                        classified.append({
                            "name": name,
                            "grade": grade,
                            "storage": "냉장",
                            "ai_reason": "",
                        })
                st.session_state.reg_items = classified
                st.session_state.reg_step = "review_list"
                st.rerun()


# ══════════════════════════════════════════════════
# STEP 2: 추출 리스트 확인
# ══════════════════════════════════════════════════
elif st.session_state.reg_step == "review_list":
    st.subheader("📝 추출된 품목 확인")
    st.caption("품목명을 수정하고, 날짜 등록할 항목을 선택하세요. A등급은 자동 선택됩니다.")

    GRADE_COLORS = {"A": "#d32f2f", "B": "#f57c00", "C": "#388e3c", "normal": "#555"}
    GRADE_LABELS = {"A": "A 집중", "B": "B 일반", "C": "C 저위험", "normal": "일반"}

    items = st.session_state.reg_items
    updated_items = []

    for i, item in enumerate(items):
        col_check, col_name, col_grade = st.columns([0.5, 3, 1.2])
        with col_check:
            default_checked = item["grade"] in ("A", "B")
            checked = st.checkbox(
                "선택", value=default_checked, key=f"check_{i}", label_visibility="collapsed"
            )
        with col_name:
            edited_name = st.text_input(
                "품목명", value=item["name"], key=f"name_{i}", label_visibility="collapsed"
            )
            ai_reason = item.get("ai_reason", "")
            if ai_reason:
                st.caption(f"AI: {ai_reason}")
        with col_grade:
            # 등급 유지 (AI 분석 결과 우선, 이름 변경 시 재분류)
            existing_grade = item.get("grade", "normal")
            display_grade = existing_grade if existing_grade in GRADE_COLORS else "normal"
            color = GRADE_COLORS.get(display_grade, "#555")
            label = GRADE_LABELS.get(display_grade, display_grade)
            storage_icon = {"냉장": "🧊", "냉동": "❄️", "실온": "🌡️"}.get(item.get("storage", "냉장"), "")
            st.markdown(
                f'<span style="background:{color}; color:#fff; padding:4px 8px; '
                f'border-radius:8px; font-size:0.8rem;">{label}</span> {storage_icon}',
                unsafe_allow_html=True,
            )

        updated_items.append({
            "name": edited_name,
            "grade": existing_grade,
            "storage": item.get("storage", "냉장"),
            "ai_reason": item.get("ai_reason", ""),
            "selected": checked,
            "preorder_id": item.get("preorder_id"),
        })

    st.markdown("---")

    if st.button("✅ 저장하고 완료", use_container_width=True, type="primary"):
        today_str = date.today().isoformat()
        products_to_save = []
        for it in updated_items:
            p = new_product(
                name=it["name"],
                grade=it["grade"],
                intake_date=today_str,
                expiry_date=None,
                status="incomplete",
                invoice_image=st.session_state.reg_invoice_path,
                registered_by="invoice",
            )
            products_to_save.append(p)
        save_products_bulk(products_to_save)

        # 발주표 완료 처리
        for it in updated_items:
            if it.get("preorder_id"):
                complete_preorder(it["preorder_id"])

        n = len(products_to_save)
        reset_workflow()
        st.success(f"✅ {n}개 품목 저장 완료! 소비기한은 [소비기한 업데이트]에서 추가하세요.")
        st.balloons()
        if st.button("🏠 홈으로", use_container_width=True, key="review_home"):
            st.switch_page(st.session_state["_home_pg"])


# ─────────────────────────────────
# TAB 4: 대기함 (AI 분석 완료 → 확인/등록)
# ─────────────────────────────────
with tab_staging:
    staging_batches = load_staging()
    settings = load_settings()
    restaurants = settings.get("restaurants", [])

    if not staging_batches:
        st.info("대기 중인 항목이 없습니다.\n\n명세서를 촬영하면 AI 분석 후 여기에 표시됩니다.")
    else:
        st.markdown(f"**{len(staging_batches)}건**의 배치가 대기 중입니다.")
        st.markdown("---")

        for batch_idx, batch in enumerate(staging_batches):
            batch_id = batch["id"]
            source_label = {
                "invoice": "📋 명세서", "bundle": "📷 제품 촬영", "manual": "✏️ 수동"
            }.get(batch.get("source", ""), "📋")
            created = batch.get("created_at", "")[:16].replace("T", " ")

            st.markdown(f"**{source_label} 배치 #{batch_idx + 1}** — {created}")

            # 사진 썸네일
            img_path = batch.get("image_path")
            if img_path:
                full_path = BASE_DIR / img_path
                if full_path.exists():
                    st.image(str(full_path), caption="원본 사진", width=200)

            # 코너/음식점 지정
            detected_corner = batch.get("restaurant", "")
            corner_options = ["(미분류)"] + restaurants

            if detected_corner and detected_corner not in restaurants:
                st.info(f"🔍 AI 감지 코너: **{detected_corner}** (기존 목록에 없음)")
                col_y, col_n = st.columns(2)
                with col_y:
                    if st.button(
                        f"'{detected_corner}' 새로 추가",
                        key=f"stg_add_corner_{batch_id}",
                        use_container_width=True,
                        type="primary",
                    ):
                        restaurants.append(detected_corner)
                        settings["restaurants"] = restaurants
                        save_settings(settings)
                        st.toast(f"'{detected_corner}' 코너 추가!")
                        st.rerun()
                with col_n:
                    if st.button("무시", key=f"stg_ign_corner_{batch_id}", use_container_width=True):
                        update_staging_batch(batch_id, {"restaurant": ""})
                        st.rerun()
                corner_options = ["(미분류)"] + restaurants

            if detected_corner and detected_corner in restaurants:
                default_idx = corner_options.index(detected_corner)
            else:
                default_idx = 0

            selected_corner = st.selectbox(
                "🏪 코너/음식점",
                corner_options,
                index=default_idx,
                key=f"stg_corner_{batch_id}",
            )

            # 품목 리스트
            items = batch.get("items", [])
            if not items:
                st.warning("품목이 없습니다.")
                if st.button("배치 삭제", key=f"stg_del_empty_{batch_id}", use_container_width=True):
                    remove_staging_batch(batch_id)
                    st.rerun()
                continue

            updated_items = []
            for item_idx, item in enumerate(items):
                grade = item.get("grade", "normal")
                grade_label = {"A": "🔴A", "B": "🟡B", "C": "🟢C", "exclude": "⚪제외"}.get(grade, "")

                col_chk, col_nm, col_gr = st.columns([1, 4, 1])
                with col_chk:
                    sel = st.checkbox("", value=item.get("selected", True),
                                      key=f"stg_sel_{batch_id}_{item_idx}", label_visibility="collapsed")
                with col_nm:
                    new_name = st.text_input("품목", value=item.get("name", ""),
                                             key=f"stg_name_{batch_id}_{item_idx}", label_visibility="collapsed")
                with col_gr:
                    st.markdown(f"<span style='font-size:0.85rem;'>{grade_label}</span>", unsafe_allow_html=True)

                # 소비기한 입력 (직접 / 사진)
                exp_tab1, exp_tab2 = st.tabs(["📅 직접입력", "📷 사진촬영"])
                with exp_tab1:
                    cur_exp = None
                    if item.get("expiry_date"):
                        try:
                            cur_exp = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
                        except ValueError:
                            pass
                    new_exp = st.date_input("소비기한", value=cur_exp or date.today(),
                                            key=f"stg_exp_{batch_id}_{item_idx}", label_visibility="collapsed")
                    final_exp = new_exp.isoformat() if new_exp else item.get("expiry_date")

                with exp_tab2:
                    uploaded = st.file_uploader("라벨 사진", type=["jpg", "jpeg", "png", "heic"],
                                               key=f"stg_upload_{batch_id}_{item_idx}", label_visibility="collapsed")
                    if uploaded:
                        api_key = settings.get("api_key", "")
                        model = settings.get("model", "gemini-2.5-flash-lite")
                        if api_key:
                            with st.spinner("AI 소비기한 추출 중..."):
                                try:
                                    img_bytes = uploaded.read()
                                    detected = extract_date_from_label(api_key, model, img_bytes)
                                    if detected:
                                        final_exp = detected
                                        st.success(f"소비기한 감지: {detected}")
                                    else:
                                        st.warning("소비기한을 찾을 수 없습니다.")
                                except Exception as e:
                                    st.error(f"AI 분석 실패: {e}")
                        else:
                            st.warning("설정에서 API 키를 등록해주세요.")

                updated_items.append({
                    **item, "name": new_name, "selected": sel, "expiry_date": final_exp,
                })

            st.markdown("---")

            # 액션 버튼
            sel_count = sum(1 for it in updated_items if it.get("selected", True))
            col_reg, col_del = st.columns(2)
            with col_reg:
                if st.button(f"✅ {sel_count}건 등록", key=f"stg_reg_{batch_id}",
                             use_container_width=True, type="primary", disabled=sel_count == 0):
                    actual_corner = "" if selected_corner == "(미분류)" else selected_corner
                    update_staging_batch(batch_id, {"items": updated_items, "restaurant": actual_corner})
                    products = register_staging_batch(batch_id, restaurant=actual_corner)
                    st.toast(f"✅ {len(products)}건 등록 완료!", icon="✅")
                    st.rerun()
            with col_del:
                if st.button("🗑️ 삭제", key=f"stg_del_{batch_id}", use_container_width=True):
                    remove_staging_batch(batch_id)
                    st.toast("배치 삭제 완료", icon="🗑️")
                    st.rerun()

            st.markdown("---")
