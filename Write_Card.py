import customtkinter as ctk
from smartcard.System import readers
from smartcard.util import toHexString
import threading
import csv
from datetime import datetime
import time
from tkinter import messagebox
import os

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class NFCManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- APP CONFIGURATION ---
        self.APP_VERSION = "v1.2.0"
        self.DEVELOPER = "Bendcemb Software Team"
        self.COMPANY = "bCloud Co., Ltd."
        self.LICENCE = "Commercial Licence (Proprietary)"
        self.CONTACT = "bendcemb@gmail.com"

        self.title(f"NFC Employee Manager - {self.APP_VERSION}")
        self.geometry("600x680")
        
        self.last_uid = None
        self.is_monitoring = True

        # --- UI Layout ---
        self.frame_read = ctk.CTkFrame(self)
        self.frame_read.pack(fill="x", padx=10, pady=(10, 5))

        self.frame_write = ctk.CTkFrame(self)
        self.frame_write.pack(fill="x", padx=10, pady=5)

        self.setup_read_tab(self.frame_read)
        self.setup_write_tab(self.frame_write)
        self.setup_footer() # เพิ่มส่วน Footer ข้อมูลผู้พัฒนา

        # เริ่มสแกนอัตโนมัติทันทีที่เปิดแอป
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def setup_read_tab(self, parent):
        self.lbl_read = ctk.CTkLabel(parent, text="ระบบบันทึกการแตะบัตรอัตโนมัติ", font=("TH Sarabun New", 20, "bold"))
        self.lbl_read.pack(pady=5)

        self.read_status = ctk.CTkLabel(parent, text="สถานะ: กำลังรอการแตะบัตร...", text_color="orange")
        self.read_status.pack(pady=5)

        self.read_log = ctk.CTkTextbox(parent, width=540, height=140)
        self.read_log.pack(pady=5)

    def validate_numbers(self, P):
        if P == "" or P.isdigit():
            return True
        return False

    def setup_write_tab(self, parent):
        self.lbl_write = ctk.CTkLabel(parent, text="เขียนข้อมูล Card ID (ตัวเลขเท่านั้น)", font=("TH Sarabun New", 20, "bold"))
        self.lbl_write.pack(pady=5)

        vcmd = (self.register(self.validate_numbers), '%P')
        self.entry_write = ctk.CTkEntry(
            parent, 
            placeholder_text="กรอกรหัสพนักงาน (0-9)", 
            width=300,
            validate="key",
            validatecommand=vcmd
        )
        self.entry_write.pack(pady=5)

        self.btn_write = ctk.CTkButton(parent, text="เขียนลงบัตร", command=self.start_write_thread)
        self.btn_write.pack(pady=5)

        self.check_var = ctk.BooleanVar(value=True)
        self.checkbox_save = ctk.CTkCheckBox(parent, text="บันทึกลงไฟล์ CSV เมื่อเขียนสำเร็จ", variable=self.check_var)
        self.checkbox_save.pack(pady=5)

        self.write_log = ctk.CTkTextbox(parent, width=540, height=100)
        self.write_log.pack(pady=5)

    def setup_footer(self):
        """ส่วนแสดงข้อมูลผู้พัฒนาและ Licence ด้านล่างแอป"""
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=20, pady=10)

        # ข้อมูลฝั่งซ้าย
        dev_info = f"Developed by: {self.DEVELOPER} | {self.COMPANY}"
        lbl_dev = ctk.CTkLabel(footer_frame, text=dev_info, font=("Arial", 11), text_color="gray")
        lbl_dev.pack(side="left")

        # ข้อมูลฝั่งขวา (Version & Info Button)
        btn_info = ctk.CTkButton(footer_frame, text=f"Info {self.APP_VERSION}", 
                                 width=80, height=20, font=("Arial", 10),
                                 command=self.show_about_info)
        btn_info.pack(side="right")

    def show_about_info(self):
        """แสดงหน้าต่าง Pop-up ข้อมูลลิขสิทธิ์และการติดต่อ"""
        about_text = (
            f"Software: NFC Employee Manager\n"
            f"Version: {self.APP_VERSION}\n\n"
            f"Developer: {self.DEVELOPER}\n"
            f"Company: {self.COMPANY}\n"
            f"Licence: {self.LICENCE}\n"
            f"Contact: {self.CONTACT}\n\n"
            f"© 2026 {self.COMPANY}. All Rights Reserved."
        )
        messagebox.showinfo("About Application", about_text)

    def hex_to_decimal_serial(self, uid_hex_str):
        try:
            # 1. กำจัดช่องว่างที่อาจติดมา เช่น "97 28 7A 4A" -> "97287A4A"
            clean_hex = uid_hex_str.replace(" ", "")
            
            # 2. หั่นทีละ 2 ตัวอักษรเพื่อทำเป็น List ของ Bytes
            bytes_list = [clean_hex[i:i+2] for i in range(0, len(clean_hex), 2)]
            
            # 3. สลับลำดับจากหลังมาหน้า (Little-Endian)
            bytes_list.reverse()
            
            # 4. ประกอบกลับเป็น String แล้วแปลงเป็นเลขฐาน 10
            reversed_hex = "".join(bytes_list)
            decimal_val = int(reversed_hex, 16)
            
            # 5. คืนค่าเป็น String 10 หลัก (เติม 0 ข้างหน้าถ้าไม่ถึง)
            return f"{decimal_val:010d}"
        except Exception as e:
            print(f"Conversion Error: {e}")
            return "Error"
        
    # --- Logic ส่วนอื่นๆ (Read/Write) ---
    def monitor_loop(self):
        while self.is_monitoring:
            try:
                r = readers()
                if len(r) > 0:
                    reader = r[0]
                    conn = reader.createConnection()
                    conn.connect()
                    uid_data, sw1, sw2 = conn.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                    uid_hex = toHexString(uid_data) # ได้ค่าเช่น 97 28 7A 4A
                    
                    if uid_hex != self.last_uid:
                        # คำนวณ Serial 10 หลัก
                        serial_dec = self.hex_to_decimal_serial(uid_hex)
                        
                        # อ่าน Data ใน Block 1 (Card ID)
                        conn.transmit([0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
                        conn.transmit([0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00])
                        b_data, s1, s2 = conn.transmit([0xFF, 0xB0, 0x00, 0x01, 0x10])
                        b_text = "".join([chr(x) if 32 <= x <= 126 else "" for x in b_data]).strip()
                        
                        ts = datetime.now().strftime('%H:%M:%S')
                        log_msg = f"[{ts}] HEX: {uid_hex} | SN: {serial_dec} | Card ID: {b_text}\n"
                        
                        self.read_log.insert("0.0", log_msg)
                        self.entry_write.delete(0, "end")
                        self.entry_write.insert(0, b_text)

                        self.last_uid = uid_hex
                else:
                    self.last_uid = None
            except:
                self.last_uid = None
            time.sleep(0.5)

    
    def log_to_csv(self, uid, serial_dec, card_id):
        now = datetime.now()
        ts = now.strftime('%Y-%m-%d %H:%M:%S')
        date_str = now.strftime('%Y-%m-%d')
        filename = f'write_card_{date_str}.csv'
        
        file_exists = os.path.isfile(filename)
        
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "UID", "Serial Number", "Card ID"])
            writer.writerow([ts, uid, serial_dec, card_id])

    def start_write_thread(self):
        data = self.entry_write.get()
        if not data: return
        self.btn_write.configure(state="disabled")
        threading.Thread(target=self.write_card, args=(data,), daemon=True).start()

    def write_card(self, text):
        try:
            r = readers()
            if len(r) == 0: return
            conn = r[0].createConnection()
            conn.connect()
            
            uid_data, u_sw1, u_sw2 = conn.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
            uid_hex = toHexString(uid_data)
            serial_dec = self.hex_to_decimal_serial(uid_hex)

            conn.transmit([0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
            res, sw1, sw2 = conn.transmit([0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00])
            
            if sw1 == 0x90:
                payload = [ord(c) for c in text[:16]]
                payload += [0x00] * (16 - len(payload))
                res, w1, w2 = conn.transmit([0xFF, 0xD6, 0x00, 0x01, 0x10] + payload)
                
                if w1 == 0x90:
                    log_entry = f"✅ เขียนสำเร็จ | UID: {uid_hex} | SN: {serial_dec} | Card ID: {text}\n"
                    self.write_log.insert("0.0", log_entry)
                    if self.check_var.get():
                        # แก้ไขให้บันทึก Serial ลงใน CSV/DB ด้วย
                        self.log_to_csv(uid_hex, serial_dec, text)      
                else:
                    self.write_log.insert("0.0", f"❌ เขียนล้มเหลว | UID: {uid_hex} | SN: {serial_dec}\n")
            else:
                self.write_log.insert("0.0", f"❌ บัตรไม่รองรับ/Key ผิด\n")
        except Exception as e:
            self.write_log.insert("0.0", f"⚠️ Error: {str(e)}\n")
        finally:
            self.btn_write.configure(state="normal")


if __name__ == "__main__":
    app = NFCManagerApp()
    app.mainloop()