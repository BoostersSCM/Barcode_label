import streamlit as st
import pandas as pd
from utils import google_sheets_manager as gsm

st.set_page_config(page_title="재고 대시보드", page_icon="📊", layout="wide")
st.title("📊 재고 대시보드")

# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()
if not client: st.stop()
spreadsheet = gsm.get_spreadsheet(client)
if not spreadsheet: st.stop()
inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
if not inventory_ws: st.stop()

# --- 데이터 로드 및 표시 ---
if st.button("🔄 새로고침"):
    st.rerun()

try:
    data = inventory_ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.subheader("현재 재고 목록")

        # 필터링
        status_filter = st.multiselect("상태 필터:", options=df["상태"].unique(), default=["재고"])
        
        filtered_df = df[df["상태"].isin(status_filter)]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("재고 데이터가 없습니다.")

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
