from smartcard.System import readers
from smartcard.util import toHexString
import csv
from datetime import datetime
import time

COOLDOWN_SECONDS = 10
last_tap_times = {}

def save_data_only_to_csv(uid, data_blocks):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = 'nfc_data_only_row.csv'
    
    try:
        with open(filename, 'r') as f: has_header = True
    except FileNotFoundError: has_header = False

    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not has_header:
            # สร้าง Header เฉพาะเลข Block ที่เป็น Data
            # (ข้าม Block 0 เพราะเป็น Manufacturer และข้ามทุกๆ Block ที่เป็น Sector Trailer)
            data_headers = []
            for b in range(64):
                if (b + 1) % 4 != 0 and b != 0: # ไม่เอา Block 3, 7, 11... และไม่เอา 0
                    data_headers.append(f'Block_{b}')
            
            headers = ['Timestamp', 'Card_UID'] + data_headers
            writer.writerow(headers)
        
        row = [timestamp, uid] + data_blocks
        writer.writerow(row)
    
    print(f"✅ [Data Only] บันทึก UID: {uid} (เฉพาะ Data Blocks) เรียบร้อยค่ะ")

def read_data_only_single_line():
    r = readers()
    if len(r) == 0: return
    reader = r[0]

    while True:
        try:
            connection = reader.createConnection()
            connection.connect()

            GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(GET_UID)
            if sw1 != 0x90: continue
            
            uid = toHexString(data)
            curr_time = time.time()

            if uid in last_tap_times and (curr_time - last_tap_times[uid] < COOLDOWN_SECONDS):
                time.sleep(1)
                continue

            print(f"กำลังดึงเฉพาะ DATA จากบัตร {uid}...")
            only_data_blocks = []

            for sector in range(16):
                LOAD_KEY = [0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
                connection.transmit(LOAD_KEY)

                first_block = sector * 4
                AUTH = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, first_block, 0x60, 0x00]
                _, sw1, sw2 = connection.transmit(AUTH)

                if sw1 == 0x90:
                    for block in range(first_block, first_block + 4):
                        # --- เงื่อนไขกรองเฉพาะ DATA ---
                        # 1. ไม่เอา Block 0 (Manufacturer Data)
                        # 2. ไม่เอา Block ที่หารด้วย 4 แล้วเหลือเศษ 3 (Sector Trailer)
                        if block == 0 or (block + 1) % 4 == 0:
                            continue

                        READ = [0xFF, 0xB0, 0x00, block, 0x10]
                        b_data, r_sw1, r_sw2 = connection.transmit(READ)
                        
                        if r_sw1 == 0x90:
                            text_data = "".join([chr(x) if 32 <= x <= 126 else "" for x in b_data]).strip()
                            # ถ้าเป็นค่าว่างให้ใส่เครื่องหมาย - เพื่อให้ Column ไม่เลื่อน
                            only_data_blocks.append(text_data if text_data else "-")
                        else:
                            only_data_blocks.append("ERR")
                else:
                    # ถ้า Auth ไม่ผ่าน ให้ใส่ข้ามไป 3 data blocks
                    for _ in range(3): only_data_blocks.append("AUTH_FAILED")

            if only_data_blocks:
                save_data_only_to_csv(uid, only_data_blocks)
                last_tap_times[uid] = curr_time
                print("--- บันทึก Data สำเร็จค่ะ ---")
            
            time.sleep(2)

        except Exception:
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        print("เริ่มระบบอ่านเฉพาะ DATA (ข้าม System Blocks)...")
        read_data_only_single_line()
    except KeyboardInterrupt:
        print("\nหยุดการทำงาน")