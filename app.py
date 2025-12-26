import streamlit as st
import google_auth_oauthlib.flow
from googleapiclient.discovery import build

# --- 페이지 설정 ---
st.set_page_config(
    page_title="바코드 재고관리 시스템",
    page_icon="📦",
    layout="centered"
)

# --- 상수 및 설정 ---
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# --- 로그인 함수 (수정됨: 파일 대신 st.secrets 사용) ---
def login():
    # st.secrets에서 정보 가져와서 설정 딕셔너리 구성
    client_config = {
        "web": {
            "client_id": st.secrets["google_auth"]["client_id"],
            "client_secret": st.secrets["google_auth"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets["google_auth"]["redirect_uri"]], 
            # ↑ 구글 콘솔에 등록된 리다이렉트 URI와 일치해야 함
        }
    }

    # from_client_secrets_file 대신 from_client_config 사용
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config, 
        scopes=SCOPES
    )
    
    # 리다이렉트 URI 설정
    flow.redirect_uri = st.secrets["google_auth"]["redirect_uri"]

    # 인증 URL 생성
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    return authorization_url

# --- 메인 로직 ---
def main():
    # 세션 초기화
    if 'is_logged_in' not in st.session_state:
        st.session_state['is_logged_in'] = False

    # 로그아웃 버튼
    if st.session_state['is_logged_in']:
        if st.sidebar.button("로그아웃"):
            st.session_state['is_logged_in'] = False
            st.session_state.pop('credentials', None)
            st.session_state.pop('user_email', None)
            st.rerun()

    # --- 로그인 프로세스 ---
    if not st.session_state['is_logged_in']:
        st.title("🔒 접근 제한")
        st.warning("관계자 외 접근을 금지합니다.")

        # URL 쿼리 파라미터에서 code 확인 (로그인 성공 후 리다이렉트 되었을 때)
        if "code" in st.query_params:
            try:
                code = st.query_params["code"]
                
                # Flow 구성을 위해 secrets 정보 다시 로드
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
                    client_config, 
                    scopes=SCOPES
                )
                flow.redirect_uri = st.secrets["google_auth"]["redirect_uri"]
                
                # 토큰 교환
                flow.fetch_token(code=code)
                credentials = flow.credentials

                # 사용자 이메일 정보 가져오기
                service = build('oauth2', 'v2', credentials=credentials)
                user_info = service.userinfo().get().execute()
                email = user_info.get('email')

                # (선택사항) 특정 이메일만 허용하고 싶다면 여기서 검사
                # allowed_emails = ["admin@example.com"]
                # if email not in allowed_emails:
                #     st.error("접근 권한이 없는 계정입니다.")
                #     return

                # 세션에 저장
                st.session_state['credentials'] = credentials
                st.session_state['user_email'] = email
                st.session_state['is_logged_in'] = True
                
                # URL 정리 및 리런
                st.query_params.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"로그인 처리 중 오류 발생: {e}")
                # 로컬 디버깅용 (배포 시에는 주석 처리 권장)
                # st.write(e) 
        
        else:
            # 로그인 버튼 표시
            try:
                auth_url = login()
                st.markdown(f'''
                    <a href="{auth_url}" target="_self">
                        <button style="
                            background-color:#4285F4; 
                            color:white; 
                            border:none; 
                            padding:10px 20px; 
                            border-radius:5px; 
                            cursor:pointer; 
                            font-size:16px; 
                            font-weight:bold;">
                            Google 계정으로 로그인
                        </button>
                    </a>
                    ''', unsafe_allow_html=True)
            except Exception as e:
                st.error("Secrets 설정이 잘못되었습니다. Streamlit Cloud 설정을 확인해주세요.")
                
    else:
        # ---------------------------------------------------------
        # 여기서부터 로그인 성공 후 보여질 기존 앱 코드 (LOCK 해제)
        # ---------------------------------------------------------
        st.success(f"로그인 됨: {st.session_state['user_email']}")
        
        st.title("📦 바코드 재고관리 시스템")
        st.image("https://storage.googleapis.com/gweb-uniblog-publish-prod/images/Gemini_SS.width-1300.jpg",
                 caption="Powered by Gemini")

        st.markdown("""
        ### 시작하기
        왼쪽 사이드바에서 메뉴를 선택하여 작업을 시작하세요.
        """)
        
        # ... (이후 기존의 입고/출고/재고현황 로직들) ...
        # (기존 코드의 스프레드시트 연동 부분도 st.secrets를 사용하도록 수정 필요할 수 있음)

if __name__ == '__main__':
    main()
