# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, ttk
from tkcalendar import DateEntry
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
# 바코드 라이브러리 추가
import barcode
from barcode.writer import ImageWriter
import qrcode
import os
import time
import re
import subprocess
import sys
import argparse
from datetime import datetime
import base64
import io
import json
import sqlite3

# 상위 디렉토리의 execute_query.py 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execute_query import call_query
from mysql_auth import boosta_boosters
from boosters_query import q_boosters_items_for_barcode_reader, q_boosters_items_limit_date


# ✅ CSV/엑셀에서 제품 리스트 불러오기
def load_products():
    try:
        df = call_query(q_boosters_items_for_barcode_reader.query,boosta_boosters)
        df_limit_date = call_query(q_boosters_items_limit_date.query,boosta_boosters)
        df = pd.merge(df, df_limit_date, on='제품코드', how='left')
        products_dict = dict(zip(df['제품코드'].astype(str), df['제품명']))
        
        # 바코드 정보도 함께 로드 (바코드 컬럼이 있는 경우)
        barcode_dict = {}
        if '바코드' in df.columns:
            for _, row in df.iterrows():
                barcode = str(row['바코드']).strip()
                if barcode and barcode != 'nan':
                    barcode_dict[barcode] = str(row['제품코드'])
        
        # 유통기한 정보도 함께 로드
        expiry_info_dict = {}
        for _, row in df.iterrows():
            product_code = str(row['제품코드'])
            expiry_days = row.get('유통기한_일수')
            expiry_unit = row.get('유통기한_구분')
            
            if expiry_days is not None and expiry_unit is not None and str(expiry_days) != 'nan' and str(expiry_unit) != 'nan':
                expiry_info_dict[product_code] = {
                    'days': expiry_days,
                    'unit': expiry_unit
                }
        
        return products_dict, barcode_dict, expiry_info_dict
    except Exception as e:
        print(f"데이터베이스 연결 실패: {e}")
        # 기본 데이터 반환
        return {"TEST001": "테스트 제품"}, {}, {}

# products, barcode_to_product = load_products("barcode_label/products.xlsx")  # 올바른 경로
products, barcode_to_product, expiry_info = load_products()  
# 보관위치 검증 함수
def validate_location(location):
    """
    보관위치 형식 검증: 알파벳(A,B) + 숫자2자리(01~05) + 숫자2자리(01~03)
    예: A-01-01, B-03-02
    """
    pattern = r'^[AB]-(0[1-5])-(0[1-3])$'
    if not re.match(pattern, location):
        return False, "보관위치 형식이 올바르지 않습니다.\n\n형식: 알파벳(A,B) + 숫자2자리(01~05) + 숫자2자리(01~03)\n예시: A-01-01, B-03-02"
    
    return True, ""

# 바코드 리딩 처리 함수
def process_barcode_scan(barcode_data):
    """바코드 스캔 처리 (일련번호 바코드 지원)"""
    barcode_data = barcode_data.strip()
    
    # 일련번호 바코드 처리 (숫자만 있는 경우)
    if barcode_data.isdigit():
        return process_serial_barcode(barcode_data)
    
    # 기존 제품 바코드 처리 (88로 시작하는 경우)
    if barcode_data.startswith('88'):
        if barcode_data in barcode_to_product:
            product_code = barcode_to_product[barcode_data]
            combo_code.set(product_code)
            update_product_name()
            return True
        else:
            messagebox.showwarning("바코드 오류", f"등록되지 않은 제품 바코드입니다: {barcode_data}")
            return False
    
    # 기존 라벨 바코드 처리 (제품코드-LOT-유통기한 형식)
    match = re.match(r'^([A-Z][0-9]{3})-([A-Z0-9]+)-(\d{4}-\d{2}-\d{2})$', barcode_data)
    if match:
        product_code, lot, expiry_date = match.groups()
        combo_code.set(product_code.upper())
        update_product_name()
        return True
    
    # 일반 제품코드 입력으로 처리
    combo_code.set(barcode_data.upper())
    update_product_name()
    return True

def check_barcode_completion():
    """
    바코드 입력 완료 여부 확인
    보관위치와 제품코드가 모두 입력되면 True 반환
    """
    location = entry_location.get().strip()
    product_code = combo_code.get().strip()
    
    # 보관위치가 올바른 형식이고 제품코드가 선택되었는지 확인
    is_valid_location, _ = validate_location(location)
    has_product = product_code and product_code in products
    
    return is_valid_location and has_product

def show_next_barcode_prompt(current_type, next_type):
    """
    다음 바코드 입력을 유도하는 메시지 표시
    """
    if next_type == "제품":
        messagebox.showinfo("바코드 스캔 완료", 
                          f"✅ {current_type} 바코드 스캔 완료\n\n"
                          f"다음 단계: 제품 바코드를 스캔하세요\n"
                          f"제품 바코드는 '88'로 시작합니다.")
        combo_code.focus()
    else:  # next_type == "보관위치"
        messagebox.showinfo("바코드 스캔 완료", 
                          f"✅ {current_type} 바코드 스캔 완료\n\n"
                          f"다음 단계: 보관위치 바코드를 스캔하세요\n"
                          f"보관위치 형식: A-01-01, B-03-02")
        entry_location.focus()

def update_barcode_status(status_text, color="#2196F3"):
    """
    바코드 리딩 창의 상태 표시 업데이트
    """
    try:
        # 바코드 리딩 창이 열려있는지 확인하고 상태 업데이트
        for widget in root.winfo_children():
            if isinstance(widget, tk.Toplevel) and widget.title() == "바코드 리딩":
                for child in widget.winfo_children():
                    if isinstance(child, tk.Frame):
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, tk.Label) and "📋" in grandchild.cget("text"):
                                grandchild.config(text=status_text, fg=color)
                                break
    except:
        pass  # 창이 닫혀있거나 오류가 발생해도 무시

# 발행 내역 저장 함수
def save_issue_history(product_code, lot, expiry, location, filename, category):
    try:
        # 발행 내역 파일 경로
        history_file = os.path.join(os.path.dirname(__file__), "issue_history.xlsx")
        # 파일이 없으면 디렉토리 생성 및 빈 파일 생성
        if not os.path.exists(history_file):
            os.makedirs(os.path.dirname(history_file), exist_ok=True)
            # 빈 DataFrame으로 엑셀 파일 생성
            empty_df = pd.DataFrame({
                '발행일시': [],
                '구분': [],
                '제품코드': [],
                '제품명': [],
                'LOT': [],
                '유통기한': [],
                '폐기일자': [],
                '보관위치': [],
                '파일명': []
            })
            empty_df.to_excel(history_file, index=False)
        
        # 폐기일자 계산 (유통기한 + 1년)
        try:
            # 유통기한이 이미 datetime 객체인 경우
            if isinstance(expiry, datetime):
                expiry_date = expiry
            else:
                # 문자열인 경우 파싱
                expiry_date = datetime.strptime(str(expiry), "%Y-%m-%d")
            
            # 1년 후 날짜 계산
            disposal_date = expiry_date.replace(year=expiry_date.year + 1)
            disposal_date_str = disposal_date.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"폐기일자 계산 오류: {e}, 유통기한: {expiry}")
            disposal_date_str = "N/A"
        
        # 기존 파일이 있으면 읽고, 없으면 새로 생성
        try:
            df_history = pd.read_excel(history_file)
        except FileNotFoundError:
            df_history = pd.DataFrame({
                '발행일시': [],
                '제품코드': [],
                '제품명': [],
                'LOT': [],
                '유통기한': [],
                '폐기일자': [],
                '보관위치': [],
                '파일명': []
            })
        
        # 새 발행 내역 추가
        product_name = products.get(product_code, "알 수 없는 제품")
        new_row = {
            '발행일시': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            '구분': category,
            '제품코드': product_code,
            '제품명': product_name,
            'LOT': lot,
            '유통기한': expiry,
            '폐기일자': disposal_date_str,
            '보관위치': location,
            '파일명': filename
        }
        
        df_history = pd.concat([df_history, pd.DataFrame([new_row])], ignore_index=True)
        df_history.to_excel(history_file, index=False)
        
        print(f"발행 내역이 {history_file}에 저장되었습니다.")
        
    except Exception as e:
        print(f"발행 내역 저장 중 오류: {e}")

