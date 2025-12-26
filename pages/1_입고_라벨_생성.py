import streamlit as st
import io
from datetime import datetime, timedelta, date
import pandas as pd
import pytz

from utils import db_manager
from utils import barcode_generator  # 기존 파일 그대로 사용
from utils import auth_manager  # 👈 임포트 추가



st.set_page_config(page_title="입고 처리", page_icon="📥")
# 👇 인증 체크 추가 (이 두 줄을 반드시 추가하세요)
auth_manager.require_auth()
st.title("📥 입고 (라벨 생성)")

# 1) 제품 데이터 로드 (ERP)
try:
    product_df = db_manager.load_product_data()
except Exception as e:
    st.error(f"제품정보 로드 실패: {e}")
    st.stop()

if product_df is None or product_df.empty:
    st.error("ERP DB에서 제품 정보를 불러오지 못했습니다.")
    st.stop()

# 제품명/코드 매핑
PRODUCTS = pd.Series(product_df.제품명.values, index=product_df.제품코드).to_dict()
PRODUCT_CODES = list(PRODUCTS.keys())

# (옵션) ERP 데이터에 '바코드' 컬럼이 있으면 간단 매핑도 사용 가능
barcode_map = None
if "바코드" in product_df.columns and "제품코드" in product_df.columns:
    barcode_map = product_df.set_index("바코드")["제품코드"].to_dict()

# 2) 바코드 스캔: 콜백/세션 상태 -----------------------------------------
def find_product_by_barcode():
    """스캔된 바코드로 제품코드를 찾아 selectbox 기본 선택값으로 반영"""
    scanned = st.session_state.get("barcode_scan_input", "").strip()
    if not scanned:
        return

    # A안) ERP DB 직접 조회 (권장)
    info = db_manager.find_product_info_by_barcode(scanned)
    if info and ("resource_code" in info or "제품코드" in info):
        st.session_state.selected_product_code = info.get("resource_code") or info.get("제품코드")
    # B안) 로컬 프레임 매핑 (대체용)
    elif barcode_map and scanned in barcode_map:
        st.session_state.selected_product_code = barcode_map[scanned]
    else:
        st.warning(f"'{scanned}' 에 해당하는 제품을 찾지 못했습니다.")

    # 다음 스캔 대비 입력칸 비우기
    st.session_state.barcode_scan_input = ""

# 초기 선택값
if "selected_product_code" not in st.session_state:
    st.session_state.selected_product_code = PRODUCT_CODES[0] if PRODUCT_CODES else None

# 3) 입력 UI -------------------------------------------------------------
st.subheader("제품 정보 입력")

# ⌨️ 바코드 스캔 입력창 (연속 스캔 지원: Enter 시 on_change 콜백)
st.text_input(
    "⌨️ 바코드 스캔으로 제품 찾기",
    key="barcode_scan_input",
    on_change=find_product_by_barcode,
    placeholder="여기에 '88...' 바코드를 스캔하고 Enter"
)

with st.form("inbound_form"):
    # 바코드 스캔 결과를 selectbox 기본 선택으로 반영
    try:
        selected_index = PRODUCT_CODES.index(st.session_state.selected_product_code)
    except (ValueError, AttributeError):
        selected_index = 0

    product_code = st.selectbox(
        "📦 제품",
        options=PRODUCT_CODES,
        index=selected_index,
        format_func=lambda x: f"{x} ({PRODUCTS.get(x, '알 수 없는 제품')})"
    )

    # 보관위치: 자유 입력 (필요시 프리셋 selectbox로 교체 가능)
    storage_location = st.text_input("보관위치 (예: A-01-01)")

    category = st.selectbox("구분", ["관리품", "표준품", "벌크표준", "샘플재고"])

    # 샘플재고: 고정값/비활성화
    expiration_date_obj = None  # 아래 로직에서 안전하게 사용하기 위해 기본값 지정
    if category == "샘플재고":
        lot_number, expiration_date, version = "SAMPLE", "N/A", "N/A"
        st.text_input("LOT", value=lot_number, disabled=True)
        st.text_input("유통기한(expiration_date)", value=expiration_date, disabled=True)
        st.text_input("버전(version)", value=version, disabled=True)
    else:
        lot_number = st.text_input("LOT 번호")
        expiration_date_obj = st.date_input(
            "유통기한(expiration_date)",
            value=datetime.now().date() + timedelta(days=365*3)
        )
        version = st.text_input("버전(version)", value="R0")

    submitted = st.form_submit_button("라벨 생성 및 입고 처리")

# 4) 처리 로직 -----------------------------------------------------------
if submitted:
    if not all([product_code, storage_location]):
        st.warning("제품코드와 보관위치는 필수입니다.")
        st.stop()

    serial_number = int(datetime.now().timestamp())  # 예시 S/N (환경에 맞게 교체 가능)
    product_name = PRODUCTS.get(product_code, "알 수 없는 제품")

    # expiration_date, disposal_date 계산
    if category == "샘플재고":
        expiration_date_str = "N/A"
        disposal_date_str = "N/A"
    else:
        if isinstance(expiration_date_obj, date):
            expiration_date_str = expiration_date_obj.strftime("%Y-%m-%d")
            disposal_date_str = (expiration_date_obj + timedelta(days=365)).strftime("%Y-%m-%d")
        else:
            expiration_date_str = "N/A"
            disposal_date_str = "N/A"

    # received_at (KST)
    kst = pytz.timezone('Asia/Seoul')
    received_at_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')

    # 라벨 이미지 생성/표시 (+ 다운로드)
    label_img = barcode_generator.create_barcode_image(
        serial_number, product_code, product_name, lot_number,
        expiration_date_str, version, storage_location, category
    )
    st.image(label_img, caption=f"라벨 (S/N: {serial_number})")

    buf = io.BytesIO()
    label_img.save(buf, format="PNG")
    st.download_button(
        "🖨️ 라벨 이미지 다운로드 (인쇄용)",
        buf.getvalue(),
        file_name=f"label_{serial_number}.png",
        mime="image/png"
    )

    # DB INSERT (영문 스키마 파라미터)
    inv_ok = db_manager.insert_inventory_record({
        "serial_number": serial_number,
        "category": category,
        "product_code": product_code,
        "product_name": product_name,
        "lot": lot_number,
        "expiration_date": expiration_date_str,
        "disposal_date": disposal_date_str,
        "storage_location": storage_location,
        "version": version,
        "received_at": received_at_str
    })

    inout_ok = db_manager.insert_inout_record({
        "timestamp": received_at_str,
        "type": "입고",
        "serial_number": str(serial_number),
        "product_code": product_code,
        "product_name": product_name,
        "quantity": 1,
        "handler": ""
    })

    if inv_ok and inout_ok:
        st.success("✅ 입고 완료! SCM DB에 저장되었습니다.")
    else:
        st.error("입고 처리 중 일부 단계에서 오류가 발생했습니다.")
