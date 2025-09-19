import streamlit as st
import pandas as pd
from datetime import datetime
from utils import google_sheets_manager as gsm
from utils import db_manager

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리")

# --- 데이터 로드 ---
product_df = db_manager.load_product_data()
if product_df.empty:
    st.error("데이터베이스에서 제품 정보를 불러올 수 없습니다. 설정을 확인하세요.")
    st.stop()

# --- 데이터 정제 (중복/빈 바코드 제거) ---
# 1. '바코드' 컬럼이 비어있거나(NaN, None) 공백만 있는 행을 제거합니다.
product_df.dropna(subset=['바코드'], inplace=True)
product_df = product_df[product_df['바코드'].astype(str).str.strip() != '']

# 2. 중복된 바코드가 있을 경우, 첫 번째 제품만 남기고 나머지는 제거합니다.
product_df.drop_duplicates(subset=['바코드'], keep='first', inplace=True)

# 이제 바코드 값은 고유하므로, 안전하게 딕셔너리를 생성할 수 있습니다.
barcode_map = product_df.set_index('바코드').to_dict('index')


# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()
if not client: st.stop()
spreadsheet = gsm.get_spreadsheet(client)
if not spreadsheet: st.stop()
inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
history_ws = gsm.get_worksheet(spreadsheet, "입출고_기록")
if not inventory_ws or not history_ws: st.stop()


# --- 출고 처리 폼 ---
st.info("여기에 라벨의 '일련번호' 또는 '제품 바코드(88...)'를 스캔하세요.")
scanned_code = st.text_input("스캔된 코드", key="barcode_input", placeholder="S/N 또는 88... 바코드")
destination = st.text_input("출고처", placeholder="예: 온라인 판매, 매장 이동")

if st.button("출고 처리 실행"):
    if not scanned_code or not destination:
        st.warning("스캔된 코드와 출고처를 모두 입력해주세요.")
    else:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        scanned_code = scanned_code.strip()

        with st.spinner(f"코드 '{scanned_code}' 처리 중..."):
            
            if scanned_code.isdigit():
                st.write("🔹 일련번호(S/N) 출고를 처리합니다 (재고 차감).")
                update_data = {"상태": "출고됨", "출고일시": now_str, "출고처": destination}
                result = gsm.find_row_and_update(inventory_ws, scanned_code, update_data)

                if result == "SUCCESS":
                    st.success(f"✅ 일련번호 '{scanned_code}'이(가) 정상적으로 출고 처리되었습니다.")
                    
                    product_code, product_name = "N/A", "N/A"
                    try:
                        cell = inventory_ws.find(scanned_code, in_column=1)
                        row_data = inventory_ws.row_values(cell.row)
                        headers = inventory_ws.row_values(1)
                        product_code = row_data[headers.index("제품코드")]
                        product_name = row_data[headers.index("제품명")]
                    except Exception:
                        st.warning("출고 기록 시 제품 정보를 찾지 못했지만, 출고 처리는 완료되었습니다.")

                    history_data = [now_str, "출고", scanned_code, product_code, product_name, destination]
                    gsm.add_row(history_ws, history_data)

                elif result == "NOT_FOUND": st.error(f"❌ 오류: 일련번호 '{scanned_code}'을(를) 찾을 수 없습니다.")
                elif result == "ALREADY_SHIPPED": st.warning(f"⚠️ 경고: 일련번호 '{scanned_code}'은(는) 이미 출고된 제품입니다.")
                else: st.error("❌ 처리 중 알 수 없는 오류가 발생했습니다.")

            elif scanned_code.startswith('88'):
                st.write("🔹 제품 바코드 출고를 처리합니다 (기록만 남김).")
                
                product_info = barcode_map.get(scanned_code)

                if product_info:
                    product_code = product_info.get('제품코드', 'N/A')
                    product_name = product_info.get('제품명', 'N/A')

                    history_data = [now_str, "출고", "N/A", product_code, product_name, destination]
                    if gsm.add_row(history_ws, history_data):
                        st.success(f"✅ 제품 '{product_name}'의 출고 기록이 추가되었습니다.")
                    else:
                        st.error("❌ 출고 기록 추가에 실패했습니다.")
                else:
                    st.error(f"❌ 오류: DB에 등록되지 않은 제품 바코드입니다: {scanned_code}")

            else:
                st.error("❌ 오류: 유효하지 않은 코드입니다. 일련번호(숫자) 또는 제품 바코드(88...)를 스캔하세요.")
