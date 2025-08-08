#!/usr/bin/env python3
# -*- coding: utf-8 -*- 라벨 관리 시스템 - stock_manager.exe 빌드 스크립트
"""

import os
import sys
import subprocess
import shutil

def build_stock_manager():
  stock_manager.exe 빌드"""
    print("🔨 stock_manager.py → stock_manager.exe 빌드 중...")
    
    # PyInstaller 명령어 구성
    cmd =     sys.executable, -m, nstaller",
        --onefile",  # 단일 파일로 생성
        --windowed",  # 콘솔 창 숨김
      --name",stock_manager,    --distpath, dist,    --workpath", "build,    --specpath", ".",
        --clean",
     --noconfirm",
        --hidden-import",pandas",
        --hidden-import", PIL
        --hidden-import", barcode",
        --hidden-import",qrcode",
        --hidden-import", "tkcalendar",
        --hidden-import", "openpyxl",
        --hidden-import", pymysql",
        --hidden-import", "cryptography",
        --hidden-import",execute_query",
        --hidden-import", "mysql_auth",
        --hidden-import,boosters_query",
     --add-data", "logo.png;.",
     --add-data", "issue_history.xlsx;.",
     --add-data, products.xlsx;.",
     --add-data", zone_config.json;.",
        --add-data",outbound_history.xlsx;.",
      --add-data", barcode_mapping.xlsx;.",
     --add-data", execute_query.py;.",
     --add-data, mysql_auth.py;.",
     --add-data,boosters_query.py;.",
       stock_manager.py"
    ]
    
    try:
        # PyInstaller 실행
        print(f실행 명령어: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ stock_manager.exe 빌드 성공!")
            
            # dist 폴더에서 현재 디렉토리로 복사
            dist_exe = os.path.join("dist", stock_manager.exe")
            target_exe = stock_manager.exe"
            
            if os.path.exists(dist_exe):
                shutil.copy2ist_exe, target_exe)
                print(f"✅ stock_manager.exe가 barcode_label 폴더에 복사되었습니다.")
                
                # 파일 크기 확인
                file_size = os.path.getsize(target_exe) / (124MB
                print(f"📁 파일 크기: {file_size:.1f} MB")
                
                # 배포용 폴더 생성
                create_deployment_package()
                return True
            else:
                print(f"❌ stock_manager.exe 파일을 찾을 수 없습니다.)            return False
        else:
            print(f"❌ stock_manager.exe 빌드 실패!")
            print("오류 출력:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ 빌드 중 오류 발생: {e}")
        return False

def create_deployment_package():
   배포용 패키지 생성"
    print(n📦 배포용 패키지 생성 중...)
    
    # 배포 폴더 생성
    deploy_dir = 배포용_stock_manager"
    if os.path.exists(deploy_dir):
        shutil.rmtree(deploy_dir)
    os.makedirs(deploy_dir)
    
    # EXE 파일 복사
    if os.path.exists(stock_manager.exe):       shutil.copy2(stock_manager.exe", deploy_dir)
        print(f"✅ stock_manager.exe 복사 완료")
    
    # 필요한 데이터 파일들 복사
    data_files = [
  logo.png",
       products.xlsx",
       zone_config.json",
       execute_query.py",
       mysql_auth.py",
        boosters_query.py"
    ]
    
    for data_file in data_files:
        if os.path.exists(data_file):
            shutil.copy2(data_file, deploy_dir)
            print(f"✅ {data_file} 복사 완료)
    
    # README 파일 생성
    readme_content =고/출고 관리 시스템 (stock_manager.exe)

## 설치 및 실행 방법

### 1. 시스템 요구사항
- Windows 101164비트)
- 최소 4B RAM
- 50MB 이상의 여유 디스크 공간

### 21`stock_manager.exe`를 더블클릭하여 실행
2. 입고/출고 관리 기능을 사용하세요

### 3. 주요 기능
- 📦 입고/출고 관리
- 🏷️ 라벨 발행 및 인쇄
- 📊 재고 현황 대시보드
- 🧐 관리품 위치 찾기
- ⚙️ 구역 관리
- 📷 바코드 리딩

### 4. 데이터베이스 연결
- MySQL 데이터베이스 연결이 필요합니다
- `mysql_auth.py` 파일에서 데이터베이스 설정을 확인하세요

### 5. 문제 해결
- 프로그램이 실행되지 않으면 Visual C++ Redistributable 설치
- 바코드 스캐너 연결 시 드라이버 설치 필요
- 데이터베이스 연결 오류 시 네트워크 및 접속 정보 확인

## 문의사항
기술 지원이 필요한 경우 개발팀에 문의하세요."""
    
    with open(os.path.join(deploy_dir,README.txt"), w, encoding="utf-8) asf:
        f.write(readme_content)
    
    print(f"✅ 배포용 패키지가 {deploy_dir}' 폴더에 생성되었습니다.")
    print(f"📁 이 폴더를 다른 컴퓨터에 복사하여 사용하세요.")

def cleanup_build_files():
 드 임시 파일들 정리"
    print("\n🧹 빌드 임시 파일 정리 중...")
    
    # 정리할 폴더들
    cleanup_dirs = ["build", dist, _pycache__]
    
    # 현재 디렉토리 내의 __pycache__ 폴더들도 정리
    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__:           cleanup_dirs.append(os.path.join(root, dir_name))
    
    # 폴더 정리
    for dir_path in cleanup_dirs:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f✅ {dir_path} 삭제 완료")
            except Exception as e:
                print(f❌[object Object]dir_path} 삭제 실패: {e})    
    # spec 파일들 정리
    for file in os.listdir("."):
        if file.endswith(".spec"):
            try:
                os.remove(file)
                print(f✅ {file} 삭제 완료")
            except Exception as e:
                print(f❌ {file} 삭제 실패: {e}")

def main():
   메인 빌드 프로세스"
    print("🚀 입고/출고 관리 시스템 EXE 빌드 시작!)
    print(= * 60)
    
    # stock_manager.exe 빌드
    if build_stock_manager():
        print("\n" +=60
        print("🎉 stock_manager.exe 빌드 성공!)
        print("=" * 60)
        
        print("\n✅ 빌드 프로세스 완료!")
        print("\n💡 사용 방법:)
        print(1.stock_manager.exe'를 실행하여 입고/출고 관리 시스템을 사용하세요)
        print("2. 배포용_stock_manager 폴더를 다른 컴퓨터에 복사하여 사용하세요)
        print("3모든 필요한 파일이 포함되어 있어 다른 컴퓨터에서도 바로 실행 가능합니다")
    else:
        print(n❌ stock_manager.exe 빌드 실패!")
    
    # 임시 파일 정리
    cleanup_build_files()

if __name__ == "__main__":
    main() 