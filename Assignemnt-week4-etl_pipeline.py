from __future__ import annotations

from pathlib import Path
import sqlite3
import pandas as pd

# กำหนดตำแหน่งไฟล์
PROJECT_DIR = Path(".").resolve()
DATA_PATH = PROJECT_DIR / "retail_logs.csv"
DB_PATH = PROJECT_DIR / "retail_warehouse.db"


def clean_text(value: object, default: str = "Unknown") -> str:
    """ทำความสะอาดและปรับรูปแบบข้อความให้เป็น Title Case สม่ำเสมอ"""
    if pd.isna(value) or str(value).strip() in ["", "nan", "NaN", "None", "null"]:
        return default
    return " ".join(str(value).strip().split()).title()


def parse_mixed_date(value: object) -> pd.Timestamp:
    """แปลงวันที่ซึ่งมีหลายรูปแบบ (Mixed Formats) ให้เป็น Timestamp"""
    if pd.isna(value) or str(value).strip() == "":
        return pd.NaT
    text = str(value).strip()
    return pd.to_datetime(text, dayfirst=True, format="mixed", errors="coerce")


def extract() -> pd.DataFrame:
    """Extract ข้อมูลดิบจากไฟล์ CSV"""
    df = pd.read_csv(DATA_PATH, dtype=str, encoding="utf-8-sig")
    print(f"[Extract] Raw rows: {len(df):,}, Duplicate Sale_IDs: {df.duplicated('Sale_ID').sum():,}")
    return df


