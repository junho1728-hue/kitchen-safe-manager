import streamlit as st

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
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] .big-button button {
    height: 25vh;
    font-size: 2.2rem;
    font-weight: 700;
    border-radius: 16px;
    margin: 6px 0;
    transition: transform 0.1s;
}
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] .big-button button:active {
    transform: scale(0.97);
}

/* 버튼 색상 개별 지정 */
.btn-expiry button { background: linear-gradient(135deg, #0d47a1, #1565c0) !important; color: #fff !important; border: none !important; }
.btn-expiry button:hover { background: linear-gradient(135deg, #1565c0, #1976d2) !important; }
.btn-register button { background: linear-gradient(135deg, #1b5e20, #2e7d32) !important; color: #fff !important; border: none !important; }
.btn-register button:hover { background: linear-gradient(135deg, #2e7d32, #388e3c) !important; }
.btn-update button { background: linear-gradient(135deg, #e65100, #ef6c00) !important; color: #fff !important; border: none !important; }
.btn-update button:hover { background: linear-gradient(135deg, #ef6c00, #f57c00) !important; }

/* 설정 버튼 */
.btn-settings button { background: transparent !important; border: 1px solid #555 !important; color: #aaa !important; }

/* 전역 버튼 최소 터치 타겟 */
.stButton > button { min-height: 52px; font-size: 1.1rem; }

/* 페이지 헤더 스타일 */
.page-header { font-size: 1.8rem; font-weight: 700; margin-bottom: 1rem; }
</style>
""",
    unsafe_allow_html=True,
)


# ── 페이지 정의 ──
def home_page():
    """메인 화면: 3대 대형 버튼 + 설정"""
    st.markdown(
        "<h1 style='text-align:center; margin-bottom:0.2em;'>🍳 주방 위생 안심 매니저</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#888; margin-bottom:1.5em;'>소비기한 관리 · 식자재 입고 · 라벨 보관</p>",
        unsafe_allow_html=True,
    )

    # 버튼 1: 소비기한 관리
    with st.container():
        st.markdown('<div class="big-button btn-expiry">', unsafe_allow_html=True)
        if st.button("🔍  소비기한 관리", use_container_width=True, key="btn_expiry"):
            st.switch_page("pages/expiry_view.py")
        st.markdown("</div>", unsafe_allow_html=True)

    # 버튼 2: 식자재 입고 등록
    with st.container():
        st.markdown('<div class="big-button btn-register">', unsafe_allow_html=True)
        if st.button("📋  식자재 입고 등록", use_container_width=True, key="btn_register"):
            st.switch_page("pages/invoice_register.py")
        st.markdown("</div>", unsafe_allow_html=True)

    # 버튼 3: 소비기한 업데이트
    with st.container():
        st.markdown('<div class="big-button btn-update">', unsafe_allow_html=True)
        if st.button("📷  소비기한 업데이트", use_container_width=True, key="btn_update"):
            st.switch_page("pages/expiry_update.py")
        st.markdown("</div>", unsafe_allow_html=True)

    # 설정 버튼 (하단)
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown('<div class="btn-settings">', unsafe_allow_html=True)
        if st.button("⚙️ 설정", use_container_width=True, key="btn_settings"):
            st.switch_page("pages/settings.py")
        st.markdown("</div>", unsafe_allow_html=True)


# ── 네비게이션 (사이드바 숨김) ──
pg = st.navigation(
    [
        st.Page(home_page, title="홈", default=True),
        st.Page("pages/expiry_view.py", title="소비기한 관리"),
        st.Page("pages/invoice_register.py", title="식자재 입고 등록"),
        st.Page("pages/expiry_update.py", title="소비기한 업데이트"),
        st.Page("pages/settings.py", title="설정"),
    ],
    position="hidden",
)
pg.run()
