import streamlit as st
import pandas as pd
from datetime import datetime
from utils import google_sheets_manager as gsm, db_manager
import time

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리 (일괄)")

# --- 세션 상태 초기화 ---
if 'outbound_list' not in st.session_state:
    # 출고할 아이템들을 담을 리스트
    st.session_state.outbound_list = []

# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()
if not client: st.stop()
spreadsheet = gsm.get_spreadsheet(client)
if not spreadsheet: st.stop()
inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
history_ws = gsm.get_worksheet(spreadsheet, "입출고_기록")
if not inventory_ws or not history_ws: st.stop()


# --- 콜백 함수 (바코드 스캔 처리) ---
def add_item_to_outbound_list():
    scanned_code = st.session_state.get("barcode_scan_input", "").strip()
    if not scanned_code:
        return

    # 이미 목록에 있는 일련번호인지 확인
    if any(item['code'] == scanned_code for item in st.session_state.outbound_list):
        st.warning(f"이미 목록에 추가된 코드입니다: {scanned_code}")
        st.session_state.barcode_scan_input = "" # 입력 필드 초기화
        return

    item_to_add = None
    # 일련번호(S/N) 스캔 시
    if scanned_code.isdigit():
        item_to_add = {"type": "S/N", "code": scanned_code, "product_name": f"일련번호-{scanned_code}", "product_code": "N/A", "qty": 1}
    # 제품 바코드(88...) 스캔 시
    elif scanned_code.startswith('88'):
        product_info = db_manager.find_product_info_by_barcode(scanned_code)
        if product_info:
            item_to_add = {
                "type": "제품",
                "code": scanned_code,
                "product_name": product_info.get('resource_name', 'N/A'),
                "product_code": product_info.get('resource_code', 'N/A'),
                "qty": 1
            }
        else:
            st.error(f"DB에 등록되지 않은 제품 바코드입니다: {scanned_code}")
    else:
        st.error(f"유효하지 않은 코드입니다: {scanned_code}")

    if item_to_add:
        st.session_state.outbound_list.insert(0, item_to_add) # 새 항목을 맨 위에 추가
    
    # 입력 필드 초기화
    st.session_state.barcode_scan_input = ""


# --- UI 구성 ---
st.info("바코드를 스캔하면 아래 '출고 목록'에 자동으로 추가됩니다.")

st.text_input(
    "스캔 입력",
    key="barcode_scan_input",
    on_change=add_item_to_outbound_list,
    placeholder="여기에 바코드를 연속으로 스캔하세요"
)

st.divider()

st.subheader("🛒 출고 목록")

if not st.session_state.outbound_list:
    st.caption("스캔된 품목이 없습니다.")
else:
    # 목록 아이템 UI
    for i, item in enumerate(st.session_state.outbound_list):
        col1, col2, col3 = st.columns([5, 2, 1])
        
        with col1:
            st.write(f"**{item['product_name']}**")
            st.caption(f"유형: {item['type']} | 코드: {item['code']}")
        
        with col2:
            # S/N의 경우 수량 변경 불가
            is_disabled = item['type'] == 'S/N'
            # 각 아이템의 수량은 st.session_state.outbound_list[i]['qty']에 저장됨
            new_qty = st.number_input(
                "수량", 
                min_value=1, 
                value=item['qty'], 
                step=1, 
                key=f"qty_{item['code']}", # 각 위젯을 구분하기 위한 고유 키
                disabled=is_disabled
            )
            st.session_state.outbound_list[i]['qty'] = new_qty
        
        with col3:
            # UI 정렬을 위해 빈 공간 추가
            st.write("") 
            if st.button("삭제", key=f"del_{item['code']}", type="secondary"):
                st.session_state.outbound_list.pop(i)
                st.rerun()

# --- 최종 처리 폼 ---
st.divider()

with st.form("process_form"):
    st.subheader("최종 출고 처리")
    outbound_person = st.text_input("출고담당자", placeholder="예: 홍길동")
    submitted = st.form_submit_button("✅ 일괄 출고 처리 실행", type="primary")

if submitted:
    if not st.session_state.outbound_list:
        st.warning("출고할 품목이 없습니다. 바코드를 먼저 스캔해주세요.")
    elif not outbound_person:
        st.warning("출고담당자를 입력해주세요.")
    else:
        success_count = 0
        fail_count = 0
        total_items = len(st.session_state.outbound_list)
        
        progress_bar = st.progress(0, text="출고 처리 시작...")

        for i, item in enumerate(st.session_state.outbound_list):
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if item['type'] == 'S/N':
                update_data = {"상태": "출고됨", "출고일시": now_str, "출고담당자": outbound_person}
                result = gsm.find_row_and_update(inventory_ws, item['code'], update_data)
                if result == "SUCCESS":
                    history_data = [now_str, "출고", item['code'], item['product_code'], item['product_name'], 1, outbound_person]
                    gsm.add_row(history_ws, history_data)
                    success_count += 1
                else:
                    fail_count += 1
            
            elif item['type'] == '제품':
                history_data = [now_str, "출고", "N/A", item['product_code'], item['product_name'], item['qty'], outbound_person]
                if gsm.add_row(history_ws, history_data):
                    success_count += 1
                else:
                    fail_count += 1

            progress_bar.progress((i + 1) / total_items, text=f"({i+1}/{total_items}) {item['product_name']} 처리 중...")
            time.sleep(0.1)

        progress_bar.empty()
        st.success(f"🚀 일괄 출고 처리 완료! 성공: {success_count}건, 실패: {fail_count}건")
        
        st.session_state.outbound_list = []
        time.sleep(1)
        st.rerun()
