import streamlit as st
import streamlit.components.v1 as components
from datetime import date
from services.background_worker import get_worker
from services.data_service import (
    new_product, save_products_bulk, record_history, update_product_by_task_id,
    load_products, load_staging,
)

st.set_page_config(
    page_title="주방 소비기한 관리",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS: Luminous Slate 디자인 시스템 ──
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');

/* 사이드바 완전 숨김 */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* 메인 영역 패딩 */
.block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; max-width: 640px !important; }

/* 전역 폰트 — span 제외 (Streamlit 내부 아이콘 폰트 보호) */
html, body, [class*="css"], p, label, div {
    font-family: 'Inter', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif !important;
    font-feature-settings: "liga" 0, "calt" 0 !important;
}
h1, h2, h3, h4, .page-header {
    font-family: 'Lexend', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif !important;
    font-weight: 800 !important;
    color: #f8fafc !important;
    font-feature-settings: "liga" 0, "calt" 0 !important;
}

/* ── 홈 메뉴 카드 버튼 ── */
.menu-card { margin-bottom: 0.75rem; }
.menu-card button {
    background: #1e293b !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 1.5rem !important;
    height: 90px !important;
    min-height: 90px !important;
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    padding: 0 2rem !important;
    transition: background 0.15s ease, transform 0.1s ease !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 4px 16px rgba(0,0,0,0.35) !important;
}
.menu-card button:hover { background: #263348 !important; }
.menu-card button:active { transform: scale(0.982) !important; }
.menu-card button p, .menu-card button div p {
    font-family: 'Lexend', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif !important;
    font-feature-settings: "liga" 0, "calt" 0 !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: #f8fafc !important;
    text-align: left !important;
    letter-spacing: -0.01em !important;
    margin: 0 !important;
    line-height: 1.2 !important;
}

/* 설정 카드 */
.settings-card { margin-top: 0.5rem; }
.settings-card button {
    background: rgba(51,65,85,0.45) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 1.5rem !important;
    height: 72px !important;
    min-height: 72px !important;
    width: 100% !important;
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    padding: 0 3.5rem 0 1.5rem !important;
}
.settings-card button:hover { background: rgba(61,77,99,0.6) !important; }
.settings-card button p, .settings-card button div p {
    font-family: 'Lexend', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif !important;
    font-feature-settings: "liga" 0, "calt" 0 !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #94a3b8 !important;
    text-align: left !important;
    margin: 0 !important;
}
.settings-card button::after {
    content: "›" !important;
    position: absolute !important;
    right: 1.4rem !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    font-size: 2rem !important;
    color: rgba(148,163,184,0.25) !important;
    font-family: serif !important;
    font-weight: 300 !important;
    line-height: 1 !important;
}

/* 전역 버튼 */
.stButton > button {
    min-height: 52px !important;
    font-family: 'Inter', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    border-radius: 0.75rem !important;
}

/* 페이지 헤더 */
.page-header {
    font-family: 'Lexend', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif !important;
    font-feature-settings: "liga" 0, "calt" 0 !important;
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    margin-bottom: 1rem !important;
    color: #f8fafc !important;
}

/* ── 파일 업로더 ── */
[data-testid="stFileUploader"] { width: 100% !important; }
[data-testid="stFileUploader"] section {
    border: 2px dashed #3b82f6 !important;
    border-radius: 1rem !important;
    padding: 24px 16px !important;
    background: #1e293b !important;
    text-align: center !important;
    cursor: pointer !important;
}
[data-testid="stFileUploader"] section:hover {
    border-color: #60a5fa !important;
    background: #1e3a5f !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    color: #93c5fd !important;
}
[data-testid="stFileUploader"] button {
    min-height: 52px !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    width: 100% !important;
    margin-top: 8px !important;
    border-radius: 0.75rem !important;
}

/* 알림 배지 */
.badge {
    display: inline-block;
    background: #ef4444;
    color: #fff;
    font-size: 0.85rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 999px;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.65; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ── 페이지 정의 ──
def home_page():
    """메인 화면: 4개 대형 버튼 (2×2 그리드) + 알림 배지 + 설정"""

    # ── 하단 네비바 클릭 처리 ──
    nav = st.query_params.get("nav", "")
    if nav:
        st.query_params.clear()
        _nav_map = {
            "staging":  "pages/staging.py",
            "expiry":   "pages/expiry_view.py",
            "register": "pages/invoice_register.py",
            "update":   "pages/expiry_update.py",
            "preorder": "pages/preorder.py",
            "settings": "pages/settings.py",
        }
        if nav in _nav_map:
            st.switch_page(_nav_map[nav])

    # mismatch 큐 초기화
    if "mismatch_queue" not in st.session_state:
        st.session_state.mismatch_queue = []

    # 알림 배지 (백그라운드 처리 중인 작업)
    worker = get_worker()
    pending = worker.pending_count()

    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h1 style='font-family:Lexend,Apple Color Emoji,Segoe UI Emoji,sans-serif;"
        "font-feature-settings:\"liga\" 0,\"calt\" 0;font-weight:900;font-size:2.2rem;"
        "margin-bottom:0.2em;color:#f8fafc;letter-spacing:-0.03em;line-height:1.1;'>"
        "주방 위생 안심 매니저</h1>"
        "<p style='color:#64748b;font-size:1rem;margin-top:0;margin-bottom:2rem;"
        "font-family:Inter,sans-serif;'>소비기한 · 식자재 · 라벨 관리</p>",
        unsafe_allow_html=True,
    )

    if pending > 0:
        st.markdown(
            f"<div style='margin-bottom:1rem;'>"
            f"<span class='badge'>🔄 AI 분석 중 {pending}건</span></div>",
            unsafe_allow_html=True,
        )

    # 완료된 백그라운드 결과 수신
    results = worker.get_all_results()
    if results:
        if "bg_results" not in st.session_state:
            st.session_state.bg_results = {}
        completed = 0
        for task_id, r in results.items():
            if r.get("status") == "mismatch":
                # mismatch → 강제등록 대기 큐에 추가
                st.session_state.mismatch_queue.append({
                    "task_id": task_id,
                    "product_name": r.get("product_name", ""),
                    "date": r.get("date"),
                    "reason": r.get("reason", ""),
                    "bundle_image_paths": r.get("bundle_image_paths", []),
                })
            else:
                # DB 조용히 업데이트 (제품명·소비기한·원산지)
                p_name = r.get("product_name", "")
                p_date = r.get("date")
                p_origin = r.get("origin")
                updated_name = update_product_by_task_id(
                    task_id,
                    name=p_name or None,
                    expiry_date=p_date,
                    origin=p_origin,
                )
                if updated_name and p_date:
                    record_history(updated_name, date.today().isoformat(), p_date)
                st.session_state.bg_results[task_id] = r
                if p_name or p_date:
                    completed += 1
        if completed:
            # 조용한 토스트 알림 (st.toast는 화면을 막지 않음)
            st.toast(f"✅ AI 분석 {completed}건 완료 — 소비기한 관리에서 확인하세요", icon="✅")

    # ── 품목 불일치 알림 패널 ──
    if st.session_state.mismatch_queue:
        for i in range(len(st.session_state.mismatch_queue) - 1, -1, -1):
            item = st.session_state.mismatch_queue[i]
            with st.container():
                st.markdown(
                    f"""<div style="background:#3e1a1a; border:2px solid #d32f2f;
                    border-radius:10px; padding:14px; margin-bottom:8px;">
                    <span style="font-size:1.2rem; font-weight:700; color:#ff5252;">
                    ⚠️ AI 품목 불일치 감지</span><br>
                    <span style="color:#ffcdd2; font-size:0.95rem;">{item['reason']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                edited_name = st.text_input(
                    "제품명 확인/수정",
                    value=item.get("product_name") or "미확인 제품",
                    key=f"mismatch_name_{i}_{item['task_id'][:8]}",
                )
                col_force, col_cancel = st.columns(2)
                with col_force:
                    if st.button(
                        "✅ 아니야, 같은 제품 맞아!\n강제 등록",
                        use_container_width=True,
                        type="primary",
                        key=f"force_{i}_{item['task_id'][:8]}",
                    ):
                        p = new_product(
                            name=edited_name or "미확인 제품",
                            grade="B",
                            intake_date=date.today().isoformat(),
                            expiry_date=item.get("date"),
                            status="complete" if item.get("date") else "incomplete",
                            label_image=item["bundle_image_paths"][-1]
                            if item["bundle_image_paths"] else None,
                            registered_by="force_override",
                        )
                        save_products_bulk([p])
                        if item.get("date"):
                            record_history(p["name"], p["intake_date"], p["expiry_date"])
                        st.session_state.mismatch_queue.pop(i)
                        st.success(f"✅ '{edited_name}' 강제 등록 완료!")
                        st.rerun()
                with col_cancel:
                    if st.button(
                        "❌ AI 판단 수용\n(등록 취소)",
                        use_container_width=True,
                        key=f"cancel_mismatch_{i}_{item['task_id'][:8]}",
                    ):
                        st.session_state.mismatch_queue.pop(i)
                        st.rerun()
        st.markdown("---")

    # ── 메뉴 카드 (st.button + CSS) ──
    all_prods = load_products()
    urgent = sum(1 for p in all_prods if p.get("expiry_date") and not p.get("no_expiry") and
                 (date.fromisoformat(p["expiry_date"]) - date.today()).days <= 3)

    # 대기함 알림 (홈 상단에 표시)
    staging_batches = load_staging()
    staging_count = len(staging_batches)
    if staging_count > 0:
        st.markdown(
            f"<div style='background:#1e3a5f;border:1px solid #3b82f6;border-radius:0.75rem;"
            f"padding:0.75rem 1rem;margin-bottom:1rem;display:flex;align-items:center;"
            f"justify-content:space-between;'>"
            f"<span style='font-size:0.95rem;'>📦 대기함에 <strong>{staging_count}건</strong> 대기 중</span>"
            f"<span style='color:#60a5fa;font-size:0.85rem;'>입고 등록 → 대기함 탭</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    menu_items = [
        ("btn_expiry",   "pages/expiry_view.py",       "⏱",  "소비기한 관리",    urgent if urgent else None),
        ("btn_register", "pages/invoice_register.py",  "📋", "식자재 입고 등록",  staging_count if staging_count else None),
        ("btn_update",   "pages/expiry_update.py",     "📷", "소비기한 업데이트", None),
        ("btn_preorder", "pages/preorder.py",          "📦", "발주표 미리 등록",  None),
    ]
    for key, page, icon, title, badge in menu_items:
        badge_txt = f"  ·  {badge}건 위험" if badge else ""
        if st.button(f"{icon}  {title}{badge_txt}", key=key, use_container_width=True):
            st.switch_page(page)

    if st.button("⚙️  설정", key="btn_settings", use_container_width=True):
        st.switch_page("pages/settings.py")

    # 하단 네비바는 components.html() JS로 부모 document에 직접 삽입 (아래 참조)


# ── 네비게이션 (사이드바 숨김) ──
_home_pg = st.Page(home_page, title="홈", default=True)

# 서브페이지에서 홈으로 돌아갈 수 있도록 세션에 저장
st.session_state["_home_pg"] = _home_pg

pg = st.navigation(
    [
        _home_pg,
        st.Page("pages/staging.py", title="대기함"),
        st.Page("pages/expiry_view.py", title="소비기한 관리"),
        st.Page("pages/invoice_register.py", title="식자재 입고 등록"),
        st.Page("pages/expiry_update.py", title="소비기한 업데이트"),
        st.Page("pages/preorder.py", title="발주표 미리 등록"),
        st.Page("pages/settings.py", title="설정"),
    ],
    position="hidden",
)
pg.run()

# ── JS 주입: 메뉴카드 클래스 + 파일 업로더 한글화 + iOS 카메라 ──
components.html("""
<script>
(function() {
    const fix = () => {
        try {
            const doc = window.parent.document;

            // ── 홈 메뉴 버튼에 카드 CSS 클래스 부여 ──
            const menuLabels = ['소비기한 관리', '식자재 입고 등록', '소비기한 업데이트', '발주표 미리 등록'];
            doc.querySelectorAll('[data-testid="stButton"]').forEach(el => {
                const btn = el.querySelector('button');
                if (!btn) return;
                const txt = btn.textContent || '';
                if (menuLabels.some(l => txt.includes(l)) && !el.classList.contains('menu-card')) {
                    el.classList.add('menu-card');
                }
                if (txt.includes('설정') && !txt.includes('관리') && !el.classList.contains('settings-card')) {
                    el.classList.add('settings-card');
                }
            });

            // ── 하단 네비바: 부모 document에 직접 삽입 ──
            if (!doc.getElementById('app-bottom-nav')) {
                const nav = doc.createElement('nav');
                nav.id = 'app-bottom-nav';
                nav.style.cssText = 'position:fixed;bottom:0;left:0;width:100%;z-index:9999;'
                    + 'background:rgba(15,23,42,0.97);backdrop-filter:blur(20px);'
                    + '-webkit-backdrop-filter:blur(20px);'
                    + 'border-top:1px solid rgba(255,255,255,0.08);'
                    + 'display:flex;justify-content:space-around;align-items:center;'
                    + 'padding:0.6rem 0 calc(0.8rem + env(safe-area-inset-bottom));';
                const items = [
                    {icon:'🏠', label:'홈',     href:'/'},
                    {icon:'⏱️', label:'소비기한', href:'/?nav=expiry'},
                    {icon:'📋', label:'입고',    href:'/?nav=register'},
                    {icon:'📦', label:'발주',    href:'/?nav=preorder'},
                    {icon:'⚙️', label:'설정',    href:'/?nav=settings'},
                ];
                items.forEach(item => {
                    const a = doc.createElement('div');
                    a.style.cssText = 'display:flex;flex-direction:column;align-items:center;'
                        + 'color:#94a3b8;font-size:0.65rem;font-weight:600;gap:3px;cursor:pointer;'
                        + 'font-family:Lexend,sans-serif;user-select:none;';
                    if (item.href === '/') a.style.color = '#3b82f6';
                    a.innerHTML = '<span style="font-size:1.5rem;">' + item.icon + '</span>' + item.label;
                    a.setAttribute('data-href', item.href);
                    a.setAttribute('onclick', 'window.location.href=this.getAttribute("data-href")');
                    nav.appendChild(a);
                });
                doc.body.appendChild(nav);
            }

            // ── 파일 업로더 텍스트 한글화 (모바일 친화적) ──
            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            doc.querySelectorAll(
                '[data-testid="stFileUploaderDropzoneInstructions"] span'
            ).forEach(el => {
                if (el.textContent.trim() === 'Drag and drop files here')
                    el.textContent = isMobile ? '아래 버튼을 눌러 사진을 선택하세요' : '사진을 여기에 끌어다 놓거나';
                if (el.textContent.startsWith('Limit'))
                    el.textContent = el.textContent
                        .replace('Limit ','최대 ')
                        .replace(' per file','/파일');
            });
            // Browse files 버튼 한글화
            doc.querySelectorAll(
                '[data-testid="stFileUploaderDropzone"] button span'
            ).forEach(el => {
                if (el.textContent.trim() === 'Browse files')
                    el.textContent = isMobile ? '📷 사진 찍기 / 앨범에서 선택' : '📁 파일 선택';
            });
            // Android만 capture 속성 적용 (iOS는 팝업 강제로 제외)
            if (!isMobile || /Android/i.test(navigator.userAgent)) {
                doc.querySelectorAll(
                    '[data-testid="stFileUploader"] input[type="file"]'
                ).forEach(input => {
                    if (!input.getAttribute('data-fixed')) {
                        input.setAttribute('accept', 'image/*,image/heic');
                        input.setAttribute('data-fixed', '1');
                    }
                });
            }
        } catch(e) {}
    };
    fix();
    try {
        new MutationObserver(fix).observe(
            window.parent.document.body,
            {childList: true, subtree: true}
        );
    } catch(e) {}
})();
</script>
""", height=0)
