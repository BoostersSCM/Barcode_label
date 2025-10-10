import streamlit as st
from datetime import datetime
import pytz
import time
from sqlalchemy import text

from utils import db_manager

st.set_page_config(page_title="출고 처리", page_icon="📤")
st.title("📤 출고 처리 (바코드 스캔 지원)")

# 세션 초기화
if "outbound_list" not in st.session_state:
    st.session_state.outbound_list = []  # [{type, code, product_code, product_name, quantity}]

# 스캔 콜백
def add_item_to_outbound_list():
    scanned = st.session_state.get("barcode_scan_input", "").strip()
    if not scanned:
        return

    if any(item["code"] == scanned for item in st.session_state.outbound_list):
        st.warning(f"이미 목록에 추가된 코드입니다: {scanned}")
        st.session_state.barcode_scan_input = ""
        return

    item_to_add = None
    # 제품 바코드(예: 88로 시작) → ERP 조회
    if scanned.startswith("88"):
        info = db_manager.find_product_info_by_barcode(scanned)
        if info:
            item_to_add = {
                "type": "제품",
                "code": scanned,
                "product_code": info.get("resource_code", "N/A"),
                "product_name": info.get("resource_name", "알 수 없는 제품"),
                "quantity": 1
            }
        else:
            st.error(f"ERP DB에 등록되지 않은 제품 바코드입니다: {scanned}")
    # 숫자만 → 일련번호(S/N)
    elif scanned.isdigit():
        item_to_add = {
            "type": "S/N",
            "code": scanned,
            "product_code": "N/A",
            "product_name": f"일련번호-{scanned}",
            "quantity": 1
        }
    else:
        st.error(f"유효하지 않은 코드 형식입니다: {scanned}")

    if item_to_add:
        st.session_state.outbound_list.insert(0, item_to_add)

    st.session_state.barcode_scan_input = ""

# 입력 UI
st.info("바코드를 스캔하면 아래 '출고 목록'에 자동으로 추가됩니다.")
st.text_input(
    "스캔 입력",
    key="barcode_scan_input",
    on_change=add_item_to_outbound_list,
    placeholder="여기에 바코드를 연속으로 스캔하세요 (Enter)"
)
st.divider()

# 목록 UI
st.subheader("🛒 출고 목록")
if not st.session_state.outbound_list:
    st.caption("스캔된 품목이 없습니다.")
else:
    for i, item in enumerate(st.session_state.outbound_list):
        col1, col2, col3 = st.columns([6, 2, 1])
        with col1:
            st.write(f"**{item['product_name']}**")
            st.caption(f"유형: {item['type']} | 코드: {item['code']} | 제품코드: {item['product_code']}")
        with col2:
            disabled = (item["type"] == "S/N")
            qty = st.number_input(
                "수량", min_value=1, value=item["quantity"], step=1,
                key=f"qty_{item['code']}", disabled=disabled
            )
            st.session_state.outbound_list[i]["quantity"] = 1 if disabled else qty
        with col3:
            st.write("")
            if st.button("삭제", key=f"del_{item['code']}", type="secondary"):
                st.session_state.outbound_list.pop(i)
                st.rerun()

# 최종 처리
st.divider()
with st.form("process_form"):
    st.subheader("최종 출고 처리")
    handler = st.text_input("출고담당자(handler)", placeholder="예: 홍길동")
    submitted = st.form_submit_button("✅ 일괄 출고 처리 실행", type="primary")

if submitted:
    if not st.session_state.outbound_list:
        st.warning("출고할 품목이 없습니다.")
        st.stop()
    if not handler:
        st.warning("출고담당자를 입력해주세요.")
        st.stop()

    kst = pytz.timezone('Asia/Seoul')
    now_kst_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')

    # 상태 테이블에 '출고됨' 표시를 하려면, 스키마에 해당 컬럼이 있어야 합니다.
    # 현재 영문 스키마에는 outbound/status 컬럼이 없으므로 '이력 기록만' 수행합니다.

    success, fail = 0, 0
    total = len(st.session_state.outbound_list)
    progress = st.progress(0, text="출고 처리 시작...")

    for idx, item in enumerate(st.session_state.outbound_list):
        try:
            # 이력 기록
            ok = db_manager.insert_inout_record({
                "timestamp": now_kst_str,
                "type": "출고",
                "serial_number": item["code"] if item["type"] == "S/N" else "N/A",
                "product_code": item["product_code"],
                "product_name": item["product_name"],
                "quantity": int(item["quantity"]),
                "handler": handler
            })
            success += 1 if ok else 0
            fail += 0 if ok else 1
        except Exception as e:
            st.error(f"처리 실패: {item['code']} / {e}")
            fail += 1

        progress.progress((idx + 1) / total, text=f"({idx+1}/{total}) {item['product_name']} 처리 중...")
        time.sleep(0.03)

    progress.empty()
    st.success(f"🚀 일괄 출고 처리 완료! 성공: {success}건, 실패: {fail}건")

    st.session_state.outbound_list = []
    time.sleep(0.3)
    st.rerun()
