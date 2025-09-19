import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import io
from datetime import datetime
import google_sheets_manager as gsm

st.set_page_config(page_title="입고 처리", page_icon="📥")
st.title("📥 입고 (라벨 생성)")

# --- Mock 데이터 (실제로는 DB나 파일에서 로드) ---
PRODUCTS = {
    "PD001": "이퀄베리 콜라겐 앰플",
    "PD002": "마켓올슨 비타민C 세럼",
    "PD003": "브랜든 저분자 콜라겐"
}
LOCATIONS = [f"{zone}-{row:02d}-{col:02d}" for zone in 'AB' for row in range(1, 6) for col in range(1, 4)]

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

# --- 입력 폼 ---
with st.form("inbound_form"):
    st.subheader("제품 정보 입력")
    product_code = st.selectbox("제품코드", options=list(PRODUCTS.keys()), format_func=lambda x: f"{x} ({PRODUCTS[x]})")
    lot_number = st.text_input("LOT 번호")
    expiry_date = st.date_input("유통기한")
    version = st.text_input("버전", "1.0")
    location = st.selectbox("보관위치", options=LOCATIONS)
    
    submitted = st.form_submit_button("라벨 생성 및 입고 처리")

# --- 로직 처리 ---
if submitted:
    if not all([product_code, lot_number, expiry_date, version, location]):
        st.warning("모든 필드를 입력해주세요.")
    else:
        with st.spinner("처리 중..."):
            # 1. 다음 일련번호 생성
            serial_number = gsm.get_next_serial_number(inventory_ws)
            if serial_number is None:
                st.error("일련번호 생성에 실패했습니다.")
                st.stop()

            # 2. 바코드 이미지 생성 (메모리에서)
            barcode_class = barcode.get_barcode_class('code128')
            barcode_image_writer = barcode_class(str(serial_number), writer=ImageWriter())
            buffer = io.BytesIO()
            barcode_image_writer.write(buffer)
            
            # PIL로 이미지 열고 텍스트 추가
            barcode_img = Image.open(buffer)
            
            # 라벨 이미지 생성
            label_width, label_height = 400, 150
            label_img = Image.new('RGB', (label_width, label_height), 'white')
            
            # 바코드 붙여넣기
            barcode_img = barcode_img.resize((380, 80))
            label_img.paste(barcode_img, (10, 5))

            draw = ImageDraw.Draw(label_img)
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except IOError:
                font = ImageFont.load_default()
            
            product_name = PRODUCTS[product_code]
            expiry_str = expiry_date.strftime('%Y-%m-%d')
            info_text = f"{product_name} | LOT: {lot_number} | EXP: {expiry_str}"
            draw.text((10, 95), info_text, fill="black", font=font)
            draw.text((10, 115), f"S/N: {serial_number} | 보관위치: {location}", fill="black", font=font)

            st.success("라벨 생성 완료!")
            st.image(label_img, caption=f"생성된 라벨 (S/N: {serial_number})")

            # 다운로드용 이미지 버퍼
            img_byte_arr = io.BytesIO()
            label_img.save(img_byte_arr, format='PNG')
            
            st.download_button(
                label="🖨️ 라벨 이미지 다운로드",
                data=img_byte_arr.getvalue(),
                file_name=f"label_{serial_number}.png",
                mime="image/png"
            )

            # 3. 구글 시트에 데이터 기록
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 재고 현황 시트 업데이트
            inventory_data = [
                serial_number, product_code, lot_number, expiry_str, version, location,
                "재고", now_str, "", ""
            ]
            gsm.add_row(inventory_ws, inventory_data)

            # 입출고 기록 시트 업데이트
            history_data = [
                now_str, "입고", serial_number, product_code, product_name, ""
            ]
            gsm.add_row(history_ws, history_data)
            
            st.info("데이터베이스에 입고 내역이 기록되었습니다.")
