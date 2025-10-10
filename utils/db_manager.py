import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

@st.cache_resource
def connect_to_mysql():
    """MySQL DB에 연결하고 SQLAlchemy 엔진을 반환합니다."""
    try:
        db_info = st.secrets["mysql"]
        conn_str = f"mysql+pymysql://{db_info['user']}:{db_info['passwd']}@{db_info['host']}:{db_info['port']}/{db_info['db']}"
        engine = create_engine(conn_str)
        return engine
    except Exception as e:
        st.error(f"MySQL 연결 실패: {e}. 'secrets.toml' 설정을 확인하세요.")
        return None

@st.cache_data(ttl=3600)
def load_product_data():
    """DB에서 전체 제품 목록을 불러와 DataFrame으로 반환합니다."""
    engine = connect_to_mysql()
    if engine is None:
        return pd.DataFrame()

    query = '''
    SELECT resource_code AS 제품코드,
           resource_name AS 제품명,
           barcode AS 바코드
    FROM boosters_items
    WHERE is_delete=0 AND brand_name IN ('이퀄베리','마켓올슨','브랜든')
    GROUP BY resource_code
    ORDER BY resource_code
    '''
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        return df
    except Exception as e:
        st.error(f"제품 정보 로드 실패: {e}")
        return pd.DataFrame()

def find_product_info_by_barcode(barcode_to_find):
    """하나의 바코드를 사용하여 DB에서 해당 제품코드와 제품명을 찾습니다."""
    engine = connect_to_mysql()
    if engine is None or not barcode_to_find:
        return None

    query = "SELECT resource_code, resource_name FROM boosters_items WHERE barcode = %(barcode)s LIMIT 1"
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection, params={"barcode": barcode_to_find})
        return df.iloc[0].to_dict() if not df.empty else None
    except Exception as e:
        st.error(f"바코드 조회 실패: {e}")
        return None


# ---------------------- 신규 추가 부분 ---------------------- #

def insert_inventory_record(data):
    """입고 데이터 → Retained_sample_status"""
    engine = connect_to_mysql()
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
    engine = connect_to_mysql()
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
