# pages/2_출고_처리.py

import streamlit as st
from datetime import datetime
from utils import db_manager
from sqlalchemy import text
import pytz

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리")

# --- DB 연결 ---
scm_engine = db_manager.connect_to_scm()

# --- 세션 상태 초기화 ---
if 'outbound_list' not in st.session_state:
    st.session_state.outbound_list = []

# --- 바코드 스캔 처리 콜백 함수 ---
def process_barcode():
    barcode = st.session_state.barcode_input
    if not barcode:
        return

    # 중복 스캔 방지
    if any(item['serial_number'] == barcode for item in st.session_state.outbound_list):
        st.warning(f"이미 목록에 있는 품목입니다: {barcode}")
        return

    if scm_engine:
        details = db_manager.get_inventory_details(scm_engine, barcode)
        if details:
            item_info = {
                "serial_number": barcode,
                "product_code": details.get('product_code', 'N/A'),
                "product_name": details.get('product_name', 'N/A')
            }
            st.session_state.outbound_list.append(item_info)
        else:
            st.error(f"DB에 존재하지 않는 S/N입니다: {barcode}")
    else:
        st.error("DB가 연결되지 않아 바코드를 처리할 수 없습니다.")
    
    # 입력 필드 초기화
    st.session_state.barcode_input = ""

# --- UI ---
st.text_input(
    "바코드 입력",
    key="barcode_input",
    placeholder="바코드 스캔 후 Enter",
    on_change=process_barcode,
    label_visibility="collapsed"
)
st.divider()

st.subheader("📦 출고 목록")
if not st.session_state.outbound_list:
    st.caption("스캔된 품목이 없습니다.")
else:
    for item in st.session_state.outbound_list:
        st.write(f"- S/N: {item['serial_number']} ({item['product_name']})")

st.divider()

with st.form("out_form"):
    person = st.text_input("출고 담당자")
    submitted = st.form_submit_button("✅ 출고 실행", type="primary", use_container_width=True)

if submitted:
    if not person:
        st.warning("출고 담당자를 입력하세요.")
    elif not st.session_state.outbound_list:
        st.warning("출고할 품목을 스캔하세요.")
    elif scm_engine is None:
        st.error("SCM DB 연결 실패")
    else:
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
        success_count = 0

        with st.spinner('출고 처리 중...'):
            for item in st.session_state.outbound_list:
                # 1. 재고 상태 업데이트
                update_query = text("""
                    UPDATE Retained_sample_status
                    SET status='출고됨', outbound_datetime=:dt, outbound_person=:person
                    WHERE serial_number=:sn AND status='재고'
                """)
                with scm_engine.begin() as conn:
                    result = conn.execute(update_query, {"dt": now, "person": person, "sn": item['serial_number']})

                if result.rowcount > 0:
                    # 2. 입출고 이력 기록
                    inout_data = {
                        "timestamp": now, "type": "출고", "serial_number": item['serial_number'],
                        "product_code": item['product_code'], "product_name": item['product_name'],
                        "qty": 1, "outbound_person": person
                    }
                    db_manager.insert_inout_record(scm_engine, inout_data)
                    success_count += 1

        st.success(f"🚀 {success_count}개 품목 출고 완료!")
        st.session_state.outbound_list = [] # 출고 목록 초기화
        st.experimental_rerun()
