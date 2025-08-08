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
import threading
import time
import json
import os.path
from functools import partial

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
        
        # 자동 바코드 감지 변수들
        self.barcode_buffer = ""
        self.last_key_time = 0
        self.barcode_timeout = 0.1  # 100ms 타임아웃
        self.is_barcode_scanning = False
        
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
        
        # 위치 확인 탭
        self.create_location_tab()
        
        # 상태 표시
        self.status_label = tk.Label(main_frame, text="", 
                                    font=("맑은 고딕", 10), fg="#2196F3")
        self.status_label.pack(pady=5)
        
        # 초기 데이터 로드
        self.update_status("시스템이 준비되었습니다. 바코드를 스캔하면 자동으로 인식됩니다.")
        
        # 전역 키보드 이벤트 바인딩 (자동 바코드 감지)
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        
        # 기존 Ctrl+B 단축키도 유지 (백업용)
        self.root.bind('<Control-b>', lambda e: self.open_inbound_barcode_reader())
        self.root.bind('<Control-B>', lambda e: self.open_inbound_barcode_reader())
        
        # 탭 변경 이벤트 핸들러 설정
        def on_tab_changed(event):
            current_tab = self.notebook.index(self.notebook.select())
            # 위치확인 탭은 이미 시각화가 임베드되어 있으므로 자동 실행 제거
            pass
        
        # 탭 변경 이벤트 바인딩
        self.notebook.bind('<<NotebookTabChanged>>', on_tab_changed)
    
    def on_key_press(self, event):
        """키보드 입력 감지 - 자동 바코드 스캔"""
        current_time = time.time()
        
        # 특수 키는 무시 (Ctrl, Alt, Shift 등)
        if event.keysym in ['Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Shift_L', 'Shift_R', 
                           'Caps_Lock', 'Tab', 'Return', 'Escape', 'F1', 'F2', 'F3', 'F4', 
                           'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12']:
            return
        
        # 입력 필드에 포커스가 있는 경우 바코드 감지 비활성화
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, tk.Entry) or isinstance(focused_widget, tk.Text):
            return
        
        # 바코드 스캔 중이 아닌 경우에만 처리
        if not self.is_barcode_scanning:
            # 이전 키 입력과의 시간 간격 확인
            if current_time - self.last_key_time > self.barcode_timeout:
                self.barcode_buffer = ""
            
            # 문자 키만 버퍼에 추가
            if len(event.char) == 1 and event.char.isprintable():
                self.barcode_buffer += event.char
            
            self.last_key_time = current_time
            
            # 바코드 패턴 감지
            self.detect_barcode_pattern()
    
    def on_key_release(self, event):
        """키보드 해제 이벤트"""
        # 바코드 스캔 완료 후 일정 시간 후 버퍼 초기화
        if self.barcode_buffer:
            self.root.after(200, self.clear_barcode_buffer)
    
    def clear_barcode_buffer(self):
        """바코드 버퍼 초기화"""
        self.barcode_buffer = ""
    
    def detect_barcode_pattern(self):
        """바코드 패턴 감지 및 처리"""
        if not self.barcode_buffer:
            return
        
        # 입고/출고 바코드 패턴 감지
        if self.barcode_buffer in ["INBOUND", "입고"]:
            self.is_barcode_scanning = True
            self.process_inbound_barcode()
            self.barcode_buffer = ""
            self.is_barcode_scanning = False
        elif self.barcode_buffer in ["OUTBOUND", "출고"]:
            self.is_barcode_scanning = True
            self.process_outbound_barcode()
            self.barcode_buffer = ""
            self.is_barcode_scanning = False
        elif self.barcode_buffer in ["LOCATION", "위치 확인", "위치확인"]:
            self.is_barcode_scanning = True
            self.process_location_check_barcode()
            self.barcode_buffer = ""
            self.is_barcode_scanning = False
        # 보관위치 바코드 패턴 감지 (A-01-01, B-03-02 형식)
        elif re.match(r'^[AB]-(0[1-5])-(0[1-3])$', self.barcode_buffer):
            self.is_barcode_scanning = True
            self.process_location_barcode(self.barcode_buffer)
            self.barcode_buffer = ""
            self.is_barcode_scanning = False
        # 제품 바코드 패턴 감지 (88로 시작하는 13자리)
        elif re.match(r'^88\d{11}$', self.barcode_buffer):
            self.is_barcode_scanning = True
            self.process_product_barcode(self.barcode_buffer)
            self.barcode_buffer = ""
            self.is_barcode_scanning = False
        # 라벨 바코드 패턴 감지 (제품코드-LOT-유통기한)
        elif re.match(r'^([A-Z][0-9]{3})-([A-Z0-9]+)-(\d{4}-\d{2}-\d{2})$', self.barcode_buffer):
            self.is_barcode_scanning = True
            self.process_label_barcode(self.barcode_buffer)
            self.barcode_buffer = ""
            self.is_barcode_scanning = False
    
    def process_inbound_barcode(self):
        """입고 바코드 처리"""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0:  # 이미 입고 탭에 있는 경우
            # 라벨 발행/인쇄 창 열기
            self.open_label_gui()
            self.update_status("✅ 라벨 발행/인쇄 창이 열렸습니다.")
        else:
            # 입고 탭으로 전환
            self.notebook.select(0)  # 첫 번째 탭 (입고)
            self.update_status("✅ 입고 관리 탭으로 전환되었습니다.")
    
    def process_outbound_barcode(self):
        """출고 바코드 처리"""
        # 출고 탭으로 전환
        self.notebook.select(1)  # 두 번째 탭 (출고)
        self.update_status("✅ 출고 관리 탭으로 전환되었습니다.")
    
    def process_location_check_barcode(self):
        """위치 확인 바코드 처리"""
        # 위치 확인 탭으로 전환
        self.notebook.select(2)  # 세 번째 탭 (위치 확인)
        self.update_status("✅ 위치 확인 탭으로 전환되었습니다.")
    
    def process_label_barcode(self, barcode_data):
        """라벨 바코드 처리 (제품코드-LOT-유통기한)"""
        # 현재 탭이 출고 탭인지 확인
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:  # 출고 탭
            # 바코드에서 정보 추출
            match = re.match(r'^([A-Z][0-9]{3})-([A-Z0-9]+)-(\d{4}-\d{2}-\d{2})$', barcode_data)
            if match:
                product_code, lot, expiry_date = match.groups()
                
                # 제품코드 설정
                self.product_var.set(product_code.upper())
                
                # 제품명 자동 업데이트
                self.update_product_name_display(product_code.upper())
                
                # LOT와 유통기한 정보 표시
                self.lot_info_label.config(text=f"LOT: {lot}", fg="#FF9800")
                self.expiry_info_label.config(text=f"유통기한: {expiry_date}", fg="#E91E63")
                
                # 보관위치가 입력되어 있고 동일한 제품코드인 경우 수량 증가
                current_location = self.location_var.get().strip()
                current_product = self.product_var.get().strip()
                current_quantity = self.quantity_var.get().strip()
                
                if current_location and current_product == product_code.upper():
                    try:
                        current_qty = int(current_quantity) if current_quantity.isdigit() else 1
                        new_qty = current_qty + 1
                        self.quantity_var.set(str(new_qty))
                        self.update_status(f"✅ 라벨 바코드 스캔 완료: {product_code}-{lot}-{expiry_date} (수량 증가: {new_qty})")
                    except ValueError:
                        self.quantity_var.set("1")
                        self.update_status(f"✅ 라벨 바코드 스캔 완료: {product_code}-{lot}-{expiry_date}")
                else:
                    self.update_status(f"✅ 라벨 바코드 스캔 완료: {product_code}-{lot}-{expiry_date}")
                
                # 자동으로 반출자 필드로 포커스 이동
                self.root.after(100, lambda: self.outbounder_entry.focus())
            else:
                self.update_status(f"❌ 잘못된 라벨 바코드 형식: {barcode_data}")
        else:
            self.update_status(f"라벨 바코드 감지: {barcode_data} (출고 탭에서 사용하세요)")
    
    def process_location_barcode(self, barcode_data):
        """보관위치 바코드 처리"""
        # 현재 탭이 출고 탭인지 확인
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:  # 출고 탭
            self.location_var.set(barcode_data)
            self.update_status(f"✅ 보관위치 스캔 완료: {barcode_data}")
            # 자동으로 제품코드 필드로 포커스 이동
            self.root.after(100, lambda: self.product_entry.focus())
        else:
            self.update_status(f"보관위치 바코드 감지: {barcode_data} (출고 탭에서 사용하세요)")
    
    def process_product_barcode(self, barcode_data):
        """제품 바코드 처리"""
        # 현재 탭이 출고 탭인지 확인
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:  # 출고 탭
            # 88로 시작하는 제품 바코드인지 확인
            if barcode_data.startswith('88'):
                # 바코드-제품코드 매핑에서 찾기
                if barcode_data in self.barcode_to_product:
                    product_code = self.barcode_to_product[barcode_data]
                    self.product_var.set(product_code.upper())
                    # 제품명 자동 업데이트
                    self.update_product_name_display(product_code.upper())
                    
                    # 보관위치가 입력되어 있고 동일한 제품코드인 경우 수량 증가
                    current_location = self.location_var.get().strip()
                    current_product = self.product_var.get().strip()
                    current_quantity = self.quantity_var.get().strip()
                    
                    if current_location and current_product == product_code.upper():
                        try:
                            current_qty = int(current_quantity) if current_quantity.isdigit() else 1
                            new_qty = current_qty + 1
                            self.quantity_var.set(str(new_qty))
                            self.update_status(f"✅ 제품코드 매칭 완료: {product_code} (수량 증가: {new_qty})")
                        except ValueError:
                            self.quantity_var.set("1")
                            self.update_status(f"✅ 제품코드 매칭 완료: {product_code}")
                    else:
                        self.update_status(f"✅ 제품코드 매칭 완료: {product_code}")
                    
                    # 자동으로 반출자 필드로 포커스 이동
                    self.root.after(100, lambda: self.outbounder_entry.focus())
                else:
                    self.update_status(f"❌ 등록되지 않은 제품 바코드: {barcode_data}")
            else:
                # 88로 시작하지 않는 경우 일반 제품코드로 처리
                self.product_var.set(barcode_data.upper())
                self.update_product_name_display(barcode_data.upper())
                self.update_status(f"✅ 제품코드 입력: {barcode_data}")
                # 자동으로 반출자 필드로 포커스 이동
                self.root.after(100, lambda: self.outbounder_entry.focus())
        else:
            self.update_status(f"제품 바코드 감지: {barcode_data} (출고 탭에서 사용하세요)")
    
    def load_data(self):
        """데이터 로드"""
        try:
            # 발행 내역 데이터 로드
            history_file = "issue_history.xlsx"
            print(f"발행 내역 파일 경로: {os.path.abspath(history_file)}")
            print(f"파일 존재 여부: {os.path.exists(history_file)}")
            
            if os.path.exists(history_file):
                self.df = pd.read_excel(history_file)
                print(f"데이터 로드 성공: {len(self.df)} 행")
                print(f"컬럼: {list(self.df.columns)}")
            else:
                print("발행 내역 파일이 없습니다.")
                self.df = pd.DataFrame()
            
            # 제품 데이터 로드 (label_gui.py에서 사용하는 방식과 동일)
            try:
                from execute_query import call_query
                from mysql_auth import boosta_boosters
                from boosters_query import q_boosters_items_for_barcode_reader
                
                df_products = call_query(q_boosters_items_for_barcode_reader.query, boosta_boosters)
                self.products = dict(zip(df_products['제품코드'].astype(str), df_products['제품명']))
                print(f"제품 데이터 로드 성공: {len(self.products)} 개")
            except Exception as e:
                print(f"제품 데이터 로드 실패: {e}")
                self.products = {"TEST001": "테스트 제품"}
                
        except Exception as e:
            print(f"데이터 로드 중 오류: {e}")
            messagebox.showerror("오류", f"데이터 로드 중 오류: {e}")
            self.df = pd.DataFrame()
            self.products = {"TEST001": "테스트 제품"}
    
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
                             text="입고와 관련된 아래버튼을 눌러주세요.\n📷 바코드를 스캔하면 자동으로 인식됩니다.",
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
        

    
    def create_location_tab(self):
        """위치 확인 탭 생성 - location_visualizer.py의 모든 기능 통합"""
        location_frame = ttk.Frame(self.notebook)
        self.notebook.add(location_frame, text="🗺️ 위치 확인")
        
        # 위치 확인 탭 내용 - 제목과 설명 제거하여 시각화 공간 확보
        
        # 위치 시각화 화면을 직접 임베드
        try:
            # 시각화 프레임 생성 - 더 많은 공간 확보
            visualizer_frame = tk.Frame(location_frame)
            visualizer_frame.pack(pady=10, fill=tk.BOTH, expand=True)
            
            # 위치 시각화 제목 - 패딩 줄여서 공간 확보
            visualizer_title = tk.Label(visualizer_frame, text="🗺️ 재고 위치 시각화", 
                                      font=("맑은 고딕", 14, "bold"), fg="#4CAF50")
            visualizer_title.pack(pady=5)
            
            # 설명 - 패딩 줄여서 공간 확보
            info_label = tk.Label(visualizer_frame, 
                                 text="각 칸을 클릭하면 해당 위치의 상세 정보를 확인할 수 있습니다.",
                                 font=("맑은 고딕", 10))
            info_label.pack(pady=2)
            
            # 자동 바코드 리딩 안내 - 패딩 줄여서 공간 확보
            barcode_info_label = tk.Label(visualizer_frame, 
                                         text="💡 바코드 스캐너를 사용하면 자동으로 제품을 검색합니다.",
                                         font=("맑은 고딕", 9), fg="#4CAF50")
            barcode_info_label.pack(pady=1)
            
            # 상태 표시 라벨
            status_label = tk.Label(visualizer_frame, 
                                   text="",
                                   font=("맑은 고딕", 10), fg="#2196F3")
            status_label.pack(pady=2)
            
            # 컨트롤 프레임 - 패딩 줄여서 공간 확보
            control_frame = tk.Frame(visualizer_frame)
            control_frame.pack(pady=5)
            
            # 새로고침 버튼
            refresh_btn = tk.Button(control_frame, text="🔄 새로고침", 
                                   command=lambda: refresh_data(),
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
            search_field_var = tk.StringVar(value="제품코드")
            search_field_combo = ttk.Combobox(search_frame, textvariable=search_field_var, 
                                            values=["구분", "제품명", "제품코드", "LOT", "보관위치"], 
                                            width=10, state="readonly")
            search_field_combo.pack(side=tk.LEFT, padx=5)
            
            # 검색어 입력
            search_var = tk.StringVar()
            search_entry = tk.Entry(search_frame, textvariable=search_var, width=20)
            search_entry.pack(side=tk.LEFT, padx=5)
            
            # 검색 버튼
            search_btn = tk.Button(search_frame, text="🔍 검색", 
                                  command=lambda: apply_search(),
                                  bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                                  relief=tk.FLAT, bd=0, padx=10, pady=3)
            search_btn.pack(side=tk.LEFT, padx=5)
            
            # 초기화 버튼
            reset_btn = tk.Button(search_frame, text="🔄 초기화", 
                                 command=lambda: reset_search(),
                                 bg="#9C27B0", fg="white", font=("맑은 고딕", 10),
                                 relief=tk.FLAT, bd=0, padx=10, pady=3)
            reset_btn.pack(side=tk.LEFT, padx=5)
            

            
            # 구역 관리 버튼 - 구역 관리 후 자동 새로고침
            def open_zone_manager_with_refresh():
                try:
                    # 구역 관리 창 열기
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    zone_manager_path = os.path.join(script_dir, "zone_manager.py")
                    
                    if os.path.exists(zone_manager_path):
                        print("구역 관리 창을 엽니다...")
                        # 구역 관리 프로세스 시작
                        process = subprocess.Popen([sys.executable, zone_manager_path])
                        
                        # 프로세스가 종료될 때까지 대기
                        process.wait()
                        print("구역 관리 창이 닫혔습니다.")
                        
                        # 구역 관리 창이 닫힌 후 새로고침
                        self.root.after(2000, refresh_data)  # 2초 후 새로고침 (파일 저장 시간 고려)
                        
                        status_label.config(text="🔄 구역 관리 완료. 새로고침 중...", fg="#FF9800")
                    else:
                        messagebox.showerror("오류", "zone_manager.py 파일을 찾을 수 없습니다.")
                except Exception as e:
                    messagebox.showerror("오류", f"구역 관리 창을 열 수 없습니다: {str(e)}")
            
            zone_manage_btn = tk.Button(control_frame, text="⚙️ 구역 관리", 
                                       command=open_zone_manager_with_refresh,
                                       bg="#607D8B", fg="white", font=("맑은 고딕", 10),
                                       relief=tk.FLAT, bd=0, padx=15, pady=5)
            zone_manage_btn.pack(side=tk.LEFT, padx=5)
            
            # 라벨 발행 버튼
            label_btn = tk.Button(control_frame, text="🏷️ 라벨 발행", 
                                 command=self.open_label_gui,
                                 bg="#795548", fg="white", font=("맑은 고딕", 10),
                                 relief=tk.FLAT, bd=0, padx=15, pady=5)
            label_btn.pack(side=tk.LEFT, padx=5)
            
            # 시각화 프레임 - 패딩 줄여서 공간 확보
            viz_frame = tk.Frame(visualizer_frame)
            viz_frame.pack(pady=10, fill=tk.BOTH, expand=True)
            
            # 구역 설정 로드
            zone_config = self.load_zone_config()
            
            # 파일 감시 관련 변수
            config_file_path = "barcode_label/zone_config.json"
            last_config_mtime = os.path.getmtime(config_file_path) if os.path.exists(config_file_path) else 0
            watching = True
            
            # 파일 감시 스레드 시작
            def watch_config_file():
                nonlocal last_config_mtime
                while watching:
                    try:
                        if os.path.exists(config_file_path):
                            current_mtime = os.path.getmtime(config_file_path)
                            if current_mtime > last_config_mtime:
                                print(f"구역 설정 파일 변경 감지: {current_mtime} > {last_config_mtime}")
                                # 파일이 변경되었으면 메인 스레드에서 새로고침
                                self.root.after(0, refresh_on_config_change)
                                last_config_mtime = current_mtime
                        else:
                            # 파일이 없으면 기본 설정으로 새로고침
                            if last_config_mtime > 0:
                                print("구역 설정 파일이 삭제됨, 기본 설정으로 새로고침")
                                self.root.after(0, refresh_on_config_change)
                                last_config_mtime = 0
                    except Exception as e:
                        print(f"파일 감시 오류: {e}")
                    
                    time.sleep(0.5)  # 0.5초마다 확인 (더 빠른 감지)
            
            # 설정 변경 시 새로고침 함수
            def refresh_on_config_change():
                try:
                    print("구역 설정 새로고침 시작")
                    
                    # 구역 설정 다시 로드
                    nonlocal zone_config
                    zone_config = self.load_zone_config()
                    print(f"구역 설정 로드 완료: {len(zone_config.get('zones', {}))}개 구역")
                    
                    # 그리드 다시 생성
                    create_dynamic_grid()
                    print("그리드 재생성 완료")
                    
                    # 데이터 업데이트
                    update_dynamic_grid()
                    print("데이터 업데이트 완료")
                    
                    # 상태 메시지 표시
                    status_label.config(text="✅ 구역 설정이 자동으로 새로고침되었습니다!", fg="#4CAF50")
                    self.root.after(3000, lambda: status_label.config(text="", fg="#2196F3"))
                    
                    print("구역 설정 새로고침 완료")
                    
                except Exception as e:
                    print(f"설정 새로고침 오류: {e}")
                    status_label.config(text=f"❌ 구역 설정 새로고침 실패: {e}", fg="#F44336")
            
            # 파일 감시 스레드 시작
            watch_thread = threading.Thread(target=watch_config_file, daemon=True)
            watch_thread.start()
            
            # 스크롤 가능한 캔버스 생성
            canvas_frame = tk.Frame(viz_frame)
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            
            # 캔버스와 스크롤바
            canvas = tk.Canvas(canvas_frame, bg="white")
            v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
            h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
            
            canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # 스크롤바 배치
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 마우스 휠 스크롤 기능 추가
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
            def on_shift_mousewheel(event):
                canvas.xview_scroll(int(-1*(event.delta/120)), "units")
            
            # 마우스 휠 이벤트 바인딩
            canvas.bind("<MouseWheel>", on_mousewheel)
            canvas.bind("<Shift-MouseWheel>", on_shift_mousewheel)
            
            # 구역들을 담을 메인 프레임 (캔버스 내부)
            zones_container = tk.Frame(canvas)
            canvas.create_window((0, 0), window=zones_container, anchor=tk.NW)
            
            # 그리드 생성
            zone_grids = {}
            
            # 셀 클릭 이벤트 처리 함수 (먼저 정의)
            def on_cell_click(location, button, event=None):
                # 클릭된 버튼의 원래 상태 저장
                original_bg = button.cget("bg")
                original_relief = button.cget("relief")
                original_text = button.cget("text")
                original_font = button.cget("font")
                original_fg = button.cget("fg")
                
                # 시각적 피드백 제공 (눌린 상태로 변경)
                button.config(bg="#FFD700", relief=tk.SUNKEN)  # 노란색 배경, 눌린 효과
                
                # 해당 위치의 데이터 확인
                location_df = self.df[self.df["보관위치"] == location] if not self.df.empty else pd.DataFrame()
                
                if location_df.empty:
                    # 빈 위치인 경우 바로 라벨 생성 옵션 제공
                    def restore_button_state():
                        button.config(bg=original_bg, relief=original_relief, 
                                    text=original_text, font=original_font, fg=original_fg)
                    
                    # 1초 후 자동 복원
                    self.root.after(1000, lambda: safe_restore_button(button, original_bg, original_relief, 
                                                                       original_text, original_font, original_fg))
                    
                    # 라벨 생성 옵션 제공
                    result = messagebox.askyesno("빈 위치", 
                                               f"{location}\n\n이 위치에는 아직 라벨이 발행되지 않았습니다.\n\n이 위치에 새 라벨을 생성하시겠습니까?")
                    if result:
                        create_label_for_location(location)
                    
                    # 버튼 상태 복원
                    restore_button_state()
                    return
                
                # 데이터가 있는 경우 상세 정보 창 열기
                detail_window = tk.Toplevel(self.root)
                detail_window.title(f"{location} 상세 정보")
                detail_window.geometry("1000x400")
                detail_window.transient(self.root)  # 모달 창으로 설정
                detail_window.grab_set()  # 다른 창과의 상호작용 차단
                
                # 창이 닫힐 때 원래 상태로 복원하는 함수
                def restore_button_state():
                    # 원래 상태로 완전히 복원
                    button.config(bg=original_bg, relief=original_relief, 
                                text=original_text, font=original_font, fg=original_fg)
                    detail_window.destroy()
                
                # 창 닫기 이벤트 바인딩
                detail_window.protocol("WM_DELETE_WINDOW", restore_button_state)
                
                # 안전장치: 2초 후 자동 복원 (창이 닫히지 않았을 경우)
                self.root.after(2000, lambda: safe_restore_button(button, original_bg, original_relief, 
                                                                   original_text, original_font, original_fg))
                
                # 상세 정보 표시
                show_location_detail_in_window(location, detail_window, restore_button_state)
            
            # 안전하게 버튼 상태를 복원하는 함수
            def safe_restore_button(button, original_bg, original_relief, original_text, original_font, original_fg):
                try:
                    # 버튼이 여전히 존재하는지 확인
                    if button.winfo_exists():
                        button.config(bg=original_bg, relief=original_relief, 
                                    text=original_text, font=original_font, fg=original_fg)
                except Exception as e:
                    print(f"버튼 복원 오류: {e}")
            
            # 지정된 창에 위치 상세 정보 표시 (두 번째 정의)
            def show_location_detail_in_window(location, window, restore_callback):
                if self.df.empty:
                    restore_callback()
                    return
                
                # 해당 위치의 데이터 필터링
                location_df = self.df[self.df["보관위치"] == location]
                
                # 데이터가 있는 경우만 상세 정보 표시 (빈 위치는 이미 on_cell_click에서 처리됨)
                if location_df.empty:
                    restore_callback()
                    return
                
                # 제목
                title_label = tk.Label(window, text=f"{location} 위치 상세 정보", 
                                      font=("맑은 고딕", 14, "bold"))
                title_label.pack(pady=10)
                
                # 통계 정보
                stats_frame = tk.Frame(window)
                stats_frame.pack(pady=10)
                
                if isinstance(location_df, pd.DataFrame):
                    try:
                        total_items = len(location_df)
                        unique_products = len(location_df["제품명"].unique())
                        
                        stats_label = tk.Label(stats_frame, 
                                             text=f"총 {total_items}개 라벨, {unique_products}개 제품",
                                             font=("맑은 고딕", 12))
                        stats_label.pack()
                        
                        # 상세 정보 표시 (Treeview)
                        tree_frame = tk.Frame(window)
                        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                        
                        # 스크롤바가 있는 Treeview
                        tree_scroll = tk.Scrollbar(tree_frame)
                        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
                        
                        tree = ttk.Treeview(tree_frame, columns=("제품명", "제품코드", "LOT", "유통기한", "폐기일자"), 
                                          show="headings", yscrollcommand=tree_scroll.set)
                        tree_scroll.config(command=tree.yview)
                        
                        # 컬럼 설정
                        tree.heading("제품명", text="제품명")
                        tree.heading("제품코드", text="제품코드")
                        tree.heading("LOT", text="LOT")
                        tree.heading("유통기한", text="유통기한")
                        tree.heading("폐기일자", text="폐기일자")
                        
                        tree.column("제품명", width=200)
                        tree.column("제품코드", width=100)
                        tree.column("LOT", width=100)
                        tree.column("유통기한", width=100)
                        tree.column("폐기일자", width=100)
                        
                        # 데이터 삽입
                        for _, row in location_df.iterrows():
                            try:
                                # 폐기일자 계산
                                expiry_date = pd.to_datetime(row["유통기한"])
                                disposal_date = expiry_date.replace(year=expiry_date.year + 1)
                                disposal_str = disposal_date.strftime("%Y-%m-%d")
                            except:
                                disposal_str = "N/A"
                            
                            tree.insert("", "end", values=(
                                row["제품명"],
                                row["제품코드"],
                                row["LOT"],
                                row["유통기한"],
                                disposal_str
                            ))
                        
                        tree.pack(fill=tk.BOTH, expand=True)
                        
                        # 버튼 프레임
                        button_frame = tk.Frame(window)
                        button_frame.pack(pady=10)
                        
                        # 라벨 생성 버튼
                        create_btn = tk.Button(button_frame, text="➕ 새 라벨 생성", 
                                             command=lambda: create_label_for_location(location),
                                             bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                             relief=tk.FLAT, bd=0, padx=15, pady=5)
                        create_btn.pack(side=tk.LEFT, padx=5)
                        
                        # 닫기 버튼
                        close_btn = tk.Button(button_frame, text="닫기", 
                                            command=restore_callback,
                                            bg="#f44336", fg="white", font=("맑은 고딕", 10),
                                            relief=tk.FLAT, bd=0, padx=15, pady=5)
                        close_btn.pack(side=tk.LEFT, padx=5)
                        
                    except Exception as e:
                        error_label = tk.Label(window, text=f"데이터 표시 오류: {e}", fg="red")
                        error_label.pack(pady=10)
                        restore_callback()
                else:
                    error_label = tk.Label(window, text="데이터 형식 오류", fg="red")
                    error_label.pack(pady=10)
                    restore_callback()
            
            # 라벨 생성 함수
            def create_label_for_location(location):
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
            
            # 동적 그리드 생성 함수
            def create_dynamic_grid():
                # 기존 그리드 위젯들 제거
                for widget in zones_container.winfo_children():
                    widget.destroy()
                
                if not zone_config["zones"]:
                    # 구역이 없으면 안내 메시지
                    no_zones_label = tk.Label(zones_container, 
                                             text="구역이 설정되지 않았습니다.\n구역 관리에서 구역을 추가해주세요.",
                                             font=("맑은 고딕", 12), fg="gray")
                    no_zones_label.pack(pady=50)
                    return
                
                # 구역별 그리드 생성
                nonlocal zone_grids
                zone_grids = {}
                
                # 구역별 그리드 생성
                for zone_code, zone_data in zone_config["zones"].items():
                    # 구역 프레임 생성
                    zone_frame = tk.Frame(zones_container)
                    zone_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
                    
                    # 구역 제목
                    zone_title = tk.Label(zone_frame, text=zone_data["name"], 
                                         font=("맑은 고딕", 12, "bold"), fg=zone_data["color"])
                    zone_title.pack(pady=5)
                    
                    # 구역 그리드 프레임
                    zone_grid_frame = tk.Frame(zone_frame)
                    zone_grid_frame.pack()
                    
                    # 구역별 그리드 생성
                    sections = zone_data["sections"]
                    zone_grid = []
                    
                    # 구역 수와 화면 크기에 따른 동적 크기 조정
                    total_zones = len(zone_config["zones"])
                    
                    # 실제 캔버스 크기 확인
                    canvas.update_idletasks()
                    canvas_width = canvas.winfo_width()
                    canvas_height = canvas.winfo_height()
                    
                    # 기본 크기 설정 (캔버스가 아직 렌더링되지 않은 경우)
                    if canvas_width <= 1:
                        canvas_width = 800
                    if canvas_height <= 1:
                        canvas_height = 600
                    
                    # 구역당 사용 가능한 공간 계산
                    available_width_per_zone = max(200, canvas_width // total_zones - 30)
                    available_height_per_zone = max(250, canvas_height - 150)
                    
                    # 섹션 크기에 따른 셀 크기 조정
                    max_sections_in_zone = max([zone["sections"]["rows"] * zone["sections"]["columns"] 
                                              for zone in zone_config["zones"].values()])
                    
                    # 더 큰 기본 크기로 설정
                    if total_zones <= 2:
                        cell_width = 18
                        cell_height = 7
                        font_size = 12
                    elif total_zones <= 3:
                        cell_width = 16
                        cell_height = 6
                        font_size = 11
                    elif total_zones <= 4:
                        cell_width = 14
                        cell_height = 5
                        font_size = 10
                    elif total_zones <= 6:
                        cell_width = 12
                        cell_height = 4
                        font_size = 9
                    else:
                        cell_width = 10
                        cell_height = 3
                        font_size = 8
                    
                    for row in range(sections["rows"]):
                        grid_row = []
                        for col in range(sections["columns"]):
                            location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                            
                            cell = tk.Button(zone_grid_frame, 
                                           text=location, 
                                           width=cell_width, 
                                           height=cell_height,
                                           font=("맑은 고딕", font_size), 
                                           relief=tk.RAISED, bd=1)
                            cell.grid(row=row, column=col, padx=1, pady=1)
                            cell.bind("<Button-1>", partial(on_cell_click, location, cell))
                            grid_row.append(cell)
                        zone_grid.append(grid_row)
                    
                    zone_grids[zone_code] = zone_grid
                
                # 스크롤 영역 업데이트
                zones_container.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
            
            # 초기 그리드 생성
            create_dynamic_grid()
            
            # 데이터 새로고침 함수
            def refresh_data():
                try:
                    # 데이터 재로드
                    self.load_data()
                    
                    # 구역 설정 재로드
                    nonlocal zone_config
                    zone_config = self.load_zone_config()
                    
                    # 그리드 재생성
                    create_dynamic_grid()
                    
                    # 데이터 업데이트
                    update_dynamic_grid()
                    
                    status_label.config(text="✅ 데이터와 구역 설정이 새로고침되었습니다.", fg="#4CAF50")
                    self.root.after(3000, lambda: status_label.config(text="", fg="#2196F3"))
                except Exception as e:
                    status_label.config(text=f"❌ 새로고침 실패: {e}", fg="#F44336")
            
            # 검색 적용 함수
            def apply_search():
                search_term = search_var.get().strip()
                search_field = search_field_var.get()
                
                if search_term:
                    # 검색 조건에 맞는 데이터만 필터링
                    filtered_df = self.df[self.df[search_field].astype(str).str.contains(search_term, case=False, na=False)]
                    update_dynamic_grid_with_data(filtered_df)
                    status_label.config(text=f"🔍 검색 결과: {len(filtered_df)}개 항목", fg="#FF9800")
                else:
                    # 검색어가 없으면 전체 데이터 표시
                    update_dynamic_grid()
                    status_label.config(text="", fg="#2196F3")
            
            # 검색 초기화 함수
            def reset_search():
                search_var.set("")
                update_dynamic_grid()
                status_label.config(text="✅ 검색이 초기화되었습니다.", fg="#4CAF50")
                self.root.after(3000, lambda: status_label.config(text="", fg="#2196F3"))
            

            
            # 셀 클릭 이벤트 처리
            def on_cell_click(location, button, event=None):
                # 클릭된 버튼의 원래 상태 저장
                original_bg = button.cget("bg")
                original_relief = button.cget("relief")
                original_text = button.cget("text")
                original_font = button.cget("font")
                original_fg = button.cget("fg")
                
                # 시각적 피드백 제공 (눌린 상태로 변경)
                button.config(bg="#FFD700", relief=tk.SUNKEN)  # 노란색 배경, 눌린 효과
                
                # 상세 정보 창을 모달로 열기
                detail_window = tk.Toplevel(self.root)
                detail_window.title(f"{location} 상세 정보")
                detail_window.geometry("1000x400")
                detail_window.transient(self.root)  # 모달 창으로 설정
                detail_window.grab_set()  # 다른 창과의 상호작용 차단
                
                # 창이 닫힐 때 원래 상태로 복원하는 함수
                def restore_button_state():
                    # 원래 상태로 완전히 복원
                    button.config(bg=original_bg, relief=original_relief, 
                                text=original_text, font=original_font, fg=original_fg)
                    detail_window.destroy()
                
                # 창 닫기 이벤트 바인딩
                detail_window.protocol("WM_DELETE_WINDOW", restore_button_state)
                
                # 안전장치: 2초 후 자동 복원 (창이 닫히지 않았을 경우)
                self.root.after(2000, lambda: safe_restore_button(button, original_bg, original_relief, 
                                                                   original_text, original_font, original_fg))
                
                # 상세 정보 표시
                show_location_detail_in_window(location, detail_window, restore_button_state)
            
            # 안전하게 버튼 상태를 복원하는 함수
            def safe_restore_button(button, original_bg, original_relief, original_text, original_font, original_fg):
                try:
                    # 버튼이 여전히 존재하는지 확인
                    if button.winfo_exists():
                        button.config(bg=original_bg, relief=original_relief, 
                                    text=original_text, font=original_font, fg=original_fg)
                except Exception as e:
                    print(f"버튼 복원 오류: {e}")
            
            # 지정된 창에 위치 상세 정보 표시
            def show_location_detail_in_window(location, window, restore_callback):
                if self.df.empty:
                    restore_callback()
                    return
                
                # 해당 위치의 데이터 필터링
                location_df = self.df[self.df["보관위치"] == location]
                
                if location_df.empty:
                    # 라벨이 없는 경우 라벨 생성 옵션 제공
                    window.destroy()
                    result = messagebox.askyesno("위치 정보", 
                                               f"{location}\n\n이 위치에는 아직 라벨이 발행되지 않았습니다.\n\n이 위치에 새 라벨을 생성하시겠습니까?")
                    if result:
                        create_label_for_location(location)
                    restore_callback()
                    return
                
                # 제목
                title_label = tk.Label(window, text=f"{location} 위치 상세 정보", 
                                      font=("맑은 고딕", 14, "bold"))
                title_label.pack(pady=10)
                
                # 통계 정보
                stats_frame = tk.Frame(window)
                stats_frame.pack(pady=10)
                
                if isinstance(location_df, pd.DataFrame):
                    try:
                        unique_products = location_df["제품명"].dropna().nunique()
                    except Exception:
                        unique_products = len(set(location_df["제품명"]))
                else:
                    try:
                        unique_products = len(set([row["제품명"] for _, row in location_df.iterrows() if row["제품명"]]))
                    except Exception:
                        unique_products = 0
                total_items = len(location_df)
                
                tk.Label(stats_frame, text=f"총 제품 수: {unique_products}개", font=("맑은 고딕", 10)).pack()
                tk.Label(stats_frame, text=f"총 라벨 수: {total_items}개", font=("맑은 고딕", 10)).pack()
                
                # 상세 테이블
                tree_frame = tk.Frame(window)
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
                    is_na = False
                    try:
                        is_na = bool(pd.isna(disposal_date))
                    except Exception:
                        is_na = disposal_date is None
                    if disposal_date == "N/A" or (isinstance(disposal_date, str) and disposal_date == "N/A") or is_na:
                        try:
                            expiry_date = pd.to_datetime(row["유통기한"])
                            if isinstance(expiry_date, pd.Timestamp):
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
                button_frame = tk.Frame(window)
                button_frame.pack(pady=10)
                
                create_label_btn = tk.Button(button_frame, text="🏷️ 이 위치에 새 라벨 생성", 
                                           command=lambda: create_label_for_location(location),
                                           bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                           relief=tk.FLAT, bd=0, padx=15, pady=5)
                create_label_btn.pack(side=tk.LEFT, padx=5)
                
                # 닫기 버튼
                close_btn = tk.Button(button_frame, text="닫기", 
                                     command=restore_callback,
                                     bg="#f44336", fg="white", font=("맑은 고딕", 10),
                                     relief=tk.FLAT, bd=0, padx=15, pady=5)
                close_btn.pack(side=tk.LEFT, padx=5)
            
            # 라벨 생성 함수 (두 번째 정의)
            def create_label_for_location(location):
                try:
                    # 라벨 GUI 창 열기
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    label_gui_path = os.path.join(script_dir, "label_gui.py")
                    
                    print(f"라벨 GUI 경로: {label_gui_path}")
                    print(f"파일 존재 여부: {os.path.exists(label_gui_path)}")
                    print(f"보관위치: {location}")
                    
                    if os.path.exists(label_gui_path):
                        # 라벨 GUI를 새 프로세스로 실행 (보관위치 인수 전달)
                        process = subprocess.Popen([sys.executable, label_gui_path, "--location", location])
                        
                        # 프로세스 시작 확인
                        if process.poll() is None:
                            print("라벨 GUI 프로세스가 성공적으로 시작되었습니다.")
                            
                            # 사용자에게 안내 메시지
                            messagebox.showinfo("라벨 생성", 
                                              f"라벨 발행 창이 열렸습니다.\n\n"
                                              f"보관위치: {location}\n\n"
                                              f"보관위치가 자동으로 설정되었습니다.\n"
                                              f"나머지 정보를 입력한 후 라벨을 생성하세요.")
                        else:
                            print("라벨 GUI 프로세스 시작 실패")
                            messagebox.showerror("오류", "라벨 발행 창을 시작할 수 없습니다.")
                    else:
                        print(f"label_gui.py 파일을 찾을 수 없습니다: {label_gui_path}")
                        messagebox.showerror("오류", f"label_gui.py 파일을 찾을 수 없습니다.\n경로: {label_gui_path}")
                        
                except Exception as e:
                    print(f"라벨 생성 오류: {e}")
                    messagebox.showerror("오류", f"라벨 생성 창을 열 수 없습니다: {str(e)}")
            
            # 셀 업데이트 함수
            def update_cell(cell, location, items, is_search_result=False):
                # 구역 수에 따른 동적 폰트 크기 계산
                total_zones = len(zone_config["zones"])
                if total_zones <= 2:
                    font_size = 12
                elif total_zones <= 3:
                    font_size = 11
                elif total_zones <= 4:
                    font_size = 10
                elif total_zones <= 6:
                    font_size = 9
                else:
                    font_size = 8  # 7개 이상 구역일 때 가장 작게
                
                # 원래 relief 상태 보존
                original_relief = cell.cget("relief")
                
                if not items:
                    # 빈 위치
                    cell.config(text=f"{location}\n\n(빈 위치)", 
                               bg="#f5f5f5", fg="gray", font=("맑은 고딕", font_size),
                               relief=original_relief)  # 원래 relief 상태 유지
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
                    cell.config(text=cell_text, bg=bg_color, fg=fg_color, font=("맑은 고딕", font_size),
                               relief=original_relief)  # 원래 relief 상태 유지
            
            # 동적 그리드 업데이트 함수
            def update_dynamic_grid():
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
                for zone_code, zone_data in zone_config["zones"].items():
                    if zone_code not in zone_grids:
                        continue
                        
                    zone_grid = zone_grids[zone_code]
                    sections = zone_data["sections"]
                    
                    for row in range(sections["rows"]):
                        for col in range(sections["columns"]):
                            location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                            cell = zone_grid[row][col]
                            update_cell(cell, location, location_data.get(location, []), is_search_result=False)
            
            # 필터링된 데이터로 동적 그리드 업데이트 함수
            def update_dynamic_grid_with_data(filtered_df):
                if filtered_df.empty:
                    # 모든 셀을 빈 상태로 설정
                    for zone_code, zone_data in zone_config["zones"].items():
                        if zone_code not in zone_grids:
                            continue
                            
                        zone_grid = zone_grids[zone_code]
                        sections = zone_data["sections"]
                        
                        for row in range(sections["rows"]):
                            for col in range(sections["columns"]):
                                location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                                cell = zone_grid[row][col]
                                # 원래 relief 상태 보존
                                original_relief = cell.cget("relief")
                                cell.config(text=f"{location}\n\n(검색 결과 없음)", 
                                           bg="#f5f5f5", fg="gray",
                                           relief=original_relief)
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
                for zone_code, zone_data in zone_config["zones"].items():
                    if zone_code not in zone_grids:
                        continue
                        
                    zone_grid = zone_grids[zone_code]
                    sections = zone_data["sections"]
                    
                    for row in range(sections["rows"]):
                        for col in range(sections["columns"]):
                            location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                            cell = zone_grid[row][col]
                            update_cell(cell, location, location_data.get(location, []), is_search_result=True)
            
            # 구역 설정 로드 함수
            def load_zone_config():
                try:
                    zone_config_file = "zone_config.json"
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
            
            # 초기 데이터 표시
            update_dynamic_grid()
            
            # 창 닫기 시 파일 감시 중단
            def on_tab_closing():
                nonlocal watching
                watching = False
            
            # 탭 변경 이벤트에 감시 중단 추가
            def on_tab_changed(event):
                nonlocal watching
                current_tab = self.notebook.index(self.notebook.select())
                if current_tab != 2:  # 위치 확인 탭이 아닐 때
                    watching = False
                else:  # 위치 확인 탭으로 돌아올 때
                    watching = True
                    # 파일 감시 스레드 재시작
                    watch_thread = threading.Thread(target=watch_config_file, daemon=True)
                    watch_thread.start()
            
            # 탭 변경 이벤트 바인딩
            self.notebook.bind("<<NotebookTabChanged>>", on_tab_changed)
            
        except Exception as e:
            # 시각화 로드 실패 시 대체 화면
            error_frame = tk.Frame(location_frame)
            error_frame.pack(pady=50)
            
            error_label = tk.Label(error_frame, text=f"시각화를 로드할 수 없습니다: {e}", 
                                  font=("맑은 고딕", 12), fg="#F44336")
            error_label.pack(pady=10)
            
            # 대체 버튼
            visualizer_btn = tk.Button(error_frame, text="🗺️ 위치 확인 실행", 
                                      command=self.open_visualizer,
                                      bg="#FF9800", fg="white", font=("맑은 고딕", 12, "bold"),
                                      relief=tk.FLAT, bd=0, padx=40, pady=15)
            visualizer_btn.pack(pady=20)
    
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
                             text="출고할 제품의 위치와 제품코드를 입력하세요.\n📷 바코드를 스캔하면 자동으로 인식됩니다.",
                             font=("맑은 고딕", 12))
        desc_label.pack(pady=10)
        
        # 관리품 출고 제한 안내
        restriction_label = tk.Label(outbound_frame, 
                                   text="⚠️ 주의: 관리품은 출고할 수 없습니다. 샘플재고만 출고 가능합니다.",
                                   font=("맑은 고딕", 11), fg="#F44336")
        restriction_label.pack(pady=5)
        
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
        
        # 바코드 자동 감지 안내
        barcode_info_label = tk.Label(location_frame, text="📷 바코드 자동 감지", 
                                     font=("맑은 고딕", 10), fg="#2196F3")
        barcode_info_label.pack(side=tk.LEFT, padx=10)
        
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
        
        # 제품 바코드 자동 감지 안내
        product_barcode_info_label = tk.Label(product_frame, text="📷 제품 바코드 자동 감지", 
                                            font=("맑은 고딕", 10), fg="#2196F3")
        product_barcode_info_label.pack(side=tk.LEFT, padx=10)
        
        # LOT 정보 표시 라벨
        self.lot_info_label = tk.Label(product_frame, text="", 
                                      font=("맑은 고딕", 10), fg="#FF9800")
        self.lot_info_label.pack(side=tk.LEFT, padx=10)
        
        # 유통기한 정보 표시 라벨
        self.expiry_info_label = tk.Label(product_frame, text="", 
                                         font=("맑은 고딕", 10), fg="#E91E63")
        self.expiry_info_label.pack(side=tk.LEFT, padx=10)
        
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
        
        # 반출자 필드에서 바코드 감지 시 자동 처리
        self.outbounder_entry.bind('<KeyRelease>', self.on_outbounder_field_change)
        
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
        
        # 수량 필드에서 바코드 감지 시 자동으로 반출자 필드로 이동
        self.quantity_entry.bind('<KeyRelease>', self.on_quantity_field_change)
        
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
        self.quantity_entry.bind('<Return>', lambda e: self.outbounder_entry.focus())
        self.outbounder_entry.bind('<Return>', lambda e: self.execute_outbound())
    
    def open_label_gui(self):
        """라벨 발행 GUI 열기"""
        try:
            # 현재 스크립트의 디렉토리를 기준으로 실행
            script_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen([sys.executable, "label_gui.py"], cwd=script_dir)
            self.update_status("라벨 발행 창이 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"라벨 발행 창을 열 수 없습니다: {e}")
    
    def open_dashboard(self):
        """재고 대시보드 열기"""
        try:
            # 현재 스크립트의 디렉토리를 기준으로 실행
            script_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen([sys.executable, "label_dashboard.py"], cwd=script_dir)
            self.update_status("재고 대시보드가 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"재고 대시보드를 열 수 없습니다: {e}")
    
    def open_visualizer(self):
        """위치 시각화 열기 - 위치 확인 탭으로 이동"""
        try:
            # 위치 확인 탭으로 이동 (인덱스 2)
            self.notebook.select(2)
            self.update_status("✅ 위치 확인 탭으로 이동했습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"위치 확인 탭으로 이동할 수 없습니다: {e}")
    
    def open_zone_manager(self):
        """구역 관리 열기"""
        try:
            # 현재 스크립트의 디렉토리를 기준으로 실행
            script_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen([sys.executable, "zone_manager.py"], cwd=script_dir)
            self.update_status("구역 관리가 열렸습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"구역 관리를 열 수 없습니다: {e}")
    
    def open_inbound_barcode_reader(self):
        """입고 바코드 리딩 창 열기"""
        def submit_barcode():
            barcode_data = barcode_entry.get().strip()
            if barcode_data:
                if barcode_data == "INBOUND" or barcode_data == "입고":
                    # 현재 탭 확인
                    current_tab = self.notebook.index(self.notebook.select())
                    if current_tab == 0:  # 이미 입고 탭에 있는 경우
                        # 라벨 발행/인쇄 창 열기
                        self.open_label_gui()
                        self.update_status("✅ 라벨 발행/인쇄 창이 열렸습니다.")
                    else:
                        # 입고 탭으로 전환
                        self.notebook.select(0)  # 첫 번째 탭 (입고)
                        self.update_status("✅ 입고 관리 탭으로 전환되었습니다.")
                    top.destroy()
                elif barcode_data == "OUTBOUND" or barcode_data == "출고":
                    # 출고 탭으로 전환
                    self.notebook.select(1)  # 두 번째 탭 (출고)
                    self.update_status("✅ 출고 관리 탭으로 전환되었습니다.")
                    top.destroy()
                else:
                    messagebox.showwarning("바코드 오류", f"인식할 수 없는 바코드입니다: {barcode_data}\n\n입고: INBOUND 또는 입고\n출고: OUTBOUND 또는 출고")
                    barcode_entry.delete(0, tk.END)
                    barcode_entry.focus()
            else:
                messagebox.showwarning("입력 오류", "바코드를 입력하세요.")
        
        def simulate_inbound_barcode():
            barcode_entry.delete(0, tk.END)
            barcode_entry.insert(0, "INBOUND")
            submit_barcode()
        
        def simulate_outbound_barcode():
            barcode_entry.delete(0, tk.END)
            barcode_entry.insert(0, "OUTBOUND")
            submit_barcode()
        
        top = tk.Toplevel(self.root)
        top.title("입고/출고 바코드 리딩 - 탭 전환")
        top.geometry("500x400")
        top.resizable(False, False)
        
        # 제목
        title_label = tk.Label(top, text="입고/출고 바코드 리딩", font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=20)
        
        # 설명
        info_text = """입고/출고 바코드를 스캔하여 탭을 전환하세요:

📋 바코드 형식:
• 입고: INBOUND 또는 입고
• 출고: OUTBOUND 또는 출고

✅ 스캔 완료 후 해당 탭으로 자동 전환됩니다.
✅ 바코드 리딩이 성공하면 창이 자동으로 닫힙니다.

실제 바코드 스캐너를 사용하거나 아래 버튼으로 시뮬레이션하세요."""
        
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
        
        # 시뮬레이션 버튼들
        sim_inbound_btn = tk.Button(button_frame, text="🧪 입고 시뮬레이션", 
                                   command=simulate_inbound_barcode,
                                   bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                   relief=tk.FLAT, bd=0, padx=20, pady=5)
        sim_inbound_btn.pack(side=tk.LEFT, padx=5)
        
        sim_outbound_btn = tk.Button(button_frame, text="🧪 출고 시뮬레이션", 
                                    command=simulate_outbound_barcode,
                                    bg="#F44336", fg="white", font=("맑은 고딕", 10),
                                    relief=tk.FLAT, bd=0, padx=20, pady=5)
        sim_outbound_btn.pack(side=tk.LEFT, padx=5)
        
        # 취소 버튼
        cancel_btn = tk.Button(button_frame, text="창 닫기", command=top.destroy,
                              bg="#f44336", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def open_outbound_barcode_reader(self):
        """출고 바코드 리딩 창 열기 (입고 바코드 리딩과 동일한 기능)"""
        self.open_inbound_barcode_reader()
    
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
    
    def on_quantity_field_change(self, event=None):
        """수량 필드 변경 시 바코드 감지 및 자동 필드 이동"""
        quantity_value = self.quantity_var.get().strip()
        
        # 숫자가 아닌 문자가 입력되면 바코드로 간주
        if quantity_value and not quantity_value.isdigit():
            # 바코드 패턴 감지
            if quantity_value in ["INBOUND", "입고"]:
                self.process_inbound_barcode()
                self.quantity_var.set("1")  # 수량 초기화
            elif quantity_value in ["OUTBOUND", "출고"]:
                self.process_outbound_barcode()
                self.quantity_var.set("1")  # 수량 초기화
            elif quantity_value in ["LOCATION", "위치 확인", "위치확인"]:
                self.process_location_check_barcode()
                self.quantity_var.set("1")  # 수량 초기화
            elif re.match(r'^[AB]-(0[1-5])-(0[1-3])$', quantity_value):
                self.process_location_barcode(quantity_value)
                self.quantity_var.set("1")  # 수량 초기화
            elif re.match(r'^88\d{11}$', quantity_value):
                self.process_product_barcode(quantity_value)
                self.quantity_var.set("1")  # 수량 초기화
            elif re.match(r'^([A-Z][0-9]{3})-([A-Z0-9]+)-(\d{4}-\d{2}-\d{2})$', quantity_value):
                self.process_label_barcode(quantity_value)
                self.quantity_var.set("1")  # 수량 초기화
            else:
                # 일반 텍스트인 경우 반출자 필드로 이동
                self.outbounder_var.set(quantity_value)
                self.quantity_var.set("1")
                self.root.after(100, lambda: self.outbounder_entry.focus())
        else:
            # 숫자인 경우 기존 재고 확인 로직
            self.check_current_stock()
    
    def on_outbounder_field_change(self, event=None):
        """반출자 필드 변경 시 바코드 감지 및 자동 처리"""
        outbounder_value = self.outbounder_var.get().strip()
        
        # 바코드 패턴 감지
        if outbounder_value in ["INBOUND", "입고"]:
            self.process_inbound_barcode()
            self.outbounder_var.set("")  # 반출자 초기화
        elif outbounder_value in ["OUTBOUND", "출고"]:
            self.process_outbound_barcode()
            self.outbounder_var.set("")  # 반출자 초기화
        elif outbounder_value in ["LOCATION", "위치 확인", "위치확인"]:
            self.process_location_check_barcode()
            self.outbounder_var.set("")  # 반출자 초기화
        elif re.match(r'^[AB]-(0[1-5])-(0[1-3])$', outbounder_value):
            self.process_location_barcode(outbounder_value)
            self.outbounder_var.set("")  # 반출자 초기화
        elif re.match(r'^88\d{11}$', outbounder_value):
            self.process_product_barcode(outbounder_value)
            self.outbounder_var.set("")  # 반출자 초기화
        elif re.match(r'^([A-Z][0-9]{3})-([A-Z0-9]+)-(\d{4}-\d{2}-\d{2})$', outbounder_value):
            self.process_label_barcode(outbounder_value)
            self.outbounder_var.set("")  # 반출자 초기화
    
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
        
        # 관리품 출고 제한 확인
        category_column = '구분' if '구분' in stock_df.columns else 'category'
        if category_column in stock_df.columns:
            # 해당 제품의 구분 확인
            item_categories = stock_df[category_column].dropna().unique()
            
            # 관리품이 포함되어 있는지 확인
            if '관리품' in item_categories:
                messagebox.showerror("출고 제한", 
                                   f"❌ 관리품은 출고할 수 없습니다.\n\n"
                                   f"제품코드: {product_code}\n"
                                   f"제품명: {product_name}\n"
                                   f"보관위치: {location}\n\n"
                                   f"관리품은 샘플재고만 출고 가능합니다.")
                return
        
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
        self.lot_info_label.config(text="")  # LOT 정보 초기화
        self.expiry_info_label.config(text="")  # 유통기한 정보 초기화
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

        # 재고 재확인 및 관리품 출고 제한 확인
        insufficient_items = []
        management_items = []
        
        for item in self.batch_items:
            try:
                stock_mask = (
                    (self.df['보관위치'] == item['location']) & 
                    (self.df['제품코드'] == item['product_code'])
                )
                current_stock = len(self.df[stock_mask])
                if current_stock < item['quantity']:
                    insufficient_items.append(f"{item['location']} - {item['product_name']} (요청: {item['quantity']}개, 재고: {current_stock}개)")
                
                # 관리품 출고 제한 확인
                stock_df = pd.DataFrame(self.df[stock_mask]).copy()
                category_column = '구분' if '구분' in stock_df.columns else 'category'
                if category_column in stock_df.columns:
                    item_categories = stock_df[category_column].dropna().unique()
                    if '관리품' in item_categories:
                        management_items.append(f"{item['location']} - {item['product_name']} (관리품)")
                        
            except Exception as e:
                insufficient_items.append(f"{item['location']} - {item['product_name']} (재고 확인 오류)")

        # 관리품 출고 제한 오류 표시
        if management_items:
            messagebox.showerror("출고 제한", 
                               f"❌ 다음 항목들은 관리품이므로 출고할 수 없습니다:\n\n" + 
                               "\n".join(management_items) + 
                               "\n\n관리품은 샘플재고만 출고 가능합니다.")
            return

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
        
        # 보관위치가 입력되어 있고 동일한 제품코드인 경우 수량 증가
        current_location = self.location_var.get().strip()
        current_product = self.product_var.get().strip()
        current_quantity = self.quantity_var.get().strip()
        
        if current_location and current_product and current_product == product_code.upper():
            try:
                current_qty = int(current_quantity) if current_quantity.isdigit() else 1
                new_qty = current_qty + 1
                self.quantity_var.set(str(new_qty))
                self.update_status(f"✅ 제품코드 입력: {product_code} (수량 증가: {new_qty})")
            except ValueError:
                self.quantity_var.set("1")
                self.update_status(f"✅ 제품코드 입력: {product_code}")
    
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
                product_name = str(filtered_df['제품명'].iloc[0])
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
    
    def load_zone_config(self):
        """구역 설정 로드"""
        try:
            zone_config_file = "barcode_label/zone_config.json"
            print(f"구역 설정 파일 경로: {os.path.abspath(zone_config_file)}")
            print(f"파일 존재 여부: {os.path.exists(zone_config_file)}")
            
            if os.path.exists(zone_config_file):
                with open(zone_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"구역 설정 로드 성공: {len(config.get('zones', {}))}개 구역")
                    return config
            else:
                print("구역 설정 파일이 없어서 기본 설정을 사용합니다.")
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
            print(f"구역 설정 로드 오류: {e}")
            messagebox.showerror("구역 설정 오류", f"구역 설정을 로드할 수 없습니다: {e}")
            return {"zones": {}}

def main():
    root = tk.Tk()
    app = StockManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
