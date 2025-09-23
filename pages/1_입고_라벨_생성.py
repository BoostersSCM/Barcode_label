import streamlit as st
import io
from datetime import datetime, timedelta, date
import pandas as pd
from utils import db_manager, google_sheets_manager as gsm, barcode_generator
import pytz # 시간대 라이브러리 import

st.set_page_config(page_title="입고 처리", page_icon="📥")
st.title("📥 입고 (라벨 생성)")

# (이전 코드와 동일한 부분 생략)...

# --- 로직 처리 ---
if submitted:
    if category != "샘플재고" and not all([product_code, lot_number, expiry_date, version, location]):
        st.warning("모든 필드를 입력해주세요.")
    elif not all([product_code, location]):
         st.warning("제품코드와 보관위치는 필수입니다.")
    else:
        with st.spinner("라벨 생성 및 데이터 기록 중..."):
            serial_number = gsm.get_next_serial_number(inventory_ws)
            if serial_number is None: st.stop()
            
            product_name = PRODUCTS.get(product_code, "알 수 없는 제품")
            
            if isinstance(expiry_date, date):
                expiry_str = expiry_date.strftime('%Y-%m-%d')
                disposal_date = expiry_date + timedelta(days=365)
                disposal_date_str = disposal_date.strftime('%Y-%m-%d')
            else:
                expiry_str, disposal_date_str = "N/A", "N/A"

            label_img = barcode_generator.create_barcode_image(
                serial_number, product_code, product_name, lot_number, expiry_str, version, location, category
            )

            st.success("라벨 생성 완료!")
            st.image(label_img, caption=f"생성된 라벨 (S/N: {serial_number})")

            img_buffer = io.BytesIO()
            label_img.save(img_buffer, format='PNG')
            st.download_button("🖨️ 라벨 이미지 다운로드 (인쇄용)", img_buffer.getvalue(), f"label_{serial_number}.png", "image/png")

            # 👇 한국 시간(KST) 기준으로 현재 시간 생성
            kst = pytz.timezone('Asia/Seoul')
            now_kst_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
            
            inventory_data = [
                serial_number, category, product_code, product_name, lot_number,
                expiry_str, disposal_date_str, location, version, now_kst_str,
                "재고", "", ""
            ]
            gsm.add_row(inventory_ws, inventory_data)

            history_data = [now_kst_str, "입고", serial_number, product_code, product_name, 1, ""] # 입고 시 담당자 없음
            gsm.add_row(history_ws, history_data)
            
            st.info("스프레드시트에 입고 내역이 기록되었습니다.")
