# -*- coding: utf-8 -*-
"""
입고/출고 관리 시스템
- 입고: 기존 label_gui, label_dashboard, location_visualizer와 연결
- 출고: 바코드 리딩 및 수기 입력으로 재고 차감
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os
import sys
import re
from datetime import datetime
import subprocess

# 상위 디렉토리의 execute_query.py 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execute_query import call_query
from mysql_auth import boosta_boosters
from boosters_query import q_boosters_items_for_barcode_reader, q_boosters_items_limit_date

# 발행 이력 파일
history_file = "barcode_label/issue_history.xlsx"

class StockManager:
    def __init__(self, root):
        self.root = root
        self.root.title("입고/출고 관리 시스템")
        self.root.geometry("1200x800")
        
        # 데이터 로드
        self.load_data()
        
        # 바코드-제품코드 매핑 로드
        self.load_barcode_mapping()
        
        # 메인 프레임
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        title_label = tk.Label(main_frame, text="📦 입고/출고 관리 시스템", 
                              font=("맑은 고딕", 18, "bold"))
        title_label.pack(pady=10)
        
        # 탭 컨트롤 생성
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 입고 탭
        self.create_inbound_tab()
        
        # 출고 탭
        self.create_outbound_tab()
        
        # 상태 표시
        self.status_label = tk.Label(main_frame, text="", 
                                    font=("맑은 고딕", 10), fg="#2196F3")
        self.status_label.pack(pady=5)
        
        # 초기 데이터 로드
        self.update_status("시스템이 준비되었습니다.")
    
    def load_data(self):
        """데이터 로드"""
        try:
            if os.path.exists(history_file):
                self.df = pd.read_excel(history_file)
            else:
                self.df = pd.DataFrame()
        except Exception as e:
            messagebox.showerror("오류", f"데이터 로드 중 오류: {e}")
            self.df = pd.DataFrame()
    
    def create_inbound_tab(self):
        """입고 탭 생성"""
        inbound_frame = ttk.Frame(self.notebook)
        self.notebook.add(inbound_frame, text="📥 입고 관리")
        
        # 입고 탭 내용
        title_label = tk.Label(inbound_frame, text="입고 관리", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=20)
        
        # 설명
        desc_label = tk.Label(inbound_frame, 
                             text="입고와 관련된 아래버튼을 눌러주세요.",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=10)
        
        # 버튼 프레임
        button_frame = tk.Frame(inbound_frame)
        button_frame.pack(pady=30)
        
        # 라벨 발행 버튼
        label_btn = tk.Button(button_frame, text="🏷️ 라벨 발행/인쇄", 
                             command=self.open_label_gui,
                             bg="#4CAF50", fg="white", font=("맑은 고딕", 12),
                             relief=tk.FLAT, bd=0, padx=30, pady=10)
        label_btn.pack(side=tk.LEFT, padx=10)
        
        # 대시보드 버튼
        dashboard_btn = tk.Button(button_frame, text="📊 재고 현황", 
                                 command=self.open_dashboard,
                                 bg="#2196F3", fg="white", font=("맑은 고딕", 12),
                                 relief=tk.FLAT, bd=0, padx=30, pady=10)
        dashboard_btn.pack(side=tk.LEFT, padx=10)
        
        # 위치 시각화 버튼
        visualizer_btn = tk.Button(button_frame, text="🗺️ 재고 위치 확인", 
                                  command=self.open_visualizer,
                                  bg="#FF9800", fg="white", font=("맑은 고딕", 12),
                                  relief=tk.FLAT, bd=0, padx=30, pady=10)
        visualizer_btn.pack(side=tk.LEFT, padx=10)
        
        # 구역 관리 버튼
        zone_btn = tk.Button(button_frame, text="⚙️ 섹션 관리", 
                            command=self.open_zone_manager,
                            bg="#9C27B0", fg="white", font=("맑은 고딕", 12),
                            relief=tk.FLAT, bd=0, padx=30, pady=10)
        zone_btn.pack(side=tk.LEFT, padx=10)
    
    def create_outbound_tab(self):
        """출고 탭 생성"""
        outbound_frame = ttk.Frame(self.notebook)
        self.notebook.add(outbound_frame, text="📤 출고 관리")
        
        # 출고 탭 내용
        title_label = tk.Label(outbound_frame, text="출고 관리", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=20)
        
        # 설명
        desc_label = tk.Label(outbound_frame, 
                             text="출고할 제품의 위치와 제품코드를 입력하세요.",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=10)
        
        # 입력 프레임
        input_frame = tk.Frame(outbound_frame)
        input_frame.pack(pady=20)
        
        # 위치 입력
        location_frame = tk.Frame(input_frame)
        location_frame.pack(pady=10)
        
        tk.Label(location_frame, text="보관위치:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        self.location_var = tk.StringVar()
        self.location_entry = tk.Entry(location_frame, textvariable=self.location_var, 
                                      width=15, font=("맑은 고딕", 12))
        self.location_entry.pack(side=tk.LEFT, padx=10)
        
        # 바코드 리딩 버튼
        barcode_btn = tk.Button(location_frame, text="📷 바코드 리딩", 
                               command=self.open_barcode_reader,
                               bg="#E91E63", fg="white", font=("맑은 고딕", 10),
                               relief=tk.FLAT, bd=0, padx=15, pady=5)
        barcode_btn.pack(side=tk.LEFT, padx=10)
        
        # 제품코드 입력
        product_frame = tk.Frame(input_frame)
        product_frame.pack(pady=10)
        
        tk.Label(product_frame, text="제품코드:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        self.product_var = tk.StringVar()
        self.product_entry = tk.Entry(product_frame, textvariable=self.product_var, 
                                     width=15, font=("맑은 고딕", 12))
        self.product_entry.pack(side=tk.LEFT, padx=10)
        
        # 제품명 표시 라벨
        self.product_name_label = tk.Label(product_frame, text="", 
                                         font=("맑은 고딕", 10), fg="#2196F3")
        self.product_name_label.pack(side=tk.LEFT, padx=10)
        
        # 제품 바코드 리딩 버튼
        product_barcode_btn = tk.Button(product_frame, text="📷 제품 바코드", 
                                       command=self.open_product_barcode_reader,
                                       bg="#E91E63", fg="white", font=("맑은 고딕", 10),
                                       relief=tk.FLAT, bd=0, padx=15, pady=5)
        product_barcode_btn.pack(side=tk.LEFT, padx=10)
        
        # 제품 검색 버튼
        search_btn = tk.Button(product_frame, text="🔍 제품 검색", 
                              command=self.search_product,
                              bg="#607D8B", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=15, pady=5)
        search_btn.pack(side=tk.LEFT, padx=10)
        
        # 제품코드 대문자 변환 및 제품명 자동 업데이트 이벤트
        self.product_entry.bind('<KeyRelease>', self.on_product_code_change)

        # 반출자 입력
        outbounder_frame = tk.Frame(input_frame)
        outbounder_frame.pack(pady=10)
        tk.Label(outbounder_frame, text="반출자:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        self.outbounder_var = tk.StringVar()
        self.outbounder_entry = tk.Entry(outbounder_frame, textvariable=self.outbounder_var, width=15, font=("맑은 고딕", 12))
        self.outbounder_entry.pack(side=tk.LEFT, padx=10)
        
        # 출고 수량 입력
        quantity_frame = tk.Frame(input_frame)
        quantity_frame.pack(pady=10)
        
        tk.Label(quantity_frame, text="출고수량:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        self.quantity_var = tk.StringVar(value="1")
        self.quantity_entry = tk.Entry(quantity_frame, textvariable=self.quantity_var, 
                                      width=10, font=("맑은 고딕", 12))
        self.quantity_entry.pack(side=tk.LEFT, padx=10)
        
        # 현재 재고 표시
        self.stock_label = tk.Label(quantity_frame, text="", 
                                   font=("맑은 고딕", 10), fg="#FF5722")
        self.stock_label.pack(side=tk.LEFT, padx=20)
        
        # 버튼 프레임
        button_frame = tk.Frame(input_frame)
        button_frame.pack(pady=20)
        
        # 출고 실행 버튼
        outbound_btn = tk.Button(button_frame, text="📤 출고 실행", 
                                command=self.execute_outbound,
                                bg="#F44336", fg="white", font=("맑은 고딕", 12),
                                relief=tk.FLAT, bd=0, padx=30, pady=10)
        outbound_btn.pack(side=tk.LEFT, padx=10)
        
        # 초기화 버튼
        clear_btn = tk.Button(button_frame, text="🔄 초기화", 
                             command=self.clear_outbound_form,
                             bg="#9E9E9E", fg="white", font=("맑은 고딕", 12),
                             relief=tk.FLAT, bd=0, padx=30, pady=10)
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        # 출고 내역 확인 버튼
        history_btn = tk.Button(button_frame, text="📋 출고 내역", 
                               command=self.show_outbound_history,
                               bg="#9C27B0", fg="white", font=("맑은 고딕", 12),
                               relief=tk.FLAT, bd=0, padx=30, pady=10)
        history_btn.pack(side=tk.LEFT, padx=10)
        
        # 출고 대기 목록 버튼
        batch_btn = tk.Button(button_frame, text="📋 출고 대기 목록", 
                             command=self.show_batch_outbound,
                             bg="#FF5722", fg="white", font=("맑은 고딕", 12),
                             relief=tk.FLAT, bd=0, padx=30, pady=10)
        batch_btn.pack(side=tk.LEFT, padx=10)
        
        # 이벤트 바인딩
        self.location_entry.bind('<KeyRelease>', self.on_location_change)
        self.product_entry.bind('<KeyRelease>', self.on_product_change)
        self.quantity_entry.bind('<KeyRelease>', self.on_quantity_change)
        
        # Enter 키 바인딩
        self.location_entry.bind('<Return>', lambda e: self.product_entry.focus())
        self.product_entry.bind('<Return>', lambda e: self.quantity_entry.focus())
        self.quantity_entry.bind('<Return>', lambda e: self.execute_outbound())
    
    def open_label_gui(self):
        """라벨 발행 GUI 열기"""
        try:
            subprocess.Popen([sys.executable, "barcode_label/label_gui.py"])
            self.update_status("라벨 발행 창이 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"라벨 발행 창을 열 수 없습니다: {e}")
    
    def open_dashboard(self):
        """재고 대시보드 열기"""
        try:
            subprocess.Popen([sys.executable, "barcode_label/label_dashboard.py"])
            self.update_status("재고 대시보드가 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"재고 대시보드를 열 수 없습니다: {e}")
    
    def open_visualizer(self):
        """위치 시각화 열기"""
        try:
            subprocess.Popen([sys.executable, "barcode_label/location_visualizer.py"])
            self.update_status("위치 시각화가 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"위치 시각화를 열 수 없습니다: {e}")
    
    def open_zone_manager(self):
        """구역 관리 열기"""
        try:
            subprocess.Popen([sys.executable, "barcode_label/zone_manager.py"])
            self.update_status("구역 관리가 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"구역 관리를 열 수 없습니다: {e}")
    
    def open_barcode_reader(self):
        """바코드 리딩 창 열기"""
        barcode_window = tk.Toplevel(self.root)
        barcode_window.title("바코드 리딩")
        barcode_window.geometry("500x300")
        barcode_window.resizable(False, False)
        
        # 중앙 정렬
        barcode_window.transient(self.root)
        barcode_window.grab_set()
        
        # 내용
        main_frame = tk.Frame(barcode_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(main_frame, text="📷 바코드 리딩", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)
        
        # 설명
        desc_label = tk.Label(main_frame, 
                             text="보관위치 바코드를 스캔하세요\n형식: A-01-01, B-03-02",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=10)
        
        # 입력 필드
        input_frame = tk.Frame(main_frame)
        input_frame.pack(pady=20)
        
        tk.Label(input_frame, text="바코드:", font=("맑은 고딕", 12)).pack()
        barcode_var = tk.StringVar()
        barcode_entry = tk.Entry(input_frame, textvariable=barcode_var, 
                                width=20, font=("맑은 고딕", 14))
        barcode_entry.pack(pady=10)
        barcode_entry.focus()
        
        # 상태 표시
        status_label = tk.Label(main_frame, text="바코드를 입력하세요", 
                               font=("맑은 고딕", 10), fg="#2196F3")
        status_label.pack(pady=10)
        
        def submit_barcode():
            barcode_data = barcode_var.get().strip()
            
            # 보관위치 형식 검증
            pattern = r'^[AB]-(0[1-5])-(0[1-3])$'
            if re.match(pattern, barcode_data):
                self.location_var.set(barcode_data)
                status_label.config(text="✅ 보관위치 스캔 완료", fg="#4CAF50")
                barcode_window.after(1000, barcode_window.destroy)
            else:
                status_label.config(text="❌ 잘못된 바코드 형식", fg="#F44336")
        
        def simulate_location_barcode():
            """보관위치 바코드 시뮬레이션"""
            import random
            zone = random.choice(['A', 'B'])
            row = random.randint(1, 5)
            col = random.randint(1, 3)
            barcode_data = f"{zone}-{row:02d}-{col:02d}"
            barcode_var.set(barcode_data)
            status_label.config(text=f"시뮬레이션: {barcode_data}", fg="#FF9800")
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        submit_btn = tk.Button(button_frame, text="확인", 
                              command=submit_barcode,
                              bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        submit_btn.pack(side=tk.LEFT, padx=5)
        
        simulate_btn = tk.Button(button_frame, text="시뮬레이션", 
                                command=simulate_location_barcode,
                                bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                                relief=tk.FLAT, bd=0, padx=20, pady=5)
        simulate_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="취소", 
                              command=barcode_window.destroy,
                              bg="#9E9E9E", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Enter 키 바인딩
        barcode_entry.bind('<Return>', lambda e: submit_barcode())
        barcode_window.bind('<Escape>', lambda e: barcode_window.destroy())
    
    def search_product(self):
        """제품 검색 창 열기"""
        search_window = tk.Toplevel(self.root)
        search_window.title("제품 검색")
        search_window.geometry("900x500")
        search_window.resizable(True, True)
        
        # 중앙 정렬
        search_window.transient(self.root)
        search_window.grab_set()
        
        # 내용
        main_frame = tk.Frame(search_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(main_frame, text="🔍 제품 검색", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)
        
        # 검색 프레임
        search_frame = tk.Frame(main_frame)
        search_frame.pack(pady=10)
        
        tk.Label(search_frame, text="검색어:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, 
                               width=30, font=("맑은 고딕", 12))
        search_entry.pack(side=tk.LEFT, padx=10)
        search_entry.focus()
        
        # 검색 버튼
        search_btn = tk.Button(search_frame, text="검색", 
                              command=lambda: self.perform_product_search(search_var.get(), tree),
                              bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=15, pady=5)
        search_btn.pack(side=tk.LEFT, padx=5)
        
        # 트리뷰
        tree_frame = tk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 스크롤바
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 트리뷰 생성
        tree = ttk.Treeview(tree_frame, columns=("구분", "제품코드", "제품명", "수량"), 
                            show="headings", yscrollcommand=tree_scroll.set)
        tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=tree.yview)
        
        # 컬럼 설정
        tree.heading("구분", text="구분")
        tree.heading("제품코드", text="제품코드")
        tree.heading("제품명", text="제품명")
        tree.heading("수량", text="수량")
        tree.column("구분", width=120, minwidth=100)
        tree.column("제품코드", width=180, minwidth=150)
        tree.column("제품명", width=400, minwidth=300)
        tree.column("수량", width=100, minwidth=80)
        
        # 더블클릭 이벤트
        def on_double_click(event):
            selected_item = tree.selection()
            if selected_item:
                values = tree.item(selected_item[0])['values']
                self.product_var.set(values[1].upper())  # 제품코드를 대문자로 설정
                # 제품명 자동 업데이트
                self.update_product_name_display(values[1].upper())
                # 재고 수량 자동 표시
                self.update_stock_display(values[1].upper(), values[3])  # 제품코드, 제품명
                search_window.destroy()
        
        tree.bind('<Double-1>', on_double_click)
        
        # 초기 데이터 로드
        self.load_product_data(tree)
        
        # Enter 키 바인딩
        search_entry.bind('<Return>', lambda e: self.perform_product_search(search_var.get(), tree))
        search_window.bind('<Escape>', lambda e: search_window.destroy())
    
    def load_product_data(self, tree):
        """제품 데이터 로드 (구분-제품코드-제품명-수량)"""
        try:
            if not self.df.empty:
                print(f"데이터 로드: 전체 데이터 {len(self.df)}개")
                grouped = self.df.groupby(["구분", "제품코드", "제품명"]).size().reset_index().rename(columns={0: "수량"})
                print(f"그룹화 결과: {len(grouped)}개 제품")
                for _, row in grouped.iterrows():
                    values = (
                        str(row['구분']),
                        str(row['제품코드']),
                        str(row['제품명']),
                        int(row['수량'])
                    )
                    print(f"제품 추가: {values}")
                    tree.insert("", "end", values=values)
            else:
                print("데이터가 비어있습니다.")
        except Exception as e:
            print(f"제품 데이터 로드 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def perform_product_search(self, search_term, tree):
        """제품 검색 수행 (구분-제품코드-제품명-수량)"""
        for item in tree.get_children():
            tree.delete(item)
        if not search_term.strip():
            self.load_product_data(tree)
            return
        try:
            if not self.df.empty:
                search_mask = (
                    self.df['제품코드'].astype(str).str.contains(search_term, case=False, na=False) |
                    self.df['제품명'].astype(str).str.contains(search_term, case=False, na=False)
                )
                filtered = self.df[search_mask]
                print(f"검색 결과: {len(filtered)}개 항목")
                grouped = filtered.groupby(["구분", "제품코드", "제품명"]).size().reset_index().rename(columns={0: "수량"})
                print(f"검색 그룹화 결과: {len(grouped)}개 제품")
                for _, row in grouped.iterrows():
                    values = (
                        str(row['구분']),
                        str(row['제품코드']),
                        str(row['제품명']),
                        int(row['수량'])
                    )
                    print(f"검색 제품 추가: {values}")
                    tree.insert("", "end", values=values)
        except Exception as e:
            print(f"제품 검색 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def update_stock_display(self, product_code, product_name):
        """제품 선택 시 재고 수량 표시"""
        try:
            if not self.df.empty:
                # 해당 제품의 전체 재고 확인
                stock_mask = (self.df['제품코드'] == product_code)
                total_stock = len(self.df[stock_mask])
                
                if total_stock > 0:
                    self.stock_label.config(text=f"전체 재고: {total_stock}개 ({product_name})", fg="#4CAF50")
                else:
                    self.stock_label.config(text="재고 없음", fg="#F44336")
            else:
                self.stock_label.config(text="데이터 없음", fg="#F44336")
        except Exception as e:
            self.stock_label.config(text=f"재고 확인 오류: {e}", fg="#F44336")

    def on_location_change(self, event=None):
        """위치 변경 시 재고 확인"""
        self.check_current_stock()
    
    def on_product_change(self, event=None):
        """제품 변경 시 재고 확인"""
        product_code = self.product_var.get().strip()
        if product_code:
            try:
                if not self.df.empty:
                    # 해당 제품의 전체 재고 확인
                    stock_mask = (self.df['제품코드'] == product_code)
                    total_stock = len(self.df[stock_mask])
                    
                    if total_stock > 0:
                        # 제품명 가져오기
                        product_df = pd.DataFrame(self.df[stock_mask]).copy()
                        product_name = str(product_df['제품명'].iloc[0]) if not product_df.empty else "알 수 없음"
                        self.stock_label.config(text=f"전체 재고: {total_stock}개 ({product_name})", fg="#4CAF50")
                    else:
                        self.stock_label.config(text="재고 없음", fg="#F44336")
                else:
                    self.stock_label.config(text="데이터 없음", fg="#F44336")
            except Exception as e:
                self.stock_label.config(text=f"재고 확인 오류: {e}", fg="#F44336")
        else:
            self.stock_label.config(text="", fg="#FF5722")
    
    def on_quantity_change(self, event=None):
        """수량 변경 시 재고 확인"""
        self.check_current_stock()
    
    def check_current_stock(self):
        """현재 재고 확인"""
        location = self.location_var.get().strip()
        product_code = self.product_var.get().strip()
        
        if location and product_code:
            try:
                # 해당 위치와 제품의 재고 확인
                stock_mask = (
                    (self.df['보관위치'] == location) & 
                    (self.df['제품코드'] == product_code)
                )
                current_stock = len(self.df[stock_mask])
                
                if current_stock > 0:
                    # 제품명 가져오기
                    stock_df = pd.DataFrame(self.df[stock_mask]).copy()
                    product_name = str(stock_df['제품명'].iloc[0]) if not stock_df.empty else "알 수 없음"
                    self.stock_label.config(text=f"현재 재고: {current_stock}개 ({product_name})", fg="#4CAF50")
                else:
                    self.stock_label.config(text="재고 없음", fg="#F44336")
                    
            except Exception as e:
                self.stock_label.config(text=f"재고 확인 오류: {e}", fg="#F44336")
        else:
            self.stock_label.config(text="", fg="#FF5722")
    
    def execute_outbound(self):
        """출고 실행"""
        location = self.location_var.get().strip()
        product_code = self.product_var.get().strip()
        outbounder = self.outbounder_var.get().strip()
        quantity_str = self.quantity_var.get().strip()
        
        # 입력 검증
        if not location:
            messagebox.showerror("오류", "보관위치를 입력하세요.")
            self.location_entry.focus()
            return
        
        if not product_code:
            messagebox.showerror("오류", "제품코드를 입력하세요.")
            self.product_entry.focus()
            return
        
        if not outbounder:
            messagebox.showerror("오류", "반출자를 입력하세요.")
            self.outbounder_entry.focus()
            return
        
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                messagebox.showerror("오류", "출고 수량은 1 이상이어야 합니다.")
                self.quantity_entry.focus()
                return
        except ValueError:
            messagebox.showerror("오류", "올바른 수량을 입력하세요.")
            self.quantity_entry.focus()
            return
        
        # 재고 확인
        stock_mask = (
            (self.df['보관위치'] == location) & 
            (self.df['제품코드'] == product_code)
        )
        current_stock = len(self.df[stock_mask])
        
        if current_stock < quantity:
            messagebox.showerror("오류", f"재고가 부족합니다.\n현재 재고: {current_stock}개\n요청 수량: {quantity}개")
            return
        
        # 출고 확인
        stock_df = pd.DataFrame(self.df[stock_mask]).copy()
        product_name = str(stock_df['제품명'].iloc[0]) if not stock_df.empty else "알 수 없음"
        
        result = messagebox.askyesno("출고 확인", 
                                   f"다음 항목을 출고하시겠습니까?\n\n"
                                   f"보관위치: {location}\n"
                                   f"제품코드: {product_code}\n"
                                   f"제품명: {product_name}\n"
                                   f"출고수량: {quantity}개\n"
                                   f"반출자: {outbounder}\n"
                                   f"현재재고: {current_stock}개")
        
        if result:
            # 출고 실행
            try:
                self.perform_outbound(location, product_code, quantity, outbounder)
                messagebox.showinfo("완료", f"출고가 완료되었습니다.\n\n"
                                         f"보관위치: {location}\n"
                                         f"제품: {product_name}\n"
                                         f"출고수량: {quantity}개\n"
                                         f"반출자: {outbounder}")
                
                # 폼 초기화
                self.clear_outbound_form()
                
            except Exception as e:
                messagebox.showerror("오류", f"출고 처리 중 오류가 발생했습니다: {e}")

    def perform_outbound(self, location, product_code, quantity, outbounder):
        """실제 출고 처리 및 출고내역 저장"""
        try:
            # 발행 이력 파일 다시 로드
            if os.path.exists(history_file):
                df = pd.read_excel(history_file)
            else:
                raise Exception("발행 이력 파일이 없습니다.")
            
            # 해당 위치와 제품의 항목들 찾기
            stock_mask = (
                (df['보관위치'] == location) & 
                (df['제품코드'] == product_code)
            )
            matching_items = pd.DataFrame(df[stock_mask]).copy()
            
            if len(matching_items) < quantity:
                raise Exception(f"재고가 부족합니다. (요청: {quantity}개, 보유: {len(matching_items)}개)")
            
            # 출고할 항목들 선택 (가장 오래된 것부터)
            items_to_remove = matching_items.head(quantity)
            
            # 출고내역 저장
            outbound_history_file = os.path.join(os.path.dirname(history_file), "outbound_history.xlsx")
            if os.path.exists(outbound_history_file):
                outbound_df = pd.read_excel(outbound_history_file)
            else:
                outbound_df = pd.DataFrame(columns=pd.Index(["출고일시", "보관위치", "제품코드", "제품명", "LOT", "구분", "출고수량", "반출자"]))
            now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            for _, row in items_to_remove.iterrows():
                new_row = pd.DataFrame([{
                    "출고일시": now,
                    "보관위치": row["보관위치"],
                    "제품코드": row["제품코드"],
                    "제품명": row["제품명"],
                    "LOT": row.get("LOT", ""),
                    "구분": row.get("구분", ""),
                    "출고수량": 1,
                    "반출자": outbounder
                }])
                outbound_df = pd.concat([outbound_df, new_row], ignore_index=True)
            outbound_df.to_excel(outbound_history_file, index=False)

            # 선택된 항목들을 제거
            df = df.drop(items_to_remove.index.tolist())
            # 파일 저장
            df.to_excel(history_file, index=False)
            # 메모리 데이터 업데이트
            self.df = df
            # 상태 업데이트
            self.update_status(f"출고 완료: {location} - {product_code} - {quantity}개 - {outbounder}")
        except Exception as e:
            raise Exception(f"출고 처리 실패: {e}")

    def clear_outbound_form(self):
        """출고 폼 초기화"""
        self.location_var.set("")
        self.product_var.set("")
        self.quantity_var.set("1")
        self.outbounder_var.set("")
        self.stock_label.config(text="")
        self.product_name_label.config(text="")  # 제품명 라벨도 초기화
        self.location_entry.focus()
    
    def update_status(self, message):
        """상태 메시지 업데이트"""
        self.status_label.config(text=message)
        self.root.after(3000, lambda: self.status_label.config(text=""))

    def show_outbound_history(self):
        """출고 내역 확인 창 열기"""
        history_window = tk.Toplevel(self.root)
        history_window.title("출고 내역")
        history_window.geometry("1200x700")
        history_window.resizable(True, True)

        # 중앙 정렬
        history_window.transient(self.root)
        history_window.grab_set()

        # 내용
        main_frame = tk.Frame(history_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 제목
        title_label = tk.Label(main_frame, text="📋 출고 내역", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)

        # 검색 프레임
        search_frame = tk.Frame(main_frame)
        search_frame.pack(pady=10)

        tk.Label(search_frame, text="검색어:", font=("맑은 고딕", 12)).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, 
                               width=30, font=("맑은 고딕", 12))
        search_entry.pack(side=tk.LEFT, padx=10)
        search_entry.focus()

        # 검색 버튼
        search_btn = tk.Button(search_frame, text="검색", 
                              command=lambda: self.perform_outbound_history_search(search_var.get(), tree),
                              bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=15, pady=5)
        search_btn.pack(side=tk.LEFT, padx=5)

        # 트리뷰
        tree_frame = tk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # 스크롤바
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 트리뷰 생성
        tree = ttk.Treeview(tree_frame, columns=("출고일시", "보관위치", "제품코드", "제품명", "LOT", "구분", "출고수량", "반출자"), 
                            show="headings", yscrollcommand=tree_scroll.set)
        tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=tree.yview)

        # 컬럼 설정
        tree.heading("출고일시", text="출고일시")
        tree.heading("보관위치", text="보관위치")
        tree.heading("제품코드", text="제품코드")
        tree.heading("제품명", text="제품명")
        tree.heading("LOT", text="LOT")
        tree.heading("구분", text="구분")
        tree.heading("출고수량", text="출고수량")
        tree.heading("반출자", text="반출자")
        tree.column("출고일시", width=150, minwidth=120)
        tree.column("보관위치", width=120, minwidth=100)
        tree.column("제품코드", width=180, minwidth=150)
        tree.column("제품명", width=300, minwidth=250)
        tree.column("LOT", width=100, minwidth=80)
        tree.column("구분", width=100, minwidth=80)
        tree.column("출고수량", width=100, minwidth=80)
        tree.column("반출자", width=150, minwidth=120)

        # 더블클릭 이벤트
        def on_double_click(event):
            selected_item = tree.selection()
            if selected_item:
                values = tree.item(selected_item[0])['values']
                # 출고 내역 확인 창에서 출고 내역 파일을 다시 로드하여 상세 정보 표시
                outbound_history_file = os.path.join(os.path.dirname(history_file), "outbound_history.xlsx")
                if os.path.exists(outbound_history_file):
                    outbound_df = pd.read_excel(outbound_history_file)
                    outbound_df = outbound_df[outbound_df["출고일시"] == values[0]] # 출고일시로 필터링
                    if not outbound_df.empty:
                        detail_window = tk.Toplevel(history_window)
                        detail_window.title(f"출고 상세: {values[0]}")
                        detail_window.geometry("600x400")
                        detail_window.resizable(False, False)

                        detail_frame = tk.Frame(detail_window)
                        detail_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

                        tk.Label(detail_frame, text=f"출고일시: {values[0]}", font=("맑은 고딕", 14, "bold")).pack(pady=5)
                        tk.Label(detail_frame, text=f"보관위치: {values[1]}", font=("맑은 고딕", 12)).pack(pady=2)
                        tk.Label(detail_frame, text=f"제품코드: {values[2]}", font=("맑은 고딕", 12)).pack(pady=2)
                        tk.Label(detail_frame, text=f"제품명: {values[3]}", font=("맑은 고딕", 12)).pack(pady=2)
                        tk.Label(detail_frame, text=f"LOT: {values[4]}", font=("맑은 고딕", 12)).pack(pady=2)
                        tk.Label(detail_frame, text=f"구분: {values[5]}", font=("맑은 고딕", 12)).pack(pady=2)
                        tk.Label(detail_frame, text=f"출고수량: {values[6]}", font=("맑은 고딕", 12)).pack(pady=2)
                        tk.Label(detail_frame, text=f"반출자: {values[7]}", font=("맑은 고딕", 12)).pack(pady=2)

                        detail_window.transient(history_window)
                        detail_window.grab_set()
                        detail_window.bind('<Escape>', lambda e: detail_window.destroy())
                    else:
                        messagebox.showinfo("정보", "해당 출고 내역의 상세 정보를 찾을 수 없습니다.")
                else:
                    messagebox.showinfo("정보", "출고 내역 파일이 없습니다.")
        
        tree.bind('<Double-1>', on_double_click)

        # 초기 데이터 로드
        self.load_outbound_history_data(tree)

        # Enter 키 바인딩
        search_entry.bind('<Return>', lambda e: self.perform_outbound_history_search(search_var.get(), tree))
        history_window.bind('<Escape>', lambda e: history_window.destroy())

    def load_outbound_history_data(self, tree):
        """출고 내역 데이터 로드 (출고일시, 보관위치, 제품코드, 제품명, LOT, 구분, 출고수량, 반출자)"""
        try:
            if os.path.exists(os.path.join(os.path.dirname(history_file), "outbound_history.xlsx")):
                outbound_df = pd.read_excel(os.path.join(os.path.dirname(history_file), "outbound_history.xlsx"))
                for _, row in outbound_df.iterrows():
                    tree.insert("", "end", values=(
                        str(row['출고일시']),
                        str(row['보관위치']),
                        str(row['제품코드']),
                        str(row['제품명']),
                        str(row['LOT']),
                        str(row['구분']),
                        int(row['출고수량']),
                        str(row['반출자'])
                    ))
        except Exception as e:
            print(f"출고 내역 데이터 로드 오류: {e}")

    def perform_outbound_history_search(self, search_term, tree):
        """출고 내역 검색 수행 (출고일시, 보관위치, 제품코드, 제품명, LOT, 구분, 출고수량, 반출자)"""
        for item in tree.get_children():
            tree.delete(item)
        if not search_term.strip():
            self.load_outbound_history_data(tree)
            return
        try:
            if os.path.exists(os.path.join(os.path.dirname(history_file), "outbound_history.xlsx")):
                outbound_df = pd.read_excel(os.path.join(os.path.dirname(history_file), "outbound_history.xlsx"))
                search_mask = (
                    outbound_df['출고일시'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['보관위치'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['제품코드'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['제품명'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['LOT'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['구분'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['출고수량'].astype(str).str.contains(search_term, case=False, na=False) |
                    outbound_df['반출자'].astype(str).str.contains(search_term, case=False, na=False)
                )
                filtered = outbound_df[search_mask]
                for _, row in filtered.iterrows():
                    tree.insert("", "end", values=(
                        str(row['출고일시']),
                        str(row['보관위치']),
                        str(row['제품코드']),
                        str(row['제품명']),
                        str(row['LOT']),
                        str(row['구분']),
                        int(row['출고수량']),
                        str(row['반출자'])
                    ))
        except Exception as e:
            print(f"출고 내역 검색 오류: {e}")

    def show_batch_outbound(self):
        """출고 대기 목록 창 열기"""
        batch_window = tk.Toplevel(self.root)
        batch_window.title("출고 대기 목록")
        batch_window.geometry("1000x600")
        batch_window.resizable(True, True)

        # 중앙 정렬
        batch_window.transient(self.root)
        batch_window.grab_set()

        # 출고 대기 목록 저장용 변수
        self.batch_items = []

        # 내용
        main_frame = tk.Frame(batch_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 제목
        title_label = tk.Label(main_frame, text="📋 출고 대기 목록", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)

        # 설명
        desc_label = tk.Label(main_frame, 
                             text="출고할 항목들을 추가하고 일괄 처리하세요.",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=5)

        # 입력 프레임
        input_frame = tk.Frame(main_frame)
        input_frame.pack(pady=10)

        # 보관위치 입력
        location_frame = tk.Frame(input_frame)
        location_frame.pack(pady=5)
        tk.Label(location_frame, text="보관위치:", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        batch_location_var = tk.StringVar()
        batch_location_entry = tk.Entry(location_frame, textvariable=batch_location_var, 
                                       width=15, font=("맑은 고딕", 10))
        batch_location_entry.pack(side=tk.LEFT, padx=5)
        
        # 바코드 리딩 버튼 (위치)
        batch_location_barcode_btn = tk.Button(location_frame, text="📷 위치 바코드", 
                                             command=lambda: self.open_batch_barcode_reader(batch_location_var, "location"),
                                             bg="#E91E63", fg="white", font=("맑은 고딕", 8),
                                             relief=tk.FLAT, bd=0, padx=8, pady=3)
        batch_location_barcode_btn.pack(side=tk.LEFT, padx=5)

        # 제품코드 입력
        product_frame = tk.Frame(input_frame)
        product_frame.pack(pady=5)
        tk.Label(product_frame, text="제품코드:", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        batch_product_var = tk.StringVar()
        batch_product_entry = tk.Entry(product_frame, textvariable=batch_product_var, 
                                      width=15, font=("맑은 고딕", 10))
        batch_product_entry.pack(side=tk.LEFT, padx=5)
        
        # 바코드 리딩 버튼 (제품)
        batch_product_barcode_btn = tk.Button(product_frame, text="📷 제품 바코드", 
                                            command=lambda: self.open_batch_barcode_reader(batch_product_var, "product"),
                                            bg="#E91E63", fg="white", font=("맑은 고딕", 8),
                                            relief=tk.FLAT, bd=0, padx=8, pady=3)
        batch_product_barcode_btn.pack(side=tk.LEFT, padx=5)
        
        # 제품명 표시
        batch_product_name_label = tk.Label(product_frame, text="", 
                                          font=("맑은 고딕", 10), fg="#2196F3")
        batch_product_name_label.pack(side=tk.LEFT, padx=10)
        
        # 제품코드 대문자 변환 이벤트 (배치)
        batch_product_entry.bind('<KeyRelease>', lambda e: self.convert_batch_product_code_to_uppercase(batch_product_var, batch_product_entry))

        # 수량 입력
        quantity_frame = tk.Frame(input_frame)
        quantity_frame.pack(pady=5)
        tk.Label(quantity_frame, text="수량:", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        batch_quantity_var = tk.StringVar(value="1")
        batch_quantity_entry = tk.Entry(quantity_frame, textvariable=batch_quantity_var, 
                                       width=10, font=("맑은 고딕", 10))
        batch_quantity_entry.pack(side=tk.LEFT, padx=5)

        # 반출자 입력
        outbounder_frame = tk.Frame(input_frame)
        outbounder_frame.pack(pady=5)
        tk.Label(outbounder_frame, text="반출자:", font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        batch_outbounder_var = tk.StringVar()
        batch_outbounder_entry = tk.Entry(outbounder_frame, textvariable=batch_outbounder_var, 
                                         width=15, font=("맑은 고딕", 10))
        batch_outbounder_entry.pack(side=tk.LEFT, padx=5)

        # 추가 버튼
        add_btn = tk.Button(input_frame, text="➕ 추가", 
                           command=lambda: self.add_batch_item(batch_location_var.get(), 
                                                             batch_product_var.get(),
                                                             batch_quantity_var.get(),
                                                             batch_outbounder_var.get(),
                                                             tree),
                           bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                           relief=tk.FLAT, bd=0, padx=15, pady=5)
        add_btn.pack(pady=10)

        # 트리뷰
        tree_frame = tk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # 스크롤바
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 트리뷰 생성
        tree = ttk.Treeview(tree_frame, columns=("보관위치", "제품코드", "제품명", "수량", "반출자", "재고확인"), 
                            show="headings", yscrollcommand=tree_scroll.set)
        tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=tree.yview)

        # 컬럼 설정
        tree.heading("보관위치", text="보관위치")
        tree.heading("제품코드", text="제품코드")
        tree.heading("제품명", text="제품명")
        tree.heading("수량", text="수량")
        tree.heading("반출자", text="반출자")
        tree.heading("재고확인", text="재고확인")
        tree.column("보관위치", width=120, minwidth=100)
        tree.column("제품코드", width=150, minwidth=120)
        tree.column("제품명", width=250, minwidth=200)
        tree.column("수량", width=80, minwidth=60)
        tree.column("반출자", width=120, minwidth=100)
        tree.column("재고확인", width=100, minwidth=80)

        # 삭제 버튼
        delete_btn = tk.Button(main_frame, text="🗑️ 선택 삭제", 
                              command=lambda: self.delete_batch_item(tree),
                              bg="#F44336", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=15, pady=5)
        delete_btn.pack(pady=5)

        # 일괄 출고 버튼
        execute_btn = tk.Button(main_frame, text="📤 일괄 출고 실행", 
                               command=lambda: self.execute_batch_outbound(tree),
                               bg="#FF9800", fg="white", font=("맑은 고딕", 12),
                               relief=tk.FLAT, bd=0, padx=30, pady=10)
        execute_btn.pack(pady=10)

        # Enter 키 바인딩
        batch_location_entry.bind('<Return>', lambda e: batch_product_entry.focus())
        batch_product_entry.bind('<Return>', lambda e: batch_quantity_entry.focus())
        batch_quantity_entry.bind('<Return>', lambda e: batch_outbounder_entry.focus())
        batch_outbounder_entry.bind('<Return>', lambda e: add_btn.invoke())
        batch_window.bind('<Escape>', lambda e: batch_window.destroy())
        
        # 제품코드 변경 시 제품명 자동 업데이트
        batch_product_entry.bind('<KeyRelease>', lambda e: self.update_batch_product_name(batch_product_var.get(), batch_product_name_label))

    def add_batch_item(self, location, product_code, quantity, outbounder, tree):
        """배치 출고 목록에 항목 추가"""
        if not location or not product_code or not quantity or not outbounder:
            messagebox.showerror("오류", "모든 필드를 입력하세요.")
            return

        try:
            quantity = int(quantity)
            if quantity <= 0:
                messagebox.showerror("오류", "수량은 1 이상이어야 합니다.")
                return
        except ValueError:
            messagebox.showerror("오류", "올바른 수량을 입력하세요.")
            return

        # 제품명 조회
        product_name = "알 수 없음"
        try:
            if not self.df.empty:
                product_mask = (self.df['제품코드'] == product_code)
                if len(self.df[product_mask]) > 0:
                    product_df = pd.DataFrame(self.df[product_mask]).copy()
                    product_name = str(product_df['제품명'].iloc[0])
        except Exception as e:
            print(f"제품명 조회 오류: {e}")

        # 재고 확인
        stock_check = "재고 부족"
        try:
            if not self.df.empty:
                stock_mask = (
                    (self.df['보관위치'] == location) & 
                    (self.df['제품코드'] == product_code)
                )
                current_stock = len(self.df[stock_mask])
                if current_stock >= quantity:
                    stock_check = f"재고 OK ({current_stock}개)"
                else:
                    stock_check = f"재고 부족 ({current_stock}개)"
        except Exception as e:
            print(f"재고 확인 오류: {e}")

        # 트리뷰에 추가
        item_id = tree.insert("", "end", values=(
            location, product_code, product_name, quantity, outbounder, stock_check
        ))

        # 배치 목록에 저장
        self.batch_items.append({
            'location': location,
            'product_code': product_code,
            'product_name': product_name,
            'quantity': quantity,
            'outbounder': outbounder,
            'item_id': item_id
        })

        # 입력 필드 초기화
        # (입력 필드 변수들을 전역으로 관리하거나 별도 메서드로 처리)

    def delete_batch_item(self, tree):
        """배치 출고 목록에서 선택된 항목 삭제"""
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showwarning("경고", "삭제할 항목을 선택하세요.")
            return

        # 선택된 항목 삭제
        for item in selected_item:
            tree.delete(item)

        # 배치 목록에서도 삭제
        self.batch_items = [item for item in self.batch_items if item['item_id'] not in selected_item]

    def execute_batch_outbound(self, tree):
        """일괄 출고 실행"""
        if not self.batch_items:
            messagebox.showwarning("경고", "출고할 항목이 없습니다.")
            return

        # 재고 재확인
        insufficient_items = []
        for item in self.batch_items:
            try:
                stock_mask = (
                    (self.df['보관위치'] == item['location']) & 
                    (self.df['제품코드'] == item['product_code'])
                )
                current_stock = len(self.df[stock_mask])
                if current_stock < item['quantity']:
                    insufficient_items.append(f"{item['location']} - {item['product_name']} (요청: {item['quantity']}개, 재고: {current_stock}개)")
            except Exception as e:
                insufficient_items.append(f"{item['location']} - {item['product_name']} (재고 확인 오류)")

        if insufficient_items:
            messagebox.showerror("재고 부족", f"다음 항목들의 재고가 부족합니다:\n\n" + "\n".join(insufficient_items))
            return

        # 출고 확인
        confirm_text = f"다음 {len(self.batch_items)}개 항목을 출고하시겠습니까?\n\n"
        for item in self.batch_items:
            confirm_text += f"• {item['location']} - {item['product_name']} - {item['quantity']}개 - {item['outbounder']}\n"

        result = messagebox.askyesno("일괄 출고 확인", confirm_text)
        if not result:
            return

        # 일괄 출고 실행
        success_count = 0
        failed_items = []

        for item in self.batch_items:
            try:
                self.perform_outbound(item['location'], item['product_code'], 
                                   item['quantity'], item['outbounder'])
                success_count += 1
            except Exception as e:
                failed_items.append(f"{item['location']} - {item['product_name']}: {e}")

        # 결과 표시
        if failed_items:
            messagebox.showwarning("일괄 출고 완료", 
                                 f"성공: {success_count}개\n실패: {len(failed_items)}개\n\n실패 항목:\n" + "\n".join(failed_items))
        else:
            messagebox.showinfo("일괄 출고 완료", f"모든 {success_count}개 항목이 성공적으로 출고되었습니다.")

        # 배치 목록 초기화
        self.batch_items = []
        for item in tree.get_children():
            tree.delete(item)

    def open_batch_barcode_reader(self, var, field_type):
        """배치 출고 목록에서 보관위치 또는 제품코드 바코드 리딩"""
        barcode_window = tk.Toplevel(self.root)
        barcode_window.title(f"바코드 리딩 ({field_type})")
        barcode_window.geometry("500x300")
        barcode_window.resizable(False, False)
        
        # 중앙 정렬
        barcode_window.transient(self.root)
        barcode_window.grab_set()
        
        # 내용
        main_frame = tk.Frame(barcode_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(main_frame, text=f"📷 바코드 리딩 ({field_type})", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)
        
        # 설명
        desc_label = tk.Label(main_frame, 
                             text=f"{field_type} 바코드를 스캔하세요\n형식: A-01-01, B-03-02",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=10)
        
        # 입력 필드
        input_frame = tk.Frame(main_frame)
        input_frame.pack(pady=20)
        
        tk.Label(input_frame, text="바코드:", font=("맑은 고딕", 12)).pack()
        barcode_var = tk.StringVar()
        barcode_entry = tk.Entry(input_frame, textvariable=barcode_var, 
                                width=20, font=("맑은 고딕", 14))
        barcode_entry.pack(pady=10)
        barcode_entry.focus()
        
        # 상태 표시
        status_label = tk.Label(main_frame, text="바코드를 입력하세요", 
                               font=("맑은 고딕", 10), fg="#2196F3")
        status_label.pack(pady=10)
        
        def submit_barcode():
            barcode_data = barcode_var.get().strip()
            
            # 보관위치 또는 제품코드 형식 검증
            if field_type == "location":
                pattern = r'^[AB]-(0[1-5])-(0[1-3])$'
                if re.match(pattern, barcode_data):
                    var.set(barcode_data)
                    status_label.config(text="✅ 보관위치 스캔 완료", fg="#4CAF50")
                    barcode_window.after(1000, barcode_window.destroy)
                else:
                    status_label.config(text="❌ 잘못된 바코드 형식", fg="#F44336")
            else: # field_type == "product"
                # 제품코드 형식 검증 (예: A001, B002 등)
                pattern = r'^[A-Z][0-9]{3}$'
                if re.match(pattern, barcode_data):
                    var.set(barcode_data.upper())  # 대문자로 변환
                    status_label.config(text="✅ 제품코드 스캔 완료", fg="#4CAF50")
                    barcode_window.after(1000, barcode_window.destroy)
                else:
                    status_label.config(text="❌ 잘못된 제품코드 형식", fg="#F44336")
        
        def simulate_barcode():
            """바코드 시뮬레이션"""
            import random
            if field_type == "location":
                zone = random.choice(['A', 'B'])
                row = random.randint(1, 5)
                col = random.randint(1, 3)
                barcode_data = f"{zone}-{row:02d}-{col:02d}"
            else: # field_type == "product"
                zone = random.choice(['A', 'B'])
                code = random.randint(1, 999)
                barcode_data = f"{zone}{code:03d}"

            barcode_var.set(barcode_data)
            status_label.config(text=f"시뮬레이션: {barcode_data}", fg="#FF9800")
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        submit_btn = tk.Button(button_frame, text="확인", 
                              command=submit_barcode,
                              bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        submit_btn.pack(side=tk.LEFT, padx=5)
        
        simulate_btn = tk.Button(button_frame, text="시뮬레이션", 
                                command=simulate_barcode,
                                bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                                relief=tk.FLAT, bd=0, padx=20, pady=5)
        simulate_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="취소", 
                              command=barcode_window.destroy,
                              bg="#9E9E9E", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Enter 키 바인딩
        barcode_entry.bind('<Return>', lambda e: submit_barcode())
        barcode_window.bind('<Escape>', lambda e: barcode_window.destroy())

    def update_batch_product_name(self, product_code, label):
        """배치 출고 목록에서 제품코드가 변경될 때 제품명을 자동으로 업데이트합니다."""
        if not product_code:
            label.config(text="")
            return

        try:
            if not self.df.empty:
                product_mask = (self.df['제품코드'] == product_code)
                if len(self.df[product_mask]) > 0:
                    product_df = pd.DataFrame(self.df[product_mask]).copy()
                    product_name = str(product_df['제품명'].iloc[0])
                    label.config(text=product_name)
                else:
                    label.config(text="제품 없음")
        except Exception as e:
            print(f"제품명 업데이트 오류: {e}")

    def on_product_code_change(self, event=None):
        """제품코드 입력 시 대문자 변환 및 제품명 자동 업데이트"""
        product_code = self.product_entry.get().strip()
        
        # 대문자 변환
        if product_code:
            self.product_var.set(product_code.upper())
        
        # 제품명 자동 업데이트
        self.update_product_name_display(product_code.upper() if product_code else "")
    
    def update_product_name_display(self, product_code):
        """제품코드에 해당하는 제품명을 표시"""
        if not product_code:
            self.product_name_label.config(text="")
            return
        
        try:
            # SQL 쿼리를 사용하여 제품명 조회
            df = call_query(q_boosters_items_for_barcode_reader.query, boosta_boosters)
            product_mask = (df['제품코드'] == product_code)
            filtered_df = df[product_mask]
            
            if len(filtered_df) > 0:
                product_name = str(filtered_df['제품명'].values[0])
                self.product_name_label.config(text=product_name, fg="#4CAF50")
            else:
                self.product_name_label.config(text="제품 없음", fg="#F44336")
        except Exception as e:
            print(f"제품명 조회 오류: {e}")
            self.product_name_label.config(text="조회 오류", fg="#F44336")
    
    def convert_product_code_to_uppercase(self, event):
        """제품코드 입력 시 소문자를 대문자로 자동 변환합니다."""
        if self.product_entry.get():
            self.product_var.set(self.product_entry.get().upper())

    def convert_batch_product_code_to_uppercase(self, var, entry):
        """배치 출고 목록에서 제품코드 입력 시 소문자를 대문자로 자동 변환합니다."""
        if entry.get():
            var.set(entry.get().upper())

    def open_product_barcode_reader(self):
        """제품코드 바코드 리딩 창 열기"""
        barcode_window = tk.Toplevel(self.root)
        barcode_window.title("제품코드 바코드 리딩")
        barcode_window.geometry("500x300")
        barcode_window.resizable(False, False)
        
        # 중앙 정렬
        barcode_window.transient(self.root)
        barcode_window.grab_set()
        
        # 내용
        main_frame = tk.Frame(barcode_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(main_frame, text="📷 제품코드 바코드 리딩", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)
        
        # 설명
        desc_label = tk.Label(main_frame, 
                             text="제품 바코드를 스캔하세요\n88로 시작하는 제품 바코드",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=10)
        
        # 입력 필드
        input_frame = tk.Frame(main_frame)
        input_frame.pack(pady=20)
        
        tk.Label(input_frame, text="바코드:", font=("맑은 고딕", 12)).pack()
        barcode_var = tk.StringVar()
        barcode_entry = tk.Entry(input_frame, textvariable=barcode_var, 
                                width=20, font=("맑은 고딕", 14))
        barcode_entry.pack(pady=10)
        barcode_entry.focus()
        
        # 상태 표시
        status_label = tk.Label(main_frame, text="바코드를 입력하세요", 
                               font=("맑은 고딕", 10), fg="#2196F3")
        status_label.pack(pady=10)
        
        def submit_barcode():
            barcode_data = barcode_var.get().strip()
            
            # 디버깅 정보 출력
            print(f"입력된 바코드: {barcode_data}")
            print(f"바코드 매핑 개수: {len(self.barcode_to_product)}")
            print(f"사용 가능한 바코드 샘플: {list(self.barcode_to_product.keys())[:5]}")
            
            # 88로 시작하는 제품 바코드인지 확인
            if barcode_data.startswith('88'):
                # 바코드-제품코드 매핑에서 찾기
                if barcode_data in self.barcode_to_product:
                    product_code = self.barcode_to_product[barcode_data]
                    self.product_var.set(product_code.upper())  # 대문자로 변환
                    # 제품명 자동 업데이트
                    self.update_product_name_display(product_code.upper())
                    status_label.config(text=f"✅ 제품코드 매칭 완료: {product_code}", fg="#4CAF50")
                    print(f"매칭 성공: {barcode_data} -> {product_code}")
                    barcode_window.after(1000, barcode_window.destroy)
                else:
                    status_label.config(text="❌ 등록되지 않은 제품 바코드", fg="#F44336")
                    print(f"매칭 실패: {barcode_data} (등록되지 않은 바코드)")
            else:
                status_label.config(text="❌ 88로 시작하는 제품 바코드가 아닙니다", fg="#F44336")
                print(f"잘못된 바코드 형식: {barcode_data}")
        
        def simulate_barcode():
            """제품 바코드 시뮬레이션 (실제 데이터베이스 바코드 사용)"""
            import random
            if self.barcode_to_product:
                # 실제 바코드 중에서 랜덤 선택
                available_barcodes = list(self.barcode_to_product.keys())
                barcode_data = random.choice(available_barcodes)
                barcode_var.set(barcode_data)
                status_label.config(text=f"시뮬레이션: {barcode_data}", fg="#FF9800")
                print(f"시뮬레이션 바코드 선택: {barcode_data} -> {self.barcode_to_product[barcode_data]}")
            else:
                # 바코드가 없으면 88로 시작하는 랜덤 바코드 생성
                barcode_data = f"88{random.randint(10000000000, 99999999999)}"
                barcode_var.set(barcode_data)
                status_label.config(text=f"시뮬레이션: {barcode_data} (실제 바코드 없음)", fg="#FF9800")
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        submit_btn = tk.Button(button_frame, text="확인", 
                              command=submit_barcode,
                              bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        submit_btn.pack(side=tk.LEFT, padx=5)
        
        simulate_btn = tk.Button(button_frame, text="시뮬레이션", 
                                command=simulate_barcode,
                                bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                                relief=tk.FLAT, bd=0, padx=20, pady=5)
        simulate_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="취소", 
                              command=barcode_window.destroy,
                              bg="#9E9E9E", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Enter 키 바인딩
        barcode_entry.bind('<Return>', lambda e: submit_barcode())
        barcode_window.bind('<Escape>', lambda e: barcode_window.destroy())

    def load_barcode_mapping(self):
        """SQL 쿼리를 사용하여 바코드-제품코드 매핑을 로드합니다."""
        try:
            # SQL 쿼리를 사용하여 제품 정보 로드
            df = call_query(q_boosters_items_for_barcode_reader.query, boosta_boosters)
            df_limit_date = call_query(q_boosters_items_limit_date.query, boosta_boosters)
            df = pd.merge(df, df_limit_date, on='제품코드', how='left')
            
            # 바코드-제품코드 매핑 생성
            self.barcode_to_product = {}
            if '바코드' in df.columns:
                for _, row in df.iterrows():
                    barcode = str(row['바코드']).strip()
                    if barcode and barcode != 'nan':
                        self.barcode_to_product[barcode] = str(row['제품코드'])
            
            print(f"바코드 매핑 로드: {len(self.barcode_to_product)}개 항목")
            
            # 디버깅을 위해 일부 바코드 정보 출력
            if self.barcode_to_product:
                sample_barcodes = list(self.barcode_to_product.keys())[:3]
                print(f"샘플 바코드: {sample_barcodes}")
                for barcode in sample_barcodes:
                    print(f"  {barcode} -> {self.barcode_to_product[barcode]}")
            
        except Exception as e:
            messagebox.showerror("오류", f"바코드 매핑을 로드하는 중 오류가 발생했습니다: {e}")
            self.barcode_to_product = {}
            print(f"바코드 매핑 로드 오류: {e}")

def main():
    root = tk.Tk()
    app = StockManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
