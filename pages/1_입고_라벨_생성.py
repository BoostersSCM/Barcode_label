import streamlit as st
import io
from datetime import datetime, timedelta
import pandas as pd
from utils import db_manager, google_sheets_manager as gsm, barcode_generator

st.set_page_config(page_title="입고 처리", page_icon="📥")
st.title("📥 입고 (라벨 생성)")

# --- 데이터 로드 ---
product_df = db_manager.load_product_data()
if product_df.empty:
    st.error("데이터베이스에서 제품 정보를 불러올 수 없습니다. 설정을 확인하세요.")
    st.stop()
PRODUCTS = pd.Series(product_df.제품명.values, index=product_df.제품코드).to_dict()
LOCATIONS = [f"{zone}-{row:02d}-{col:02d}" for zone in 'ABCDE' for row in range(1, 6) for col in range(1, 4)]

# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()
if not client: st.stop()
spreadsheet = gsm.get_spreadsheet(client)
if not spreadsheet: st.stop()
inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
history_ws = gsm.get_worksheet(spreadsheet, "입출고_기록")
if not inventory_ws or not history_ws: st.stop()

# --- 입력 폼 ---
with st.form("inbound_form"):
    st.subheader("제품 정보 입력")
    product_code = st.selectbox("제품", options=list(PRODUCTS.keys()), format_func=lambda x: f"{x} ({PRODUCTS.get(x, '알수없음')})")
    location = st.selectbox("보관위치", options=LOCATIONS)
    category = st.selectbox("구분", ["관리품", "표준품", "벌크표준", "샘플재고"])

    # 👇 '구분' 선택에 따라 UI를 동적으로 변경
    if category == "샘플재고":
        st.info("샘플재고는 LOT, 유통기한, 버전이 자동으로 설정됩니다.")
        lot_number = "SAMPLE"
        expiry_date = "N/A"
        version = "N/A"
        
        # 비활성화된 필드로 자동 설정된 값 보여주기
        st.text_input("LOT 번호", value=lot_number, disabled=True)
        st.text_input("유통기한", value=expiry_date, disabled=True)
        st.text_input("버전", value=version, disabled=True)
        
    else: # 관리품, 표준품, 벌크표준의 경우
        lot_number = st.text_input("LOT 번호")
        default_expiry_date = datetime.now().date() + timedelta(days=365 * 3)
        expiry_date = st.date_input("유통기한", value=default_expiry_date)
        version = st.text_input("버전", value="R0")

    submitted = st.form_submit_button("라벨 생성 및 입고 처리")

# --- 로직 처리 ---
if submitted:
    # 샘플재고가 아닐 경우에만 빈 값인지 확인
    if category != "샘플재고" and not all([product_code, lot_number, expiry_date, version, location]):
        st.warning("모든 필드를 입력해주세요.")
    elif not all([product_code, location]):
         st.warning("제품코드와 보관위치는 필수입니다.")
    else:
        with st.spinner("라벨 생성 및 데이터 기록 중..."):
            serial_number = gsm.get_next_serial_number(inventory_ws)
            if serial_number is None: st.stop()
            
            product_name = PRODUCTS.get(product_code, "알 수 없는 제품")
            
            # 유통기한 및 폐기일자 처리
            if isinstance(expiry_date, datetime.date):
                expiry_str = expiry_date.strftime('%Y-%m-%d')
                disposal_date = expiry_date + timedelta(days=365)
                disposal_date_str = disposal_date.strftime('%Y-%m-%d')
            else: # 샘플재고의 경우 "N/A"
                expiry_str = "N/A"
                disposal_date_str = "N/A"

            label_img = barcode_generator.create_barcode_image(
                serial_number, product_code, product_name, lot_number, expiry_str, version, location, category
            )

            st.success("라벨 생성 완료!")
            st.image(label_img, caption=f"생성된 라벨 (S/N: {serial_number})")

            img_buffer = io.BytesIO()
            label_img.save(img_buffer, format='PNG')
            st.download_button("🖨️ 라벨 이미지 다운로드 (인쇄용)", img_buffer.getvalue(), f"label_{serial_number}.png", "image/png")

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            inventory_data = [
                serial_number, category, product_code, product_name, lot_number,
                expiry_str, disposal_date_str, location, version, now_str,
                "재고", "", ""
            ]
            gsm.add_row(inventory_ws, inventory_data)

            history_data = [now_str, "입고", serial_number, product_code, product_name, ""]
            gsm.add_row(history_ws, history_data)
            
            st.info("스프레드시트에 입고 내역이 기록되었습니다.")
