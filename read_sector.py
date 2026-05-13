from smartcard.System import readers
from smartcard.util import toHexString
import time

def read_nfc_sector():
    r = readers()
    if len(r) == 0:
        print("ไม่พบเครื่องอ่านค่ะ")
        return

    reader = r[0]
    print(f"เชื่อมต่อ: {reader}")

    try:
        connection = reader.createConnection()
        connection.connect()

        # 1. Load Key (เก็บ Key ไว้ในเครื่องอ่าน - ใช้ Key A มาตรฐาน: FF FF FF FF FF FF)
        # CLA: FF, INS: 82, P1: 00 (Key Structure), P2: 00 (Key Slot), Lc: 06, Data: Key
        LOAD_KEY = [0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        res, sw1, sw2 = connection.transmit(LOAD_KEY)
        
        if sw1 == 0x90:
            print("1. Load Key สำเร็จ")
        else:
            print(f"Load Key ล้มเหลว: {sw1:02X} {sw2:02X}")
            return

        # 2. Authenticate Sector (ยืนยันตัวตนเพื่อเข้าถึง Block 4)
        # CLA: FF, INS: 86, P1: 00, P2: 00, Lc: 05, Data: [01, 00, Block#, KeyType, KeySlot]
        # KeyType 60 = Key A, 61 = Key B
        AUTH_BLOCK = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x04, 0x60, 0x00]
        res, sw1, sw2 = connection.transmit(AUTH_BLOCK)

        if sw1 == 0x90:
            print("2. Authenticate Block 4 สำเร็จ")
            
            # 3. Read Data (อ่านข้อมูล 16 bytes จาก Block 4)
            # CLA: FF, INS: B0, P1: 00, P2: Block#, Le: 10 (16 bytes)
            READ_BLOCK = [0xFF, 0xB0, 0x00, 0x04, 0x10]
            data, sw1, sw2 = connection.transmit(READ_BLOCK)
            
            if sw1 == 0x90:
                print(f"✅ ข้อมูลใน Block 4 (Hex): {toHexString(data)}")
                # แปลง Hex เป็นตัวอักษร (ถ้าข้อมูลที่เก็บเป็น Text)
                try:
                    text_data = "".join([chr(x) for x in data if 32 <= x <= 126])
                    print(f"✅ ข้อมูลใน Block 4 (Text): {text_data}")
                except:
                    pass
        else:
            print(f"Authenticate ล้มเหลว: {sw1:02X} {sw2:02X} (อาจใช้ Key ผิด หรือบัตรคนละประเภท)")

    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    read_nfc_sector()