#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구역 관리 시스템
구역과 섹션을 동적으로 관리할 수 있는 GUI 프로그램
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from datetime import datetime

class ZoneManager:
    def __init__(self, root):
        self.root = root
        self.root.title("구역 관리 시스템")
        self.root.geometry("1200x800")
        
        # 설정 파일 경로
        self.config_file = "barcode_label/zone_config.json"
        
        # 설정 로드
        self.load_config()
        
        # 메인 프레임
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        title_label = tk.Label(main_frame, text="구역 관리 시스템", 
                              font=("맑은 고딕", 16, "bold"))
        title_label.pack(pady=10)
        
        # 설명
        info_label = tk.Label(main_frame, 
                             text="구역과 섹션을 동적으로 관리할 수 있습니다.\n구역을 추가/수정/삭제하고 각 구역의 섹션 크기를 설정하세요.",
                             font=("맑은 고딕", 10))
        info_label.pack(pady=5)
        
        # 컨트롤 프레임
        control_frame = tk.Frame(main_frame)
        control_frame.pack(pady=10)
        
        # 새로고침 버튼
        refresh_btn = tk.Button(control_frame, text="🔄 새로고침", 
                               command=self.refresh_display,
                               bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                               relief=tk.FLAT, bd=0, padx=15, pady=5)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # 구역 추가 버튼
        add_zone_btn = tk.Button(control_frame, text="➕ 구역 추가", 
                                command=self.add_zone_dialog,
                                bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                relief=tk.FLAT, bd=0, padx=15, pady=5)
        add_zone_btn.pack(side=tk.LEFT, padx=5)
        
        # 설정 저장 버튼
        save_btn = tk.Button(control_frame, text="💾 설정 저장", 
                            command=self.save_config,
                            bg="#FF9800", fg="white", font=("맑은 고딕", 10),
                            relief=tk.FLAT, bd=0, padx=15, pady=5)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        # 미리보기 버튼
        preview_btn = tk.Button(control_frame, text="👁 미리보기", 
                               command=self.preview_zones,
                               bg="#9C27B0", fg="white", font=("맑은 고딕", 10),
                               relief=tk.FLAT, bd=0, padx=15, pady=5)
        preview_btn.pack(side=tk.LEFT, padx=5)
        
        # 구역 목록 프레임
        zones_frame = tk.Frame(main_frame)
        zones_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 구역 목록 제목
        zones_title = tk.Label(zones_frame, text="현재 구역 설정", 
                              font=("맑은 고딕", 12, "bold"))
        zones_title.pack(pady=5)
        
        # 구역 목록 (Treeview)
        self.create_zones_treeview(zones_frame)
        
        # 선택 정보 표시 라벨
        self.selection_info_label = tk.Label(main_frame, 
                                            text="항목을 선택하세요 (Ctrl+클릭으로 다중 선택 가능)", 
                                            relief=tk.SUNKEN, bd=1, padx=10, pady=5)
        self.selection_info_label.pack(fill=tk.X, padx=10, pady=5)
        
        # 초기 데이터 로드
        self.refresh_display()
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                # 기본 설정
                self.config = {
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
            messagebox.showerror("설정 로드 오류", f"설정 파일을 로드할 수 없습니다: {e}")
            self.config = {"zones": {}, "default_location_format": "{zone}-{row:02d}-{col:02d}"}
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("저장 완료", "구역 설정이 저장되었습니다.\n\n시각화 창에서 자동으로 새로고침되고 창 크기가 조정됩니다.")
            
            # 시각화 창에 알림
            self.notify_visualizer()
            
        except Exception as e:
            messagebox.showerror("저장 오류", f"설정을 저장할 수 없습니다: {e}")
    
    def notify_visualizer(self):
        """시각화 창에 설정 변경 알림"""
        try:
            # 시각화 창이 열려있는지 확인하고 알림
            for widget in self.root.winfo_children():
                if isinstance(widget, tk.Toplevel) and "관리품 어디어디에 있을까" in widget.title():
                    # 알림 메시지 표시
                    notification = tk.Toplevel(widget)
                    notification.title("설정 변경 알림")
                    notification.geometry("350x180")
                    notification.resizable(False, False)
                    
                    # 알림 메시지
                    msg_label = tk.Label(notification, 
                                       text="✅ 구역 설정이 변경되었습니다!\n\n시각화가 자동으로 새로고침되고\n창 크기가 조정됩니다.",
                                       font=("맑은 고딕", 10), justify=tk.CENTER)
                    msg_label.pack(pady=20)
                    
                    # 확인 버튼
                    ok_btn = tk.Button(notification, text="확인", command=notification.destroy,
                                      bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                                      relief=tk.FLAT, bd=0, padx=20, pady=5)
                    ok_btn.pack(pady=10)
                    
                    # 3초 후 자동으로 닫기
                    notification.after(3000, notification.destroy)
                    break
        except:
            pass  # 시각화 창이 없으면 무시
        
        # 파일 감시를 통한 자동 새로고침도 작동하므로 추가 알림은 선택사항
    
    def create_zones_treeview(self, parent):
        """구역 목록 Treeview 생성"""
        # 프레임 생성
        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview 생성 (다중선택 가능)
        columns = ("구역코드", "구역명", "색상", "행", "열", "총 섹션", "설명")
        self.zones_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10, selectmode="extended")
        
        # 컬럼 설정
        column_widths = {
            "구역코드": 80,
            "구역명": 120,
            "색상": 100,  # 색상 이름이 더 길 수 있으므로 넓게
            "행": 50,
            "열": 50,
            "총 섹션": 80,
            "설명": 200
        }
        
        for col in columns:
            self.zones_tree.heading(col, text=col)
            self.zones_tree.column(col, width=column_widths.get(col, 100))
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.zones_tree.yview)
        self.zones_tree.configure(yscrollcommand=scrollbar.set)
        
        self.zones_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 더블클릭 이벤트
        self.zones_tree.bind("<Double-1>", self.edit_zone)
        
        # 선택 변경 이벤트 (선택된 항목 정보 표시)
        self.zones_tree.bind("<<TreeviewSelect>>", self.show_selection_info)
        
        # 버튼 프레임
        button_frame = tk.Frame(parent)
        button_frame.pack(pady=10)
        
        # 편집 버튼
        edit_btn = tk.Button(button_frame, text="✏️ 편집", 
                            command=self.edit_selected_zone,
                            bg="#2196F3", fg="white", font=("맑은 고딕", 10),
                            relief=tk.FLAT, bd=0, padx=15, pady=5)
        edit_btn.pack(side=tk.LEFT, padx=5)
        
        # 삭제 버튼 (다중선택 지원)
        delete_btn = tk.Button(button_frame, text="🗑️ 삭제 (다중선택)", 
                              command=self.delete_selected_zones,
                              bg="#f44336", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=15, pady=5)
        delete_btn.pack(side=tk.LEFT, padx=5)
    
    def refresh_display(self):
        """구역 목록 새로고침"""
        # 기존 항목 삭제
        for item in self.zones_tree.get_children():
            self.zones_tree.delete(item)
        
        # 색상 매핑 딕셔너리
        color_names = {
            "#2196F3": "파란색",
            "#FF9800": "주황색", 
            "#4CAF50": "초록색",
            "#9C27B0": "보라색",
            "#E91E63": "분홍색",
            "#607D8B": "회색",
            "#795548": "갈색",
            "#FF5722": "빨간색",
            "#00BCD4": "청록색",
            "#FFC107": "노란색"
        }
        
        # 구역 데이터 추가
        for zone_code, zone_data in self.config["zones"].items():
            sections = zone_data["sections"]
            total_sections = sections["rows"] * sections["columns"]
            
            # 색상을 단어로 변환
            color_hex = zone_data["color"]
            color_name = color_names.get(color_hex, color_hex)
            
            self.zones_tree.insert("", "end", values=(
                zone_code,
                zone_data["name"],
                color_name,
                sections["rows"],
                sections["columns"],
                total_sections,
                sections["description"]
            ))
    
    def add_zone_dialog(self):
        """구역 추가 다이얼로그"""
        dialog = tk.Toplevel(self.root)
        dialog.title("구역 추가")
        dialog.geometry("400x500")
        dialog.resizable(False, False)
        
        # 제목
        title_label = tk.Label(dialog, text="새 구역 추가", 
                              font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=10)
        
        # 입력 프레임
        input_frame = tk.Frame(dialog)
        input_frame.pack(pady=20, padx=20, fill=tk.X)
        
        # 구역 코드
        tk.Label(input_frame, text="구역 코드:", font=("맑은 고딕", 10)).pack(anchor=tk.W)
        zone_code_var = tk.StringVar()
        zone_code_entry = tk.Entry(input_frame, textvariable=zone_code_var, width=30)
        zone_code_entry.pack(fill=tk.X, pady=5)
        
        # 구역명
        tk.Label(input_frame, text="구역명:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        zone_name_var = tk.StringVar()
        zone_name_entry = tk.Entry(input_frame, textvariable=zone_name_var, width=30)
        zone_name_entry.pack(fill=tk.X, pady=5)
        
        # 색상 선택
        tk.Label(input_frame, text="색상:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        color_var = tk.StringVar(value="#2196F3")
        
        # 색상 옵션 (단어 + HEX)
        color_options = [
            ("파란색", "#2196F3"),
            ("주황색", "#FF9800"),
            ("초록색", "#4CAF50"),
            ("보라색", "#9C27B0"),
            ("분홍색", "#E91E63"),
            ("회색", "#607D8B"),
            ("갈색", "#795548"),
            ("빨간색", "#FF5722"),
            ("청록색", "#00BCD4"),
            ("노란색", "#FFC107")
        ]
        
        color_combo = ttk.Combobox(input_frame, textvariable=color_var, 
                                  values=[f"{name} ({hex})" for name, hex in color_options],
                                  width=30, state="readonly")
        color_combo.pack(fill=tk.X, pady=5)
        
        # 섹션 설정
        tk.Label(input_frame, text="섹션 설정:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        
        section_frame = tk.Frame(input_frame)
        section_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(section_frame, text="행:").pack(side=tk.LEFT)
        rows_var = tk.StringVar(value="5")
        rows_spin = tk.Spinbox(section_frame, from_=1, to=10, textvariable=rows_var, width=10)
        rows_spin.pack(side=tk.LEFT, padx=5)
        
        tk.Label(section_frame, text="열:").pack(side=tk.LEFT, padx=(10, 0))
        cols_var = tk.StringVar(value="3")
        cols_spin = tk.Spinbox(section_frame, from_=1, to=10, textvariable=cols_var, width=10)
        cols_spin.pack(side=tk.LEFT, padx=5)
        
        # 섹션 설정 안내
        section_info = tk.Label(input_frame, 
                               text="💡 섹션 설정 안내:\n• 행/열: 1~10개까지 설정 가능\n• 총 섹션 수: 행 × 열 (최대 100개)\n• 구역이 많을수록 셀 크기가 작아집니다",
                               font=("맑은 고딕", 8), fg="gray", justify=tk.LEFT)
        section_info.pack(anchor=tk.W, pady=(5, 0))
        
        # 설명
        tk.Label(input_frame, text="설명:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        desc_var = tk.StringVar()
        desc_entry = tk.Entry(input_frame, textvariable=desc_var, width=30)
        desc_entry.pack(fill=tk.X, pady=5)
        
        # 버튼 프레임
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def add_zone():
            zone_code = zone_code_var.get().strip().upper()
            zone_name = zone_name_var.get().strip()
            color_selection = color_var.get()
            
            # 색상에서 HEX 값 추출
            if "(" in color_selection and ")" in color_selection:
                color = color_selection.split("(")[1].split(")")[0]
            else:
                color = color_selection
            
            rows = int(rows_var.get())
            cols = int(cols_var.get())
            description = desc_var.get().strip()
            
            # 입력 검증
            if not zone_code or not zone_name:
                messagebox.showwarning("입력 오류", "구역 코드와 구역명을 입력하세요.")
                return
            
            if zone_code in self.config["zones"]:
                messagebox.showwarning("중복 오류", "이미 존재하는 구역 코드입니다.")
                return
            
            # 구역 추가
            self.config["zones"][zone_code] = {
                "name": zone_name,
                "color": color,
                "sections": {
                    "rows": rows,
                    "columns": cols,
                    "description": description or f"{zone_name} {rows}x{cols} 섹션"
                }
            }
            
            self.refresh_display()
            dialog.destroy()
            messagebox.showinfo("추가 완료", f"구역 '{zone_name}' ({zone_code})이 추가되었습니다.")
        
        # 추가 버튼
        add_btn = tk.Button(button_frame, text="추가", command=add_zone,
                           bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                           relief=tk.FLAT, bd=0, padx=20, pady=5)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        # 취소 버튼
        cancel_btn = tk.Button(button_frame, text="취소", command=dialog.destroy,
                              bg="#f44336", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def edit_selected_zone(self):
        """선택된 구역 편집"""
        selected = self.zones_tree.selection()
        if not selected:
            messagebox.showwarning("선택 오류", "편집할 구역을 선택하세요.")
            return
        
        zone_code = self.zones_tree.item(selected[0])["values"][0]
        self.edit_zone(zone_code)
    
    def edit_zone(self, event_or_zone_code):
        """구역 편집"""
        if isinstance(event_or_zone_code, str):
            zone_code = event_or_zone_code
        else:
            selected = self.zones_tree.selection()
            if not selected:
                return
            zone_code = self.zones_tree.item(selected[0])["values"][0]
        
        if zone_code not in self.config["zones"]:
            return
        
        zone_data = self.config["zones"][zone_code]
        
        # 편집 다이얼로그
        dialog = tk.Toplevel(self.root)
        dialog.title(f"구역 편집 - {zone_code}")
        dialog.geometry("400x500")
        dialog.resizable(False, False)
        
        # 제목
        title_label = tk.Label(dialog, text=f"구역 편집: {zone_code}", 
                              font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=10)
        
        # 입력 프레임
        input_frame = tk.Frame(dialog)
        input_frame.pack(pady=20, padx=20, fill=tk.X)
        
        # 구역명
        tk.Label(input_frame, text="구역명:", font=("맑은 고딕", 10)).pack(anchor=tk.W)
        zone_name_var = tk.StringVar(value=zone_data["name"])
        zone_name_entry = tk.Entry(input_frame, textvariable=zone_name_var, width=30)
        zone_name_entry.pack(fill=tk.X, pady=5)
        
        # 색상 선택
        tk.Label(input_frame, text="색상:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        
        # 색상 옵션 (단어 + HEX)
        color_options = [
            ("파란색", "#2196F3"),
            ("주황색", "#FF9800"),
            ("초록색", "#4CAF50"),
            ("보라색", "#9C27B0"),
            ("분홍색", "#E91E63"),
            ("회색", "#607D8B"),
            ("갈색", "#795548"),
            ("빨간색", "#FF5722"),
            ("청록색", "#00BCD4"),
            ("노란색", "#FFC107")
        ]
        
        # 현재 색상을 단어로 변환
        current_color = zone_data["color"]
        color_names = {hex: name for name, hex in color_options}
        current_color_name = color_names.get(current_color, current_color)
        current_selection = f"{current_color_name} ({current_color})"
        
        color_var = tk.StringVar(value=current_selection)
        color_combo = ttk.Combobox(input_frame, textvariable=color_var, 
                                  values=[f"{name} ({hex})" for name, hex in color_options],
                                  width=30, state="readonly")
        color_combo.pack(fill=tk.X, pady=5)
        
        # 섹션 설정
        tk.Label(input_frame, text="섹션 설정:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        
        section_frame = tk.Frame(input_frame)
        section_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(section_frame, text="행:").pack(side=tk.LEFT)
        rows_var = tk.StringVar(value=str(zone_data["sections"]["rows"]))
        rows_spin = tk.Spinbox(section_frame, from_=1, to=10, textvariable=rows_var, width=10)
        rows_spin.pack(side=tk.LEFT, padx=5)
        
        tk.Label(section_frame, text="열:").pack(side=tk.LEFT, padx=(10, 0))
        cols_var = tk.StringVar(value=str(zone_data["sections"]["columns"]))
        cols_spin = tk.Spinbox(section_frame, from_=1, to=10, textvariable=cols_var, width=10)
        cols_spin.pack(side=tk.LEFT, padx=5)
        
        # 설명
        tk.Label(input_frame, text="설명:", font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=(10, 0))
        desc_var = tk.StringVar(value=zone_data["sections"]["description"])
        desc_entry = tk.Entry(input_frame, textvariable=desc_var, width=30)
        desc_entry.pack(fill=tk.X, pady=5)
        
        # 버튼 프레임
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def update_zone():
            zone_name = zone_name_var.get().strip()
            color_selection = color_var.get()
            
            # 색상에서 HEX 값 추출
            if "(" in color_selection and ")" in color_selection:
                color = color_selection.split("(")[1].split(")")[0]
            else:
                color = color_selection
            
            rows = int(rows_var.get())
            cols = int(cols_var.get())
            description = desc_var.get().strip()
            
            # 입력 검증
            if not zone_name:
                messagebox.showwarning("입력 오류", "구역명을 입력하세요.")
                return
            
            # 구역 업데이트
            self.config["zones"][zone_code] = {
                "name": zone_name,
                "color": color,
                "sections": {
                    "rows": rows,
                    "columns": cols,
                    "description": description or f"{zone_name} {rows}x{cols} 섹션"
                }
            }
            
            self.refresh_display()
            dialog.destroy()
            messagebox.showinfo("수정 완료", f"구역 '{zone_name}' ({zone_code})이 수정되었습니다.")
        
        # 수정 버튼
        update_btn = tk.Button(button_frame, text="수정", command=update_zone,
                              bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        update_btn.pack(side=tk.LEFT, padx=5)
        
        # 취소 버튼
        cancel_btn = tk.Button(button_frame, text="취소", command=dialog.destroy,
                              bg="#f44336", fg="white", font=("맑은 고딕", 10),
                              relief=tk.FLAT, bd=0, padx=20, pady=5)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def delete_selected_zones(self):
        """선택된 구역들 삭제 (다중선택 지원)"""
        selected = self.zones_tree.selection()
        if not selected:
            messagebox.showwarning("선택 오류", "삭제할 구역을 선택하세요.\n\n💡 다중선택 방법:\n• Ctrl+클릭: 개별 항목 선택/해제\n• Shift+클릭: 범위 선택")
            return
        
        # 선택된 구역들의 정보 수집
        selected_zones = []
        for item in selected:
            values = self.zones_tree.item(item)["values"]
            zone_code = values[0]
            zone_name = values[1]
            selected_zones.append({
                'item_id': item,
                'zone_code': zone_code,
                'zone_name': zone_name
            })
        
        # 삭제 확인 메시지 (다중 선택 시)
        if len(selected) == 1:
            zone = selected_zones[0]
            confirm_msg = f"구역 '{zone['zone_name']}' ({zone['zone_code']})을 삭제하시겠습니까?"
        else:
            confirm_msg = f"선택된 {len(selected)}개 구역을 모두 삭제하시겠습니까?\n\n"
            for i, zone in enumerate(selected_zones[:3], 1):  # 처음 3개만 표시
                confirm_msg += f"{i}. {zone['zone_name']} ({zone['zone_code']})\n"
            if len(selected_zones) > 3:
                confirm_msg += f"... 외 {len(selected_zones) - 3}개 구역"
        
        if not messagebox.askyesno("삭제 확인", confirm_msg):
            return
        
        # 구역들 삭제
        deleted_count = 0
        for zone in selected_zones:
            try:
                del self.config["zones"][zone['zone_code']]
                deleted_count += 1
            except KeyError:
                pass  # 이미 삭제된 경우 무시
        
        self.refresh_display()
        
        # 완료 메시지
        if len(selected) == 1:
            messagebox.showinfo("삭제 완료", f"구역 '{selected_zones[0]['zone_name']}' ({selected_zones[0]['zone_code']})이 삭제되었습니다.")
        else:
            messagebox.showinfo("삭제 완료", f"선택된 {deleted_count}개 구역이 삭제되었습니다.")
    
    def delete_selected_zone(self):
        """선택된 구역 삭제 (단일 선택용, 하위 호환성)"""
        self.delete_selected_zones()
    
    def show_selection_info(self, event=None):
        """선택된 항목 정보 표시"""
        selected_items = self.zones_tree.selection()
        if selected_items:
            if len(selected_items) == 1:
                # 단일 선택
                item_values = self.zones_tree.item(selected_items[0])["values"]
                info_text = f"선택된 구역:\n구역코드: {item_values[0]}\n구역명: {item_values[1]}\n색상: {item_values[2]}\n섹션: {item_values[3]}x{item_values[4]} ({item_values[5]}개)"
            else:
                # 다중 선택
                info_text = f"선택된 구역: {len(selected_items)}개\n"
                for i, item in enumerate(selected_items[:3], 1):  # 처음 3개만 표시
                    item_values = self.zones_tree.item(item)["values"]
                    info_text += f"{i}. {item_values[1]} ({item_values[0]}) - {item_values[3]}x{item_values[4]} 섹션\n"
                if len(selected_items) > 3:
                    info_text += f"... 외 {len(selected_items) - 3}개 구역"
            self.selection_info_label.config(text=info_text)
        else:
            self.selection_info_label.config(text="항목을 선택하세요 (Ctrl+클릭으로 다중 선택 가능)")
    
    def preview_zones(self):
        """구역 미리보기"""
        if not self.config["zones"]:
            messagebox.showinfo("미리보기", "구역이 없습니다.")
            return
        
        # 미리보기 창
        preview_window = tk.Toplevel(self.root)
        preview_window.title("구역 미리보기")
        preview_window.geometry("1000x600")
        
        # 제목
        title_label = tk.Label(preview_window, text="구역 미리보기", 
                              font=("맑은 고딕", 14, "bold"))
        title_label.pack(pady=10)
        
        # 스크롤 가능한 프레임
        canvas = tk.Canvas(preview_window)
        scrollbar = tk.Scrollbar(preview_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 구역별 미리보기 생성
        for zone_code, zone_data in self.config["zones"].items():
            zone_frame = tk.Frame(scrollable_frame)
            zone_frame.pack(pady=10, padx=10, fill=tk.X)
            
            # 구역 제목
            zone_title = tk.Label(zone_frame, 
                                 text=f"{zone_data['name']} ({zone_code})", 
                                 font=("맑은 고딕", 12, "bold"),
                                 fg=zone_data["color"])
            zone_title.pack(pady=5)
            
            # 섹션 그리드
            sections_frame = tk.Frame(zone_frame)
            sections_frame.pack()
            
            sections = zone_data["sections"]
            for row in range(sections["rows"]):
                for col in range(sections["columns"]):
                    location = f"{zone_code}-{row+1:02d}-{col+1:02d}"
                    cell = tk.Button(sections_frame, text=location, 
                                   width=8, height=2,
                                   font=("맑은 고딕", 8),
                                   bg=zone_data["color"], fg="white",
                                   relief=tk.RAISED, bd=1)
                    cell.grid(row=row, column=col, padx=2, pady=2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

def main():
    root = tk.Tk()
    root.title("구역 관리 시스템")
    root.geometry("1200x800")
    app = ZoneManager(root)
    root.mainloop()

if __name__ == "__main__":
    main() 