#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
보관위치 시각화 프로그램
동적 구역 설정을 지원하는 보관위치 시각화 시스템
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os
import subprocess
import sys
import re
import json
import time
import threading
from datetime import datetime

# 발행 이력 파일
history_file = "barcode_label/issue_history.xlsx"
products_file = "barcode_label/products.xlsx"
zone_config_file = "barcode_label/zone_config.json"

def load_inventory():
    """발행 이력 로드"""
    if not os.path.exists(history_file):
        messagebox.showerror("오류", "발행 이력이 없습니다.")
        return pd.DataFrame()
    df = pd.read_excel(history_file)
    return df

def load_products():
    """제품 정보 로드"""
    if not os.path.exists(products_file):
        messagebox.showerror("오류", "제품 정보 파일이 없습니다.")
        return {}, {}
    
    try:
        df = pd.read_excel(products_file)
        products_dict = dict(zip(df['제품코드'].astype(str), df['제품명']))
        
        # 바코드 정보도 함께 로드 (바코드 컬럼이 있는 경우)
        barcode_dict = {}
        if '바코드' in df.columns:
            for _, row in df.iterrows():
                barcode = str(row['바코드']).strip()
                if barcode and barcode != 'nan':
                    barcode_dict[barcode] = str(row['제품코드'])
        
        return products_dict, barcode_dict
    except Exception as e:
        messagebox.showerror("오류", f"제품 정보 로드 중 오류: {e}")
        return {}, {}

