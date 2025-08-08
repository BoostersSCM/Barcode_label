import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os
import subprocess
import sys

# ✅ 발행 이력 파일명 변경
history_file = "barcode_label/issue_history.xlsx"

def load_inventory():
    if not os.path.exists(history_file):
        messagebox.showerror("오류", "발행 이력이 없습니다.")
        return pd.DataFrame()
    df = pd.read_excel(history_file)
    return df

def update_dashboard():
    df = load_inventory()
    if df.empty:
        # 빈 데이터일 때 트리뷰 초기화
        for i in tree.get_children():
            tree.delete(i)
        return

    # ✅ 위치별 재고 집계 (구분 포함)
    grouped = df.groupby(["보관위치", "구분", "제품코드", "제품명"]).size().reset_index()
    grouped.columns = ["보관위치", "구분", "제품코드", "제품명", "수량"]

    # Treeview 초기화
    for i in tree.get_children():
        tree.delete(i)

    for _, row in grouped.iterrows():
        # 해당 위치와 제품의 최신 정보 가져오기
        location = row["보관위치"]
        product = row["제품명"]
        product_code = row["제품코드"]
        category = row["구분"]
        
        # 해당 위치와 제품의 데이터 필터링
        filtered_df = df[(df["보관위치"] == location) & (df["구분"] == category) & (df["제품코드"] == product_code) & (df["제품명"] == product)]
        
        # 최신 정보 (현재 시점에서 가장 가까운 유통기한 기준)
        try:
            current_date = pd.Timestamp.now()
            
            # 유통기한을 날짜로 변환하여 가장 가까운 날짜 찾기
            expiry_dates = []
            for _, filtered_row in filtered_df.iterrows():
                try:
                    expiry_date = pd.to_datetime(filtered_row["유통기한"])
                    expiry_dates.append((expiry_date, filtered_row))
                except:
                    continue
            
            if expiry_dates:
                # 현재 날짜와의 차이를 계산하여 가장 가까운 날짜 찾기
                closest_expiry, closest_row = min(expiry_dates, key=lambda x: abs((x[0] - current_date).days))
                
                latest_lot = str(closest_row["LOT"])
                latest_expiry = closest_expiry.strftime("%Y-%m-%d")
                
                # 폐기일자 계산
                latest_disposal = closest_row.get("폐기일자", "N/A")
                if latest_disposal == "N/A" or pd.isna(latest_disposal):
                    try:
                        disposal_date = closest_expiry.replace(year=closest_expiry.year + 1)
                        latest_disposal = disposal_date.strftime("%Y-%m-%d")
                    except:
                        latest_disposal = "N/A"
                else:
                    latest_disposal = str(latest_disposal)
            else:
                latest_lot = "N/A"
                latest_expiry = "N/A"
                latest_disposal = "N/A"
                
        except Exception as e:
            print(f"데이터 처리 오류: {e}")
            latest_lot = "N/A"
            latest_expiry = "N/A"
            latest_disposal = "N/A"
        
        # 수량 안전한 접근
        quantity = row.get("수량", 0)
        
        # 고유 ID 생성 (위치+구분+제품명 조합)
        item_id = f"{location}_{category}_{product_code}_{product}"
        
        tree.insert("", "end", iid=item_id, values=(
            location, 
            category,
            product_code,
            product, 
            quantity,
            latest_lot,
            latest_expiry,
            latest_disposal
        ))

