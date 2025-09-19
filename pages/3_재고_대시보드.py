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


def clean_data(df):
    """데이터프레임을 정제하여 앱과 호환되도록 만듭니다."""
    # 1. 컬럼 이름 통일 (기존 데이터의 '바코드숫자'를 '일련번호'로 변경)
    if '바코드숫자' in df.columns:
        df = df.rename(columns={'바코드숫자': '일련번호'})

    # 2. 필수 컬럼이 없는 경우, 빈 값으로 생성
    required_cols = ["일련번호", "구분", "제품코드", "제품명", "LOT", "유통기한", "폐기기한", "보관위치", "버전", "입고일시", "상태", "출고일시", "출고처"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "" # 빈 문자열로 초기화

    # 3. 데이터 타입 변환 (오류 발생 시에도 앱이 멈추지 않도록)
    df['일련번호'] = pd.to_numeric(df['일련번호'], errors='coerce').fillna(0).astype(int)
    df['입고일시'] = pd.to_datetime(df['입고일시'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    df['유통기한'] = pd.to_datetime(df['유통기한'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # 4. 빈 '상태' 값을 '재고'로 채우기
    df['상태'] = df['상태'].astype(str).replace('', '재고').fillna('재고')
    
    return df[required_cols] # 최종적으로 정해진 순서의 컬럼만 반환

# --- 데이터 로드 및 표시 ---
if st.button("🔄 새로고침"):
    st.rerun()

try:
    data = inventory_ws.get_all_records()
    if data:
        df_raw = pd.DataFrame(data)
        df = clean_data(df_raw) # 데이터 정제 함수 호출
        
        st.subheader("현재 재고 목록")

        # 필터링
        status_filter = st.multiselect("상태 필터:", options=df["상태"].unique(), default=["재고"])
        
        filtered_df = df[df["상태"].isin(status_filter)]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("재고 데이터가 없습니다.")

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
