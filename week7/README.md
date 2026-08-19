& "C:\Users\iszau\AppData\Local\Programs\Python\Python312\python.exe" -c "
content = '''# Retail Data Pipeline & Data Warehouse

โครงการประมวลผลข้อมูลการขายด้วย ETL Data Pipeline แบบ Batch Processing นำเข้าข้อมูลจากไฟล์ Excel เข้าสู่ฐานข้อมูล Data Warehouse (SQLite) พร้อมระบบ Data Validation และ Quarantine Management

---

## วิธีติดตั้ง (Installation)

1. **ตรวจสอบสภาพแวดล้อม:** ต้องมี Python เวอร์ชั่น 3.10 ขึ้นไป
2. **ติดตั้ง Dependencies:** เปิด Terminal แล้วรันคำสั่งติดตั้งคลังไลบรารีที่ต้องใช้:
   \`\`\`bash
   pip install pandas openpyxl
   \`\`\`
3. **เตรียมไฟล์ข้อมูล:** นำไฟล์ชุดข้อมูล \`Python_Data_Pipeline_Lab_Dataset.xlsx\` มาวางไว้ในโฟลเดอร์เดียวกับ \`pipeline.py\`

---

## วิธีรัน (Execution)

1. **สั่งรันโปรแกรม:** พิมพ์คำสั่งด้านล่างนี้ใน Terminal:
   \`\`\`bash
   python pipeline.py
   \`\`\`
2. **ตรวจสอบผลลัพธ์:** หลังประมวลผลสำเร็จ ระบบจะสร้างและส่งออกไฟล์ให้อัตโนมัติ:
   * **\`retail_dw.db\`**: ฐานข้อมูล SQLite ที่เก็บตาราง Star Schema
   * **\`quarantine.csv\`**: รายการข้อมูลที่ถูกปฏิเสธพร้อมระบุสาเหตุ (\`reason_code\`)
   * **\`pipeline_run_log.csv\`**: ประวัติบันทึกสถานะการรัน จำนวนแถวที่อ่าน ถูกต้อง ปฏิเสธ และนำเข้าจริง

---

## โครงสร้าง Star Schema

| ชื่อตาราง | ประเภท | คอลัมน์ / รายละเอียด |
| :--- | :--- | :--- |
| **\`fact_sales\`** | Fact Table | **\`order_id\`** (PK), **\`date_key\`** (FK), **\`customer_key\`** (FK), **\`product_key\`** (FK), \`quantity\`, \`unit_price\`, \`discount_pct\`, \`gross_amount\`, \`net_amount\`, \`payment_method\`, \`sales_channel\`, \`updated_at\` |
| **\`dim_customer\`** | Dimension | **\`customer_key\`** (PK), \`customer_id\` (Unique), \`customer_name\`, \`province\`, \`segment\` |
| **\`dim_product\`** | Dimension | **\`product_key\`** (PK), \`product_id\` (Unique), \`product_name\`, \`category\` |
| **\`dim_date\`** | Dimension | **\`date_key\`** (PK YYYYMMDD), \`full_date\`, \`day\`, \`month\`, \`quarter\`, \`year\` |
| **\`quarantine\`** | Audit Table | **\`quarantine_id\`** (PK), \`order_id\`, \`customer_id\`, \`product_id\`, \`reason_code\`, \`source_batch\` |
| **\`pipeline_run_log\`** | Log Table | **\`run_id\`** (PK), \`batch_name\`, \`started_at\`, \`ended_at\`, \`rows_read\`, \`rows_valid\`, \`rows_rejected\`, \`rows_loaded\`, \`status\` |

---

## เหตุใด Availability จึงมักสำคัญกว่า Strictness ใน Production Pipeline 

ในระบบ Production Data Pipeline จริง Availability มักสำคัญกว่า Strictness เนื่องจากธุรกิจต้องการความสดใหม่ของข้อมูล (Data Freshness) ในการตัดสินใจและรัน Dashboard หากใช้แนวทาง Strictness ที่สั่งให้กระบวนการทั้งหมดล้มเหลว (Crash) เพียงเพราะเจอข้อมูลผิดปกติ 1 แถว จะทำให้ระบบ downstream ทั้งหมดหยุดชะงักและเกิดความเสียหายทางธุรกิจ การออกแบบ Pipeline ให้เน้น Availability ผ่านแนวคิด Quarantine Pattern ช่วยให้ข้อมูลที่ดี (Valid Data) ไหลเข้า Data Warehouse เพื่อให้ธุรกิจใช้งานต่อได้ทันที ในขณะที่ข้อมูลผิดปกติจะถูกคัดแยกไว้อย่างเป็นระเบียบโดยไม่ขัดขวางกระบวนการหลัก ซึ่งช่วยรักษาสภาพระบบให้ทำงานได้อย่างต่อเนื่องและยังมี Audit Trail ให้วิศวกรตามแก้ไขข้อมูลย้อนหลังได้ง่ายอีกด้วย
'''
open('README.md', 'w', encoding='utf-8').write(content)
print('Created README.md successfully!')
"