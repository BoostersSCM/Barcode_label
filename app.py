import streamlit as st

st.set_page_config(
    page_title="바코드 재고관리 시스템",
    page_icon="📦",
    layout="centered"
)

st.title("📦 바코드 재고관리 시스템")

st.markdown("""
### 시작하기

왼쪽 사이드바에서 메뉴를 선택하여 작업을 시작하세요.

- **입고 (라벨 생성)**: 새로운 제품을 입고하고 바코드 라벨을 생성합니다.
- **출고 (바코드 스캔)**: 바코드를 스캔하여 제품을 출고 처리합니다.
- **재고 현황**: 현재 재고 목록을 확인합니다.

---

**💡 사용 전 준비사항**

1.  `secrets.toml` 파일에 Google Cloud 서비스 계정 정보와 스프레드시트 ID를 설정해야 합니다.
2.  Google Sheets API와 Google Drive API가 활성화되어 있어야 합니다.
3.  서비스 계정 이메일에 대상 스프레드시트의 **편집자 권한**을 부여해야 합니다.
""")
