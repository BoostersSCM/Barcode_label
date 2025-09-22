import streamlit as st
import json
import os

# 설정 파일 경로
CONFIG_FILE = "zone_config.json"

def get_default_config():
    """기본 보관위치 설정을 반환합니다."""
    return {
        "zones": {
            "A": {"name": "A 구역", "rows": 5, "columns": 3},
            "B": {"name": "B 구역", "rows": 5, "columns": 3}
        }
    }

def load_config():
    """zone_config.json 파일을 읽어 설정을 반환합니다. 파일이 없으면 기본값으로 새로 만듭니다."""
    if not os.path.exists(CONFIG_FILE):
        config = get_default_config()
        save_config(config)
        return config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        st.error("보관위치 설정 파일을 읽는 데 실패했습니다. 기본 설정으로 복원합니다.")
        return get_default_config()

def save_config(config):
    """설정 내용을 zone_config.json 파일에 저장합니다."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except IOError:
        st.error("보관위치 설정 파일을 저장하는 데 실패했습니다.")
        return False

def generate_location_options(config):
    """설정 파일 기반으로 보관위치 드롭다운 목록을 생성합니다."""
    options = []
    zones = config.get("zones", {})
    for code, details in zones.items():
        rows = details.get("rows", 1)
        columns = details.get("columns", 1)
        for r in range(1, rows + 1):
            for c in range(1, columns + 1):
                options.append(f"{code}-{r:02d}-{c:02d}")
    return options
