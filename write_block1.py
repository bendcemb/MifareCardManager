from smartcard.System import readers
from smartcard.util import toHexString

def write_nfc_block1():
    r = readers()
    if len(r) == 0: 
        print("ไม่พบเครื่องอ่านบัตรค่ะ")
        return
    
    reader = r[0]
    try:
        connection = reader.createConnection()
        connection.connect()

        # 1. Load Key A มาตรฐาน (FF FF FF FF FF FF)
        LOAD_KEY = [0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        connection.transmit(LOAD_KEY)

        # 2. Authenticate สำหรับ Block 1 (Sector 0)
        # เปลี่ยนตำแหน่งที่ 8 (Block Number) จาก 0x04 เป็น 0x01
        AUTH_BLOCK = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00]
        res, sw1, sw2 = connection.transmit(AUTH_BLOCK)

        if sw1 == 0x90:
            # 3. เตรียมข้อมูล 16 Bytes
            text_to_write = "EMP-69001" # เปลี่ยนข้อความได้ตามต้องการค่ะ
            data_bytes = [ord(c) for c in text_to_write]
            
            if len(data_bytes) > 16:
                print("⚠️ ข้อความยาวเกิน 16 ตัวอักษรค่ะ")
                return
                
            data_bytes += [0x00] * (16 - len(data_bytes)) 

            # 4. ส่งคำสั่ง Update Binary (Write) ไปยัง Block 1
            # เปลี่ยน P2 (ตำแหน่งที่ 4) จาก 0x04 เป็น 0x01
            WRITE_COMMAND = [0xFF, 0xD6, 0x00, 0x01, 0x10] + data_bytes
            res, sw1, sw2 = connection.transmit(WRITE_COMMAND)

            if sw1 == 0x90:
                print(f"✅ เขียนข้อมูล '{text_to_write}' ลง Block 1 สำเร็จแล้วค่ะ!")
            else:
                print(f"❌ เขียนไม่สำเร็จ: {sw1:02X} {sw2:02X}")
        else:
            print(f"❌ Authenticate Block 1 ล้มเหลว (SW1: {sw1:02X} SW2: {sw2:02X})")
            
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    write_nfc_block1()