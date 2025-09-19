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

def wrap_text(draw, text, font, max_width):
    """
    텍스트가 최대 너비를 초과하면 자동으로 줄바꿈하여 리스트로 반환합니다.
    공백 없는 긴 텍스트도 글자 단위로 잘라 처리합니다.
    """
    lines = []
    
    if draw.textlength(text, font) <= max_width:
        return [text]

    current_line = ""
    for char in text:
        if draw.textlength(current_line + char, font) <= max_width:
            current_line += char
        else:
            lines.append(current_line)
            current_line = char
    
    if current_line:
        lines.append(current_line)
        
    return lines

def create_barcode_image(serial_number, product_code, product_name, lot, expiry, version, location, category):
    """입력된 정보로 30x20mm 사이즈의 라벨 PIL Image 객체를 생성합니다."""
    barcode_class = barcode.get_barcode_class('code128')
    barcode_image = barcode_class(str(serial_number), writer=ImageWriter())
    barcode_pil_img = barcode_image.render({'write_text': False})

    LABEL_WIDTH, LABEL_HEIGHT = 480, 320
    label = Image.new('RGB', (LABEL_WIDTH, LABEL_HEIGHT), 'white')
    draw = ImageDraw.Draw(label)

    # 👇👇👇 폰트 크기 전체적으로 상향 조정 👇👇👇
    font_large = get_korean_font(26)   # 제품명 (20 -> 26)
    font_medium = get_korean_font(22)  # 구분 (16 -> 22)
    font_small = get_korean_font(18)   # 상세정보 (14 -> 18)
    font_tiny = get_korean_font(14)    # 바코드 하단 (12 -> 14)

    # --- 라벨 내용 그리기 ---
    y_pos, margin = 10, 15
    
    prefix = "제품명: "
    prefix_width = draw.textlength(prefix, font=font_large)
    
    wrapped_lines = wrap_text(draw, product_name, font_large, LABEL_WIDTH - margin * 2 - prefix_width)

    # 최대 2줄까지만 표시
    for i, line in enumerate(wrapped_lines[:2]):
        if i == 0:
            draw.text((margin, y_pos), prefix + line, fill="black", font=font_large)
        else:
            draw.text((margin + prefix_width, y_pos), line, fill="black", font=font_large)
        y_pos += 28 # 👇 줄 간격 조정

    y_pos += 8 # 추가 간격
    draw.text((margin, y_pos), f"구분: {category}", fill="black", font=font_medium); y_pos += 28 # 👇 줄 간격 조정
    draw.text((margin, y_pos), f"LOT: {lot} | 유통기한: {expiry}", fill="black", font=font_small); y_pos += 24 # 👇 줄 간격 조정
    draw.text((margin, y_pos), f"보관위치: {location} | 버전: {version}", fill="black", font=font_small)

    barcode_pil_img = barcode_pil_img.resize((LABEL_WIDTH - 40, 80)) # 바코드 높이 소폭 조정
    label.paste(barcode_pil_img, (10, LABEL_HEIGHT - 140)) # 바코드 위치 조정
    
    barcode_text = f"{product_code}-{lot}-{expiry}-{version}"
    text_x = (LABEL_WIDTH - draw.textlength(barcode_text, font=font_tiny)) // 2
    draw.text((text_x, LABEL_HEIGHT - 35), barcode_text, fill="black", font=font_tiny)
    
    return label
