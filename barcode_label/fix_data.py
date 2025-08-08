import pandas as pd
import os

# 발행 이력 파일 수정
history_file = "issue_history.xlsx"

if os.path.exists(history_file):
    df = pd.read_excel(history_file)
    print("=== 수정 전 데이터 ===")
    print(df[['구분', '제품코드', '제품명', '보관위치']].to_string())
    
    # 문제가 있는 행들 확인
    print("\n=== 문제가 있는 행들 ===")
    print("구분이 NaN인 행:")
    print(df[df['구분'].isna()])
    print("\n보관위치가 날짜인 행:")
    print(df[df['보관위치'].str.contains('-', na=False) & df['보관위치'].str.contains(':', na=False)])
    
    # 데이터 수정
    print("\n=== 데이터 수정 중... ===")
    
    # 1. 구분이 NaN인 행들을 '관리품'으로 설정
    df.loc[df['구분'].isna(), '구분'] = '관리품'
    
    # 2. 구분이 날짜/시간인 행들을 '관리품'으로 설정
    df.loc[df['구분'].str.contains('-', na=False) & df['구분'].str.contains(':', na=False), '구분'] = '관리품'
    
    # 3. 보관위치가 날짜인 행들을 올바른 위치로 수정 (A-01-01로 임시 설정)
    df.loc[df['보관위치'].str.contains('-', na=False) & df['보관위치'].str.contains(':', na=False), '보관위치'] = 'A-01-01'
    
    print("=== 수정 후 데이터 ===")
    print(df[['구분', '제품코드', '제품명', '보관위치']].to_string())
    
    # 수정된 데이터 저장
    df.to_excel(history_file, index=False)
    print(f"\n✅ 데이터가 수정되어 {history_file}에 저장되었습니다.")
    
    # 수정 후 통계
    print("\n=== 수정 후 통계 ===")
    print(f"총 {len(df)}개 라벨")
    print(f"고유 제품: {df['제품명'].nunique()}개")
    print(f"고유 위치: {df['보관위치'].nunique()}개")
    
    # 구분별 현황
    print("\n구분별 현황:")
    print(df['구분'].value_counts())
    
    # 대시보드 방식으로 그룹화
    grouped = df.groupby(["보관위치", "구분", "제품명"]).size().reset_index()
    grouped.columns = ["보관위치", "구분", "제품명", "수량"]
    print(f"\n대시보드 항목 수: {len(grouped)}개")
    print(grouped.to_string())
    
else:
    print("발행 이력 파일이 없습니다.") 