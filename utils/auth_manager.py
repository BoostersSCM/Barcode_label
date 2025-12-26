# utils/auth_manager.py (새로 생성)
import streamlit as st
import google_auth_oauthlib.flow
from googleapiclient.discovery import build

# --- 설정 ---
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def get_flow():
    """OAuth Flow 객체를 생성하여 반환합니다."""
    # st.secrets에서 설정 로드
    client_config = {
        "web": {
            "client_id": st.secrets["google_auth"]["client_id"],
            "client_secret": st.secrets["google_auth"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets["google_auth"]["redirect_uri"]],
        }
    }
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config, scopes=SCOPES
    )
    flow.redirect_uri = st.secrets["google_auth"]["redirect_uri"]
    return flow

def _handle_login_flow():
    """로그인 프로세스(토큰 교환 등)를 처리합니다."""
    # URL에 code가 있으면(로그인 직후 리다이렉트) 토큰 교환 시도
    if "code" in st.query_params:
        try:
            code = st.query_params["code"]
            flow = get_flow()
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # 사용자 정보 가져오기
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            # 세션에 저장
            st.session_state['credentials'] = credentials
            st.session_state['user_email'] = user_info.get('email')
            st.session_state['is_logged_in'] = True
            
            # URL 파라미터 정리 및 리런
            st.query_params.clear()
            st.rerun()
            return True
        except Exception as e:
            st.error(f"로그인 처리 중 오류 발생: {e}")
            return False
            
    # 로그인 버튼 표시
    flow = get_flow()
    auth_url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    
    st.markdown(f'''
        <a href="{auth_url}" target="_self">
            <button style="padding:10px 20px; background-color:#4285F4; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">
                Google 계정으로 로그인
            </button>
        </a>
    ''', unsafe_allow_html=True)
    return False

def require_auth(is_home=False):
    """
    모든 페이지의 최상단에서 호출해야 하는 함수입니다.
    - 로그인 상태: 사이드바에 로그아웃 버튼 표시 후 통과
    - 비로그인 상태: 
        - is_home=True (메인): 로그인 버튼 표시
        - is_home=False (서브): 경고 메시지 표시 및 실행 중단
    """
    # 세션 초기화
    if "is_logged_in" not in st.session_state:
        st.session_state["is_logged_in"] = False

    # 1. 로그인 된 경우: 사이드바에 로그아웃 버튼 표시하고 함수 종료(통과)
    if st.session_state["is_logged_in"]:
        st.sidebar.write(f"👤 {st.session_state.get('user_email', '')}")
        if st.sidebar.button("로그아웃", key="logout_btn_common"):
            st.session_state["is_logged_in"] = False
            st.session_state.pop('credentials', None)
            st.session_state.pop('user_email', None)
            st.rerun()
        return  # 인증 통과, 페이지 내용 렌더링 진행

    # 2. 로그인 안 된 경우
    st.title("🔒 접근 제한")
    
    if is_home:
        st.warning("시스템 사용을 위해 로그인이 필요합니다.")
        _handle_login_flow() # 로그인 버튼 표시 및 처리
    else:
        st.warning("로그인이 필요합니다. 메인 페이지에서 로그인해주세요.")
        st.info("왼쪽 사이드바 상단의 [app] 또는 [메인] 페이지로 이동하세요.")
    
    st.stop() # 이후 코드 실행 차단
