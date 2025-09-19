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
    if '바코드숫자' in df.columns:
        df = df.rename(columns={'바코드숫자': '일련번호'})

    required_cols = ["일련번호", "구분", "제품코드", "제품명", "LOT", "유통기한", "폐기기한", "보관위치", "버전", "입고일시", "상태", "출고일시", "출고처"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df['일련번호'] = pd.to_numeric(df['일련번호'], errors='coerce').fillna(0).astype(int)
    df['입고일시'] = pd.to_datetime(df['입고일시'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    df['유통기한'] = pd.to_datetime(df['유통기한'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['상태'] = df['상태'].astype(str).replace('', '재고').fillna('재고')
    
    return df[required_cols]

# --- 데이터 로드 및 표시 ---
st.info("💡 행을 선택하고 Delete 키를 누르거나, 표 왼쪽의 체크박스를 선택하여 행을 삭제할 수 있습니다.")

if 'original_df' not in st.session_state:
    st.session_state.original_df = pd.DataFrame()

def load_data():
    """데이터를 로드하고 세션 상태에 저장합니다."""
    data = inventory_ws.get_all_records()
    if data:
        df_raw = pd.DataFrame(data)
        st.session_state.original_df = clean_data(df_raw)
    else:
        st.session_state.original_df = pd.DataFrame()

# 페이지 로드 시 또는 새로고침 시 데이터 로드
if st.button("🔄 데이터 새로고침"):
    load_data()
if st.session_state.original_df.empty:
    load_data()


df_display = st.session_state.original_df.copy()

# 필터링
status_filter = st.multiselect("상태 필터:", options=df_display["상태"].unique(), default=["재고"])
filtered_df = df_display[df_display["상태"].isin(status_filter)]

# 데이터 에디터 UI
st.subheader("현재 재고 목록 (편집 가능)")
edited_df = st.data_editor(
    filtered_df,
    key="data_editor",
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic" # 행 추가/삭제 활성화
)

# 변경사항 저장 버튼
if st.button("🗑️ 삭제된 행 구글 시트에 반영하기"):
    original_serials = set(st.session_state.original_df['일련번호'])
    edited_serials = set(edited_df['일련번호'])
    
    # 삭제된 일련번호 찾기
    serials_to_delete = list(original_serials - edited_serials)
    
    if not serials_to_delete:
        st.warning("삭제된 행이 없습니다.")
    else:
        with st.spinner(f"{len(serials_to_delete)}개 행을 삭제하는 중..."):
            success, count = gsm.delete_rows_by_serial(inventory_ws, serials_to_delete)
            if success:
                st.success(f"✅ {count}개의 행이 구글 시트에서 성공적으로 삭제되었습니다.")
                # 성공 후 데이터 다시 로드
                load_data()
                st.rerun()
            else:
                st.error("행 삭제 중 오류가 발생했습니다.")
