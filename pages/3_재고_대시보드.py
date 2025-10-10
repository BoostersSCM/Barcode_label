# pages/3_재고_대시보드.py

import streamlit as st
import pandas as pd
from utils import db_manager

st.set_page_config(page_title="재고 대시보드", page_icon="📊", layout="wide")
st.title("📊 재고 대시보드")

# SCM DB 연결
engine = db_manager.connect_to_scm()

if engine is None:
    st.error("SCM DB에 연결할 수 없습니다.")
    st.stop()

# 데이터 로드
try:
    df_inventory = pd.read_sql("SELECT * FROM Retained_sample_status ORDER BY inbound_datetime DESC", engine)
    df_history = pd.read_sql("SELECT * FROM Retained_sample_in_out ORDER BY timestamp DESC", engine)

    st.subheader("📦 재고 현황")
    st.dataframe(df_inventory, use_container_width=True)

    st.divider()
    st.subheader("📜 입출고 기록")
    st.dataframe(df_history, use_container_width=True)

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
