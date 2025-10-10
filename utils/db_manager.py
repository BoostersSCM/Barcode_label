# utils/db_manager.py

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# ① Boosters DB (ERP - 제품 정보 조회용)
# ============================================================
@st.cache_resource
def connect_to_boosters():
    """제품정보용 boosters DB에 연결하고 engine 객체를 반환합니다."""
    try:
        db_info = st.secrets["boosters_db"]
        conn_str = f"mysql+pymysql://{db_info['user']}:{db_info['passwd']}@{db_info['host']}:{db_info['port']}/{db_info['db']}"
        return create_engine(conn_str)
    except Exception as e:
        st.error(f"제품정보 DB 연결 실패: {e}")
        return None

@st.cache_data(ttl=3600)
def load_product_data(_engine):
    """boosters DB에서 제품 목록을 불러옵니다."""
    if _engine is None: return pd.DataFrame()
    query = """
    SELECT resource_code AS 제품코드, resource_name AS 제품명
    FROM boosters_items
    WHERE is_delete=0 AND brand_name IN ('이퀄베리','마켓올슨','브랜든')
    GROUP BY resource_code ORDER BY resource_code
    """
    try:
        with _engine.connect() as conn:
            return pd.read_sql(text(query), conn)
    except Exception as e:
        st.error(f"제품 정보 로드 실패: {e}")
        return pd.DataFrame()

# ============================================================
# ② SCM DB (입출고 / 재고 관리용)
# ============================================================
@st.cache_resource
def connect_to_scm():
    """SCM DB에 연결하고 engine 객체를 반환합니다."""
    try:
        db_info = st.secrets["scm_db"]
        conn_str = f"mysql+pymysql://{db_info['user']}:{db_info['passwd']}@{db_info['host']}:{db_info['port']}/{db_info['db']}"
        return create_engine(conn_str)
    except Exception as e:
        st.error(f"SCM DB 연결 실패: {e}")
        return None

def get_inventory_details(_engine, serial_number):
    """SCM DB에서 serial_number로 재고 상세 정보를 조회합니다."""
    if _engine is None or not serial_number: return None
    query = "SELECT product_code, product_name FROM Retained_sample_status WHERE serial_number = :sn LIMIT 1"
    try:
        with _engine.connect() as conn:
            result = conn.execute(text(query), {"sn": serial_number}).fetchone()
        return result._asdict() if result else None
    except Exception as e:
        st.error(f"재고 정보 조회 실패: {e}")
        return None


def insert_inventory_record(_engine, data):
    """입고 데이터를 Retained_sample_status 테이블에 저장합니다."""
    if _engine is None: return False
    query = """
    INSERT INTO Retained_sample_status
    (serial_number, category, product_code, product_name, lot, expiry, disposal_date,
     location, version, inbound_datetime, status, outbound_datetime, outbound_person)
    VALUES (%(serial_number)s, %(category)s, %(product_code)s, %(product_name)s,
            %(lot)s, %(expiry)s, %(disposal_date)s, %(location)s, %(version)s,
            %(inbound_datetime)s, %(status)s, %(outbound_datetime)s, %(outbound_person)s)
    """
    try:
        with _engine.begin() as conn:
            conn.execute(text(query), data)
        return True
    except Exception as e:
        st.error(f"입고 데이터 DB 저장 실패: {e}")
        return False

def insert_inout_record(_engine, data):
    """입출고 이력을 Retained_sample_in_out 테이블에 저장합니다."""
    if _engine is None: return False
    query = """
    INSERT INTO Retained_sample_in_out
    (timestamp, type, serial_number, product_code, product_name, qty, outbound_person)
    VALUES (%(timestamp)s, %(type)s, %(serial_number)s, %(product_code)s,
            %(product_name)s, %(qty)s, %(outbound_person)s)
    """
    try:
        with _engine.begin() as conn:
            conn.execute(text(query), data)
        return True
    except Exception as e:
        st.error(f"입출고 이력 DB 저장 실패: {e}")
        return False
