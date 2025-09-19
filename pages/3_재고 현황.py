import streamlit as st
import pandas as pd
import google_sheets_manager as gsm

st.set_page_config(page_title="재고 현황", page_icon="📊", layout="wide")
st.title("📊 재고 현황")

# --- 구글 시트 연결 ---
client = gsm.connect_to_google_sheets()

if client:
    spreadsheet = gsm.get_spreadsheet(client)
    if spreadsheet:
        inventory_ws = gsm.get_worksheet(spreadsheet, "재고_현황")
    else:
        st.stop()
else:
    st.stop()

# --- 데이터 로드 및 표시 ---
if st.button("🔄 새로고침"):
    st.rerun()

try:
    data = inventory_ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
        
        st.subheader("현재 재고 목록")

        # 필터링 옵션
        status_filter = st.multiselect(
            "상태 필터:",
            options=df["상태"].unique(),
            default=df["상태"].unique()
        )
        
        filtered_df = df[df["상태"].isin(status_filter)]
        
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("재고 데이터가 없습니다.")

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
