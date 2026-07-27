import pandas as pd
import sqlite3

#โหลดข้อมูล
df_raw = pd.read_csv('raw_ecommerce_data.csv')

#Data Cleaning & Transformation

#ลบข้อมูลแถวที่ซ้ำกันออกก่อน
df_raw = df_raw.drop_duplicates()

# 2.2 จัดการข้อความ (ตัดช่องว่าง + ปรับเป็น Title Case / Lower Case)
df_raw['Customer_Name'] = df_raw['Customer_Name'].fillna('Unknown').astype(str).str.strip().str.title()
df_raw['Email'] = df_raw['Email'].fillna('N/A').astype(str).str.strip().str.lower()
df_raw['Product'] = df_raw['Product'].fillna('Unknown').astype(str).str.strip().str.title()
df_raw['Category'] = df_raw['Category'].fillna('Uncategorized').astype(str).str.strip().str.title()

#คลีนคอลัมน์ตัวเลข (ลบ ฿ และ , ออก แล้วแปลงเป็น float)
def clean_numeric(series):
    return series.astype(str).str.replace('฿', '', regex=False).str.replace(',', '', regex=False).str.strip().astype(float)

df_raw['Unit_Price'] = clean_numeric(df_raw['Unit_Price'])

#คำนวณ Amount ใหม่ทั้งหมดเพื่อแก้ปัญหาค่าว่าง
df_raw['Amount'] = df_raw['Quantity'] * df_raw['Unit_Price']

#แปลงวันที่ให้เป็น Format เดียวกัน
df_raw['Order_Date'] = pd.to_datetime(df_raw['Order_Date'], format='mixed')


#สร้าง Dimension Tables & Fact Table


# --- dim_customer ---
dim_customer = df_raw[['Customer_Name', 'Email']].drop_duplicates().reset_index(drop=True)
dim_customer['customer_id'] = dim_customer.index + 1
dim_customer = dim_customer[['customer_id', 'Customer_Name', 'Email']]

# --- dim_product ---
dim_product = df_raw[['Product', 'Category']].drop_duplicates().reset_index(drop=True)
dim_product['product_id'] = dim_product.index + 1
dim_product = dim_product[['product_id', 'Product', 'Category']]

# --- fact_sales ---
fact_sales = pd.merge(df_raw, dim_customer, on=['Customer_Name', 'Email'], how='left')
fact_sales = pd.merge(fact_sales, dim_product, on=['Product', 'Category'], how='left')

# จัดโครงสร้างตาราง fact_sales
fact_sales['transaction_id'] = range(1, len(fact_sales) + 1)
fact_sales = fact_sales.rename(columns={'Amount': 'amount'})
fact_sales = fact_sales[['transaction_id', 'customer_id', 'product_id', 'amount']]


#Database Setup & Load Into SQLite

conn = sqlite3.connect('warehouse.db')
cursor = conn.cursor()

#เปิดใช้งาน Foreign Key Constraints
cursor.execute('PRAGMA foreign_keys = ON;')

#จุดที่แก้ไขไป ลบตารางเก่าทิ้งก่อน (ถ้ามี) เพื่อป้องกัน UNIQUE Constraint Error เวลารันซ้ำ
cursor.execute('DROP TABLE IF EXISTS fact_sales;')
cursor.execute('DROP TABLE IF EXISTS dim_customer;')
cursor.execute('DROP TABLE IF EXISTS dim_product;')

#สร้างตาราง dim_customer
cursor.execute('''
    CREATE TABLE dim_customer (
        customer_id INTEGER PRIMARY KEY,
        Customer_Name TEXT,
        Email TEXT
    )
''')

#สร้างตาราง dim_product
cursor.execute('''
    CREATE TABLE dim_product (
        product_id INTEGER PRIMARY KEY,
        Product TEXT,
        Category TEXT
    )
''')

# สร้างตาราง fact_sales
cursor.execute('''
    CREATE TABLE fact_sales (
        transaction_id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        product_id INTEGER,
        amount REAL,
        FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
        FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
    )
''')
conn.commit()

# โหลดข้อมูลลง SQLite
dim_customer.to_sql('dim_customer', con=conn, if_exists='append', index=False)
dim_product.to_sql('dim_product', con=conn, if_exists='append', index=False)
fact_sales.to_sql('fact_sales', con=conn, if_exists='append', index=False)

print('ETL Pipeline ran successfully!')


#Query Data (Top 3 Spenders)

#รัน Query ดึงข้อมูล
query = '''
SELECT
    c.Customer_Name,
    SUM(f.amount) as Total_Spend
FROM fact_sales f
JOIN dim_customer c ON f.customer_id = c.customer_id
GROUP BY c.Customer_Name
ORDER BY Total_Spend DESC
LIMIT 3;
'''

df_top_customers = pd.read_sql(query, conn)

#จัดฟอร์แมตตัวเลขให้มีลูกน้ำและทศนิยม 2 ตำแหน่ง
df_top_customers['Total_Spend'] = df_top_customers['Total_Spend'].map('{:,.2f}'.format)

#แสดงผลตารางแบบในรูปภาพ
print(df_top_customers.to_markdown(index=False))

# ปิดการเชื่อมต่อ DB
conn.close()
