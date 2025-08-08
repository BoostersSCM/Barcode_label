class boosters_query:
    def __init__(self, query):
        self.query = query

    def get_query(self, **params):
        # 파라미터가 없을 경우 기본 템플릿 반환
        return self.query.format(**params) if params else self.query

#채널별 출고 데이터
q_channel_output = boosters_query(
    query='''
            SELECT brand_name
                     ,channel_name
                     ,date
                     ,boosters_item_id
                     ,resource_name
                     ,SUM(output_stock) AS output
                FROM snap_boosters_stock_channel_infos
                WHERE date>'2023-12-01'
                GROUP BY brand_name,channel_name,date,boosters_item_id,resource_name
          '''
)

q_boosters_items = boosters_query('''
SELECT brand_name,
		 resource_code,
		 resource_name,
		 manager,
		 OPTION1,
		 OPTION2,
		 resource_lot_name,
		 cogs,
		 nansoft_standard_quantity
from boosters_items
WHERE is_delete=0 AND brand_name='이퀄베리'
'''
)


q_boosters_items_for_barcode_reader = boosters_query('''
SELECT   resource_code as 제품코드,
		 resource_name as 제품명,
         barcode as 바코드

from boosters_items
WHERE is_delete=0 AND brand_name IN ('이퀄베리','마켓올슨','브랜든')
group by barcode
order by resource_code
''')


q_boosters_items_limit_date = boosters_query(
    query='''SELECT ItemNo as 제품코드,
            SMLimitTermKindName as 유통기한_구분,
            LimitTerm as 유통기한_일수
from boosters_erp.erp_item_leadtimes
WHERE LimitTerm>0
''')