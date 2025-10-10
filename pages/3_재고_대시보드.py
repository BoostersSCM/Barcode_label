import streamlit as st
import pandas as pd
from utils import db_manager

st.set_page_config(page_title="재고 대시보드", page_icon="📊", layout="wide")
st.title("📊 재고 대시보드")

engine = db_manager.connect_to_scm()
if engine is None:
    st.error("SCM DB 연결 실패")
    st.stop()

# 상태/이력 조회
try:
    df_inventory = pd.read_sql("SELECT * FROM `Retained_sample_status`", engine)
except Exception as e:
    st.error(f"재고 현황 로드 실패: {e}")
    df_inventory = pd.DataFrame()

try:
    df_history = pd.read_sql("SELECT * FROM `Retained_sample_in_out`", engine)
except Exception as e:
    st.error(f"입출고 기록 로드 실패: {e}")
    df_history = pd.DataFrame()

# 재고 현황
st.subheader("📦 재고 현황")
# 컬럼이 존재하면 보기 좋게 정렬/선택
inv_cols = [
    "serial_number", "category", "product_code", "product_name", "lot",
    "expiration_date", "disposal_date", "storage_location", "version", "received_at"
]
show_inv = [c for c in inv_cols if c in df_inventory.columns]
st.dataframe(df_inventory[show_inv] if show_inv else df_inventory, use_container_width=True)

st.divider()

# 입출고 기록
st.subheader("📜 입출고 기록")
if "timestamp" in df_history.columns:
    df_history = df_history.sort_values(by="timestamp", ascending=False)
st.dataframe(df_history, use_container_width=True)