def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Transform ข้อมูลดิบเป็น Star Schema (Dimensions & Fact)"""
    #ลบรายการที่ Sale_ID ซ้ำ
    df = df.drop_duplicates(subset=["Sale_ID"], keep="first").copy()

    #ทำความสะอาดข้อความสถานที่
    df["Store_Code"] = df["Store_Code"].str.strip().str.upper()
    df["Branch"] = df["Branch"].apply(clean_text)
    df["Province"] = df["Province"].apply(clean_text)
    df["Region"] = df["Region"].apply(lambda x: clean_text(x, default=""))

    # เติมค่า Region ที่ขาดหายไปโดยการอ้างอิงกับ Store_Code
    region_map = (
        df[df["Region"] != ""]
        .groupby("Store_Code")["Region"]
        .first()
        .to_dict()
    )
    df["Region"] = df["Store_Code"].map(region_map).fillna("Unknown")

    #ทำความสะอาดข้อความสินค้า
    df["Product_Name"] = df["Product_Name"].apply(clean_text)
    df["Category"] = df["Category"].apply(clean_text)

    #แปลงตัวเลขและวันที่
    df["Sale_Date_Clean"] = df["Sale_Date"].apply(parse_mixed_date)
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    df["Unit_Price"] = pd.to_numeric(df["Unit_Price"], errors="coerce").fillna(0.0)
    df["Discount_Percent"] = pd.to_numeric(df["Discount_Percent"], errors="coerce").fillna(0.0)

    # กรองข้อมูลที่ไม่สมบูรณ์หรือผิดปกติออก
    df = df.dropna(subset=["Sale_Date_Clean"]).copy()
    df = df[(df["Quantity"] > 0) & (df["Unit_Price"] >= 0)].copy()

    # Build Dimension 1: Dim_Location
    dim_location = (
        df[["Store_Code", "Branch", "Province", "Region"]]
        .drop_duplicates(subset=["Store_Code"])
        .sort_values("Store_Code")
        .reset_index(drop=True)
    )

    # Build Dimension 2: Dim_Product
    dim_product = (
        df[["Product_Name", "Category"]]
        .drop_duplicates(subset=["Product_Name"])
        .sort_values(["Category", "Product_Name"])
        .reset_index(drop=True)
    )
    dim_product.insert(0, "Product_ID", ["PROD-" + str(i + 1).zfill(3) for i in range(len(dim_product))])

    # Build Dimension 3: Dim_Date
    dim_date = (
        df[["Sale_Date_Clean"]]
        .drop_duplicates()
        .sort_values("Sale_Date_Clean")
        .reset_index(drop=True)
        .rename(columns={"Sale_Date_Clean": "Full_Date"})
    )
    dim_date["Date_ID"] = dim_date["Full_Date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["Year"] = dim_date["Full_Date"].dt.year
    dim_date["Quarter"] = dim_date["Full_Date"].dt.quarter
    dim_date["Month"] = dim_date["Full_Date"].dt.month
    dim_date["Month_Name"] = dim_date["Full_Date"].dt.strftime("%B")
    dim_date["Day"] = dim_date["Full_Date"].dt.day
    dim_date["Day_Of_Week"] = dim_date["Full_Date"].dt.strftime("%A")

    dim_date = dim_date[[
        "Date_ID", "Full_Date", "Year", "Quarter", "Month", "Month_Name", "Day", "Day_Of_Week"
    ]].copy()
    dim_date["Full_Date"] = dim_date["Full_Date"].dt.strftime("%Y-%m-%d")

    # Build Fact Table: Fact_Sales
    mapped = df.merge(
        dim_product[["Product_ID", "Product_Name"]],
        on="Product_Name",
        how="left"
    )
    mapped["Date_ID"] = mapped["Sale_Date_Clean"].dt.strftime("%Y%m%d").astype(int)

    # คำนวณยอดขายสุทธิ
    mapped["Total_Amount"] = mapped["Quantity"] * mapped["Unit_Price"] * (1.0 - (mapped["Discount_Percent"] / 100.0))
    mapped["Total_Amount"] = mapped["Total_Amount"].round(2)

    fact_sales = mapped[[
        "Sale_ID", "Date_ID", "Store_Code", "Product_ID",
        "Quantity", "Unit_Price", "Discount_Percent", "Total_Amount"
    ]].copy()

    print(f"[Transform] Locations: {len(dim_location)}, Products: {len(dim_product)}, Dates: {len(dim_date)}, Sales Facts: {len(fact_sales)}")
    return dim_location, dim_product, dim_date, fact_sales


def load(dim_location: pd.DataFrame, dim_product: pd.DataFrame, dim_date: pd.DataFrame, fact_sales: pd.DataFrame) -> None:
    """สร้าง Database Schema พร้อม Foreign Key Constraints แล้ว Load ข้อมูลลง SQLite"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript("""
        DROP TABLE IF EXISTS Fact_Sales;
        DROP TABLE IF EXISTS Dim_Location;
        DROP TABLE IF EXISTS Dim_Product;
        DROP TABLE IF EXISTS Dim_Date;

        CREATE TABLE Dim_Location (
            Store_Code TEXT PRIMARY KEY,
            Branch TEXT NOT NULL,
            Province TEXT NOT NULL,
            Region TEXT NOT NULL
        );

        CREATE TABLE Dim_Product (
            Product_ID TEXT PRIMARY KEY,
            Product_Name TEXT NOT NULL UNIQUE,
            Category TEXT NOT NULL
        );

        CREATE TABLE Dim_Date (
            Date_ID INTEGER PRIMARY KEY,
            Full_Date TEXT NOT NULL UNIQUE,
            Year INTEGER NOT NULL,
            Quarter INTEGER NOT NULL,
            Month INTEGER NOT NULL,
            Month_Name TEXT NOT NULL,
            Day INTEGER NOT NULL,
            Day_Of_Week TEXT NOT NULL
        );

        CREATE TABLE Fact_Sales (
            Sale_ID TEXT PRIMARY KEY,
            Date_ID INTEGER NOT NULL REFERENCES Dim_Date(Date_ID),
            Store_Code TEXT NOT NULL REFERENCES Dim_Location(Store_Code),
            Product_ID TEXT NOT NULL REFERENCES Dim_Product(Product_ID),
            Quantity INTEGER NOT NULL CHECK(Quantity > 0),
            Unit_Price REAL NOT NULL CHECK(Unit_Price >= 0),
            Discount_Percent REAL NOT NULL DEFAULT 0.0 CHECK(Discount_Percent >= 0 AND Discount_Percent <= 100),
            Total_Amount REAL NOT NULL CHECK(Total_Amount >= 0)
        );
        """)

        dim_location.to_sql("Dim_Location", conn, if_exists="append", index=False)
        dim_product.to_sql("Dim_Product", conn, if_exists="append", index=False)
        dim_date.to_sql("Dim_Date", conn, if_exists="append", index=False)
        fact_sales.to_sql("Fact_Sales", conn, if_exists="append", index=False)
        conn.commit()

    print(f"[Load] Successfully loaded into database at '{DB_PATH.name}'")


def verify() -> None:
    """รัน SQL Query ตรวจสอบยอดขายรวม 10 อันดับแรก"""
    sql = """
    SELECT
        l.Region,
        l.Branch,
        p.Category,
        p.Product_Name,
        SUM(f.Quantity) AS Total_Quantity,
        ROUND(SUM(f.Total_Amount), 2) AS Total_Sales_Baht
    FROM Fact_Sales f
    JOIN Dim_Location l ON f.Store_Code = l.Store_Code
    JOIN Dim_Product p ON f.Product_ID = p.Product_ID
    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
    GROUP BY l.Region, l.Branch, p.Category, p.Product_Name
    ORDER BY Total_Sales_Baht DESC
    LIMIT 10;
    """
    with sqlite3.connect(DB_PATH) as conn:
        result = pd.read_sql_query(sql, conn)
    print("\n[Verify] Top 10 Branch & Product Sales Summary:")
    print(result.to_string(index=False))


if __name__ == "__main__":
    raw_df = extract()
    dim_loc, dim_prod, dim_dt, fact = transform(raw_df)
    load(dim_loc, dim_prod, dim_dt, fact)
    verify()