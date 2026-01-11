# Chạy lấy dữ liệu giá đã chia
# run_catchup.py
import os
import sys
# --- SETUP PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
from etl.runner import ETLRunner
from etl.runner import ETLRunner

if __name__ == "__main__":
    runner = ETLRunner()
    runner.audit_and_fix_vnindex()