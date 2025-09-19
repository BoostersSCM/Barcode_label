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
    except Exception as e:
        st.error(f"워크시트 '{sheet_name}' 처리 실패: {e}")
        return None

def get_next_serial_number(worksheet):
    """'재고_현황' 시트에서 다음 일련번호를 생성합니다."""
    try:
        serials_raw = worksheet.col_values(1)
        numeric_serials = [int(s) for s in serials_raw[1:] if s and str(s).isdigit()]
        last_serial = max(numeric_serials) if numeric_serials else 0
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
        if not cell: return "NOT_FOUND"
        
        row_index = cell.row
        headers = worksheet.row_values(1)
        
        status_col_index = headers.index("상태") + 1
        if worksheet.cell(row_index, status_col_index).value == "출고됨": return "ALREADY_SHIPPED"
        
        for col_name, value in update_data.items():
            if col_name in headers:
                col_index = headers.index(col_name) + 1
                worksheet.update_cell(row_index, col_index, value)
        return "SUCCESS"
    except Exception as e:
        st.error(f"행 업데이트 실패: {e}")
        return "ERROR"

def delete_rows_by_serial(worksheet, serials_to_delete):
    """'재고_현황' 시트에서 제공된 일련번호 목록에 해당하는 행들을 삭제합니다."""
    if not serials_to_delete:
        return True, 0
    
    try:
        all_serials = worksheet.col_values(1)
        rows_to_delete_indices = []
        for serial in serials_to_delete:
            try:
                # gspread는 1-based index, 리스트는 0-based
                row_index = all_serials.index(str(serial)) + 1
                rows_to_delete_indices.append(row_index)
            except ValueError:
                continue
        
        if not rows_to_delete_indices:
            return True, 0
            
        # 행 인덱스를 역순으로 정렬하여 삭제 시 인덱스 변경 문제를 방지
        rows_to_delete_indices.sort(reverse=True)
        
        for row_index in rows_to_delete_indices:
            worksheet.delete_rows(row_index)
            
        return True, len(rows_to_delete_indices)

    except Exception as e:
        st.error(f"행 삭제 실패: {e}")
        return False, 0
