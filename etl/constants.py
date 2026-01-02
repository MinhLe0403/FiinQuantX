# etl/constants.py

# --- 1. NHÓM CHỈ SỐ THỊ TRƯỜNG (MARKET INDICES) ---

# 1.1. Nhóm VN (HOSE)
VN_INDICES = [
    "VNINDEX", "VN30", "VN100", "VNALL", "VNXALL", "VN50", 
    "VNFIN", "VNFINSELECT", "VNFINLEAD", "VNSI", "VNDIAMOND", 
    "VNMID", "VNREAL", "VNMAT", "VNCONS", "VNIND", 
    "VNSML", "VNIT", "VNCOND"
]

# 1.2. Nhóm HNX
HNX_INDICES = [
    "HNXINDEX", "HNX30"
]

# 1.3. Nhóm UPCOM
UPCOM_INDICES = [
    "UPCOMINDEX"
]

# Gộp tất cả index lại để quét một thể
ALL_INDICES = VN_INDICES + HNX_INDICES + UPCOM_INDICES

# Danh sách hiển thị trên UI cho người dùng chọn
VN_INDICES_OPTIONS = [
    "VNINDEX", "VN30", "VN100", "VNALL", "VNXALL", "VN50", 
    "VNFIN", "VNFINSELECT", "VNFINLEAD", "VNSI", "VNDIAMOND", 
    "VNMID", "VNREAL", "VNMAT", "VNCONS", "VNIND", 
    "VNSML", "VNIT", "VNCOND"
]

HNX_INDICES_OPTIONS = ["HNXINDEX", "HNX30"]
UPCOM_INDICES_OPTIONS = ["UPCOMINDEX"]

# Gộp dict để mapping nếu cần (hiện tại dùng tên trực tiếp làm mã là được)
ALL_INDICES_OPTIONS = VN_INDICES_OPTIONS + HNX_INDICES_OPTIONS + UPCOM_INDICES_OPTIONS

# --- 2. NHÓM NGÀNH (ICB SECTORS) ---
# Mapping: Tên Tiếng Việt -> Mã Code (truyền vào API)
# Bạn có thể comment (#) những ngành quá nhỏ không muốn quét
ICB_SECTORS = {
    # --- Cấp 1 (L1) ---
    "Dầu khí L1": "OIL_AND_GAS_L1",
    "Nguyên vật liệu L1": "BASIC_MATERIALS_L1",
    "Công nghiệp L1": "INDUSTRIALS_L1",
    "Hàng Tiêu dùng L1": "CONSUMER_GOODS_L1",
    "Dược phẩm và Y tế L1": "HEALTH_CARE_L1",
    "Dịch vụ Tiêu dùng L1": "CONSUMER_SERVICES_L1",
    "Viễn thông L1": "TELECOMMUNICATIONS_L1",
    "Tiện ích Cộng đồng L1": "UTILITIES_L1",
    "Tài chính L1": "FINANCIALS_L1",
    "Công nghệ Thông tin L1": "TECHNOLOGY_L1",

    # --- Cấp 2 (L2 - Quan trọng) ---
    "Ngân hàng": "BANKS_L2",
    "Bất động sản": "REAL_ESTATE_L2",
    "Dịch vụ tài chính (Chứng khoán)": "FINANCIAL_SERVICES_L2",
    "Bảo hiểm": "INSURANCE_L2",
    "Thực phẩm đồ uống": "FOOD_AND_BEVERAGE_L2",
    "Xây dựng và Vật liệu": "CONSTRUCTION_AND_MATERIALS_L2",
    "Hóa chất": "CHEMICALS_L2",
    "Tài nguyên cơ bản (Thép)": "BASIC_RESOURCES_L2",
    "Bán lẻ": "RETAIL_L2",
    "Dầu khí L2": "OIL_AND_GAS_L2",
    "Ô tô và phụ tùng": "AUTOMOBILES_AND_PARTS_L2",
    "Hàng cá nhân & Gia dụng": "PERSONAL_AND_HOUSEHOLD_GOODS_L2",
    "Truyền thông": "MEDIA_L2",
    "Du lịch và Giải trí": "TRAVEL_AND_LEISURE_L2",
    "Viễn thông L2": "TELECOMMUNICATIONS_L2",
    "Tiện ích (Điện/Nước)": "UTILITIES_L2",
    "Công nghệ L2": "TECHNOLOGY_L2",

    # --- Cấp 3 & 4 (Các ngành ngách phổ biến) ---
    "Sản xuất Dầu khí": "OIL_AND_GAS_PRODUCERS_L3",
    "Thép": "STEEL_L4",
    "Dệt may (Hàng may mặc)": "CLOTHING_AND_ACCESSORIES_L4",
    "Thủy sản (Nuôi trồng)": "FARMING_AND_FISHING_L4", 
    "Phân bón (Hóa chất nông nghiệp)": "FERTILIZER_L5", # Lấy code L5 nếu cần chi tiết
    "Logistics (Kho bãi)": "TRANSPORTATION_SERVICES_L4",
    "Vận tải biển": "MARINE_TRANSPORTATION_L4",
    "Điện (Sản xuất & PP)": "ELECTRICITY_L3",
    "Nhựa & Cao su": "COMMODITY_CHEMICALS_L4",
    "Dược phẩm": "PHARMACEUTICALS_L3",
    "Công nghệ thông tin (Phần mềm)": "SOFTWARE_AND_COMPUTER_SERVICES_L3"
}

# Danh sách chỉ chứa Code để chạy vòng lặp
SECTOR_CODES_LIST = list(ICB_SECTORS.values())