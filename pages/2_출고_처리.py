import streamlit as st
from datetime import datetime
from utils import db_manager
from sqlalchemy import text
import pytz
import time

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리")

if 'outbound_list' not in st.session_state:
    st.session_state.outbound_list = []

st.text_input("바코드 입력", key="barcode_input", placeholder="바코드 스캔 후 Enter")
st.divider()

st.subheader("출고 목록")
if not st.session_state.outbound_list:
    st.caption("스캔된 품목이 없습니다.")
else:
    for item in st.session_state.outbound_list:
        st.write(f"- {item['code']} (수량: {item['qty']})")

st.divider()

with st.form("out_form"):
    person = st.text_input("출고 담당자")
    submitted = st.form_submit_button("✅ 출고 실행", type="primary")

if submitted:
    if not person:
        st.warning("출고 담당자를 입력하세요.")
        st.stop()

    engine = db_manager.connect_to_scm()
    if engine is None:
        st.error("SCM DB 연결 실패")
        st.stop()

    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')

    for item in st.session_state.outbound_list:
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
            "qty": 1,
            "outbound_person": person
        })

    st.success("🚀 출고 완료! SCM DB에 반영되었습니다.")