# 미리보기 함수
def show_preview(label_image, filename, product_code, lot, expiry, location, category):
    try:
        print(f"미리보기 창 생성 시작: {filename}")
        # 미리보기 창 생성
        preview_window = tk.Toplevel()
        preview_window.title("라벨 미리보기")
        preview_window.geometry("800x700")  # 4배 해상도 라벨에 맞게 크기 조정
        
        # 제목
        title_label = tk.Label(preview_window, text="생성된 라벨 미리보기", 
                               font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=10)
        
        # 라벨 정보
        info_frame = tk.Frame(preview_window)
        info_frame.pack(pady=5)
        
        tk.Label(info_frame, text=f"구분: {category}", font=("맑은 고딕", 10)).pack()
        tk.Label(info_frame, text=f"제품코드: {product_code}", font=("맑은 고딕", 10)).pack()
        tk.Label(info_frame, text=f"LOT: {lot}", font=("맑은 고딕", 10)).pack()
        tk.Label(info_frame, text=f"유통기한: {expiry}", font=("맑은 고딕", 10)).pack()
        tk.Label(info_frame, text=f"보관위치: {location}", font=("맑은 고딕", 10)).pack()
        tk.Label(info_frame, text=f"파일명: {filename}", font=("맑은 고딕", 10)).pack()
        
        # 스크롤 가능한 캔버스 생성
        canvas_frame = tk.Frame(preview_window)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 캔버스와 스크롤바
        canvas = tk.Canvas(canvas_frame, bg="white")
        v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 라벨 이미지 표시
        temp_preview = "temp_preview.png"
        label_image.save(temp_preview)
        
        # 이미지 로드 및 크기 조정
        img = tk.PhotoImage(file=temp_preview)
        
        # 이미지 크기 조정 (원본 크기 유지)
        img_width = img.width()
        img_height = img.height()
        
        # 캔버스에 이미지 추가
        canvas.create_image(0, 0, anchor=tk.NW, image=img)
        # 참조 유지를 위해 전역 변수로 저장 (미리보기 창에 저장)
        preview_window.image = img
        
        # 스크롤 영역 설정
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # 스크롤바 배치
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 버튼 프레임
        button_frame = tk.Frame(preview_window)
        button_frame.pack(pady=20)
        
        # 인쇄 버튼
        def print_label():
            try:
                os.startfile(filename, "print")
                time.sleep(2)
                messagebox.showinfo("인쇄 완료", "라벨이 프린터로 전송되었습니다.\n\n💡 인쇄 팁:\n- 인쇄 창에서 '크기 조정' 옵션을 '실제 크기'로 설정하세요\n- '여백'을 '없음'으로 설정하면 더 깔끔하게 인쇄됩니다")
                preview_window.destroy()
            except Exception as e:
                messagebox.showerror("인쇄 오류", f"인쇄 실패: {e}")
        
        print_btn = tk.Button(button_frame, text="인쇄", command=print_label,
                              bg="#4CAF50", fg="white", font=("맑은 고딕", 11),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        print_btn.pack(side=tk.LEFT, padx=5)
        
        # 닫기 버튼
        def close_preview():
            try:
                os.remove(temp_preview)  # 임시 파일 삭제
            except:
                pass
            preview_window.destroy()
        
        close_btn = tk.Button(button_frame, text="닫기", command=close_preview,
                              bg="#f44336", fg="white", font=("맑은 고딕", 11),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        close_btn.pack(side=tk.LEFT, padx=5)
        
        # 창이 닫힐 때 임시 파일 삭제
        preview_window.protocol("WM_DELETE_WINDOW", close_preview)
        
        print("미리보기 창 생성 완료")
        
    except Exception as e:
        print(f"미리보기 창 생성 중 오류: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("미리보기 오류", f"미리보기 창을 생성할 수 없습니다:\n{e}")

def create_label(product_code, lot, expiry, location, category):
    # 제품명 조회
    product_name = products.get(product_code, "알 수 없는 제품")

    # 일련번호 생성 및 라벨 정보 저장
    serial_number = save_label_info(product_code, lot, expiry, location, category)
    
    # 바코드 데이터는 일련번호만 사용
    barcode_data = str(serial_number)

    # 라벨 캔버스 생성 (40mm x 30mm 용지, 4배 확대된 해상도)
    LABEL_WIDTH = 640  # 가로 (40mm * 4 * 4 = 640px)
    LABEL_HEIGHT = 480  # 세로 (30mm * 4 * 4 = 480px)
    label = Image.new('RGB', (LABEL_WIDTH, LABEL_HEIGHT), 'white')
    draw = ImageDraw.Draw(label)
    
    # 한글 폰트 설정 (4배 확대된 해상도에 맞춰 폰트 크기 조정)
    try:
        font = ImageFont.truetype("malgun.ttf", 28)  # 기본 폰트 (7 * 4)
        font_small = ImageFont.truetype("malgun.ttf", 20)  # 작은 폰트 (5 * 4)
        font_large = ImageFont.truetype("malgun.ttf", 28)  # 제품코드용 (7 * 4)
        font_product = ImageFont.truetype("malgun.ttf", 24)  # 제품명용 (6 * 4)
        font_info = ImageFont.truetype("malgun.ttf", 24)  # LOT/유통기한용 (6 * 4)
    except:
        try:
            font = ImageFont.truetype("gulim.ttc", 28)
            font_small = ImageFont.truetype("gulim.ttc", 20)
            font_large = ImageFont.truetype("gulim.ttc", 28)  # 제품코드용 (7 * 4)
            font_product = ImageFont.truetype("gulim.ttc", 24)  # 제품명용 (6 * 4)
            font_info = ImageFont.truetype("gulim.ttc", 24)  # LOT/유통기한용 (6 * 4)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_large = ImageFont.load_default()
            font_product = ImageFont.load_default()
            font_info = ImageFont.load_default()

    # 텍스트 줄바꿈 함수 (라벨 크기에 맞게 개선) - draw 객체 정의 후에 이동
    def wrap_text(text, max_width):
        if not text:
            return []
        
        # 한글과 영문이 섞인 경우를 고려하여 하이브리드 처리
        lines = []
        current_line = ""
        
        # 한글과 영문을 구분하여 처리
        for char in text:
            test_line = current_line + char
            
            # 현재 폰트로 텍스트 너비 측정 (제품명 폰트 사용)
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font_product)
                text_width = bbox[2] - bbox[0]
            except:
                # 폰트 측정이 실패하면 대략적인 계산
                if ord(char) > 127:  # 한글인 경우
                    text_width = len(test_line) * 13
                else:  # 영문인 경우
                    text_width = len(test_line) * 9
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        return lines

    # 제품명 줄바꿈 (4배 확대된 해상도에 맞춰 조정)
    # "제품명: " 부분을 고려하여 실제 제품명만 줄바꿈 처리
    label_prefix = "제품명: "
    prefix_width = draw.textbbox((0, 0), label_prefix, font=font_product)[2] - draw.textbbox((0, 0), "", font=font_product)[0]
    available_width = LABEL_WIDTH - 40 - prefix_width  # 좌우 여백 조정 (10 * 4)
    
    product_name_lines = wrap_text(product_name, available_width)
    
    y_pos = 15  # 상단 여백 조정 (약 4 * 4)
    for i, line in enumerate(product_name_lines):
        if i == 0:
            draw.text((20, y_pos), f"제품명: {line}", fill="black", font=font_product)
        else:
            # 들여쓰기로 정렬 (제품명: 과 같은 위치에서 시작)
            draw.text((20 + prefix_width, y_pos), line, fill="black", font=font_product)
        y_pos += 32  # 줄 간격 조정 (8 * 4)
    
    # LOT과 유통기한을 같은 줄에 배치
    lot_expiry_text = f"LOT: {lot}    유통기한: {expiry}"
    draw.text((20, y_pos), lot_expiry_text, fill="black", font=font_info)
    
    # 보관위치는 LOT 행 아래에 배치 (간격 조정)
    draw.text((20, y_pos + 30), f"보관위치: {location}", fill="black", font=font_info)

    # 바코드 생성 및 추가
    try:
        # Code128 바코드 생성 (더 인식하기 쉬운 형식)
        barcode_class = barcode.get_barcode_class('code128')
        barcode_image = barcode_class(barcode_data, writer=ImageWriter())
        
        # 바코드 이미지 생성
        barcode_img = barcode_image.render()
        
        # 바코드 크기 조정 (4배 확대된 해상도에 맞춰 조정, 높이 증가로 인식성 향상)
        barcode_width = LABEL_WIDTH - 40  # 좌우 여백 조정 (약 10 * 4)
        barcode_height = 200  # 바코드 높이 조정 (더 큰 바코드로 인식성 향상)
        
        # 바코드 이미지 리사이즈
        barcode_img = barcode_img.resize((barcode_width, barcode_height), Image.Resampling.LANCZOS)
        
        # 바코드를 더 아래쪽에 배치 (보관위치 텍스트가 보이도록)
        barcode_x = 5  # 좌측 여백 조정 (약 1.25 * 4)
        barcode_y = LABEL_HEIGHT - barcode_height - 10  # 하단 여백 조정 (약 2.5 * 4)
        
        # 바코드 이미지를 라벨에 붙이기
        label.paste(barcode_img, (barcode_x, barcode_y))
        
        # 바코드 아래 텍스트 (제품코드-LOT-유통기한 형식)
        barcode_text = f"{product_code}-{lot}-{expiry}"
        draw.text((20, LABEL_HEIGHT - 80), barcode_text, fill="black", font=font_small)
        
    except Exception as e:
        print(f"바코드 생성 실패: {e}")
        # Code128 실패 시 Code39로 재시도
        try:
            barcode_class = barcode.get_barcode_class('code39')
            barcode_image = barcode_class(barcode_data, writer=ImageWriter())
            barcode_img = barcode_image.render()
            barcode_img = barcode_img.resize((LABEL_WIDTH - 40, 200), Image.Resampling.LANCZOS)
            label.paste(barcode_img, (5, LABEL_HEIGHT - 200 - 10))
        except Exception as e2:
            print(f"Code39 바코드 생성도 실패: {e2}")
            # 바코드 생성 실패 시 텍스트만 표시
            draw.text((20, LABEL_HEIGHT - 80), f"바코드: {barcode_data}", fill="black", font=font_small)
            # 제품 정보 텍스트도 표시
            barcode_text = f"{product_code}-{lot}-{expiry}"
            draw.text((20, LABEL_HEIGHT - 60), barcode_text, fill="black", font=font_small)

    # labeljpg 폴더 생성 및 확인
    labeljpg_dir = "labeljpg"
    if not os.path.exists(labeljpg_dir):
        os.makedirs(labeljpg_dir)
    
    # 라벨 저장 (파일명: 제품코드-보관위치.jpg)
    filename = os.path.join(labeljpg_dir, f"{product_code}-{location}.jpg")
    
    # 파일 저장
    label.save(filename)
    
    # 발행 내역 저장
    save_issue_history(product_code, lot, expiry, location, filename, category)
    
    return label, filename

def image_to_zpl(image_path, label_width=240, label_height=160):
    try:
        # 이미지 로드 및 리사이즈
        img = Image.open(image_path)
        img = img.resize((label_width, label_height))
        
        # 이미지를 1비트 흑백으로 변환
        img = img.convert('1')
        
        # 이미지를 바이트로 변환
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_bytes = buffer.getvalue()
        
        # Base64 인코딩
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # ZPL 코드 생성 (이미지 포함)
        zpl_code = f"""^XA
^PW{label_width}
^LL{label_height}
^GFA,{len(img_bytes)},{len(img_bytes)},{label_width},{img_base64}
^XZ"""
        return zpl_code
    except Exception as e:
        print(f"이미지 ZPL 변환 오류: {e}")
        return None

def create_zpl_label(product_code, lot, expiry, location, category):
    # 제품명 조회
    product_name = products.get(product_code, "Unknown Product")
    
    # 일련번호 생성 및 라벨 정보 저장
    serial_number = save_label_info(product_code, lot, expiry, location, category)
    
    # 바코드 데이터는 일련번호만 사용
    barcode_data = str(serial_number)
    
    # 영문 ZPL 코드 생성 (40mm x 30mm 용지, 4배 확대된 해상도, Code128 바코드 사용)
    zpl_code = f"""^XA
^PW640
^LL480
^FO25,25^A0N,24,24^FDProduct: {product_name}^FS
^FO25,90^A0N,24,24^FDLOT: {lot}    Expiry: {expiry}^FS
^FO25,200^A0N,24,24^FDLocation: {location}^FS
^FO5,240^BY40^B2N,1200,Y,N,N^FD{barcode_data}^FS
^FO25,440^A0N,20,20^FD{product_code}-{lot}-{expiry}^FS
^XZ"""
    return zpl_code

def save_zpl_file(zpl_code, product_code, lot, expiry, location):
    """ZPL 코드를 파일로 저장"""
    # zpl 폴더 생성
    zpl_dir = "zpl"
    if not os.path.exists(zpl_dir):
        os.makedirs(zpl_dir)
    
    # ZPL 파일 저장
    filename = os.path.join(zpl_dir, f"{product_code}-{location}.zpl")
    with open(filename, "w", encoding='utf-8') as f:
        f.write(zpl_code)
    
    return filename

def update_category_ui():
    """구분에 따라 UI 업데이트"""
    category = category_var.get()
    
    if category == "관리품":
        # 관리품일 때 LOT과 유통기한 표시
        lot_label.pack(pady=5)
        entry_lot.pack(pady=5)
        expiry_label.pack(pady=5)
        expiry_frame.pack(pady=5)
        entry_expiry.pack(side=tk.LEFT, padx=(0, 10))
        
        # 관리품으로 전환 시 기본값 설정
        entry_lot.delete(0, tk.END)
        entry_lot.insert(0, "")
        entry_expiry.delete(0, tk.END)
        entry_expiry.insert(0, "")
        
        # 제품코드 초기화
        combo_code.set("")
        label_product_name.config(text="제품명: ")
        
        # 포커스를 제품코드 입력창으로 이동
        combo_code.focus()
        
    else:
        # 샘플재고일 때 LOT과 유통기한 숨김
        lot_label.pack_forget()
        entry_lot.pack_forget()
        expiry_label.pack_forget()
        expiry_frame.pack_forget()
        entry_expiry.pack_forget()
        
        # 샘플재고로 전환 시 기본값 설정
        entry_lot.delete(0, tk.END)
        entry_lot.insert(0, "SAMPLE")
        entry_expiry.delete(0, tk.END)
        entry_expiry.insert(0, "N/A")
        
        # 제품코드 초기화
        combo_code.set("")
        label_product_name.config(text="제품명: ")
        
        # 포커스를 제품코드 입력창으로 이동
        combo_code.focus()

def update_product_name(event=None):
    code = combo_code.get().upper()  # 소문자를 대문자로 변환
    name = products.get(code, "알 수 없는 제품")
    
    # 유통기한 정보 표시
    expiry_text = ""
    if code in expiry_info:
        expiry_data = expiry_info[code]
        expiry_days = expiry_data['days']
        expiry_unit = expiry_data['unit']
        if expiry_days is not None and expiry_unit is not None and str(expiry_days) != 'nan' and str(expiry_unit) != 'nan':
            expiry_text = f" {expiry_days} {expiry_unit}"
    
    label_product_name.config(text=f"제품명: {name}")
    
    # 유통기한 라벨 업데이트
    expiry_label.config(text=f"유통기한:{expiry_text}")
    
    # 유통기한 기본값 설정
    if code in expiry_info:
        expiry_data = expiry_info[code]
        expiry_days = expiry_data['days']
        expiry_unit = expiry_data['unit']
        
        if expiry_days is not None and expiry_unit is not None and str(expiry_days) != 'nan' and str(expiry_unit) != 'nan':
            try:
                # 오늘 날짜에서 30일을 뺀 후 유통기한을 더함
                from datetime import datetime, timedelta
                today = datetime.now()
                base_date = today - timedelta(days=30)
                
                # 유통기한 계산
                if expiry_unit == '월':
                    # 월 단위 계산 (대략 30일로 계산)
                    calculated_days = int(expiry_days) * 30
                elif expiry_unit == '일':
                    calculated_days = int(expiry_days)
                else:
                    calculated_days = 0
                
                if calculated_days > 0:
                    expiry_date = base_date + timedelta(days=calculated_days)
                    entry_expiry.delete(0, tk.END)
                    entry_expiry.insert(0, expiry_date.strftime("%Y-%m-%d"))
            except Exception as e:
                print(f"유통기한 계산 오류: {e}")

def on_submit():
    try:
        print("라벨 생성 시작...")
        product_code = combo_code.get().upper()  # 소문자를 대문자로 변환
        category = category_var.get()
        location = location_var.get()
        
        print(f"입력된 데이터: 제품코드={product_code}, 구분={category}, 보관위치={location}")
    
        # 기본 입력 검증
        if not product_code or not location:
            messagebox.showwarning("경고", "제품코드와 보관위치를 입력하세요.")
            return
        
        # 관리품일 때만 LOT과 유통기한 검증
        if category == "관리품":
            lot = entry_lot.get()
            expiry = entry_expiry.get()
            if not lot or not expiry:
                messagebox.showwarning("경고", "관리품은 LOT과 유통기한을 모두 입력하세요.")
                return
        else:
            # 샘플재고일 때는 기본값 설정
            lot = "SAMPLE"
            expiry = "N/A"
        
        print(f"검증된 데이터: LOT={lot}, 유통기한={expiry}")
            
        # 보관위치 형식 검증
        is_valid, error_message = validate_location(location)
        if not is_valid:
            messagebox.showerror("보관위치 오류", error_message)
            location_combo.focus()
            return
        
        print("라벨 생성 함수 호출...")
        # 라벨 생성
        label_image, filename = create_label(product_code, lot, expiry, location, category)
        print(f"라벨 생성 완료: {filename}")
        
        # ZPL 코드 생성
        zpl_code = create_zpl_label(product_code, lot, expiry, location, category)
        zpl_filename = save_zpl_file(zpl_code, product_code, lot, expiry, location)
        print(f"ZPL 파일 생성 완료: {zpl_filename}")
        
        print("미리보기 창 표시...")
        # 미리보기 창 표시
        show_preview(label_image, filename, product_code, lot, expiry, location, category)
        print("미리보기 창 표시 완료")

        # 발행 완료 메시지
        messagebox.showinfo("완료", f"라벨({filename})이 생성되었습니다!\n발행 내역이 자동으로 저장되었습니다.\n\n미리보기 창에서 인쇄하실 수 있습니다.")
        print("라벨 생성 프로세스 완료")
        
    except Exception as e:
        print(f"라벨 생성 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("오류", f"라벨 생성 중 오류가 발생했습니다:\n{e}")

# ✅ Tkinter GUI 생성
root = tk.Tk()
root.title("바코드 라벨 관리 시스템 - 라벨 발행")
root.geometry("600x500")

# 명령행 인수 처리
parser = argparse.ArgumentParser(description='라벨 발행 GUI')
parser.add_argument('--location', type=str, help='보관위치 설정')
args, unknown = parser.parse_known_args()

# 전역 바코드 리딩 단축키 (Ctrl+B) - 제품코드 필드로 포커스
def open_barcode_global(event):
    combo_code.focus()
    messagebox.showinfo("바코드 리딩", "제품코드 필드에 바코드를 스캔하세요.\n\n💡 팁:\n- 각 입력창에서 Enter 키를 누르면 바코드가 처리됩니다\n- 자동으로 다음 필드로 이동합니다")

root.bind('<Control-b>', open_barcode_global)
root.bind('<Control-B>', open_barcode_global)

# 구분 선택
tk.Label(root, text="구분:").pack(pady=5)
category_var = tk.StringVar(value="관리품")
category_frame = tk.Frame(root)
category_frame.pack(pady=5)

# 라디오 버튼으로 구분 선택
management_radio = tk.Radiobutton(category_frame, text="관리품", variable=category_var, value="관리품",
                                  font=("맑은 고딕", 10), command=lambda: refresh_ui_for_management())
management_radio.pack(side=tk.LEFT, padx=10)

sample_radio = tk.Radiobutton(category_frame, text="샘플재고", variable=category_var, value="샘플재고",
                              font=("맑은 고딕", 10), command=lambda: refresh_ui_for_sample())
sample_radio.pack(side=tk.LEFT, padx=10)

def refresh_ui_for_management():
    """관리품 선택 시 UI 새로고침"""
    update_category_ui()
    # 관리품 관련 안내 메시지
    messagebox.showinfo("관리품 모드", 
                       "✅ 관리품 모드로 전환되었습니다.\n\n"
                       "📋 관리품은 다음 정보가 필요합니다:\n"
                       "• 제품코드\n"
                       "• LOT 번호\n"
                       "• 유통기한\n"
                       "• 보관위치\n\n"
                       "모든 필드를 입력한 후 라벨을 생성하세요.")

def refresh_ui_for_sample():
    """샘플재고 선택 시 UI 새로고침"""
    update_category_ui()
    # 샘플재고 관련 안내 메시지
    messagebox.showinfo("샘플재고 모드", 
                       "✅ 샘플재고 모드로 전환되었습니다.\n\n"
                       "📋 샘플재고는 다음 정보가 필요합니다:\n"
                       "• 제품코드\n"
                       "• 보관위치\n\n"
                       "LOT과 유통기한은 자동으로 설정됩니다:\n"
                       "• LOT: SAMPLE\n"
                       "• 유통기한: N/A")

# 제품코드 검색 및 드롭다운
tk.Label(root, text="제품코드:").pack(pady=5)
product_codes = list(products.keys())
product_var = tk.StringVar()

# 검색 가능한 콤보박스
combo_code = ttk.Combobox(root, textvariable=product_var, values=product_codes, width=30)
combo_code.pack(pady=5)
combo_code.bind("<KeyRelease>", lambda e: filter_products())
combo_code.bind("<<ComboboxSelected>>", update_product_name)

# 제품코드 바코드 리딩 기능 (자동 다음 필드 이동)
def on_product_code_change(*args):
    """제품코드 변경 시 자동으로 보관위치 필드로 이동"""
    product_code = combo_code.get().strip()
    if product_code:
        # 바코드 처리
        if process_barcode_scan_for_field(product_code, "product"):
            # 성공 시 보관위치 필드로 자동 이동
            location_combo.focus()

combo_code.bind('<<ComboboxSelected>>', lambda e: on_product_code_change())
combo_code.bind('<Return>', lambda e: on_product_code_change())

# 제품명 표시
label_product_name = tk.Label(root, text="제품명: ", wraplength=450)
label_product_name.pack(pady=5)

# 보관위치 (수기입력 + 바코드 스캐너) - 제품코드 다음으로 이동
tk.Label(root, text="보관위치:").pack(pady=5)
location_frame = tk.Frame(root)
location_frame.pack(pady=5)

# 보관위치 드롭다운 생성
location_options = []
for zone in ['A', 'B']:
    for section in range(1, 6):
        for position in range(1, 4):
            location_options.append(f"{zone}-{section:02d}-{position:02d}")

location_var = tk.StringVar()
location_combo = ttk.Combobox(location_frame, textvariable=location_var, values=location_options, width=15)
location_combo.pack(side=tk.LEFT, padx=(0, 10))

# 보관위치 바코드 리딩 기능 (자동 다음 필드 이동)
def on_location_change(*args):
    """보관위치 변경 시 자동으로 LOT 필드로 이동"""
    location = location_var.get().strip()
    if location:
        # 바코드 처리
        if process_barcode_scan_for_field(location, "location"):
            # 성공 시 LOT 필드로 자동 이동 (관리품인 경우)
            if category_var.get() == "관리품":
                entry_lot.focus()
            else:
                # 샘플재고인 경우 바로 라벨 생성
                on_submit()

location_combo.bind('<<ComboboxSelected>>', on_location_change)
location_combo.bind('<KeyRelease>', on_location_change)
location_combo.bind('<Return>', lambda e: on_location_change())

# 명령행 인수로 받은 보관위치가 있으면 자동 설정
if args.location:
    location_var.set(args.location)

# 보관위치 실시간 검증
def validate_location_realtime(*args):
    location = location_var.get().strip()
    if location:
        is_valid, _ = validate_location(location)
        if is_valid:
            help_label.config(text="✓ 올바른 형식입니다", fg="green")
        else:
            help_label.config(text="형식: A-01-01, B-03-02 (A,B 구역, 01~05, 01~03)", fg="red")
    else:
        help_label.config(text="형식: A-01-01, B-03-02 (A,B 구역, 01~05, 01~03)", fg="gray")

location_combo.bind('<KeyRelease>', validate_location_realtime)

# 보관위치 도움말
help_label = tk.Label(root, text="형식: A-01-01, B-03-02 (A,B 구역, 01~05, 01~03)", 
                      font=("맑은 고딕", 8), fg="gray")
help_label.pack(pady=2)

# LOT 번호 (관리품일 때만 표시) - 보관위치 다음으로 이동
lot_label = tk.Label(root, text="LOT 번호:")
entry_lot = tk.Entry(root, width=30)

# LOT 번호 (관리품일 때만 표시) - 보관위치 다음으로 이동
lot_label = tk.Label(root, text="LOT 번호:")
entry_lot = tk.Entry(root, width=30)

# 유통기한 (수기입력 + 달력) - 관리품일 때만 표시 - LOT 다음으로 이동
global expiry_label, expiry_frame, entry_expiry
expiry_label = tk.Label(root, text="유통기한:")
expiry_frame = tk.Frame(root)
entry_expiry = tk.Entry(expiry_frame, width=20)

# 유통기한 입력 시 Enter 키로만 라벨 생성
def on_expiry_enter(event):
    """유통기한 입력 후 Enter 키로 라벨 생성"""
    if event.char == '\r':  # Enter 키
        on_submit()

entry_expiry.bind('<Return>', on_expiry_enter)

# 달력 버튼
def show_calendar():
    def set_date():
        selected_date = cal.get_date()
        entry_expiry.delete(0, tk.END)
        entry_expiry.insert(0, selected_date.strftime("%Y-%m-%d"))
        top.destroy()
    
    top = tk.Toplevel(root)
    top.title("유통기한 선택")
    top.geometry("300x250")
    
    # 현재 유통기한 입력창의 값을 기본값으로 사용
    current_expiry = entry_expiry.get().strip()
    default_date = None
    
    if current_expiry:
        try:
            # 현재 입력된 날짜를 기본값으로 설정
            default_date = datetime.strptime(current_expiry, "%Y-%m-%d")
        except:
            pass
    
    # 기본값이 없으면 오늘 날짜 사용
    if default_date is None:
        default_date = datetime.now()
    
    cal = DateEntry(top, width=12, background='darkblue', foreground='white', 
                   borderwidth=2, date_pattern='yyyy-mm-dd')
    cal.pack(pady=20)
    
    # 기본 날짜 설정
    if default_date:
        cal.set_date(default_date)
    
    tk.Button(top, text="선택", command=set_date).pack(pady=10)

tk.Button(expiry_frame, text="📅", command=show_calendar, width=3).pack(side=tk.LEFT)

# 필드별 바코드 리딩 처리 함수
def process_barcode_scan_for_field(barcode_data, field_type):
    """
    특정 필드에서 바코드 리딩 처리
    field_type: "product", "location"
    """
    barcode_data = barcode_data.strip()
    
    # 모드 전환 바코드 처리
    if barcode_data.lower() in ["관리품", "sample", "샘플재고"]:
        if barcode_data.lower() == "관리품":
            category_var.set("관리품")
            refresh_ui_for_management()
            messagebox.showinfo("모드 전환", "관리품 모드로 전환되었습니다.\n제품코드, 보관위치, LOT, 유통기한을 입력하세요.")
        else:
            category_var.set("샘플재고")
            refresh_ui_for_sample()
            messagebox.showinfo("모드 전환", "샘플재고 모드로 전환되었습니다.\n제품코드, 보관위치를 입력하세요.")
        return True
    
    if field_type == "product":
        # 제품 바코드 처리 (88로 시작하는 경우)
        if barcode_data.startswith('88'):
            if barcode_data in barcode_to_product:
                product_code = barcode_to_product[barcode_data]
                combo_code.set(product_code)
                update_product_name()
                return True
            else:
                messagebox.showwarning("바코드 오류", f"등록되지 않은 제품 바코드입니다: {barcode_data}")
                return False
        else:
            # 일반 제품코드 입력으로 처리
            combo_code.set(barcode_data.upper())
            update_product_name()
            return True
    
    elif field_type == "location":
        # 보관위치 처리
        is_valid, error_message = validate_location(barcode_data)
        if is_valid:
            location_var.set(barcode_data)
            return True
        else:
            messagebox.showerror("보관위치 오류", error_message)
            return False
    
    return False

# 제품 검색 필터링 함수
def filter_products():
    search_term = combo_code.get().upper()
    filtered_codes = [code for code in product_codes if search_term in code.upper()]
    combo_code['values'] = filtered_codes

# 초기 UI 설정
update_category_ui()

# 바코드 리딩 기능 안내
messagebox.showinfo("바코드 리딩 기능", 
                   "🆕 새로운 바코드 리딩 기능이 추가되었습니다!\n\n"
                   "💡 사용법:\n"
                   "• 제품코드와 보관위치만 바코드 스캔 가능\n"
                   "• 제품코드와 보관위치는 자동으로 다음 필드로 이동\n"
                   "• LOT과 유통기한은 수동 입력 후 Enter 키로 진행\n"
                   "• '관리품' 또는 '샘플재고' 바코드로 모드 전환 가능\n"
                   "• Ctrl+B 단축키로 제품코드 필드로 바로 이동\n\n"
                   "📋 입력 순서:\n"
                   "1. 제품코드 (바코드 스캔 또는 직접 입력) → 자동 이동\n"
                   "2. 보관위치 (바코드 스캔 또는 직접 입력) → 자동 이동\n"
                   "3. LOT 번호 (관리품만, 수동 입력) → 수동 진행\n"
                   "4. 유통기한 (관리품만, 수동 입력) → Enter 키로 라벨 생성")

# 발행 내역 조회 함수 (검색 및 필터링 기능 포함)
def open_dashboard():
    """대시보드 창 열기"""
    try:
        # 현재 스크립트의 디렉토리에서 label_dashboard.py 실행
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dashboard_path = os.path.join(script_dir, "label_dashboard.py")
        
        if os.path.exists(dashboard_path):
            subprocess.Popen([sys.executable, dashboard_path])
        else:
            messagebox.showerror("오류", "label_dashboard.py 파일을 찾을 수 없습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"대시보드 창을 열 수 없습니다: {str(e)}")

def open_location_visualizer():
    """관리품 위치 찾기 창 열기"""
    try:
        # 현재 스크립트의 디렉토리에서 location_visualizer.py 실행
        script_dir = os.path.dirname(os.path.abspath(__file__))
        visualizer_path = os.path.join(script_dir, "location_visualizer.py")
        
        if os.path.exists(visualizer_path):
            subprocess.Popen([sys.executable, visualizer_path])
        else:
            messagebox.showerror("오류", "location_visualizer.py 파일을 찾을 수 없습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"관리품 위치 찾기 창을 열 수 없습니다: {str(e)}")

def open_zone_manager():
    """구역 관리 창 열기"""
    try:
        # 현재 스크립트의 디렉토리에서 zone_manager.py 실행
        script_dir = os.path.dirname(os.path.abspath(__file__))
        zone_manager_path = os.path.join(script_dir, "zone_manager.py")
        
        if os.path.exists(zone_manager_path):
            subprocess.Popen([sys.executable, zone_manager_path])
        else:
            messagebox.showerror("오류", "zone_manager.py 파일을 찾을 수 없습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"구역 관리 창을 열 수 없습니다: {str(e)}")

def view_history():
    try:
        history_file = "barcode_label/issue_history.xlsx"
        if os.path.exists(history_file):
            df_history = pd.read_excel(history_file)
            
            # 새 창에 발행 내역 표시
            history_window = tk.Toplevel(root)
            history_window.title("발행 내역 조회 및 관리")
            history_window.geometry("1200x700")
            
            # 검색 및 필터링 프레임
            search_frame = tk.Frame(history_window)
            search_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # 검색 옵션
            tk.Label(search_frame, text="검색:", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
            
            # 검색 필드 선택
            search_field_var = tk.StringVar(value="제품코드")
            search_field_combo = ttk.Combobox(search_frame, textvariable=search_field_var, 
                                            values=["구분", "제품코드", "제품명", "LOT", "유통기한", "보관위치"], 
                                            width=10, state="readonly")
            search_field_combo.pack(side=tk.LEFT, padx=5)
            
            # 검색어 입력
            search_var = tk.StringVar()
            search_entry = tk.Entry(search_frame, textvariable=search_var, width=20)
            search_entry.pack(side=tk.LEFT, padx=5)
            search_entry.bind('<Return>', lambda e: apply_filters())  # Enter 키로 검색
            
            # 날짜 필터 프레임
            date_filter_frame = tk.Frame(history_window)
            date_filter_frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(date_filter_frame, text="날짜 범위:", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
            
            # 시작일
            start_date_var = tk.StringVar()
            start_date_entry = tk.Entry(date_filter_frame, textvariable=start_date_var, width=12)
            start_date_entry.pack(side=tk.LEFT, padx=5)
            start_date_entry.insert(0, "YYYY-MM-DD")
            start_date_entry.bind('<FocusIn>', lambda e: start_date_entry.delete(0, tk.END) if start_date_entry.get() == "YYYY-MM-DD" else None)
            start_date_entry.bind('<FocusOut>', lambda e: start_date_entry.insert(0, "YYYY-MM-DD") if not start_date_entry.get() else None)
            tk.Label(date_filter_frame, text="~").pack(side=tk.LEFT, padx=2)
            
            # 종료일
            end_date_var = tk.StringVar()
            end_date_entry = tk.Entry(date_filter_frame, textvariable=end_date_var, width=12)
            end_date_entry.pack(side=tk.LEFT, padx=5)
            end_date_entry.insert(0, "YYYY-MM-DD")
            end_date_entry.bind('<FocusIn>', lambda e: end_date_entry.delete(0, tk.END) if end_date_entry.get() == "YYYY-MM-DD" else None)
            end_date_entry.bind('<FocusOut>', lambda e: end_date_entry.insert(0, "YYYY-MM-DD") if not end_date_entry.get() else None)
            
            # 정렬 옵션
            sort_frame = tk.Frame(history_window)
            sort_frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(sort_frame, text="정렬:", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
            
            sort_field_var = tk.StringVar(value="발행일시")
            sort_field_combo = ttk.Combobox(sort_frame, textvariable=sort_field_var, 
                                          values=["발행일시", "구분", "제품코드", "제품명", "LOT", "유통기한", "보관위치"], 
                                          width=10, state="readonly")
            sort_field_combo.pack(side=tk.LEFT, padx=5)
            
            sort_order_var = tk.StringVar(value="내림차순")
            sort_order_combo = ttk.Combobox(sort_frame, textvariable=sort_order_var, 
                                          values=["오름차순", "내림차순"], 
                                          width=8, state="readonly")
            sort_order_combo.pack(side=tk.LEFT, padx=5)
            
            # 버튼 프레임
            button_frame = tk.Frame(history_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # 검색 및 필터링 함수
            def apply_filters():
                try:
                    # 검색어 필터링
                    filtered_df = df_history.copy()
                    
                    search_term = search_var.get().strip()
                    if search_term:
                        search_field = search_field_var.get()
                        filtered_df = filtered_df[filtered_df[search_field].astype(str).str.contains(search_term, case=False, na=False)]
                    
                    # 날짜 필터링
                    start_date = start_date_var.get().strip()
                    end_date = end_date_var.get().strip()
                    
                    if start_date or end_date:
                        try:
                            filtered_df['발행일시'] = pd.to_datetime(filtered_df['발행일시'])
                            
                            if start_date:
                                start_dt = pd.to_datetime(start_date)
                                filtered_df = filtered_df[filtered_df['발행일시'] >= start_dt]
                            
                            if end_date:
                                end_dt = pd.to_datetime(end_date)
                                filtered_df = filtered_df[filtered_df['발행일시'] <= end_dt]
                        except:
                            pass
                    
                    # 정렬
                    sort_field = sort_field_var.get()
                    ascending = sort_order_var.get() == "오름차순"
                    
                    if sort_field == "발행일시":
                        filtered_df['발행일시'] = pd.to_datetime(filtered_df['발행일시'])
                    
                    if hasattr(filtered_df, 'sort_values'):
                        filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending)
                    
                    # 트리뷰 업데이트
                    for item in tree.get_children():
                        tree.delete(item)
                    
                    # 데이터 추가
                    if hasattr(filtered_df, 'iterrows'):
                        for idx, row in filtered_df.iterrows():
                            tree.insert('', 'end', values=list(row), tags=(str(idx),))
                    
                    # 결과 개수 표시
                    result_count = len(filtered_df)
                    total_count = len(df_history)
                    status_label.config(text=f"검색 결과: {result_count}개 / 전체: {total_count}개")
                    
                except Exception as e:
                    messagebox.showerror("필터링 오류", f"필터링 중 오류가 발생했습니다: {e}")
            
            # 초기화 함수
            def reset_filters():
                search_var.set("")
                start_date_var.set("")
                end_date_var.set("")
                sort_field_var.set("발행일시")
                sort_order_var.set("내림차순")
                apply_filters()
            
            # 검색 버튼
            search_btn = tk.Button(button_frame, text="🔍 검색", command=apply_filters,
                                  bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                                  relief=tk.FLAT, bd=0, padx=15, pady=3)
            search_btn.pack(side=tk.LEFT, padx=5)
            
            # 초기화 버튼
            reset_btn = tk.Button(button_frame, text="🔄 초기화", command=reset_filters,
                                 bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                                 relief=tk.FLAT, bd=0, padx=15, pady=3)
            reset_btn.pack(side=tk.LEFT, padx=5)
            
            # 엑셀 내보내기 버튼
            def export_to_excel():
                try:
                    export_filename = f"발행내역_내보내기_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    
                    # 현재 트리뷰에 표시된 데이터 수집
                    export_data = []
                    for item in tree.get_children():
                        values = tree.item(item)['values']
                        export_data.append(values)
                    
                    if export_data:
                        export_df = pd.DataFrame(export_data, columns=df_history.columns)
                        export_df.to_excel(export_filename, index=False)
                        messagebox.showinfo("내보내기 완료", f"데이터가 {export_filename}로 내보내기되었습니다.")
                    else:
                        messagebox.showwarning("내보내기 실패", "내보낼 데이터가 없습니다.")
                        
                except Exception as e:
                    messagebox.showerror("내보내기 오류", f"내보내기 실패: {e}")
            
            export_btn = tk.Button(button_frame, text="📊 엑셀 내보내기", command=export_to_excel,
                                  bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                  relief=tk.FLAT, bd=0, padx=15, pady=3)
            export_btn.pack(side=tk.LEFT, padx=5)
            
            # 프레임 생성
            tree_frame = tk.Frame(history_window)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Treeview로 표시 (다중 선택 가능)
            tree = ttk.Treeview(tree_frame, columns=list(df_history.columns), show='headings', height=15, selectmode='extended')
            
            # 스크롤바 추가
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # 컬럼 설정
            column_widths = {
                '발행일시': 150,
                '구분': 80,
                '제품코드': 100,
                '제품명': 200,
                'LOT': 100,
                '유통기한': 120,
                '보관위치': 100,
                '파일명': 200
            }
            
            for col in df_history.columns:
                tree.heading(col, text=col)
                tree.column(col, width=column_widths.get(col, 120))
            
            # 데이터 추가
            for idx, row in df_history.iterrows():
                tree.insert('', 'end', values=list(row), tags=(str(idx),))
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 상태 라벨 (검색 결과 개수 표시)
            status_label = tk.Label(history_window, text=f"전체: {len(df_history)}개", 
                                   relief=tk.SUNKEN, bd=1, padx=10, pady=5)
            status_label.pack(fill=tk.X, padx=10, pady=5)
            
            # 재발행 함수
            def reprint_selected():
                selected_item = tree.selection()
                if not selected_item:
                    messagebox.showwarning("경고", "재발행할 항목을 선택하세요.")
                    return
                
                # 선택된 항목의 데이터 가져오기
                item_values = tree.item(selected_item[0])['values']
                category = item_values[0]  # 구분
                product_code = item_values[1]  # 제품코드
                lot = item_values[3]           # LOT
                expiry = item_values[4]        # 유통기한
                location = item_values[5]      # 보관위치
                filename = item_values[6]      # 파일명
                
                # 파일 존재 확인 (labeljpg 폴더 내에서 확인)
                labeljpg_dir = "labeljpg"
                file_path = os.path.join(labeljpg_dir, filename)
                
                if os.path.exists(file_path):
                    try:
                        # 파일을 다시 생성하여 새로운 UI 적용
                        create_label(product_code, lot, expiry, location, category)
                        messagebox.showinfo("재발행 완료", f"라벨을 새로 생성했습니다.\n\n구분: {category}\n제품: {product_code}\nLOT: {lot}\n유통기한: {expiry}\n보관위치: {location}\n\n미리보기 창에서 확인 후 인쇄하세요.")
                    except Exception as e:
                        messagebox.showerror("재발행 오류", f"라벨 생성 실패: {e}")
                else:
                    # 파일이 없으면 새로 생성
                    try:
                        create_label(product_code, lot, expiry, location, category)
                        messagebox.showinfo("재발행 완료", f"라벨을 새로 생성했습니다.\n\n구분: {category}\n제품: {product_code}\nLOT: {lot}\n유통기한: {expiry}\n보관위치: {location}\n\n미리보기 창에서 확인 후 인쇄하세요.")
                    except Exception as e:
                        messagebox.showerror("재발행 오류", f"라벨 생성 실패: {e}")
            
            # 삭제 함수 (다중 선택 지원)
            def delete_selected():
                selected_items = tree.selection()
                if not selected_items:
                    messagebox.showwarning("경고", "삭제할 항목을 선택하세요.")
                    return
                
                # 다중 선택된 항목들의 정보 수집
                selected_data = []
                for item in selected_items:
                    item_values = tree.item(item)['values']
                    selected_data.append({
                        'item_id': item,
                        'category': item_values[0],
                        'product_code': item_values[1],
                        'product_name': item_values[2],
                        'lot': item_values[3],
                        'expiry': item_values[4],
                        'location': item_values[5],
                        'filename': item_values[6]
                    })
                
                # 삭제 확인 메시지 (다중 선택 시)
                if len(selected_items) == 1:
                    data = selected_data[0]
                    confirm_msg = f"다음 항목을 삭제하시겠습니까?\n\n구분: {data['category']}\n제품코드: {data['product_code']}\n제품명: {data['product_name']}\nLOT: {data['lot']}\n유통기한: {data['expiry']}\n보관위치: {data['location']}"
                else:
                    confirm_msg = f"선택된 {len(selected_items)}개 항목을 모두 삭제하시겠습니다?\n\n"
                    for i, data in enumerate(selected_data[:3], 1):  # 처음 3개만 표시
                        confirm_msg += f"{i}. {data['category']} - {data['product_code']} - {data['product_name']} (LOT: {data['lot']})\n"
                    if len(selected_data) > 3:
                        confirm_msg += f"... 외 {len(selected_data) - 3}개 항목"
                
                if not messagebox.askyesno("삭제 확인", confirm_msg):
                    return
                
                try:
                    # 엑셀 파일에서 해당 행들 삭제
                    df_history = pd.read_excel(history_file)
                    deleted_count = 0
                    file_deleted_count = 0
                    
                    # 선택된 항목들을 역순으로 삭제 (인덱스 변경 방지)
                    for data in selected_data:
                        # 선택된 항목과 일치하는 행 찾기
                        mask = (df_history['구분'] == data['category']) & \
                               (df_history['제품코드'] == data['product_code']) & \
                               (df_history['LOT'] == data['lot']) & \
                               (df_history['유통기한'] == data['expiry']) & \
                               (df_history['보관위치'] == data['location'])
                        
                        # 해당 행 삭제
                        df_history = df_history[~mask]
                        deleted_count += 1
                        
                        # 트리뷰에서도 삭제
                        tree.delete(data['item_id'])
                        
                        # 파일도 삭제 (선택사항) - labeljpg 폴더 내에서 확인
                        labeljpg_dir = "labeljpg"
                        file_path = os.path.join(labeljpg_dir, data['filename'])
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                file_deleted_count += 1
                            except:
                                pass
                    
                    # 파일 저장
                    if hasattr(df_history, 'to_excel'):
                        df_history.to_excel(history_file, index=False)
                    
                    # 완료 메시지
                    if len(selected_items) == 1:
                        messagebox.showinfo("삭제 완료", f"선택한 항목이 삭제되었습니다.\n파일도 함께 삭제되었습니다." if file_deleted_count > 0 else "선택한 항목이 삭제되었습니다.")
                    else:
                        messagebox.showinfo("삭제 완료", f"선택된 {deleted_count}개 항목이 삭제되었습니다.\n파일 {file_deleted_count}개도 함께 삭제되었습니다.")
                    
                except Exception as e:
                    messagebox.showerror("삭제 오류", f"삭제 실패: {e}")
            
            # 버튼 프레임
            button_frame = tk.Frame(history_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # 재발행 버튼
            reprint_btn = tk.Button(button_frame, text="선택 항목 재발행", command=reprint_selected, 
                                   bg="#4CAF50", fg="white", font=("맑은 고딕", 11), 
                                   relief=tk.FLAT, bd=0, padx=15, pady=5)
            reprint_btn.pack(side=tk.LEFT, padx=5)
            
            # 삭제 버튼
            delete_btn = tk.Button(button_frame, text="선택 항목 삭제 (다중선택)", command=delete_selected, 
                                  bg="#f44336", fg="white", font=("맑은 고딕", 11), 
                                  relief=tk.FLAT, bd=0, padx=15, pady=5)
            delete_btn.pack(side=tk.LEFT, padx=5)
            
            # 닫기 버튼
            close_btn = tk.Button(button_frame, text="닫기", command=history_window.destroy)
            close_btn.pack(side=tk.RIGHT, padx=5)
            
            # 선택된 항목 정보 표시 (다중 선택 지원)
            def show_selection_info(event):
                selected_items = tree.selection()
                if selected_items:
                    if len(selected_items) == 1:
                        # 단일 선택
                        item_values = tree.item(selected_items[0])['values']
                        info_text = f"선택된 항목:\n구분: {item_values[0]}\n제품코드: {item_values[1]}\n제품명: {item_values[2]}\nLOT: {item_values[3]}\n유통기한: {item_values[4]}\n보관위치: {item_values[5]}"
                    else:
                        # 다중 선택
                        info_text = f"선택된 항목: {len(selected_items)}개\n"
                        for i, item in enumerate(selected_items[:3], 1):  # 처음 3개만 표시
                            item_values = tree.item(item)['values']
                            info_text += f"{i}. {item_values[0]} - {item_values[1]} - {item_values[2]} (LOT: {item_values[3]})\n"
                        if len(selected_items) > 3:
                            info_text += f"... 외 {len(selected_items) - 3}개 항목"
                    info_label.config(text=info_text)
                else:
                    info_label.config(text="항목을 선택하세요 (Ctrl+클릭으로 다중 선택 가능)")
            
            tree.bind('<<TreeviewSelect>>', show_selection_info)
            
            # 선택 정보 표시 라벨
            info_label = tk.Label(history_window, text="항목을 선택하세요 (Ctrl+클릭으로 다중 선택 가능)", 
                                 relief=tk.SUNKEN, bd=1, padx=10, pady=5)
            info_label.pack(fill=tk.X, padx=10, pady=5)
            
            # 초기 필터 적용 (최신순으로 정렬)
            apply_filters()
            
        else:
            messagebox.showinfo("알림", "발행 내역이 없습니다.")
            
    except Exception as e:
        messagebox.showerror("오류", f"발행 내역 조회 중 오류: {e}")

# 명령행 인수 처리
def parse_arguments():
    parser = argparse.ArgumentParser(description='라벨 생성 GUI')
    parser.add_argument('--location', type=str, help='보관위치 (예: A-01-01)')
    return parser.parse_args()

# 명령행 인수 파싱
args = parse_arguments()

# 명령행에서 보관위치가 전달된 경우 자동 설정
if args.location:
    location_var.set(args.location)
    update_product_name()  # UI 업데이트

# 버튼 프레임
button_frame = tk.Frame(root)
button_frame.pack(pady=20)

tk.Button(button_frame, text="라벨 생성 및 인쇄", command=on_submit).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="📷 바코드 리딩", command=lambda: combo_code.focus(), 
          bg="#FF9800", fg="white", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=5)

# 두 번째 버튼 프레임 (관리 도구들)
button_frame2 = tk.Frame(root)
button_frame2.pack(pady=10)

tk.Button(button_frame2, text="📊 대시보드", command=open_dashboard, 
          bg="#2196F3", fg="white", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame2, text="🧐 관리품 위치 찾기", command=open_location_visualizer, 
          bg="#4CAF50", fg="white", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame2, text="📋 발행 내역", command=view_history, 
          bg="#9C27B0", fg="white", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame2, text="⚙️ 구역 관리", command=open_zone_manager, 
          bg="#607D8B", fg="white", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT, padx=5)

# 일련번호 관리 시스템
def init_serial_database():
    """일련번호 데이터베이스 초기화"""
    conn = sqlite3.connect('label_serial.db')
    cursor = conn.cursor()
    
    # 라벨 정보 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS label_info (
            serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            lot TEXT NOT NULL,
            expiry TEXT NOT NULL,
            location TEXT NOT NULL,
            category TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_next_serial_number():
    """다음 일련번호 가져오기"""
    conn = sqlite3.connect('label_serial.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT MAX(serial_number) FROM label_info')
    result = cursor.fetchone()
    
    conn.close()
    
    if result[0] is None:
        return 1
    else:
        return result[0] + 1

def save_label_info(product_code, lot, expiry, location, category):
    """라벨 정보 저장 및 일련번호 반환"""
    conn = sqlite3.connect('label_serial.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO label_info (product_code, lot, expiry, location, category)
        VALUES (?, ?, ?, ?, ?)
    ''', (product_code, lot, expiry, location, category))
    
    serial_number = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return serial_number

def get_label_info_by_serial(serial_number):
    """일련번호로 라벨 정보 조회"""
    conn = sqlite3.connect('label_serial.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT product_code, lot, expiry, location, category
        FROM label_info WHERE serial_number = ?
    ''', (serial_number,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'product_code': result[0],
            'lot': result[1],
            'expiry': result[2],
            'location': result[3],
            'category': result[4]
        }
    else:
        return None

def process_serial_barcode(serial_number):
    """일련번호 바코드 처리"""
    try:
        serial_number = int(serial_number)
        label_info = get_label_info_by_serial(serial_number)
        
        if label_info:
            product_code = label_info['product_code']
            lot = label_info['lot']
            expiry = label_info['expiry']
            location = label_info['location']
            category = label_info['category']
            
            # 제품명 조회
            product_name = products.get(product_code, "알 수 없는 제품")
            
            # 결과 메시지 생성
            result_message = f"""
일련번호: {serial_number}
제품코드: {product_code}
제품명: {product_name}
LOT: {lot}
유통기한: {expiry}
보관위치: {location}
구분: {category}
"""
            messagebox.showinfo("라벨 정보", result_message)
            return True
        else:
            messagebox.showwarning("바코드 오류", f"일련번호 {serial_number}에 해당하는 라벨 정보를 찾을 수 없습니다.")
            return False
            
    except ValueError:
        messagebox.showerror("바코드 오류", "올바르지 않은 일련번호 형식입니다.")
        return False
    except Exception as e:
        messagebox.showerror("오류", f"바코드 처리 중 오류가 발생했습니다: {e}")
        return False

# 데이터베이스 초기화
init_serial_database()

# 제품 정보 로드
products, barcode_to_product, expiry_info = load_products()

root.mainloop()