import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# ① ERP DB (제품 정보 조회용)
# ============================================================
@st.cache_resource
def connect_to_erp():
    """ERP DB (제품정보) 연결"""
    try:
        db_info = {
            "host": st.secrets["db_server_erp"],
            "port": st.secrets["db_port_erp"],
            "user": st.secrets["db_user_erp"],
            "passwd": st.secrets["db_password_erp"],
            "db": st.secrets["db_name_erp"]
        }
        conn_str = (
            f"mysql+pymysql://{db_info['user']}:{db_info['passwd']}@"
            f"{db_info['host']}:{db_info['port']}/{db_info['db']}"
        )
        engine = create_engine(conn_str)
        return engine
    except Exception as e:
        st.error(f"ERP DB 연결 실패: {e}")
        return None


@st.cache_data(ttl=3600)
def load_product_data():
    """ERP DB에서 제품 목록을 불러옵니다."""
    engine = connect_to_erp()
    if engine is None:
        return pd.DataFrame()

    query = """
    SELECT resource_code AS 제품코드,
           resource_name AS 제품명,
           barcode AS 바코드
    FROM boosters_items
    WHERE is_delete = 0
    AND brand_name IN ('이퀄베리','마켓올슨','브랜든')
    GROUP BY resource_code
    ORDER BY resource_code
    """
    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"제품 목록 로드 실패: {e}")
        return pd.DataFrame()


def find_product_info_by_barcode(barcode_to_find):
    """ERP DB에서 바코드로 제품 정보 조회"""
    engine = connect_to_erp()
    if engine is None or not barcode_to_find:
        return None

    query = "SELECT resource_code, resource_name FROM boosters_items WHERE barcode = %(barcode)s LIMIT 1"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"barcode": barcode_to_find})
        return df.iloc[0].to_dict() if not df.empty else None
    except Exception as e:
        st.error(f"ERP 바코드 조회 실패: {e}")
        return None


# ============================================================
# ② SCM DB (재고 및 입출고 관리용)
# ============================================================
@st.cache_resource
def connect_to_scm():
    """SCM DB (입출고 및 재고관리용) 연결"""
    try:
        db_info = {
            "host": st.secrets["db_server_scm"],
            "port": st.secrets["db_port_scm"],
            "user": st.secrets["db_user_scm"],
            "passwd": st.secrets["db_password_scm"],
            "db": st.secrets["db_name_scm"]
        }
        conn_str = (
            f"mysql+pymysql://{db_info['user']}:{db_info['passwd']}@"
            f"{db_info['host']}:{db_info['port']}/{db_info['db']}"
        )
        engine = create_engine(conn_str)
        return engine
    except Exception as e:
        st.error(f"SCM DB 연결 실패: {e}")
        return None


def insert_inventory_record(data):
    """입고 데이터 → Retained_sample_status"""
    engine = connect_to_scm()
    if engine is None:
        return False
    query = """
    INSERT INTO Retained_sample_status
    (serial_number, category, product_code, product_name, lot, expiry, disposal_date,
     location, version, inbound_datetime, status, outbound_datetime, outbound_person)
    VALUES (%(serial_number)s, %(category)s, %(product_code)s, %(product_name)s,
            %(lot)s, %(expiry)s, %(disposal_date)s, %(location)s, %(version)s,
            %(inbound_datetime)s, %(status)s, %(outbound_datetime)s, %(outbound_person)s)
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(query), data)
        return True
    except Exception as e:
        st.error(f"입고 데이터 DB 저장 실패: {e}")
        return False


def insert_inout_record(data):
    """입출고 이력 → Retained_sample_in_out"""
    engine = connect_to_scm()
    if engine is None:
        return False
    query = """
    INSERT INTO Retained_sample_in_out
    (timestamp, type, serial_number, product_code, product_name, qty, outbound_person)
    VALUES (%(timestamp)s, %(type)s, %(serial_number)s, %(product_code)s,
            %(product_name)s, %(qty)s, %(outbound_person)s)
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(query), data)
        return True
    except Exception as e:
        st.error(f"입출고 이력 DB 저장 실패: {e}")
        return False
