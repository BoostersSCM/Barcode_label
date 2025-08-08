import pandas as pd
import os

# 발행 이력 파일 확인
history_file = "issue_history.xlsx"

if os.path.exists(history_file):
    df = pd.read_excel(history_file)
    print("=== 발행 이력 데이터 ===")
    print(df[['구분', '제품코드', '제품명', '보관위치']].to_string())
    print(f"\n총 {len(df)}개 라벨")
    print(f"고유 제품: {df['제품명'].nunique()}개")
    print(f"고유 위치: {df['보관위치'].nunique()}개")
    
    # 위치별 제품 수
    print("\n=== 위치별 제품 현황 ===")
    location_products = df.groupby('보관위치')['제품명'].nunique()
    print(location_products)
    
    # 구분별 현황
    print("\n=== 구분별 현황 ===")
    category_counts = df['구분'].value_counts()
    print(category_counts)
    
    # 대시보드 방식으로 그룹화
    print("\n=== 대시보드 그룹화 결과 ===")
    grouped = df.groupby(["보관위치", "구분", "제품명"]).size().reset_index()
    grouped.columns = ["보관위치", "구분", "제품명", "수량"]
    print(grouped.to_string())
    print(f"대시보드 항목 수: {len(grouped)}개")
    
else:
    print("발행 이력 파일이 없습니다.") 