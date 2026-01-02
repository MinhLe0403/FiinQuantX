# 📈 Vietnam Stock Analyzer

Ứng dụng phân tích thị trường chứng khoán Việt Nam, hỗ trợ nhà đầu tư theo dõi dòng tiền ngành và phân tích kỹ thuật/cơ bản của từng cổ phiếu.

![Demo App](https://via.placeholder.com/800x400?text=Screenshot+App+Cua+Ban)
*(Bạn nên chụp ảnh màn hình app, upload lên tab Issues của Github hoặc Imgur rồi dán link vào đây)*

## 🚀 Tính năng chính

- **Tổng quan thị trường (Market Dashboard):**
  - Biểu đồ Sector Rotation (Dòng tiền luân chuyển).
  - Top cổ phiếu tăng/giảm mạnh trong ngày.
  - Drill-down từ Ngành xuống Cổ phiếu chi tiết.
- **Phân tích Cổ phiếu (Stock Analysis):**
  - Biểu đồ nến (Candlestick) tương tác với Plotly.
  - Các chỉ báo kỹ thuật (MA, RSI, MACD).
  - Phân tích cơ bản (P/E, P/B, Doanh thu).

## 🛠️ Công nghệ sử dụng

- **Python 3.10+**
- **Streamlit:** Framework giao diện (Frontend).
- **Pandas & SQLAlchemy:** Xử lý dữ liệu và kết nối Database.
- **Plotly:** Vẽ biểu đồ tương tác.
- **MySQL/PostgreSQL:** Cơ sở dữ liệu lưu trữ giá và thông tin tài chính.

## ⚙️ Cài đặt và Chạy Local

1. **Clone dự án:**
   ```bash
   git clone https://github.com/USERNAME/vietnam-stock-analyzer.git
   cd vietnam-stock-analyzer
   ```

2. **Cài đặt thư viện:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Cấu hình Database:**
   - Tạo file `.streamlit/secrets.toml` với nội dung:
     ```toml
     [db]
     host = "localhost"
     user = "root"
     password = "YOUR_PASSWORD"
     db_name = "stock_db"
     ```
   - Import dữ liệu mẫu từ file `data/schema.sql` (nếu bạn có export file sql).

4. **Chạy ứng dụng:**
   ```bash
   streamlit run app.py
   ```

## 📂 Cấu trúc dự án

```
├── app.py              # File chính chạy ứng dụng
├── analysis/           # Module xử lý tính toán
│   ├── visualizer.py   # Vẽ biểu đồ
│   └── indicators.py   # Tính chỉ báo
├── database/           # Module kết nối DB
├── assets/             # Hình ảnh, CSS
├── requirements.txt    # Thư viện phụ thuộc
└── README.md           # Tài liệu hướng dẫn
```

## 🤝 Đóng góp
Mọi đóng góp (Pull Request) đều được hoan nghênh.

## 📝 License
MIT License