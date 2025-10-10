# utils/db_manager.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------
# DB 연결 (SCM / ERP)
# ---------------------------------------
@st.cache_resource
def connect_to_scm():
    """
    SCM DB(MySQL) 연결 엔진 생성
    Streamlit Cloud 환경의 st.secrets 사용 가정:
      - db_user_scm, db_password_scm, db_server_scm, db_port_scm, db_name_scm
    """
    try:
        db_uri = (
            f"mysql+pymysql://{st.secrets['db_user_scm']}:{st.secrets['db_password_scm']}"
            f"@{st.secrets['db_server_scm']}:{st.secrets.get('db_port_scm', 3306)}"
            f"/{st.secrets['db_name_scm']}"
        )
        return create_engine(db_uri)
    except Exception as e:
        st.error(f"SCM DB 연결 오류: {e}")
        return None

@st.cache_resource
def connect_to_erp():
    """
    ERP DB(MySQL) 연결 엔진 생성
      - db_user_erp, db_password_erp, db_server_erp, db_port_erp, db_name_erp
    """
    try:
        db_uri = (
            f"mysql+pymysql://{st.secrets['db_user_erp']}:{st.secrets['db_password_erp']}"
            f"@{st.secrets['db_server_erp']}:{st.secrets.get('db_port_erp', 3306)}"
            f"/{st.secrets['db_name_erp']}"
        )
        return create_engine(db_uri)
    except Exception as e:
        st.error(f"ERP DB 연결 오류: {e}")
        return None

# ---------------------------------------
# ERP 제품 데이터 로드
# ---------------------------------------
def load_product_data() -> pd.DataFrame:
    """
    ERP에서 제품코드/제품명/(선택)바코드 컬럼을 조회하여 DataFrame 반환
    - 테이블/칼럼명은 환경에 맞춰 수정
    """
    engine = connect_to_erp()
    if engine is None:
        return pd.DataFrame()

    # 예시 쿼리: 제품코드, 제품명, 바코드
    query = text("""
        SELECT
            product_code   AS `제품코드`,
            product_name   AS `제품명`,
            barcode        AS `바코드`
        FROM products
        WHERE is_active = 1
    """)
    try:
        with engine.begin() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"ERP 제품정보 로드 실패: {e}")
        return pd.DataFrame()

# ---------------------------------------
# 바코드로 제품 찾기 (권장: DB 조회)
# ---------------------------------------
def find_product_info_by_barcode(barcode: str) -> dict | None:
    """
    ERP에서 바코드로 제품 정보를 조회
    반환 예: {"resource_code": "P0001", "resource_name": "제품A"} 등
    실제 테이블/컬럼명은 환경에 맞추어 수정
    """
    engine = connect_to_erp()
    if engine is None:
        return None

    query = text("""
        SELECT
            product_code AS resource_code,
            product_name AS resource_name
        FROM products
        WHERE barcode = :barcode
        LIMIT 1
    """)
    try:
        with engine.begin() as conn:
            row = conn.execute(query, {"barcode": barcode}).mappings().first()
            return dict(row) if row else None
    except Exception as e:
        st.error(f"바코드 조회 실패: {e}")
        return None

# ---------------------------------------
# INSERT: Retained_sample_status (영문 파라미터명과 1:1 매칭)
# ---------------------------------------
def insert_inventory_record(data: dict) -> bool:
    """
    입고 데이터 → SCM.Retained_sample_status
    data 키(=플레이스홀더)와 컬럼명을 영문으로 1:1 매칭:
      serial_number, category, product_code, product_name, lot,
      expiration_date, disposal_date, storage_location, version, received_at
    """
    engine = connect_to_scm()
    if engine is None:
        return False

    query = text("""
        INSERT INTO `Retained_sample_status`
        (serial_number, category, product_code, product_name, lot,
         expiration_date, disposal_date, storage_location, version, received_at)
        VALUES
        (:serial_number, :category, :product_code, :product_name, :lot,
         :expiration_date, :disposal_date, :storage_location, :version, :received_at)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, data)
        return True
    except Exception as e:
        st.error(f"입고 데이터 DB 저장 실패: {e}")
        return False

# ---------------------------------------
# INSERT: Retained_sample_in_out (영문 파라미터명과 1:1 매칭)
# ---------------------------------------
def insert_inout_record(data: dict) -> bool:
    """
    입출고 이력 → SCM.Retained_sample_in_out
    data 키(=플레이스홀더)와 컬럼명을 영문으로 1:1 매칭:
      timestamp, type, serial_number, product_code, product_name, quantity, handler
    """
    engine = connect_to_scm()
    if engine is None:
        return False

    query = text("""
        INSERT INTO `Retained_sample_in_out`
        (`timestamp`, `type`, serial_number, product_code, product_name, quantity, handler)
        VALUES
        (:timestamp, :type, :serial_number, :product_code, :product_name, :quantity, :handler)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, data)
        return True
    except Exception as e:
        st.error(f"입출고 이력 DB 저장 실패: {e}")
        return False
