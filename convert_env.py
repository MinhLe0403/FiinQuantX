from dotenv import dotenv_values
import toml

def convert_env_to_toml(env_path, toml_path):
    # 1. Đọc file .env vào một Dictionary
    # dotenv_values sẽ tự động xử lý các key=value
    config = dotenv_values(env_path)
    
    # 2. Ghi Dictionary đó ra file .toml
    with open(toml_path, "w", encoding="utf-8") as f:
        toml.dump(config, f)
    
    print(f"✅ Đã chuyển đổi thành công: {toml_path}")

# Chạy hàm
convert_env_to_toml(".env", "secrets.toml")