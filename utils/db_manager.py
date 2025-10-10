import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

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
    SELECT   resource_code as 제품코드,
             resource_name as 제품명,
             barcode as 바코드
    FROM boosters_items
    WHERE is_delete=0 AND brand_name IN ('이퀄베리','마켓올슨','브랜든')
    GROUP BY resource_code
    ORDER BY resource_code
    '''
    try:
        # 👇 with 구문을 사용해 안전하게 연결을 관리합니다.
        # 작업이 끝나면 연결이 자동으로 닫히고, 오류 발생 시 롤백됩니다.
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        return df
    except Exception as e:
        st.error(f"제품 정보 로드 실패: {e}")
        return pd.DataFrame()

def find_product_info_by_barcode(barcode_to_find):
    """
    하나의 바코드를 사용하여 DB에서 해당하는 제품코드와 제품명을 찾습니다.
    """
    engine = connect_to_mysql()
    if engine is None or not barcode_to_find:
        return None

    query = "SELECT resource_code, resource_name FROM boosters_items WHERE barcode = %(barcode)s LIMIT 1"
    
    try:
        # 👇 여기에도 with 구문을 적용하여 연결 안정성을 높입니다.
        with engine.connect() as connection:
            df = pd.read_sql(query, connection, params={"barcode": barcode_to_find})
        
        if not df.empty:
            return df.iloc[0].to_dict()
        else:
            return None
    except Exception as e:
        st.error(f"바코드 조회 실패: {e}")
        return None
