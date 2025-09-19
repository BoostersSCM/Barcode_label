import os
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

def get_korean_font(size):
    """프로젝트 내 폰트 파일을 로드합니다."""
    font_path = os.path.join("fonts", "NotoSansKR-Regular.otf")
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()

def create_barcode_image(serial_number, product_code, product_name, lot, expiry, version, location, category):
    """입력된 정보로 라벨 PIL Image 객체를 생성합니다."""
    barcode_class = barcode.get_barcode_class('code128')
    barcode_image = barcode_class(str(serial_number), writer=ImageWriter())
    barcode_pil_img = barcode_image.render({'write_text': False})
    
    LABEL_WIDTH, LABEL_HEIGHT = 480, 320
    label = Image.new('RGB', (LABEL_WIDTH, LABEL_HEIGHT), 'white')
    draw = ImageDraw.Draw(label)
    
    font_large, font_medium, font_small, font_tiny = get_korean_font(20), get_korean_font(16), get_korean_font(14), get_korean_font(12)
    
    y_pos, margin = 10, 15
    product_text = f"제품명: {product_name}"
    
    # 간단한 줄바꿈
    if len(product_text) > 28:
        try:
            split_point = product_text.rfind(' ', 0, 28)
            line1, line2 = product_text[:split_point], " " * 4 + product_text[split_point+1:]
            draw.text((margin, y_pos), line1, fill="black", font=font_large); y_pos += 22
            draw.text((margin, y_pos), line2, fill="black", font=font_large); y_pos += 22
        except:
            draw.text((margin, y_pos), product_text, fill="black", font=font_large); y_pos += 30
    else:
        draw.text((margin, y_pos), product_text, fill="black", font=font_large); y_pos += 30

    draw.text((margin, y_pos), f"구분: {category}", fill="black", font=font_medium); y_pos += 24
    draw.text((margin, y_pos), f"LOT: {lot}  유통기한: {expiry}  버전: {version}", fill="black", font=font_small); y_pos += 24
    draw.text((margin, y_pos), f"보관위치: {location}", fill="black", font=font_small)
    
    barcode_pil_img = barcode_pil_img.resize((LABEL_WIDTH - 40, 100))
    label.paste(barcode_pil_img, (10, LABEL_HEIGHT - 170))
    
    barcode_text = f"S/N: {serial_number} / {product_code}"
    text_bbox = draw.textbbox((0, 0), barcode_text, font=font_tiny)
    text_x = (LABEL_WIDTH - (text_bbox[2] - text_bbox[0])) // 2
    draw.text((text_x, LABEL_HEIGHT - 40), barcode_text, fill="black", font=font_tiny)
    
    return label
