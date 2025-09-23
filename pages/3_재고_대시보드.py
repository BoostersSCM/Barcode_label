import streamlit as st
import pandas as pd
from utils import google_sheets_manager as gsm

st.set_page_config(page_title="재고 대시보드", page_icon="📊", layout="wide")
st.title("📊 재고 대시보드")
st.info("현재 재고 상태와 모든 입출고 기록을 함께 확인할 수 있습니다.")

# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()
if not client: st.stop()
spreadsheet = gsm.get_spreadsheet(client)
if not spreadsheet: st.stop()
inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
history_ws = gsm.get_worksheet(spreadsheet, "입출고_기록")
if not inventory_ws or not history_ws: st.stop()


def clean_inventory_data(df):
    """재고 현황 데이터프레임을 정제합니다."""
    if '바코드숫자' in df.columns:
        df = df.rename(columns={'바코드숫자': '일련번호'})
    required_cols = ["일련번호", "구분", "제품코드", "제품명", "LOT", "유통기한", "폐기기한", "보관위치", "버전", "입고일시", "상태", "출고일시", "출고담당자"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
    df['일련번호'] = pd.to_numeric(df['일련번호'], errors='coerce').fillna(0).astype(int)
    df['상태'] = df['상태'].astype(str).replace('', '재고').fillna('재고')
    return df[required_cols]

def clean_history_data(df):
    """입출고 기록 데이터프레임을 정제합니다."""
    # 👇 '출고담당자'를 필수 컬럼에 추가
    required_cols = ["타임스탬프", "유형", "일련번호", "제품코드", "제품명", "수량", "출고담당자"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
    df['타임스탬프'] = pd.to_datetime(df['타임스탬프'], errors='coerce')
    df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(1).astype(int)
    return df[required_cols]

# --- 데이터 로드 ---
try:
    inventory_data = inventory_ws.get_all_records()
    history_data = history_ws.get_all_records()

    if not inventory_data:
        st.info("재고 데이터가 없습니다. 먼저 입고 처리를 진행해주세요.")
        st.stop()
    
    df_inventory = clean_inventory_data(pd.DataFrame(inventory_data))
    df_history = clean_history_data(pd.DataFrame(history_data))

    # --- 1. 현재 재고 현황 표시 ---
    st.subheader("📦 현재 재고 현황")
    status_filter = st.multiselect(
        "상태 필터:", 
        options=df_inventory["상태"].unique(), 
        default=["재고"]
    )
    filtered_inventory_df = df_inventory[df_inventory["상태"].isin(status_filter)]
    st.dataframe(filtered_inventory_df, use_container_width=True, hide_index=True)

    st.divider()

    # --- 2. 입출고 전체 기록 표시 ---
    st.subheader("📜 입출고 전체 기록")
    st.dataframe(df_history.sort_values(by="타임스탬프", ascending=False), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"대시보드를 불러오는 중 오류가 발생했습니다: {e}")
