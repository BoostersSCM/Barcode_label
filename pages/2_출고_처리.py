import streamlit as st
import pandas as pd
from datetime import datetime
from utils import google_sheets_manager as gsm, db_manager
import pytz # 시간대 라이브러리 import

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리 (일괄)")

# (이전 코드와 동일한 부분 생략)...

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
        # (이전 코드와 동일한 부분 생략)...
        progress_bar = st.progress(0, text="출고 처리 시작...")

        for i, item in enumerate(st.session_state.outbound_list):
            # 👇 한국 시간(KST) 기준으로 현재 시간 생성
            kst = pytz.timezone('Asia/Seoul')
            now_kst_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
            
            if item['type'] == 'S/N':
                update_data = {"상태": "출고됨", "출고일시": now_kst_str, "출고담당자": outbound_person}
                result = gsm.find_row_and_update(inventory_ws, item['code'], update_data)
                if result == "SUCCESS":
                    history_data = [now_kst_str, "출고", item['code'], item['product_code'], item['product_name'], 1, outbound_person]
                    gsm.add_row(history_ws, history_data)
                    success_count += 1
                else:
                    fail_count += 1
            
            elif item['type'] == '제품':
                history_data = [now_kst_str, "출고", "N/A", item['product_code'], item['product_name'], item['qty'], outbound_person]
                if gsm.add_row(history_ws, history_data):
                    success_count += 1
                else:
                    fail_count += 1
            # (이하 코드 동일)
