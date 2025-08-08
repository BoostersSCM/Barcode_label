# -*- coding: utf-8 -*-
"""
바코드 생성 및 인쇄 프로그램
- 원하는 텍스트를 바코드로 변환하여 인쇄
- 다양한 바코드 형식 지원 (Code128, EAN13, QR 등)
- 인쇄 미리보기 및 설정 기능
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import qrcode
import os
import sys
import subprocess
from datetime import datetime

class BarcodePrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("바코드 생성 및 인쇄")
        self.root.geometry("800x700")
        
        # 바코드 이미지 저장용 변수
        self.current_barcode_image = None
        self.current_filename = ""
        
        # 메인 프레임
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(main_frame, text="🏷️ 바코드 생성 및 인쇄", 
                              font=("맑은 고딕", 18, "bold"))
        title_label.pack(pady=10)
        
        # 입력 프레임
        input_frame = tk.LabelFrame(main_frame, text="바코드 정보 입력", 
                                   font=("맑은 고딕", 12, "bold"))
        input_frame.pack(fill=tk.X, pady=10)
        
        # 바코드 형식 선택
        format_frame = tk.Frame(input_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(format_frame, text="바코드 형식:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        self.barcode_format = tk.StringVar(value="code128")
        format_combo = ttk.Combobox(format_frame, textvariable=self.barcode_format, 
                                    values=["code128", "ean13", "ean8", "upc", "qr"], 
                                    state="readonly", width=15)
        format_combo.pack(side=tk.LEFT, padx=10)
        
        # 텍스트 입력
        text_frame = tk.Frame(input_frame)
        text_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(text_frame, text="바코드 텍스트:", font=("맑은 고딕", 12)).pack(anchor=tk.W)
        self.text_var = tk.StringVar()
        self.text_entry = tk.Entry(text_frame, textvariable=self.text_var, 
                                  font=("맑은 고딕", 12), width=50)
        self.text_entry.pack(fill=tk.X, pady=5)
        self.text_entry.focus()
        
        # 바코드 설정 프레임
        settings_frame = tk.LabelFrame(main_frame, text="바코드 설정", 
                                      font=("맑은 고딕", 12, "bold"))
        settings_frame.pack(fill=tk.X, pady=10)
        
        # 설정 그리드
        settings_grid = tk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # 첫 번째 행
        row1 = tk.Frame(settings_grid)
        row1.pack(fill=tk.X, pady=5)
        
        tk.Label(row1, text="폰트 크기:", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        self.font_size = tk.IntVar(value=12)
        font_size_spin = tk.Spinbox(row1, from_=8, to=24, textvariable=self.font_size, 
                                   width=10, font=("맑은 고딕", 10))
        font_size_spin.pack(side=tk.LEFT, padx=10)
        
        tk.Label(row1, text="바코드 높이:", font=("맑은 고딕", 10)).pack(side=tk.LEFT, padx=(20,0))
        self.barcode_height = tk.IntVar(value=50)
        height_spin = tk.Spinbox(row1, from_=20, to=100, textvariable=self.barcode_height, 
                                width=10, font=("맑은 고딕", 10))
        height_spin.pack(side=tk.LEFT, padx=10)
        
        # 두 번째 행
        row2 = tk.Frame(settings_grid)
        row2.pack(fill=tk.X, pady=5)
        
        tk.Label(row2, text="여백 (px):", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        self.margin = tk.IntVar(value=10)
        margin_spin = tk.Spinbox(row2, from_=0, to=50, textvariable=self.margin, 
                                width=10, font=("맑은 고딕", 10))
        margin_spin.pack(side=tk.LEFT, padx=10)
        
        tk.Label(row2, text="텍스트 표시:", font=("맑은 고딕", 10)).pack(side=tk.LEFT, padx=(20,0))
        self.show_text = tk.BooleanVar(value=True)
        text_check = tk.Checkbutton(row2, variable=self.show_text, 
                                   font=("맑은 고딕", 10))
        text_check.pack(side=tk.LEFT, padx=10)
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        # 생성 버튼
        generate_btn = tk.Button(button_frame, text="🔧 바코드 생성", 
                                command=self.generate_barcode,
                                bg="#4CAF50", fg="white", font=("맑은 고딕", 12),
                                relief=tk.FLAT, bd=0, padx=30, pady=10)
        generate_btn.pack(side=tk.LEFT, padx=10)
        
        # 미리보기 버튼
        preview_btn = tk.Button(button_frame, text="👁️ 미리보기", 
                               command=self.preview_barcode,
                               bg="#2196F3", fg="white", font=("맑은 고딕", 12),
                               relief=tk.FLAT, bd=0, padx=30, pady=10)
        preview_btn.pack(side=tk.LEFT, padx=10)
        
        # 저장 버튼
        save_btn = tk.Button(button_frame, text="💾 저장", 
                            command=self.save_barcode,
                            bg="#FF9800", fg="white", font=("맑은 고딕", 12),
                            relief=tk.FLAT, bd=0, padx=30, pady=10)
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # 인쇄 버튼
        print_btn = tk.Button(button_frame, text="🖨️ 인쇄", 
                             command=self.print_barcode,
                             bg="#9C27B0", fg="white", font=("맑은 고딕", 12),
                             relief=tk.FLAT, bd=0, padx=30, pady=10)
        print_btn.pack(side=tk.LEFT, padx=10)
        
        # 일괄 생성 버튼
        batch_btn = tk.Button(button_frame, text="📦 일괄 생성", 
                             command=self.batch_generate_barcodes,
                             bg="#FF5722", fg="white", font=("맑은 고딕", 12),
                             relief=tk.FLAT, bd=0, padx=30, pady=10)
        batch_btn.pack(side=tk.LEFT, padx=10)
        
        # 미리보기 영역
        preview_frame = tk.LabelFrame(main_frame, text="미리보기", 
                                     font=("맑은 고딕", 12, "bold"))
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 캔버스 (미리보기용)
        self.canvas = tk.Canvas(preview_frame, bg="white", relief=tk.SUNKEN, bd=1)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 상태 표시
        self.status_label = tk.Label(main_frame, text="바코드 텍스트를 입력하고 생성 버튼을 클릭하세요", 
                                    font=("맑은 고딕", 10), fg="#2196F3")
        self.status_label.pack(pady=5)
        
        # Enter 키 바인딩
        self.text_entry.bind('<Return>', lambda e: self.generate_barcode())
        
        # 초기 상태
        self.update_status("바코드 텍스트를 입력하고 생성 버튼을 클릭하세요")
    
    def convert_korean_to_english(self, text):
        """한글 문자를 영문으로 변환"""
        korean_to_english = {
            'ㅁ': 'M', 'ㅂ': 'B', 'ㅅ': 'S', 'ㅇ': 'O', 'ㅈ': 'J',
            'ㅊ': 'C', 'ㅋ': 'K', 'ㅌ': 'T', 'ㅍ': 'P', 'ㅎ': 'H',
            'ㄱ': 'G', 'ㄴ': 'N', 'ㄷ': 'D', 'ㄹ': 'R', 'ㅏ': 'A',
            'ㅑ': 'YA', 'ㅓ': 'EO', 'ㅕ': 'YEO', 'ㅗ': 'O', 'ㅛ': 'YO',
            'ㅜ': 'U', 'ㅠ': 'YU', 'ㅡ': 'EU', 'ㅣ': 'I'
        }
        
        converted_text = text
        for korean, english in korean_to_english.items():
            converted_text = converted_text.replace(korean, english)
        
        return converted_text
    
    def generate_barcode(self):
        """바코드 생성"""
        text = self.text_var.get().strip()
        if not text:
            messagebox.showerror("오류", "바코드 텍스트를 입력하세요.")
            self.text_entry.focus()
            return
        
        try:
            barcode_format = self.barcode_format.get()
            
            # 한글 문자를 영문으로 변환
            if barcode_format != "qr":
                original_text = text
                text = self.convert_korean_to_english(text)
                if original_text != text:
                    print(f"한글 변환: {original_text} -> {text}")
            
            if barcode_format == "qr":
                # QR 코드 생성
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(text)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                # PIL Image를 PhotoImage로 변환
                self.current_barcode_image = self.pil_to_photoimage(img)
                
            else:
                # 일반 바코드 생성
                if barcode_format == "ean13" and len(text) != 13:
                    messagebox.showerror("오류", "EAN13 바코드는 13자리 숫자여야 합니다.")
                    return
                elif barcode_format == "ean8" and len(text) != 8:
                    messagebox.showerror("오류", "EAN8 바코드는 8자리 숫자여야 합니다.")
                    return
                elif barcode_format == "upc" and len(text) != 12:
                    messagebox.showerror("오류", "UPC 바코드는 12자리 숫자여야 합니다.")
                    return
                
                # 바코드 생성
                barcode_class = barcode.get_barcode_class(barcode_format)
                barcode_instance = barcode_class(text, writer=ImageWriter())
                
                # 설정 적용
                options = {
                    'font_size': self.font_size.get(),
                    'text_distance': 3.0 if self.show_text.get() else 0,  # 텍스트와 바코드 사이 거리를 더 늘림
                    'module_height': self.barcode_height.get() / 10.0,
                    'module_width': 0.2,
                    'quiet_zone': self.margin.get() / 10.0,
                    'write_text': self.show_text.get()
                }
                
                img = barcode_instance.render(options)
                # PIL Image를 PhotoImage로 변환
                self.current_barcode_image = self.pil_to_photoimage(img)
            
            # 미리보기 업데이트
            self.update_preview()
            self.update_status(f"바코드 생성 완료: {text}")
            
        except Exception as e:
            messagebox.showerror("오류", f"바코드 생성 중 오류가 발생했습니다: {e}")
            self.update_status("바코드 생성 실패")
    
    def pil_to_photoimage(self, pil_image):
        """PIL Image를 PhotoImage로 변환"""
        # 이미지 크기 조정 (너무 크면 축소)
        max_width = 600
        max_height = 400
        
        width, height = pil_image.size
        if width > max_width or height > max_height:
            ratio = min(max_width / width, max_height / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # PIL Image를 PhotoImage로 변환
        from PIL import ImageTk
        return ImageTk.PhotoImage(pil_image)
    
    def update_preview(self):
        """미리보기 업데이트"""
        if self.current_barcode_image:
            # 캔버스 초기화
            self.canvas.delete("all")
            
            # 캔버스 크기 가져오기
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                # 이미지 중앙 배치
                img_width = self.current_barcode_image.width()
                img_height = self.current_barcode_image.height()
                
                x = (canvas_width - img_width) // 2
                y = (canvas_height - img_height) // 2
                
                self.canvas.create_image(x, y, anchor=tk.NW, image=self.current_barcode_image)
    
    def preview_barcode(self):
        """바코드 미리보기 창"""
        if not self.current_barcode_image:
            messagebox.showwarning("경고", "먼저 바코드를 생성하세요.")
            return
        
        preview_window = tk.Toplevel(self.root)
        preview_window.title("바코드 미리보기")
        preview_window.geometry("600x400")
        preview_window.resizable(True, True)
        
        # 중앙 정렬
        preview_window.transient(self.root)
        preview_window.grab_set()
        
        # 미리보기 캔버스
        preview_canvas = tk.Canvas(preview_window, bg="white")
        preview_canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 이미지 표시
        img_width = self.current_barcode_image.width()
        img_height = self.current_barcode_image.height()
        
        # 창 크기에 맞게 조정
        window_width = 600
        window_height = 400
        
        if img_width > window_width - 40 or img_height > window_height - 40:
            ratio = min((window_width - 40) / img_width, (window_height - 40) / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            # 이미지 리사이즈
            from PIL import Image, ImageTk
            # 원본 이미지를 그대로 사용
            resized_img = self.current_barcode_image
        else:
            resized_img = self.current_barcode_image
        
        # 중앙 배치
        x = (window_width - img_width) // 2
        y = (window_height - img_height) // 2
        preview_canvas.create_image(x, y, anchor=tk.NW, image=resized_img)
        
        # 닫기 버튼
        close_btn = tk.Button(preview_window, text="닫기", 
                             command=preview_window.destroy,
                             bg="#9E9E9E", fg="white", font=("맑은 고딕", 10),
                             relief=tk.FLAT, bd=0, padx=20, pady=5)
        close_btn.pack(pady=10)
    
    def save_barcode(self):
        """바코드 이미지 저장"""
        if not self.current_barcode_image:
            messagebox.showwarning("경고", "먼저 바코드를 생성하세요.")
            return
        
        try:
            # 파일 저장 대화상자
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG 파일", "*.png"), ("JPEG 파일", "*.jpg"), ("모든 파일", "*.*")],
                title="바코드 이미지 저장"
            )
            
            if filename:
                # PIL Image로 다시 변환하여 저장
                if self.barcode_format.get() == "qr":
                    # QR 코드는 이미 PIL Image
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(self.text_var.get().strip())
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                else:
                    # 일반 바코드
                    barcode_class = barcode.get_barcode_class(self.barcode_format.get())
                    barcode_instance = barcode_class(self.text_var.get().strip(), writer=ImageWriter())
                    
                    options = {
                        'font_size': self.font_size.get(),
                        'text_distance': 3.0 if self.show_text.get() else 0,
                        'module_height': self.barcode_height.get() / 10.0,
                        'module_width': 0.2,
                        'quiet_zone': self.margin.get() / 10.0,
                        'write_text': self.show_text.get()
                    }
                    
                    img = barcode_instance.render(options)
                
                img.save(filename)
                self.current_filename = filename
                self.update_status(f"바코드 이미지 저장 완료: {os.path.basename(filename)}")
                messagebox.showinfo("완료", f"바코드 이미지가 저장되었습니다:\n{filename}")
                
        except Exception as e:
            messagebox.showerror("오류", f"바코드 이미지 저장 중 오류가 발생했습니다: {e}")
    
    def print_barcode(self):
        """바코드 인쇄"""
        if not self.current_barcode_image:
            messagebox.showwarning("경고", "먼저 바코드를 생성하세요.")
            return
        
        try:
            # 임시 파일로 저장 후 인쇄
            temp_filename = f"temp_barcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            # PIL Image로 다시 변환하여 저장
            if self.barcode_format.get() == "qr":
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(self.text_var.get().strip())
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
            else:
                barcode_class = barcode.get_barcode_class(self.barcode_format.get())
                barcode_instance = barcode_class(self.text_var.get().strip(), writer=ImageWriter())
                
                options = {
                    'font_size': self.font_size.get(),
                    'text_distance': 3.0 if self.show_text.get() else 0,
                    'module_height': self.barcode_height.get() / 10.0,
                    'module_width': 0.2,
                    'quiet_zone': self.margin.get() / 10.0,
                    'write_text': self.show_text.get()
                }
                
                img = barcode_instance.render(options)
            
            img.save(temp_filename)
            
            # 시스템 기본 인쇄 프로그램으로 열기
            if sys.platform == "win32":
                os.startfile(temp_filename, "print")
            else:
                subprocess.run(["xdg-open", temp_filename])
            
            self.update_status("인쇄 요청 완료")
            messagebox.showinfo("인쇄", "인쇄 요청이 완료되었습니다.\n시스템 인쇄 대화상자에서 인쇄 설정을 확인하세요.")
            
            # 임시 파일 삭제 (잠시 후)
            self.root.after(5000, lambda: self.delete_temp_file(temp_filename))
            
        except Exception as e:
            messagebox.showerror("오류", f"인쇄 중 오류가 발생했습니다: {e}")
    
    def delete_temp_file(self, filename):
        """임시 파일 삭제"""
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except:
            pass  # 삭제 실패해도 무시
    
    def batch_generate_barcodes(self):
        """30개의 바코드를 일괄 생성"""
        try:
            # barcodejpg 폴더 생성
            output_folder = "barcodejpg"
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                print(f"폴더 생성: {output_folder}")
            
            # 설정값 고정
            self.font_size.set(8)
            self.barcode_height.set(80)
            self.margin.set(7)
            self.show_text.set(True)
            self.barcode_format.set("code128")
            
            # 바코드 생성 카운터
            success_count = 0
            failed_count = 0
            
            # A와 B 구역에 대해 바코드 생성
            for zone in ['F']:
                for xx in range(1, 6):  # 01~05
                    for yy in range(1, 4):  # 01~03
                        # 바코드 텍스트 생성
                        barcode_text = f"{zone}-{xx:02d}-{yy:02d}"
                        filename = f"{barcode_text}.jpeg"
                        filepath = os.path.join(output_folder, filename)
                        
                        try:
                            # 바코드 생성
                            barcode_class = barcode.get_barcode_class("code128")
                            barcode_instance = barcode_class(barcode_text, writer=ImageWriter())
                            
                            # 설정 적용
                            options = {
                                'font_size': 8,
                                'text_distance': 3.0,
                                'module_height': 8.0,  # 80/10
                                'module_width': 0.2,
                                'quiet_zone': 0.7,  # 7/10
                                'write_text': True
                            }
                            
                            img = barcode_instance.render(options)
                            img.save(filepath)
                            
                            success_count += 1
                            print(f"생성 완료: {filename}")
                            
                        except Exception as e:
                            failed_count += 1
                            print(f"생성 실패: {filename} - {e}")
            
            # 결과 메시지
            result_message = f"일괄 생성 완료!\n\n성공: {success_count}개\n실패: {failed_count}개\n저장 위치: {output_folder} 폴더"
            messagebox.showinfo("일괄 생성 완료", result_message)
            self.update_status(f"일괄 생성 완료: {success_count}개 바코드")
            
        except Exception as e:
            messagebox.showerror("오류", f"일괄 생성 중 오류가 발생했습니다: {e}")
            self.update_status("일괄 생성 실패")
    
    def update_status(self, message):
        """상태 메시지 업데이트"""
        self.status_label.config(text=message)
        self.root.after(3000, lambda: self.status_label.config(text=""))

def main():
    root = tk.Tk()
    app = BarcodePrinter(root)
    root.mainloop()

if __name__ == "__main__":
    main()
