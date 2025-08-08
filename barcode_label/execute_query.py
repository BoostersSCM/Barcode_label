import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(os.path.dirname(__file__))
from mysql_auth import boosters_db_info
import pandas as pd
from sqlalchemy import create_engine
import os
from pathlib import Path
import pyodbc

def call_query(query_string,boosters_db_info):

    # 데이터베이스 연결 설정
        conn =  {
                    "host": boosters_db_info.host,
                    "port":boosters_db_info.port,
                    "user":boosters_db_info.user,
                    "passwd":boosters_db_info.passwd,
                    "db":boosters_db_info.db,
                    "charset":boosters_db_info.charset
                }

            
        # SQLAlchemy 엔진 생성
        engine = create_engine(f"mysql+pymysql://{conn['user']}:{conn['passwd']}@{conn['host']}:3306/{conn['db']}")


        # SQL 쿼리 실행
        query = query_string  # 'your_table_name'을 실제 테이블 이름으로 변경하세요.
        df_result = pd.read_sql(query, engine)
        df = pd.DataFrame(df_result)

        # 데이터 확인
        return df


def call_query_mssql(query_string,boosters_db_info):

    # MSSQL 연결 문자열 생성
    connection_string = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={boosters_db_info.host},{boosters_db_info.port};"
        f"DATABASE={boosters_db_info.db};"
        f"UID={boosters_db_info.user};"
        f"PWD={boosters_db_info.passwd};"
        f"charset={boosters_db_info.charset}"
    )
    

    conn = pyodbc.connect(connection_string)
    df = pd.read_sql(query_string, conn)
    conn.close()
    return df