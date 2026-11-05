"""
Script mở rộng và tạo thêm dữ liệu phong phú cho dự án Excel Rule Engine.
Bao gồm:
1. Employees_IT.xlsx: 15 nhân sự IT (Fullstack, Frontend, Backend, AI, Data, Security...)
2. Employees_Business.xlsx: 15 nhân sự Sales, Marketing, HR, Finance
3. Employees_Operations.xlsx: 10 nhân sự Warehouse, Production, Logistics
4. Sales_Data.xlsx: 60 bản ghi doanh thu theo nhiều miền, sản phẩm, cả 12 tháng
5. Root_Employees.xlsx: Bảng gốc nhân sự mở rộng
6. Update_Employees.xlsx: Bảng cập nhật tương ứng với các ca Added, Updated, Unchanged
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Thêm project root vào sys.path
sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "excel_rule_engine")))

import pandas as pd

OUTPUT_DIR = (Path(__file__).resolve().parents[1] / "excel_rule_engine") / "projects" / "demo_project" / "input"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_employees_it() -> None:
    data = {
        "employee_id": [f"IT{i:03d}" for i in range(1, 16)],
        "name": [
            "Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Cường", "Phạm Thu Dung", "Hoàng Văn Em",
            "Đặng Quốc Huy", "Bùi Lan Hương", "Vũ Tuấn Kiệt", "Dương Ngọc Mai", "Lý Gia Phúc",
            "Trương Hoài Nam", "Ngô Bảo Châu", "Đinh Trọng Tấn", "Đỗ Hải Yến", "Phan Thanh Tùng"
        ],
        "department": ["IT"] * 15,
        "position": [
            "Senior Backend Dev", "Junior Frontend Dev", "DevOps Lead", "QA Automation", "Tech Lead",
            "AI Engineer", "Data Engineer", "Frontend Dev", "Mobile Dev", "Cloud Architect",
            "Database Admin", "Security Specialist", "Backend Dev", "UI/UX Designer", "Product Owner"
        ],
        "salary": [
            28_000_000, 12_500_000, 32_000_000, 16_000_000, 45_000_000,
            35_000_000, 30_000_000, 18_000_000, 20_000_000, 42_000_000,
            24_000_000, 33_000_000, 22_000_000, 19_000_000, 38_000_000
        ],
        "status": [
            "active", "active", "active", "active", "active",
            "active", "active", "active", "suspended", "active",
            "active", "active", "inactive", "active", "active"
        ],
        "email": [
            f"it.{i:03d}@company.com" for i in range(1, 16)
        ],
        "start_date": [
            "2020-03-01", "2023-08-15", "2019-11-20", "2022-02-10", "2018-06-01",
            "2021-05-12", "2021-09-01", "2023-01-15", "2022-11-01", "2019-04-18",
            "2020-07-22", "2021-10-05", "2022-03-14", "2023-04-01", "2019-08-10"
        ],
    }
    df = pd.DataFrame(data)
    path = OUTPUT_DIR / "Employees_IT.xlsx"
    df.to_excel(path, index=False)
    print(f"  ✓ {path.name} ({len(df)} rows)")


def create_employees_business() -> None:
    data = {
        "employee_id": [f"BIZ{i:03d}" for i in range(1, 16)],
        "name": [
            "Vũ Thị Phương", "Đỗ Quang Huy", "Bùi Thị Lan", "Ngô Văn Minh", "Đinh Thị Nga",
            "Trịnh Hồng Nhung", "Cao Thái Sơn", "Mai Thu Huyền", "Lê Tấn Phát", "Hoàng Kim Ngân",
            "Tạ Đình Phong", "Hà Kiều Anh", "Chu Minh Trí", "Lương Mỹ Linh", "Phùng Thế Vinh"
        ],
        "department": [
            "HR", "HR", "Accounting", "Accounting", "Accounting",
            "Sales", "Sales", "Sales", "Sales", "Sales",
            "Marketing", "Marketing", "Marketing", "Finance", "Finance"
        ],
        "position": [
            "HR Manager", "HR Specialist", "Chief Accountant", "Senior Accountant", "Junior Accountant",
            "Sales Director", "Key Account Manager", "Sales Executive", "Sales Executive", "Telesales Lead",
            "Marketing Director", "Content Strategist", "Performance Media Lead", "Financial Analyst", "Risk Manager"
        ],
        "salary": [
            26_000_000, 14_000_000, 35_000_000, 18_500_000, 11_000_000,
            40_000_000, 25_000_000, 15_000_000, 13_500_000, 16_000_000,
            36_000_000, 17_000_000, 22_000_000, 28_000_000, 31_000_000
        ],
        "status": [
            "active", "active", "active", "active", "inactive",
            "active", "active", "active", "active", "active",
            "active", "active", "suspended", "active", "active"
        ],
        "email": [
            f"biz.{i:03d}@company.com" for i in range(1, 16)
        ],
        "start_date": [
            "2018-04-01", "2022-09-01", "2016-01-15", "2021-05-20", "2023-02-01",
            "2017-10-10", "2020-06-15", "2022-04-12", "2023-03-01", "2021-12-05",
            "2019-02-20", "2022-08-18", "2021-07-07", "2020-11-15", "2019-05-25"
        ],
    }
    df = pd.DataFrame(data)
    path = OUTPUT_DIR / "Employees_Business.xlsx"
    df.to_excel(path, index=False)
    print(f"  ✓ {path.name} ({len(df)} rows)")


def create_employees_operations() -> None:
    data = {
        "employee_id": [f"OPS{i:03d}" for i in range(1, 11)],
        "name": [
            "Nguyễn Đức Chung", "Phạm Văn Long", "Đoàn Quốc Đạt", "Võ Thị Hạnh", "Lâm Thanh Hà",
            "Thái Hữu Thắng", "Diệp Lạc Băng", "Quách Thành Danh", "Tống Bá Quát", "Triệu Lệ Quyên"
        ],
        "department": [
            "Warehouse", "Warehouse", "Warehouse", "Production", "Production",
            "Production", "Admin", "Admin", "Engineering", "Engineering"
        ],
        "position": [
            "Warehouse Manager", "Inventory Specialist", "Forklift Driver", "Plant Manager", "QA Inspector",
            "Assembly Technician", "Admin Officer", "Facility Supervisor", "Chief Engineer", "Maintenance Specialist"
        ],
        "salary": [
            22_000_000, 13_000_000, 9_500_000, 30_000_000, 14_000_000,
            11_500_000, 12_000_000, 15_000_000, 32_000_000, 16_500_000
        ],
        "status": [
            "active", "active", "active", "active", "active",
            "inactive", "active", "active", "active", "active"
        ],
        "email": [
            f"ops.{i:03d}@company.com" for i in range(1, 11)
        ],
        "start_date": [
            "2019-01-10", "2021-03-25", "2023-05-10", "2018-08-01", "2022-07-15",
            "2020-04-12", "2022-10-01", "2021-01-20", "2017-09-15", "2020-12-01"
        ],
    }
    df = pd.DataFrame(data)
    path = OUTPUT_DIR / "Employees_Operations.xlsx"
    df.to_excel(path, index=False)
    print(f"  ✓ {path.name} ({len(df)} rows)")


def create_sales_data() -> None:
    months = [
        "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06",
        "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"
    ]
    products = ["Laptop Pro X", "Màn Hình 4K", "Bàn Phím Cơ", "Chuột Không Dây", "Tai Nghe ANC"]
    regions = ["Miền Bắc", "Miền Nam", "Miền Trung"]
    
    rows = []
    import random
    random.seed(42)
    for m in months:
        for p in products:
            reg = random.choice(regions)
            qty = random.randint(50, 400)
            unit_price = {
                "Laptop Pro X": 25_000_000,
                "Màn Hình 4K": 12_000_000,
                "Bàn Phím Cơ": 2_500_000,
                "Chuột Không Dây": 1_800_000,
                "Tai Nghe ANC": 4_200_000
            }[p]
            rev = qty * unit_price
            cost = int(rev * random.uniform(0.55, 0.75))
            rows.append({
                "month": m,
                "product": p,
                "region": reg,
                "quantity": qty,
                "revenue": rev,
                "cost": cost,
                "profit": rev - cost
            })

    df = pd.DataFrame(rows)
    path = OUTPUT_DIR / "Sales_Data.xlsx"
    df.to_excel(path, index=False)
    print(f"  ✓ {path.name} ({len(df)} rows)")


def create_root_and_update_files() -> None:
    root_data = {
        "employee_id": [f"EMP{i:03d}" for i in range(1, 13)],
        "name": [
            "Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Cường", "Phạm Thu Dung", "Hoàng Văn Em",
            "Vũ Thị Phương", "Đỗ Quang Huy", "Bùi Thị Lan", "Ngô Văn Minh", "Đặng Quốc Huy",
            "Mai Thu Huyền", "Lâm Thanh Hà"
        ],
        "department": [
            "IT", "IT", "IT", "IT", "IT",
            "HR", "HR", "Accounting", "Accounting", "IT",
            "Sales", "Production"
        ],
        "salary": [
            28_000_000, 12_500_000, 32_000_000, 16_000_000, 45_000_000,
            26_000_000, 14_000_000, 35_000_000, 18_500_000, 35_000_000,
            15_000_000, 14_000_000
        ],
        "status": [
            "active", "active", "active", "active", "active",
            "active", "active", "active", "active", "active",
            "active", "active"
        ]
    }
    df_root = pd.DataFrame(root_data)
    path_root = OUTPUT_DIR / "Root_Employees.xlsx"
    df_root.to_excel(path_root, index=False)
    print(f"  ✓ {path_root.name} ({len(df_root)} rows)")

    update_data = {
        "employee_id": [
            "EMP001", "EMP002", "EMP003", "EMP004", "EMP005",
            "EMP006", "EMP007", "EMP008", "EMP010", "EMP011", "EMP012",
            "EMP013", "EMP014"
        ],
        "name": [
            "Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Cường", "Phạm Thu Dung", "Hoàng Văn Em",
            "Vũ Thị Phương", "Đỗ Quang Huy", "Bùi Thị Lan", "Đặng Quốc Huy", "Mai Thu Huyền", "Lâm Thanh Hà",
            "Trịnh Văn Phong (Mới)", "Hà Mỹ Duyên (Mới)"
        ],
        "department": [
            "IT", "IT", "IT", "IT", "IT",
            "HR", "HR", "Accounting", "IT", "Sales", "Production",
            "Marketing", "IT"
        ],
        "salary": [
            30_000_000, 12_500_000, 32_000_000, 16_000_000, 45_000_000,
            26_000_000, 16_000_000, 35_000_000, 35_000_000, 15_000_000, 14_000_000,
            21_000_000, 27_000_000
        ],
        "status": [
            "active", "active", "active", "inactive", "active",
            "active", "active", "active", "active", "active", "active",
            "active", "active"
        ]
    }
    df_update = pd.DataFrame(update_data)
    path_update = OUTPUT_DIR / "Update_Employees.xlsx"
    df_update.to_excel(path_update, index=False)
    print(f"  ✓ {path_update.name} ({len(df_update)} rows)")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(f"\n📁 Đang tạo bộ dữ liệu phong phú mới vào: {OUTPUT_DIR}\n")
    create_employees_it()
    create_employees_business()
    create_employees_operations()
    create_sales_data()
    create_root_and_update_files()
    print("\n✅ Hoàn tất! Đã cập nhật xong tất cả file Excel mẫu.")