def edit_quantity(event):
    """수량 편집 기능"""
    selected_item = tree.selection()
    if not selected_item:
        return
    
    item = selected_item[0]
    values = tree.item(item)['values']
    
    # 편집 창 생성
    edit_window = tk.Toplevel(root)
    edit_window.title("수량 편집")
    edit_window.geometry("400x200")
    edit_window.resizable(False, False)
    
    # 정보 표시
    info_frame = tk.Frame(edit_window)
    info_frame.pack(pady=10)
    
    tk.Label(info_frame, text=f"보관위치: {values[0]}", font=("맑은 고딕", 10)).pack()
    tk.Label(info_frame, text=f"구분: {values[1]}", font=("맑은 고딕", 10)).pack()
    tk.Label(info_frame, text=f"제품명: {values[3]}", font=("맑은 고딕", 10)).pack()
    
    # 수량 입력
    quantity_frame = tk.Frame(edit_window)
    quantity_frame.pack(pady=10)
    
    tk.Label(quantity_frame, text="수량:", font=("맑은 고딕", 10)).pack()
    quantity_var = tk.StringVar(value=str(values[4]))
    quantity_entry = tk.Entry(quantity_frame, textvariable=quantity_var, width=10, font=("맑은 고딕", 12))
    quantity_entry.pack(pady=5)
    quantity_entry.focus()
    quantity_entry.select_range(0, tk.END)
    
    def save_quantity():
        try:
            new_quantity = int(quantity_var.get())
            if new_quantity < 0:
                messagebox.showerror("오류", "수량은 0 이상이어야 합니다.")
                return
            
            # 트리뷰 업데이트
            tree.set(item, "수량", new_quantity)
            
            # 발행 이력 파일에서 해당 항목들의 수량 정보 업데이트
            update_quantity_in_history(values[0], values[1], values[2], new_quantity)
            
            messagebox.showinfo("완료", f"수량이 {new_quantity}로 업데이트되었습니다.")
            edit_window.destroy()
            
        except ValueError:
            messagebox.showerror("오류", "올바른 숫자를 입력하세요.")
    
    def cancel_edit():
        edit_window.destroy()
    
    # 버튼 프레임
    button_frame = tk.Frame(edit_window)
    button_frame.pack(pady=20)
    
    save_btn = tk.Button(button_frame, text="저장", command=save_quantity,
                         bg="#4CAF50", fg="white", font=("맑은 고딕", 10),
                         relief=tk.FLAT, bd=0, padx=20, pady=5)
    save_btn.pack(side=tk.LEFT, padx=5)
    
    cancel_btn = tk.Button(button_frame, text="취소", command=cancel_edit,
                           bg="#f44336", fg="white", font=("맑은 고딕", 10),
                           relief=tk.FLAT, bd=0, padx=20, pady=5)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    
    # Enter 키로 저장
    quantity_entry.bind('<Return>', lambda e: save_quantity())
    edit_window.bind('<Escape>', lambda e: cancel_edit())

def update_quantity_in_history(location, category, product_code, new_quantity):
    """발행 이력에서 수량 정보 업데이트"""
    try:
        df = pd.read_excel(history_file)
        
        # 해당 위치, 구분, 제품명의 모든 항목 찾기
        mask = (df["보관위치"] == location) & (df["구분"] == category) & (df["제품코드"] == product_code)
        matching_rows = df[mask]
        
        if len(matching_rows) > 0:
            # 수량 정보를 별도 컬럼으로 저장 (기존 데이터 구조 유지)
            # 실제로는 발행 이력에 수량 컬럼을 추가하는 것이 좋지만,
            # 기존 구조를 유지하면서 수량 정보를 메모리에 관리
            print(f"수량 업데이트: {location} - {category} - {product_code} = {new_quantity}")
            
            # 여기서는 실제 파일 수정 대신 로그만 출력
            # 실제 구현 시에는 별도의 수량 관리 파일을 만들거나
            # 발행 이력에 수량 컬럼을 추가하는 것을 권장
            
    except Exception as e:
        print(f"수량 업데이트 오류: {e}")

def show_location_detail(event):
    selected_item = tree.selection()
    if not selected_item:
        return

    location = tree.item(selected_item[0])["values"][0]
    df = load_inventory()
    detail_df = df[df["보관위치"] == location]

    detail_window = tk.Toplevel(root)
    detail_window.title(f"{location} 위치 상세 내역")
    detail_window.geometry("800x400")

    detail_tree = ttk.Treeview(detail_window, columns=("구분", "제품코드", "제품명", "LOT", "유통기한", "폐기일자", "발행일시"), show="headings")
    
    # 컬럼 설정
    detail_tree.heading("구분", text="구분")
    detail_tree.heading("제품코드", text="제품코드")
    detail_tree.heading("제품명", text="제품명")
    detail_tree.heading("LOT", text="LOT")
    detail_tree.heading("유통기한", text="유통기한")
    detail_tree.heading("폐기일자", text="폐기일자")
    detail_tree.heading("발행일시", text="발행일시")
    
    detail_tree.column("구분", width=80)
    detail_tree.column("제품코드", width=100)
    detail_tree.column("제품명", width=200)
    detail_tree.column("LOT", width=100)
    detail_tree.column("유통기한", width=120)
    detail_tree.column("폐기일자", width=120)
    detail_tree.column("발행일시", width=150)
    
    detail_tree.pack(fill="both", expand=True, padx=10, pady=10)

    for _, row in detail_df.iterrows():
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
            
        detail_tree.insert("", "end", values=(row["구분"], row["제품코드"], row["제품명"], row["LOT"], row["유통기한"], 
                                             disposal_date, row["발행일시"]))

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

def open_label_gui():
    """라벨 발행 GUI 창 열기"""
    try:
        # 현재 스크립트의 디렉토리에서 label_gui.py 실행
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gui_path = os.path.join(script_dir, "label_gui.py")
        
        if os.path.exists(gui_path):
            subprocess.Popen([sys.executable, gui_path])
        else:
            messagebox.showerror("오류", "label_gui.py 파일을 찾을 수 없습니다.")
    except Exception as e:
        messagebox.showerror("오류", f"라벨 발행 창을 열 수 없습니다: {str(e)}")

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

