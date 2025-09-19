import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

@st.cache_resource
def connect_to_google_sheets():
    """Google Sheets API에 연결하고 클라이언트 객체를 반환합니다."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["google_sheets"], scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Google Sheets 연결 실패: {e}. 'secrets.toml' 설정과 API 권한을 확인하세요.")
        return None

def get_spreadsheet(_client):
    """설정된 SPREADSHEET_ID로 스프레드시트 객체를 가져옵니다."""
    try:
        spreadsheet = _client.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])
        return spreadsheet
    except Exception as e:
        st.error(f"스프레드시트를 열 수 없습니다: {e}. ID와 공유 설정을 확인하세요.")
        return None

def get_worksheet(spreadsheet, sheet_name):
    """스프레드시트에서 특정 워크시트를 가져오거나 새로 생성합니다."""
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
        headers = []
        if sheet_name == "재고_현황":
            headers = ["일련번호", "구분", "제품코드", "제품명", "LOT", "유통기한", "폐기기한", "보관위치", "버전", "입고일시", "상태", "출고일시", "출고처"]
        elif sheet_name == "입출고_기록":
            headers = ["타임스탬프", "유형", "일련번호", "제품코드", "제품명", "출고처"]
        if headers:
            worksheet.append_row(headers)
        return worksheet
    except Exception
