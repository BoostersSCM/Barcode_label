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

@st.cache_data(ttl=3600) # 1시간 동안 제품 목록 캐시
def load_product_data():
    """DB에서 제품 목록을 불러와 DataFrame으로 반환합니다."""
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
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        st.error(f"제품 정보 로드 실패: {e}")
        return pd.DataFrame()
