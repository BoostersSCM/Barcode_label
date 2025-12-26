import streamlit as st
from utils import location_manager as lm
from utils import auth_manager  # 👈 임포트 추가

st.set_page_config(page_title="보관위치 관리", page_icon="⚙️")
# 👇 인증 체크 추가 (이 두 줄을 반드시 추가하세요)
auth_manager.require_auth()
st.title("⚙️ 보관위치 관리")

st.info("이곳에서 재고를 보관할 구역(Zone)과 크기를 설정할 수 있습니다.")

# 현재 설정 로드
config = lm.load_config()
zones = config.get("zones", {})

# --- 현재 구역 목록 표시 ---
st.subheader("현재 구역 목록")

if not zones:
    st.warning("설정된 구역이 없습니다. 아래에서 새 구역을 추가해주세요.")
else:
    for code, details in zones.items():
        with st.expander(f"**{details['name']} (코드: {code})**"):
            st.write(f"- **크기**: {details['rows']}행 x {details['columns']}열")
            if st.button(f"{details['name']} 삭제", key=f"delete_{code}", type="primary"):
                del zones[code]
                if lm.save_config(config):
                    st.success(f"'{details['name']}' 구역이 삭제되었습니다.")
                    st.rerun()
                else:
                    # 삭제 실패 시 복원
                    zones[code] = details


# --- 새 구역 추가 ---
st.divider()
st.subheader("새 구역 추가")

with st.form("add_zone_form"):
    new_name = st.text_input("구역 이름", placeholder="예: C 구역")
    new_code = st.text_input("구역 코드 (알파벳 한 글자)", max_chars=1, placeholder="예: C").upper()
    new_rows = st.number_input("행(세로) 수", min_value=1, max_value=20, value=5, step=1)
    new_cols = st.number_input("열(가로) 수", min_value=1, max_value=10, value=3, step=1)
    
    submitted = st.form_submit_button("새 구역 추가하기")

if submitted:
    if not new_name or not new_code:
        st.error("구역 이름과 코드를 모두 입력해야 합니다.")
    elif not new_code.isalpha():
        st.error("구역 코드는 반드시 알파벳이어야 합니다.")
    elif new_code in zones:
        st.error(f"이미 사용 중인 구역 코드입니다: {new_code}")
    else:
        zones[new_code] = {"name": new_name, "rows": new_rows, "columns": new_cols}
        if lm.save_config(config):
            st.success(f"새 구역 '{new_name}'이(가) 추가되었습니다!")
            st.rerun()
