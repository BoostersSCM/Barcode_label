import os
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

@st.cache_data
def get_korean_font(size):
    """
    프로젝트에 포함된 한글 폰트를 로드합니다.
    Streamlit Cloud 환경에서 안정적으로 작동하도록 설계되었습니다.
    """
    font_path = os.path.join("fonts", "NotoSansKR-Regular.ttf")
    try:
        font = ImageFont.truetype(font_path, size)
        print(f"폰트 로드 성공: {font_path}")
        return font
    except Exception as e:
        st.error(f"🚨 폰트 파일 로드 실패! 'fonts/NotoSansKR-Regular.ttf' 파일이 있는지 확인하세요. 오류: {e}")
        return ImageFont.load_default()

def create_barcode_image(serial_number, product_code, product_name, lot, expiry, version, location, category):
    """입력된 정보로 30x20mm 사이즈의 라벨 PIL Image 객체를 생성합니다."""
    barcode_class = barcode.get_barcode_class('code128')
    barcode_image = barcode_class(str(serial_number), writer=ImageWriter())
    barcode_pil_img = barcode_image.render({'write_text': False})

    # 30x20mm 비율 (고해상도)
    LABEL_WIDTH, LABEL_HEIGHT = 480, 320
    label = Image.new('RGB', (LABEL_WIDTH, LABEL_HEIGHT), 'white')
    draw = ImageDraw.Draw(label)

    # 폰트 로드
    font_large = get_korean_font(20)
    font_medium = get_korean_font(16)
    font_small = get_korean_font(14)
    font_tiny = get_korean_font(12)

    # --- 라벨 내용 그리기 ---
    y_pos, margin = 10, 15
    product_text = f"제품명: {product_name}"
    
    # 간단한 줄바꿈 로직
    if draw.textlength(product_text, font=font_large) > LABEL_WIDTH - (margin * 2):
        try:
            split_point = product_text.rfind(' ', 0, 28)
            if split_point == -1: split_point = 25
            line1 = product_text[:split_point]
            line2 = " " * 4 + product_text[split_point+1:]
            draw.text((margin, y_pos), line1, fill="black", font=font_large); y_pos += 22
            draw.text((margin, y_pos), line2, fill="black", font=font_large); y_pos += 22
        except:
            draw.text((margin, y_pos), product_text, fill="black", font=font_large); y_pos += 30
    else:
        draw.text((margin, y_pos), product_text, fill="black", font=font_large); y_pos += 30
    
    draw.text((margin, y_pos), f"구분: {category}", fill="black", font=font_medium); y_pos += 24
    draw.text((margin, y_pos), f"LOT: {lot} | 유통기한: {expiry}", fill="black", font=font_small); y_pos += 22
    draw.text((margin, y_pos), f"보관위치: {location} | 버전: {version}", fill="black", font=font_small)

    # 바코드 이미지 배치
    barcode_pil_img = barcode_pil_img.resize((LABEL_WIDTH - 40, 100))
    label.paste(barcode_pil_img, (10, LABEL_HEIGHT - 170))
    
    # 👇 요청하신 형식으로 하단 텍스트 변경
    barcode_text = f"{product_code}-{lot}-{expiry}-{version}"
    text_x = (LABEL_WIDTH - draw.textlength(barcode_text, font=font_tiny)) // 2
    draw.text((text_x, LABEL_HEIGHT - 40), barcode_text, fill="black", font=font_tiny)
    
    return label