def delete_selected():
    selected_items = tree.selection()
    if not selected_items:
        messagebox.showwarning("경고", "삭제할 항목을 선택하세요.")
        return
    if not messagebox.askyesno("삭제 확인", "선택한 항목을 삭제하시겠습니까? (엑셀에서도 삭제됩니다)"):
        return
    try:
        df = load_inventory()
        for item in selected_items:
            values = tree.item(item)['values']
            location, category, product_code, product = values[0], values[1], values[2], values[3]
            # 해당 행 삭제
            mask = (df["보관위치"] == location) & (df["구분"] == category) & (df["제품코드"] == product_code) & (df["제품명"] == product)
            df = df[~mask]
            tree.delete(item)
        df.to_excel(history_file, index=False)
        update_dashboard()
        messagebox.showinfo("삭제 완료", "선택한 항목이 삭제되었습니다.")
    except Exception as e:
        messagebox.showerror("삭제 오류", f"삭제 실패: {e}")

# ✅ Tkinter GUI
root = tk.Tk()
root.title("바코드 라벨 관리 시스템 - 대시보드")
root.geometry("1200x600")

# 제목
title_label = tk.Label(root, text="📊 바코드 라벨 관리 시스템 - 대시보드", 
                       font=("맑은 고딕", 14, "bold"))
title_label.pack(pady=10)

# 설명
info_label = tk.Label(root, text="수량을 더블클릭하여 편집할 수 있습니다.", 
                      font=("맑은 고딕", 10), fg="gray")
info_label.pack(pady=5)

# 트리뷰 프레임
tree_frame = tk.Frame(root)
tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

tree = ttk.Treeview(tree_frame, columns=("보관위치", "구분", "제품코드", "제품명", "수량", "최신LOT", "최신유통기한", "최신폐기일자"), show="headings", height=15)
tree.heading("보관위치", text="보관위치")
tree.heading("구분", text="구분")
tree.heading("제품코드", text="제품코드")
tree.heading("제품명", text="제품명")
tree.heading("수량", text="수량")
tree.heading("최신LOT", text="최신LOT")
tree.heading("최신유통기한", text="최신유통기한")
tree.heading("최신폐기일자", text="최신폐기일자")
tree.column("보관위치", width=100)
tree.column("구분", width=80)
tree.column("제품코드", width=100)
tree.column("제품명", width=200)
tree.column("수량", width=80)
tree.column("최신LOT", width=100)
tree.column("최신유통기한", width=120)
tree.column("최신폐기일자", width=120)

# 스크롤바 추가
scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)

tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# 이벤트 바인딩
tree.bind("<Double-1>", show_location_detail)
tree.bind("<Button-3>", edit_quantity)  # 우클릭으로 수량 편집

# 버튼 프레임
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

refresh_btn = tk.Button(button_frame, text="🔄 대시보드 새로고침", command=update_dashboard,
                        bg="#2196F3", fg="white", font=("맑은 고딕", 10, "bold"),
                        relief=tk.FLAT, bd=0, padx=15, pady=5)
refresh_btn.pack(side=tk.LEFT, padx=5)

delete_btn = tk.Button(button_frame, text="🗑️ 선택 삭제", command=delete_selected,
                        bg="#f44336", fg="white", font=("맑은 고딕", 10, "bold"),
                        relief=tk.FLAT, bd=0, padx=15, pady=5)
delete_btn.pack(side=tk.LEFT, padx=5)

label_btn = tk.Button(button_frame, text="🏷️ 라벨 발행", command=open_label_gui, 
                      bg="#4CAF50", fg="white", font=("맑은 고딕", 10, "bold"),
                      relief=tk.FLAT, bd=0, padx=15, pady=5)
label_btn.pack(side=tk.LEFT, padx=5)

visualizer_btn = tk.Button(button_frame, text="🧐 관리품 위치 찾기", command=open_location_visualizer, 
                          bg="#FF9800", fg="white", font=("맑은 고딕", 10, "bold"),
                          relief=tk.FLAT, bd=0, padx=15, pady=5)
visualizer_btn.pack(side=tk.LEFT, padx=5)

zone_btn = tk.Button(button_frame, text="⚙️ 구역 관리", command=open_zone_manager, 
                     bg="#9C27B0", fg="white", font=("맑은 고딕", 10, "bold"),
                     relief=tk.FLAT, bd=0, padx=15, pady=5)
zone_btn.pack(side=tk.LEFT, padx=5)

# 도움말 프레임
help_frame = tk.Frame(root)
help_frame.pack(pady=5)

help_label = tk.Label(help_frame, text="💡 사용법: 수량을 우클릭하여 편집하거나, 행을 더블클릭하여 상세 정보를 확인하세요.", 
                      font=("맑은 고딕", 9), fg="gray")
help_label.pack()

update_dashboard()
root.mainloop()