def load_zone_config():
    """구역 설정 로드"""
    try:
        if os.path.exists(zone_config_file):
            with open(zone_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 기본 설정 (기존 A, B 구역)
            return {
                "zones": {
                    "A": {
                        "name": "A 구역",
                        "color": "#2196F3",
                        "sections": {
                            "rows": 5,
                            "columns": 3,
                            "description": "A 구역 5x3 섹션"
                        }
                    },
                    "B": {
                        "name": "B 구역", 
                        "color": "#FF9800",
                        "sections": {
                            "rows": 5,
                            "columns": 3,
                            "description": "B 구역 5x3 섹션"
                        }
                    }
                },
                "default_location_format": "{zone}-{row:02d}-{col:02d}",
                "max_zones": 10,
                "max_sections_per_zone": 10
            }
    except Exception as e:
        messagebox.showerror("구역 설정 오류", f"구역 설정을 로드할 수 없습니다: {e}")
        return {"zones": {}}

class LocationVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("관리품 어디어디에 있을까? 🧐")
        self.root.geometry("1400x900")
        
        # 데이터 로드
        self.df = load_inventory()
        self.products, self.barcode_to_product = load_products()
        self.zone_config = load_zone_config()
        
        # 파일 감시 관련 변수
        self.last_config_mtime = os.path.getmtime(zone_config_file) if os.path.exists(zone_config_file) else 0
        self.watching = True
        
        # 파일 감시 스레드 시작
        self.watch_thread = threading.Thread(target=self.watch_config_file, daemon=True)
        self.watch_thread.start()
        
        # 메인 프레임
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        title_label = tk.Label(main_frame, text="관리품 어디어디에 있을까? 🧐", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)
        
        # 설명
        info_label = tk.Label(main_frame, 
                             text="각 칸을 클릭하면 해당 위치의 상세 정보를 확인할 수 있습니다.",
                             font=("맑은 고딕", 10))
        info_label.pack(pady=5)
        
        # 상태 표시 라벨 (숨김 처리)
        self.status_label = tk.Label(main_frame, 
                                    text="",
                                    font=("맑은 고딕", 10), fg="#2196F3")
        self.status_label.pack(pady=2)
        
        # 컨트롤 프레임
        control_frame = tk.Frame(main_frame)
        control_frame.pack(pady=10)
        
        # 새로고침 버튼
        refresh_btn = tk.Button(control_frame, text="🔄 새로고침", 
                               command=self.refresh_data,
                               bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                               relief=tk.FLAT, bd=0, padx=15, pady=5)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # 검색 프레임
        search_frame = tk.Frame(control_frame)
        search_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(search_frame, text="검색:", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        
        # 검색 도움말
        search_help = tk.Label(search_frame, text="(검색 결과는 붉은색으로 표시)", 
                              font=("맑은 고딕", 8), fg="#d32f2f")
        search_help.pack(side=tk.LEFT, padx=(5, 0))
        
        # 검색 필드 선택
        self.search_field_var = tk.StringVar(value="제품명")
        search_field_combo = ttk.Combobox(search_frame, textvariable=self.search_field_var, 
                                        values=["구분", "제품명", "제품코드", "LOT", "보관위치"], 
                                        width=10, state="readonly")
        search_field_combo.pack(side=tk.LEFT, padx=5)
        
        # 검색어 입력
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda e: self.apply_search())
        
        # 검색 버튼
        search_btn = tk.Button(search_frame, text="🔍 검색", 
                              command=self.apply_search,
                              bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=10, pady=3)
        search_btn.pack(side=tk.LEFT, padx=5)
        
        # 초기화 버튼
        reset_btn = tk.Button(search_frame, text="🔄 초기화", 
                             command=self.reset_search,
                             bg="#9C27B0", fg="white", font=("맑은 고딕", 10),
                             relief=tk.FLAT, bd=0, padx=10, pady=3)
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        # 바코드 리딩 버튼
        barcode_btn = tk.Button(control_frame, text="📷 바코드 리딩", 
                               command=self.open_barcode_input,
                               bg="#E91E63", fg="white", font=("맑은 고딕", 10),
                               relief=tk.FLAT, bd=0, padx=15, pady=5)
        barcode_btn.pack(side=tk.LEFT, padx=5)
        
        # 통계 버튼
        stats_btn = tk.Button(control_frame, text="📊 통계 보기", 
                             command=self.show_statistics,
                             bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                             relief=tk.FLAT, bd=0, padx=15, pady=5)
        stats_btn.pack(side=tk.LEFT, padx=5)
        
        # 구역 관리 버튼
        zone_manage_btn = tk.Button(control_frame, text="⚙️ 구역 관리", 
                                   command=self.open_zone_manager,
                                   bg="#607D8B", fg="white", font=("맑은 고딕", 10),
                                   relief=tk.FLAT, bd=0, padx=15, pady=5)
        zone_manage_btn.pack(side=tk.LEFT, padx=5)
        
        # 라벨 생성 버튼
        create_label_btn = tk.Button(control_frame, text="🏷️ 라벨 생성", 
                                   command=self.open_label_gui,
                                   bg="#E91E63", fg="white", font=("맑은 고딕", 10),
                                   relief=tk.FLAT, bd=0, padx=15, pady=5)
        create_label_btn.pack(side=tk.LEFT, padx=5)
        
        # 시각화 프레임
        self.viz_frame = tk.Frame(main_frame)
        self.viz_frame.pack(pady=20)
        
        # 그리드 생성
        self.create_dynamic_grid()
        
        # 초기 데이터 로드
        self.refresh_data()
        
        # 전역 바코드 리딩 단축키 (Ctrl+B)
        self.root.bind('<Control-b>', lambda e: self.open_barcode_input())
        self.root.bind('<Control-B>', lambda e: self.open_barcode_input())
        
        # 창이 닫힐 때 감시 중지
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def apply_search(self):
        """검색 적용"""
        search_term = self.search_var.get().strip()
        search_field = self.search_field_var.get()
        
        if search_term:
            # 검색 조건에 맞는 데이터만 필터링
            filtered_df = self.df[self.df[search_field].astype(str).str.contains(search_term, case=False, na=False)]
            self.update_grid_with_data(filtered_df)
        else:
            # 검색어가 없으면 전체 데이터 표시
            self.update_grid()
    
    def reset_search(self):
        """검색 초기화"""
        self.search_var.set("")
        # 검색 초기화 시 일반 그리드로 복원
        self.update_grid()
    
    def open_barcode_input(self):
        """바코드 리딩 창 열기"""
        def submit_barcode():
            barcode_data = barcode_entry.get().strip()
            if barcode_data:
                # 바코드에서 제품코드 찾기
                if barcode_data in self.barcode_to_product:
                    product_code = self.barcode_to_product[barcode_data]
                    product_name = self.products.get(product_code, "알 수 없는 제품")
                    
                    # 해당 제품코드로 발행 내역 검색
                    product_df = self.df[self.df["제품코드"] == product_code]
                    if not product_df.empty:
                        # 검색 결과를 그리드에 표시
                        self.update_grid_with_data(product_df)
                        messagebox.showinfo("제품 찾기", f"제품 바코드 {barcode_data}를 찾았습니다.\n\n제품: {product_name} ({product_code})\n해당 제품이 있는 위치들이 하이라이트되었습니다.\n\n바코드 리딩 창을 닫습니다.")
                        top.destroy()
                    else:
                        messagebox.showinfo("제품 정보", f"제품 바코드 {barcode_data}\n\n제품: {product_name} ({product_code})\n해당 제품은 아직 발행되지 않았습니다.\n\n바코드 리딩 창을 닫습니다.")
                        top.destroy()
                else:
                    messagebox.showwarning("바코드 오류", f"등록되지 않은 제품 바코드입니다: {barcode_data}\n\n제품 정보 파일에 등록된 바코드만 사용 가능합니다.")
                    barcode_entry.delete(0, tk.END)
                    barcode_entry.focus()
            else:
                messagebox.showwarning("입력 오류", "바코드를 입력하세요.")
        
        def simulate_product_barcode():
            import random
            # 등록된 바코드 중에서 랜덤 선택
            if self.barcode_to_product:
                available_barcodes = list(self.barcode_to_product.keys())
                barcode_entry.delete(0, tk.END)
                barcode_entry.insert(0, random.choice(available_barcodes))
                submit_barcode()
            else:
                messagebox.showwarning("시뮬레이션 오류", "등록된 바코드가 없습니다.\n제품 정보 파일을 확인해주세요.")
        
        top = tk.Toplevel(self.root)
        top.title("바코드 리딩 - 위치 검색")
        top.geometry("500x400")
        top.resizable(False, False)
        
        # 제목
        title_label = tk.Label(top, text="바코드 리딩 - 제품 검색", font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=20)
        
        # 설명
        info_text = """제품 바코드를 스캔하여 해당 제품이 보관된 위치를 확인하세요:

📋 바코드 형식:
• 제품 정보 파일에 등록된 바코드
• 예: 8801234567890

✅ 스캔 완료 후 해당 제품이 있는 위치들이 하이라이트됩니다.
✅ 바코드 리딩이 성공하면 창이 자동으로 닫힙니다.

실제 바코드 스캐너를 사용하거나 아래 버튼으로 시뮬레이션하세요.

💡 단축키: Ctrl+B로 언제든지 바코드 리딩 창을 열 수 있습니다."""
        
        info_label = tk.Label(top, text=info_text, font=("맑은 고딕", 10), justify=tk.LEFT)
        info_label.pack(pady=10)
        
        # 바코드 입력 프레임
        input_frame = tk.Frame(top)
        input_frame.pack(pady=20)
        
        tk.Label(input_frame, text="바코드:", font=("맑은 고딕", 10)).pack()
        barcode_entry = tk.Entry(input_frame, width=30, font=("맑은 고딕", 12))
        barcode_entry.pack(pady=5)
        barcode_entry.focus()
        
        # Enter 키로 제출
        barcode_entry.bind('<Return>', lambda e: submit_barcode())
        
        # 버튼 프레임
        button_frame = tk.Frame(top)
        button_frame.pack(pady=20)
        
        # 제출 버튼
        submit_btn = tk.Button(button_frame, text="확인", command=submit_barcode,
                              bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        submit_btn.pack(side=tk.LEFT, padx=5)
        
        # 시뮬레이션 버튼
        sim_btn = tk.Button(button_frame, text="🧪 제품 바코드 시뮬레이션", 
                           command=simulate_product_barcode,
                           bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                           relief=tk.FLAT, bd=0, padx=20, pady=5)
        sim_btn.pack(side=tk.LEFT, padx=5)
        
        # 취소 버튼
        cancel_btn = tk.Button(button_frame, text="창 닫기", command=top.destroy,
                              bg="#f44336", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def update_grid_with_data(self, filtered_df):
        """필터링된 데이터로 그리드 업데이트 (동적 그리드 사용)"""
        self.update_dynamic_grid_with_data(filtered_df)
    
    def create_grid(self):
        """기존 고정 그리드 생성 (하위 호환성)"""
        self.create_dynamic_grid()
    
    def refresh_data(self):
        """데이터 새로고침 및 그리드 업데이트"""
        self.df = load_inventory()
        self.products, self.barcode_to_product = load_products()
        self.zone_config = load_zone_config()
        self.update_dynamic_grid()
    
    def update_grid(self):
        """그리드 업데이트 (동적 그리드 사용)"""
        self.update_dynamic_grid()
    
    def watch_config_file(self):
        """구역 설정 파일 감시"""
        while self.watching:
            try:
                if os.path.exists(zone_config_file):
                    current_mtime = os.path.getmtime(zone_config_file)
                    if current_mtime > self.last_config_mtime:
                        # 파일이 변경되었으면 메인 스레드에서 새로고침
                        self.root.after(0, self.refresh_on_config_change)
                        self.last_config_mtime = current_mtime
            except Exception as e:
                print(f"파일 감시 오류: {e}")
            
            time.sleep(1)  # 1초마다 확인
    
    def refresh_on_config_change(self):
        """설정 변경 시 새로고침"""
        try:
            # 구역 설정 다시 로드
            self.zone_config = load_zone_config()
            
            # 그리드 다시 생성
            self.create_dynamic_grid()
            
            # 데이터 업데이트
            self.update_dynamic_grid()
            
            # 상태 메시지 표시
            self.show_config_refresh_message()
            
        except Exception as e:
            print(f"설정 새로고침 오류: {e}")
    
    def show_config_refresh_message(self):
        """설정 새로고침 메시지 표시"""
        try:
            # 상태 라벨 업데이트 (설정 변경 시에만 표시)
            self.status_label.config(text="✅ 구역 설정이 자동으로 새로고침되었습니다! 창 크기가 조정됩니다.", fg="#4CAF50")
            
            # 3초 후 빈 텍스트로 복원
            self.root.after(3000, lambda: self.status_label.config(text="", fg="#2196F3"))
                
        except Exception as e:
            print(f"상태 메시지 표시 오류: {e}")
    
    def create_label_for_location(self, location):
        """특정 위치에 라벨 생성"""
        try:
            # 라벨 GUI 창 열기
            script_dir = os.path.dirname(os.path.abspath(__file__))
            label_gui_path = os.path.join(script_dir, "label_gui.py")
            
            if os.path.exists(label_gui_path):
                # 라벨 GUI를 새 프로세스로 실행 (보관위치 인수 전달)
                subprocess.Popen([sys.executable, label_gui_path, "--location", location])
                
                # 사용자에게 안내 메시지
                messagebox.showinfo("라벨 생성", 
                                  f"라벨 발행 창이 열렸습니다.\n\n"
                                  f"보관위치: {location}\n\n"
                                  f"보관위치가 자동으로 설정되었습니다.\n"
                                  f"나머지 정보를 입력한 후 라벨을 생성하세요.")
            else:
                messagebox.showerror("오류", "label_gui.py 파일을 찾을 수 없습니다.")
                
        except Exception as e:
            messagebox.showerror("오류", f"라벨 생성 창을 열 수 없습니다: {str(e)}")
    
    def on_closing(self):
        """창 닫기 시 처리"""
        self.watching = False
        self.root.destroy()
    
    def update_cell(self, cell, location, items, is_search_result=False):
        # 구역 수에 따른 동적 폰트 크기 계산
        total_zones = len(self.zone_config["zones"])
        if total_zones <= 2:
            font_size = 9
        elif total_zones <= 3:
            font_size = 8
        elif total_zones <= 4:
            font_size = 7
        else:
            font_size = 6  # 5개 이상 구역일 때 가장 작게
        
        if not items:
            # 빈 위치
            cell.config(text=f"{location}\n\n(빈 위치)", 
                       bg="#f5f5f5", fg="gray", font=("맑은 고딕", font_size))
        else:
            # 아이템이 있는 위치
            unique_products = len(set(item["제품명"] for item in items))
            total_items = len(items)
            
            # 최신 폐기일자 확인 (현재 시점에서 가장 가까운 날짜)
            try:
                current_date = pd.Timestamp.now()
                disposal_dates = []
                for item in items:
                    try:
                        # 폐기일자 계산
                        expiry_date = pd.to_datetime(item["유통기한"])
                        disposal_date = expiry_date.replace(year=expiry_date.year + 1)
                        disposal_dates.append(disposal_date)
                    except:
                        continue
                if disposal_dates:
                    # 현재 날짜와의 차이를 계산하여 가장 가까운 날짜 찾기
                    closest_disposal = min(disposal_dates, key=lambda x: abs((x - current_date).days))
                    latest_disposal_str = closest_disposal.strftime("%Y-%m-%d")
                else:
                    latest_disposal_str = "N/A"
            except Exception as e:
                print(f"날짜 계산 오류: {e}")
                latest_disposal_str = "N/A"
            
            # 검색 결과인지 여부에 따라 배경색 결정
            if is_search_result:
                bg_color = "#ffebee"  # 밝은 붉은색
                fg_color = "#d32f2f"  # 진한 붉은색 텍스트
            else:
                bg_color = "#e8f5e8"
                fg_color = "black"
            
            # 텍스트 레이아웃 개선 (유통기한 제외)
            cell_text = f"{location}\n\n{unique_products}개 제품\n{total_items}개 라벨\n폐기: {latest_disposal_str}"
            cell.config(text=cell_text, bg=bg_color, fg=fg_color, font=("맑은 고딕", font_size))
    
    def show_location_detail(self, location):
        """위치 상세 정보 표시"""
        if self.df.empty:
            return
        
        # 해당 위치의 데이터 필터링
        location_df = self.df[self.df["보관위치"] == location]
        
        if location_df.empty:
            # 라벨이 없는 경우 라벨 생성 옵션 제공
            result = messagebox.askyesno("위치 정보", 
                                       f"{location}\n\n이 위치에는 아직 라벨이 발행되지 않았습니다.\n\n이 위치에 새 라벨을 생성하시겠습니까?")
            if result:
                self.create_label_for_location(location)
            return
        
        # 상세 창 생성
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"{location} 상세 정보")
        detail_window.geometry("1000x400")
        
        # 제목
        title_label = tk.Label(detail_window, text=f"{location} 위치 상세 정보", 
                              font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=10)
        
        # 통계 정보
        stats_frame = tk.Frame(detail_window)
        stats_frame.pack(pady=10)
        
        unique_products = len(location_df["제품명"].dropna().unique())
        total_items = len(location_df)
        
        tk.Label(stats_frame, text=f"총 제품 수: {unique_products}개", font=("맑은 고딕", 10)).pack()
        tk.Label(stats_frame, text=f"총 라벨 수: {total_items}개", font=("맑은 고딕", 10)).pack()
        
        # 상세 테이블
        tree_frame = tk.Frame(detail_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(tree_frame, columns=("구분", "제품코드", "제품명", "LOT", "유통기한", "폐기일자", "발행일시"), show="headings")
        
        # 컬럼 설정
        tree.heading("구분", text="구분")
        tree.heading("제품코드", text="제품코드")
        tree.heading("제품명", text="제품명")
        tree.heading("LOT", text="LOT")
        tree.heading("유통기한", text="유통기한")
        tree.heading("폐기일자", text="폐기일자")
        tree.heading("발행일시", text="발행일시")
        
        tree.column("구분", width=80)
        tree.column("제품코드", width=100)
        tree.column("제품명", width=200)
        tree.column("LOT", width=100)
        tree.column("유통기한", width=100)
        tree.column("폐기일자", width=100)
        tree.column("발행일시", width=150)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 데이터 추가
        for _, row in location_df.iterrows():
            # 폐기일자 계산 (기존 데이터에 폐기일자가 없는 경우)
            disposal_date = row.get("폐기일자", "N/A")
            if disposal_date == "N/A" or (isinstance(disposal_date, str) and disposal_date == "N/A") or pd.isna(disposal_date):
                try:
                    expiry_date = pd.to_datetime(row["유통기한"])
                    if hasattr(expiry_date, 'replace'):
                        disposal_date = expiry_date.replace(year=expiry_date.year + 1)
                        disposal_date = disposal_date.strftime("%Y-%m-%d")
                    else:
                        disposal_date = "N/A"
                except:
                    disposal_date = "N/A"
            else:
                disposal_date = str(disposal_date)
                
            tree.insert("", "end", values=(
                row["구분"],
                row["제품코드"],
                row["제품명"],
                row["LOT"],
                row["유통기한"],
                disposal_date,
                row["발행일시"]
            ))
        
        # 라벨 생성 버튼 추가
        button_frame = tk.Frame(detail_window)
        button_frame.pack(pady=10)
        
        create_label_btn = tk.Button(button_frame, text="🏷️ 이 위치에 새 라벨 생성", 
                                   command=lambda: self.create_label_for_location(location),
                                   bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                   relief=tk.FLAT, bd=0, padx=15, pady=5)
        create_label_btn.pack(side=tk.LEFT, padx=5)
    
    def show_statistics(self):
        """전체 통계 표시"""
        if self.df.empty:
            messagebox.showinfo("통계", "데이터가 없습니다.")
            return
        
        # 통계 계산
        total_locations = len(self.df["보관위치"].unique())
        total_products = len(self.df["제품명"].unique())
        total_labels = len(self.df)
        
        # 구역별 통계
        a_locations = len(self.df[self.df["보관위치"].str.startswith("A")]["보관위치"].dropna().unique())
        b_locations = len(self.df[self.df["보관위치"].str.startswith("B")]["보관위치"].dropna().unique())
        
        # 통계 창
        stats_window = tk.Toplevel(self.root)
        stats_window.title("전체 통계")
        stats_window.geometry("400x300")
        
        # 제목
        title_label = tk.Label(stats_window, text="보관위치 통계", 
                              font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=10)
        
        # 통계 정보
        stats_text = f"""
📊 전체 통계

📍 위치 정보:
• 총 사용 위치: {total_locations}개
• A 구역 사용: {a_locations}개
• B 구역 사용: {b_locations}개

📦 제품 정보:
• 총 제품 종류: {total_products}개
• 총 라벨 수: {total_labels}개

📅 최신 정보:
• 최신 발행일: {self.df['발행일시'].max()}
        """
        
        stats_label = tk.Label(stats_window, text=stats_text, 
                              font=("맑은 고딕", 10), justify=tk.LEFT)
        stats_label.pack(pady=20)
    
    def open_zone_manager(self):
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
    
    def open_label_gui(self):
        """라벨 생성 창 열기"""
        try:
            # 현재 스크립트의 디렉토리에서 label_gui.py 실행
            script_dir = os.path.dirname(os.path.abspath(__file__))
            label_gui_path = os.path.join(script_dir, "label_gui.py")
            
            if os.path.exists(label_gui_path):
                subprocess.Popen([sys.executable, label_gui_path])
            else:
                messagebox.showerror("오류", "label_gui.py 파일을 찾을 수 없습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"라벨 생성 창을 열 수 없습니다: {str(e)}")
    
    def create_dynamic_grid(self):
        """동적 구역 설정에 따른 그리드 생성"""
        # 기존 그리드 위젯들 제거
        for widget in self.viz_frame.winfo_children():
            widget.destroy()
        
        if not self.zone_config["zones"]:
            # 구역이 없으면 안내 메시지
            no_zones_label = tk.Label(self.viz_frame, 
                                     text="구역이 설정되지 않았습니다.\n구역 관리에서 구역을 추가해주세요.",
                                     font=("맑은 고딕", 12), fg="gray")
            no_zones_label.pack(pady=50)
            return
        
        # 구역별 그리드 생성
        self.zone_grids = {}
        
        # 구역들을 담을 메인 프레임
        zones_container = tk.Frame(self.viz_frame)
        zones_container.pack(fill=tk.BOTH, expand=True)
        
        # 구역 수와 총 섹션 수 계산
        total_zones = len(self.zone_config["zones"])
        total_sections = sum(zone_data["sections"]["rows"] * zone_data["sections"]["columns"] 
                           for zone_data in self.zone_config["zones"].values())
        
        # 동적 칸 크기 계산
        base_cell_width = 180
        base_cell_height = 120
        
        # 구역 수에 따른 칸 크기 조정 (최소 크기 보장)
        if total_zones <= 2:
            cell_width = base_cell_width
            cell_height = base_cell_height
            font_size = 10
        elif total_zones <= 3:
            cell_width = max(base_cell_width - 20, 140)
            cell_height = max(base_cell_height - 15, 95)
            font_size = 9
        elif total_zones <= 4:
            cell_width = max(base_cell_width - 35, 125)
            cell_height = max(base_cell_height - 25, 85)
            font_size = 8
        else:
            # 5개 이상 구역일 때도 최소 크기 보장
            cell_width = max(base_cell_width - 50, 110)
            cell_height = max(base_cell_height - 35, 75)
            font_size = 7
        
        # 구역별 그리드 생성
        total_width = 0
        max_height = 0
        
        for zone_code, zone_data in self.zone_config["zones"].items():
            # 구역 프레임 생성
            zone_frame = tk.Frame(zones_container)
            zone_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)  # 구역 간 여백을 5px로 줄임
            
            # 구역 제목
            zone_title = tk.Label(zone_frame, text=zone_data["name"], 
                                 font=("맑은 고딕", 14, "bold"), fg=zone_data["color"])
            zone_title.pack(pady=2)  # 제목 여백을 2px로 줄임
            
            # 구역 그리드 프레임
            zone_grid_frame = tk.Frame(zone_frame)
            zone_grid_frame.pack()
            
            # 구역별 그리드 생성
            sections = zone_data["sections"]
            zone_grid = []
            
            for row in range(sections["rows"]):
                grid_row = []
                for col in range(sections["columns"]):
                    location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                    # 동적 크기로 셀 생성 (폰트 크기도 동적 조정, 최소 크기 보장)
                    cell_width_pixels = max(15, cell_width // 10)  # 최소 15자 너비
                    cell_height_pixels = max(5, cell_height // 20)  # 최소 5줄 높이
                    
                    cell = tk.Button(zone_grid_frame, 
                                   text=location, 
                                   width=cell_width_pixels, 
                                   height=cell_height_pixels,
                                   font=("맑은 고딕", font_size), 
                                   relief=tk.RAISED, bd=1)
                    cell.grid(row=row, column=col, padx=1, pady=1)  # 여백을 1px로 줄임
                    cell.bind("<Button-1>", lambda e, loc=location: self.show_location_detail(loc))
                    grid_row.append(cell)
                zone_grid.append(grid_row)
            
            self.zone_grids[zone_code] = zone_grid
            
            # 구역 크기 계산 (동적 크기 적용)
            cell_padding = 2   # 셀 간격을 2px로 줄임
            title_height = 30  # 제목 높이를 30px로 줄임
            zone_padding = 8   # 구역 패딩을 8px로 줄임
            
            zone_width = sections["columns"] * (cell_width + cell_padding) + zone_padding * 2
            zone_height = sections["rows"] * (cell_height + cell_padding) + title_height + zone_padding * 2
            total_width += zone_width
            max_height = max(max_height, zone_height)
        
        # 창 크기 자동 조정 (최대화 고려)
        zones_container.update_idletasks()
        
        # 구역 수에 따른 최소 크기 조정
        if total_zones <= 2:
            content_width = max(total_width, 1400)
            content_height = max(max_height, 800)
        elif total_zones <= 3:
            content_width = max(total_width, 1600)
            content_height = max(max_height, 900)
        elif total_zones <= 4:
            content_width = max(total_width, 1800)
            content_height = max(max_height, 1000)
        else:
            # 5개 이상 구역일 때 더 넓게
            content_width = max(total_width, 2000)
            content_height = max(max_height, 1100)
        
        # 약간의 지연 후 창 크기 조정 (레이아웃이 완전히 계산된 후)
        self.root.after(100, lambda: self.adjust_window_size_with_maximize(content_width, content_height))
    
    def adjust_window_size(self, content_width, content_height):
        """창 크기를 콘텐츠에 맞게 조정"""
        # 최소/최대 창 크기 설정
        min_width = 1200
        min_height = 700
        max_width = 2400  # 더 넓게 설정
        max_height = 1400  # 더 높게 설정
        
        # 콘텐츠 크기에 여유 공간 추가 (상태창, 제목, 버튼 등 고려)
        window_width = min(max(content_width + 100, min_width), max_width)
        window_height = min(max(content_height + 300, min_height), max_height)  # 더 많은 여유 공간
        
        # 현재 창 크기 가져오기
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        
        # 크기가 변경된 경우에만 조정
        if abs(current_width - window_width) > 50 or abs(current_height - window_height) > 50:
            # 화면 중앙에 위치하도록 조정
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # 창 크기와 위치 설정
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 상태 메시지 표시
            self.show_size_adjustment_message(window_width, window_height)
    
    def adjust_window_size_with_maximize(self, content_width, content_height):
        """최대화를 고려한 창 크기 조정"""
        # 구역 수에 따른 창 크기 결정
        total_zones = len(self.zone_config["zones"])
        
        # 최소/최대 창 크기 설정
        min_width = 1200
        min_height = 700
        
        # 화면 크기 가져오기
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 구역 수에 따른 최대 크기 조정 (화면 크기를 넘지 않도록)
        if total_zones <= 2:
            max_width = min(1800, screen_width - 100)
            max_height = min(1000, screen_height - 100)
        elif total_zones <= 3:
            max_width = min(2200, screen_width - 100)
            max_height = min(1100, screen_height - 100)
        elif total_zones <= 4:
            max_width = min(2600, screen_width - 100)
            max_height = min(1200, screen_height - 100)
        else:
            # 5개 이상 구역일 때 화면 크기의 90%까지 사용
            max_width = min(int(screen_width * 0.95), screen_width - 50)
            max_height = min(int(screen_height * 0.95), screen_height - 50)
        
        # 콘텐츠 크기에 여유 공간 추가
        window_width = min(max(content_width + 100, min_width), max_width)
        window_height = min(max(content_height + 300, min_height), max_height)
        
        # 현재 창 크기 가져오기
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        
        # 크기가 변경된 경우에만 조정
        if abs(current_width - window_width) > 50 or abs(current_height - window_height) > 50:
            # 화면 중앙에 위치하도록 조정
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # 창 크기와 위치 설정
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 상태 메시지 표시
            self.show_size_adjustment_message(window_width, window_height)
    
    def show_size_adjustment_message(self, width, height):
        """창 크기 조정 메시지 표시"""
        try:
            self.status_label.config(text=f"✅ 창 크기가 자동으로 조정되었습니다 ({width}x{height})", fg="#4CAF50")
            
            # 3초 후 메시지 제거
            self.root.after(3000, lambda: self.status_label.config(text="", fg="#2196F3"))
        except:
            pass
    
    def update_dynamic_grid(self):
        """동적 그리드 업데이트"""
        if self.df.empty:
            return
        
        # 각 위치별 데이터 집계
        location_data = {}
        for _, row in self.df.iterrows():
            location = row["보관위치"]
            if location not in location_data:
                location_data[location] = []
            location_data[location].append({
                "제품명": row["제품명"],
                "LOT": row["LOT"],
                "유통기한": row["유통기한"],
                "발행일시": row["발행일시"]
            })
        
        # 각 구역별로 그리드 업데이트
        for zone_code, zone_data in self.zone_config["zones"].items():
            if zone_code not in self.zone_grids:
                continue
                
            zone_grid = self.zone_grids[zone_code]
            sections = zone_data["sections"]
            
            for row in range(sections["rows"]):
                for col in range(sections["columns"]):
                    location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                    cell = zone_grid[row][col]
                    self.update_cell(cell, location, location_data.get(location, []), is_search_result=False)
    
    def update_dynamic_grid_with_data(self, filtered_df):
        """필터링된 데이터로 동적 그리드 업데이트"""
        if filtered_df.empty:
            # 모든 셀을 빈 상태로 설정
            for zone_code, zone_data in self.zone_config["zones"].items():
                if zone_code not in self.zone_grids:
                    continue
                    
                zone_grid = self.zone_grids[zone_code]
                sections = zone_data["sections"]
                
                for row in range(sections["rows"]):
                    for col in range(sections["columns"]):
                        location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                        cell = zone_grid[row][col]
                        cell.config(text=f"{location}\n\n(검색 결과 없음)", 
                                   bg="#f5f5f5", fg="gray")
            return
        
        # 각 위치별 데이터 집계
        location_data = {}
        for _, row in filtered_df.iterrows():
            location = row["보관위치"]
            if location not in location_data:
                location_data[location] = []
            location_data[location].append({
                "제품명": row["제품명"],
                "LOT": row["LOT"],
                "유통기한": row["유통기한"],
                "발행일시": row["발행일시"]
            })
        
        # 각 구역별로 그리드 업데이트
        for zone_code, zone_data in self.zone_config["zones"].items():
            if zone_code not in self.zone_grids:
                continue
                
            zone_grid = self.zone_grids[zone_code]
            sections = zone_data["sections"]
            
            for row in range(sections["rows"]):
                for col in range(sections["columns"]):
                    location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                    cell = zone_grid[row][col]
                    self.update_cell(cell, location, location_data.get(location, []), is_search_result=True)

def main():
    root = tk.Tk()
    root.title("관리품 어디어디에 있을까? 🧐")
    root.geometry("1400x900")
    app = LocationVisualizer(root)
    root.mainloop()

if __name__ == "__main__":
    main() 