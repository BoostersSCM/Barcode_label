import streamlit as st
import pandas as pd
from datetime import datetime
from utils import db_manager
from sqlalchemy import text
import pytz
import time

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리")

if 'outbound_list' not in st.session_state:
    st.session_state.outbound_list = []

def add_item():
    code = st.session_state.get("barcode_input", "").strip()
    if not code:
        return
    if any(item['code'] == code for item in st.session_state.outbound_list):
        st.warning("이미 목록에 있습니다.")
    else:
        st.session_state.outbound_list.append({"code": code, "qty": 1})
    st.session_state.barcode_input = ""

st.text_input("바코드 스캔", key="barcode_input", on_change=add_item)
st.divider()
st.subheader("🛒 출고 목록")
for i, item in enumerate(st.session_state.outbound_list):
    st.write(f"- {item['code']} | 수량: {item['qty']}")
st.divider()

with st.form("out_form"):
    person = st.text_input("출고 담당자")
    submit = st.form_submit_button("✅ 출고 실행", type="primary")

if submit:
    if not st.session_state.outbound_list:
        st.warning("출고할 품목이 없습니다.")
        st.stop()
    if not person:
        st.warning("출고 담당자를 입력하세요.")
        st.stop()

    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')

    engine = db_manager.connect_to_mysql()
    success = 0
    for i, item in enumerate(st.session_state.outbound_list):
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE Retained_sample_status
                SET status='출고됨', outbound_datetime=:dt, outbound_person=:person
                WHERE serial_number=:sn
            """), {"dt": now, "person": person, "sn": item['code']})
        db_manager.insert_inout_record({
            "timestamp": now,
            "type": "출고",
            "serial_number": item['code'],
            "product_code": "",
            "product_name": "",
            "qty": item['qty'],
            "outbound_person": person
        })
        success += 1
        time.sleep(0.1)

    st.success(f"🚀 {success}건 출고 완료")
    st.session_state.outbound_list = []
