import streamlit as st
from datetime import datetime
import google_sheets_manager as gsm

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 (바코드 스캔)")

# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()

if client:
    spreadsheet = gsm.get_spreadsheet(client)
    if spreadsheet:
        inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
        history_ws = gsm.get_worksheet(spreadsheet, "입출고_기록")
    else:
        st.stop()
else:
    st.stop()

# --- 출고 처리 폼 ---
st.info("여기에 바코드 스캐너로 라벨의 일련번호를 스캔하세요.")
scanned_serial = st.text_input("스캔된 일련번호", key="barcode_input")
destination = st.text_input("출고처 (예: 온라인 판매, 매장 이동)")

if st.button("출고 처리 실행"):
    if not scanned_serial or not destination:
        st.warning("일련번호와 출고처를 모두 입력해주세요.")
    else:
        with st.spinner(f"일련번호 '{scanned_serial}' 처리 중..."):
            
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_data = {
                "상태": "출고됨",
                "출고일시": now_str,
                "출고처": destination
            }
            
            result = gsm.find_row_and_update(inventory_ws, scanned_serial, update_data)

            if result == "SUCCESS":
                st.success(f"✅ 일련번호 '{scanned_serial}'이(가) 정상적으로 출고 처리되었습니다.")
                
                # 입출고 기록 추가
                # 제품 정보를 재고 시트에서 다시 찾아야 함
                try:
                    cell = inventory_ws.find(scanned_serial, in_column=1)
                    product_code = inventory_ws.cell(cell.row, 2).value
                    # (실제 앱에서는 PRODUCTS 딕셔너리를 DB에서 가져와야 함)
                    product_name = "제품명 조회 필요" 
                except:
                    product_code = "N/A"
                    product_name = "N/A"

                history_data = [
                    now_str, "출고", scanned_serial, product_code, product_name, destination
                ]
                gsm.add_row(history_ws, history_data)

            elif result == "NOT_FOUND":
                st.error(f"❌ 오류: 일련번호 '{scanned_serial}'을(를) 찾을 수 없습니다.")
            elif result == "ALREADY_SHIPPED":
                st.warning(f"⚠️ 경고: 일련번호 '{scanned_serial}'은(는) 이미 출고 처리된 제품입니다.")
            else:
                st.error("❌ 처리 중 알 수 없는 오류가 발생했습니다.")
