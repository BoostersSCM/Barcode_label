# pages/1_입고_라벨_생성.py

import streamlit as st
from datetime import datetime, timedelta, date
import pandas as pd
from utils import db_manager, barcode_generator
import pytz

st.set_page_config(page_title="입고 처리", page_icon="📥")
st.title("📥 입고 (라벨 생성)")

# --- DB 연결 (페이지 로드 시 1회 수행) ---
erp_engine = db_manager.connect_to_boosters()
scm_engine = db_manager.connect_to_scm()

# --- 제품 데이터 로드 ---
product_df = db_manager.load_product_data(erp_engine)
if product_df.empty:
    st.error("제품정보 DB에서 데이터를 불러올 수 없습니다.")
    st.stop()

PRODUCTS = pd.Series(product_df.제품명.values, index=product_df.제품코드).to_dict()
PRODUCT_CODES = list(PRODUCTS.keys())

# --- UI ---
st.subheader("제품 정보 입력")
with st.form("inbound_form"):
    product_code = st.selectbox("📦 제품", options=PRODUCT_CODES, format_func=lambda x: f"{x} ({PRODUCTS.get(x, 'N/A')})")
    location = st.text_input("보관위치 (예: A-01-01)")
    category = st.selectbox("구분", ["관리품", "표준품", "벌크표준", "샘플재고"])

    if category == "샘플재고":
        lot_number, expiry_date, version = "SAMPLE", "N/A", "N/A"
        st.text_input("LOT", value=lot_number, disabled=True)
    else:
        lot_number = st.text_input("LOT 번호")
        expiry_date = st.date_input("유통기한", value=datetime.now().date() + timedelta(days=365 * 3))
        version = st.text_input("버전", value="R0")

    submitted = st.form_submit_button("라벨 생성 및 입고 처리")

# --- 처리 ---
if submitted:
    if not all([product_code, location, lot_number]):
        st.warning("제품, 보관위치, LOT 번호는 필수입니다.")
    elif scm_engine is None:
        st.error("SCM DB에 연결할 수 없어 처리를 중단합니다.")
    else:
        serial_number = int(datetime.now().timestamp() * 1000)
        product_name = PRODUCTS.get(product_code, "알 수 없는 제품")
        expiry_str = expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, date) else "N/A"
        disposal_date_str = (expiry_date + timedelta(days=365)).strftime('%Y-%m-%d') if isinstance(expiry_date, date) else "N/A"
        kst = pytz.timezone('Asia/Seoul')
        now_kst_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')

        # 바코드 생성
        label_img = barcode_generator.create_barcode_image(serial_number, product_code, product_name, lot_number, expiry_str, version, location, category)
        st.image(label_img, caption=f"S/N: {serial_number}")

        # --- DB 저장 ---
        inventory_data = {
            "serial_number": serial_number, "category": category, "product_code": product_code,
            "product_name": product_name, "lot": lot_number, "expiry": expiry_str,
            "disposal_date": disposal_date_str, "location": location, "version": version,
            "inbound_datetime": now_kst_str, "status": "재고", "outbound_datetime": "", "outbound_person": ""
        }
        inout_data = {
            "timestamp": now_kst_str, "type": "입고", "serial_number": serial_number,
            "product_code": product_code, "product_name": product_name, "qty": 1, "outbound_person": ""
        }

        if db_manager.insert_inventory_record(scm_engine, inventory_data) and \
           db_manager.insert_inout_record(scm_engine, inout_data):
            st.success("✅ 입고 완료! SCM DB에 저장되었습니다.")
        else:
            st.error("DB 저장 중 오류가 발생했습니다.")
