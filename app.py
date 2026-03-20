import streamlit as st
from services.background_worker import get_worker

st.set_page_config(
    page_title="주방 소비기한 관리",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS: 다크모드, 대형 버튼, 모바일 최적화 ──
st.markdown(
    """
<style>
/* 사이드바 완전 숨김 */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* 메인 영역 패딩 최소화 (모바일) */
.block-container { padding-top: 1rem !important; padding-bottom: 0 !important; }

/* 홈 화면 대형 버튼 */
.big-button button {
    height: 22vh;
    font-size: 2rem;
    font-weight: 700;
    border-radius: 16px;
    margin: 4px 0;
    transition: transform 0.1s;
    width: 100%;
}
.big-button button:active { transform: scale(0.97); }

/* 버튼 색상 개별 지정 */
.btn-expiry button  { background: linear-gradient(135deg, #0d47a1, #1565c0) !important; color: #fff !important; border: none !important; }
.btn-expiry button:hover  { background: linear-gradient(135deg, #1565c0, #1976d2) !important; }
.btn-register button { background: linear-gradient(135deg, #1b5e20, #2e7d32) !important; color: #fff !important; border: none !important; }
.btn-register button:hover { background: linear-gradient(135deg, #2e7d32, #388e3c) !important; }
.btn-update button  { background: linear-gradient(135deg, #e65100, #ef6c00) !important; color: #fff !important; border: none !important; }
.btn-update button:hover  { background: linear-gradient(135deg, #ef6c00, #f57c00) !important; }
.btn-preorder button { background: linear-gradient(135deg, #4a148c, #6a1b9a) !important; color: #fff !important; border: none !important; }
.btn-preorder button:hover { background: linear-gradient(135deg, #6a1b9a, #7b1fa2) !important; }

/* 설정 버튼 */
.btn-settings button { background: transparent !important; border: 1px solid #555 !important; color: #aaa !important; }

/* 전역 버튼 최소 터치 타겟 */
.stButton > button { min-height: 52px; font-size: 1.1rem; }

/* 페이지 헤더 스타일 */
.page-header { font-size: 1.8rem; font-weight: 700; margin-bottom: 1rem; }

/* 알림 배지 */
.badge {
    display: inline-block;
    background: #d32f2f;
    color: #fff;
    font-size: 0.8rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ── 페이지 정의 ──
def home_page():
    """메인 화면: 4개 대형 버튼 (2×2 그리드) + 알림 배지 + 설정"""

    # 알림 배지 (백그라운드 처리 중인 작업)
    worker = get_worker()
    pending = worker.pending_count()

    st.markdown(
        "<h1 style='text-align:center; margin-bottom:0.2em;'>🍳 주방 위생 안심 매니저</h1>",
        unsafe_allow_html=True,
    )

    if pending > 0:
        st.markdown(
            f"<div style='text-align:center; margin-bottom:0.5em;'>"
            f"<span class='badge'>🔄 AI 분석 중 {pending}건</span></div>",
            unsafe_allow_html=True,
        )
        # 완료된 백그라운드 결과를 세션에 저장
        results = worker.get_all_results()
        if results:
            if "bg_results" not in st.session_state:
                st.session_state.bg_results = {}
            st.session_state.bg_results.update(results)
            completed = sum(1 for r in results.values() if "date" in r)
            if completed:
                st.success(f"✅ 백그라운드 분석 {completed}건 완료! 소비기한 관리에서 확인하세요.")
    else:
        st.markdown(
            "<p style='text-align:center; color:#888; margin-bottom:1em;'>소비기한 관리 · 식자재 입고 · 라벨 보관</p>",
            unsafe_allow_html=True,
        )

    # 2×2 그리드 버튼
    col1, col2 = st.columns(2, gap="small")

    with col1:
        # 버튼 1: 소비기한 관리
        st.markdown('<div class="big-button btn-expiry">', unsafe_allow_html=True)
        if st.button("🔍\n소비기한 관리", use_container_width=True, key="btn_expiry"):
            st.switch_page("pages/expiry_view.py")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        # 버튼 2: 식자재 입고 등록
        st.markdown('<div class="big-button btn-register">', unsafe_allow_html=True)
        if st.button("📋\n식자재 입고 등록", use_container_width=True, key="btn_register"):
            st.switch_page("pages/invoice_register.py")
        st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2, gap="small")

    with col3:
        # 버튼 3: 소비기한 업데이트
        st.markdown('<div class="big-button btn-update">', unsafe_allow_html=True)
        if st.button("📷\n소비기한 업데이트", use_container_width=True, key="btn_update"):
            st.switch_page("pages/expiry_update.py")
        st.markdown("</div>", unsafe_allow_html=True)

    with col4:
        # 버튼 4: 발주표 미리 등록
        st.markdown('<div class="big-button btn-preorder">', unsafe_allow_html=True)
        if st.button("📦\n발주표 미리 등록", use_container_width=True, key="btn_preorder"):
            st.switch_page("pages/preorder.py")
        st.markdown("</div>", unsafe_allow_html=True)

    # 설정 버튼 (하단)
    st.markdown("---")
    col_l, col_c, col_r = st.columns([1, 1, 1])
    with col_c:
        st.markdown('<div class="btn-settings">', unsafe_allow_html=True)
        if st.button("⚙️ 설정", use_container_width=True, key="btn_settings"):
            st.switch_page("pages/settings.py")
        st.markdown("</div>", unsafe_allow_html=True)


# ── 네비게이션 (사이드바 숨김) ──
_home_pg = st.Page(home_page, title="홈", default=True)

# 서브페이지에서 홈으로 돌아갈 수 있도록 세션에 저장
st.session_state["_home_pg"] = _home_pg

pg = st.navigation(
    [
        _home_pg,
        st.Page("pages/expiry_view.py", title="소비기한 관리"),
        st.Page("pages/invoice_register.py", title="식자재 입고 등록"),
        st.Page("pages/expiry_update.py", title="소비기한 업데이트"),
        st.Page("pages/preorder.py", title="발주표 미리 등록"),
        st.Page("pages/settings.py", title="설정"),
    ],
    position="hidden",
)
pg.run()
