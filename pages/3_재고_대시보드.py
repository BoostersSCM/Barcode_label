import streamlit as st
import pandas as pd
from utils import db_manager

st.set_page_config(page_title="재고 대시보드", page_icon="📊", layout="wide")
st.title("📊 재고 대시보드")

engine = db_manager.connect_to_mysql()
if engine is None:
    st.error("DB 연결 실패")
    st.stop()

df_inventory = pd.read_sql("SELECT * FROM Retained_sample_status", engine)
df_history = pd.read_sql("SELECT * FROM Retained_sample_in_out", engine)

st.subheader("📦 재고 현황")
st.dataframe(df_inventory, use_container_width=True)

st.divider()
st.subheader("📜 입출고 기록")
st.dataframe(df_history.sort_values(by="timestamp", ascending=False), use_container_width=True)
