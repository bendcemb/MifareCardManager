from smartcard.System import readers
from smartcard.util import toHexString
import csv
from datetime import datetime
import time

# ตั้งค่า
COOLDOWN_SECONDS = 10
last_tap_times = {}

def save_block1_to_csv(uid, block1_text):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = 'nfc_block1_log.csv'
    
    try:
        with open(filename, 'r') as f: has_header = True
    except FileNotFoundError: has_header = False

    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not has_header:
            writer.writerow(['Timestamp', 'Card_UID', 'Block_1_Data'])
        
        writer.writerow([timestamp, uid, block1_text])
    
    print(f"✅ [บันทึกสำเร็จ] UID: {uid} | Block1: {block1_text}")

def read_only_block1():
    r = readers()
    if len(r) == 0: return
    reader = r[0]

    while True:
        try:
            connection = reader.createConnection()
            connection.connect()

            # 1. อ่าน UID เพื่อระบุตัวตน
            GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(GET_UID)
            if sw1 != 0x90: continue
            
            uid = toHexString(data)
            curr_time = time.time()

            # เช็คหน่วงเวลาแตะซ้ำ
            if uid in last_tap_times and (curr_time - last_tap_times[uid] < COOLDOWN_SECONDS):
                time.sleep(0.5)
                continue

            # 2. เข้าถึง Block 1 (Sector 0)
            # Load Key A (FF FF FF FF FF FF)
            LOAD_KEY = [0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
            connection.transmit(LOAD_KEY)

            # Authenticate Block 1 (Sector 0 เริ่มที่ Block 0)
            AUTH = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00]
            _, sw1, sw2 = connection.transmit(AUTH)

            if sw1 == 0x90:
                # อ่านข้อมูล 16 Bytes จาก Block 1
                READ = [0xFF, 0xB0, 0x00, 0x01, 0x10]
                b_data, r_sw1, r_sw2 = connection.transmit(READ)
                
                if r_sw1 == 0x90:
                    # แปลงเป็น Text (กรองเฉพาะตัวอักษรที่อ่านออก)
                    text_data = "".join([chr(x) if 32 <= x <= 126 else "" for x in b_data]).strip()
                    
                    # ถ้า Block 1 ว่าง (เป็นค่า 0) ให้แสดงว่า <Empty>
                    if not text_data: text_data = "(Empty/Null)"
                    
                    # 3. บันทึกผล
                    save_block1_to_csv(uid, text_data)
                    last_tap_times[uid] = curr_time
                else:
                    print(f"❌ อ่าน Block 1 ไม่สำเร็จ (UID: {uid})")
            else:
                print(f"❌ Authenticate Block 1 ล้มเหลว")
            
            time.sleep(1)

        except Exception:
            # กรณีไม่มีบัตรวางอยู่
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        print("ระบบพร้อมบันทึก UID และ Block 1 ลง CSV ค่ะ...")
        read_only_block1()
    except KeyboardInterrupt:
        print("\nหยุดการทำงาน")