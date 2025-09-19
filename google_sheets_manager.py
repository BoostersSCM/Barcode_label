import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Streamlit의 캐싱 기능을 사용하여 API 연결을 효율적으로 관리
@st.cache_resource
def connect_to_google_sheets():
    """Google Sheets API에 연결하고 클라이언트 객체를 반환합니다."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["google_sheets"], scopes=scopes
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Google Sheets 연결 실패: {e}")
        return None

def get_spreadsheet(client):
    """설정된 SPREADSHEET_ID로 스프레드시트 객체를 가져옵니다."""
    try:
        spreadsheet = client.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])
        return spreadsheet
    except Exception as e:
        st.error(f"스프레드시트를 여는 데 실패했습니다: {e}")
        return None

def get_worksheet(spreadsheet, sheet_name):
    """스프레드시트에서 특정 워크시트(탭)를 가져옵니다. 없으면 생성합니다."""
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        # 워크시트가 없으면 헤더와 함께 새로 생성
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
        if sheet_name == "재고_현황":
            headers = ["일련번호", "제품코드", "LOT", "유통기한", "버전", "보관위치", "상태", "입고일시", "출고일시", "출고처"]
        elif sheet_name == "입출고_기록":
            headers = ["타임스탬프", "유형", "일련번호", "제품코드", "제품명", "출고처"]
        else:
            headers = []
        
        if headers:
            worksheet.append_row(headers)
        return worksheet
    except Exception as e:
        st.error(f"워크시트 '{sheet_name}'을(를) 가져오는 데 실패했습니다: {e}")
        return None

def get_next_serial_number(worksheet):
    """'재고_현황' 시트에서 다음 일련번호를 생성합니다."""
    try:
        # A열(일련번호)의 모든 값을 가져옵니다.
        serials = worksheet.col_values(1)
        if len(serials) <= 1: # 헤더만 있는 경우
            return 1
        # 헤더를 제외한 마지막 숫자 값에 1을 더합니다.
        last_serial = int(serials[-1])
        return last_serial + 1
    except Exception as e:
        st.error(f"다음 일련번호 생성 실패: {e}")
        return None

def add_row(worksheet, data):
    """워크시트에 새로운 행을 추가합니다."""
    try:
        worksheet.append_row(data)
        return True
    except Exception as e:
        st.error(f"행 추가 실패: {e}")
        return False

def find_row_and_update(worksheet, serial_number, update_data):
    """일련번호로 행을 찾아 데이터를 업데이트합니다."""
    try:
        cell = worksheet.find(str(serial_number), in_column=1)
        if not cell:
            return "NOT_FOUND"

        row_index = cell.row
        current_status = worksheet.cell(row_index, 7).value # 7번째 열이 '상태'
        if current_status == "출고됨":
            return "ALREADY_SHIPPED"
        
        # 데이터 업데이트
        for col_name, value in update_data.items():
            # 헤더를 기준으로 열 인덱스 찾기
            headers = worksheet.row_values(1)
            if col_name in headers:
                col_index = headers.index(col_name) + 1
                worksheet.update_cell(row_index, col_index, value)
        
        return "SUCCESS"
    except Exception as e:
        st.error(f"행 업데이트 실패: {e}")
        return "ERROR"
