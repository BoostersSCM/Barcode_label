from sqlalchemy import text

def insert_inventory_record(data: dict) -> bool:
    """입고 데이터 → SCM.Retained_sample_status"""
    engine = connect_to_scm()
    if engine is None:
        return False

    query = text("""
        INSERT INTO `Retained_sample_status`
        (serial_number, category, product_code, product_name, lot, expiration_date, disposal_date, storage_location, version, received_at)
        VALUES
        (:serial_number, :category, :product_code, :product_name, :lot,
         :expiration_date, :disposal_date, :location, :version, :inbound_datetime)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, data)
        return True
    except Exception as e:
        st.error(f"입고 데이터 DB 저장 실패: {e}")
        return False


def insert_inout_record(data: dict) -> bool:
    """입출고 이력 → SCM.Retained_sample_in_out"""
    engine = connect_to_scm()
    if engine is None:
        return False

    query = text("""
        INSERT INTO `Retained_sample_in_out`
        (`timestamp`, `type`, serial_number, product_code, product_name, quantity, handler)
        VALUES
        (:timestamp, :type, :serial_number, :product_code, :product_name, :qty, :outbound_person)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, data)
        return True
    except Exception as e:
        st.error(f"입출고 이력 DB 저장 실패: {e}")
        return False
