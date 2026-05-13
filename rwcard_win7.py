import customtkinter as ctk
from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import NoCardException, CardConnectionException
import threading
import csv
from datetime import datetime
import time
from tkinter import messagebox
import os

# --- แก้ไขปัญหาหน้าจอเบลอ หรือ Scaling เพี้ยนบน Windows 7 ---
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

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
        self.geometry("600x600")
        
        self.last_uid = None
        self.is_monitoring = False

        # --- UI Layout ---
        self.tabview = ctk.CTkTabview(self, width=580, height=480)
        self.tabview.pack(padx=10, pady=(10, 5))
        
        self.tab_read = self.tabview.add("Read & Auto-Log")
        self.tab_write = self.tabview.add("Write Card")

        self.setup_read_tab()
        self.setup_write_tab()
        self.setup_footer()

    def setup_read_tab(self):
        # ใช้ Tahoma เพราะ Windows 7 ทุกเครื่องมี และอ่านง่ายค่ะ
        self.lbl_read = ctk.CTkLabel(self.tab_read, text="ระบบบันทึกการแตะบัตรอัตโนมัติ", font=("Tahoma", 18, "bold"))
        self.lbl_read.pack(pady=10)

        self.btn_monitor = ctk.CTkButton(self.tab_read, text="เริ่มระบบ Scan", fg_color="green", command=self.toggle_monitoring, font=("Tahoma", 14))
        self.btn_monitor.pack(pady=10)

        self.read_status = ctk.CTkLabel(self.tab_read, text="สถานะ: ปิดอยู่", text_color="gray", font=("Tahoma", 12))
        self.read_status.pack()

        self.read_log = ctk.CTkTextbox(self.tab_read, width=500, height=220, font=("Consolas", 12))
        self.read_log.pack(pady=10)

    def validate_numbers(self, P):
        if P == "" or P.isdigit():
            return True
        return False

    def setup_write_tab(self):
        self.lbl_write = ctk.CTkLabel(self.tab_write, text="เขียนข้อมูลลง Block 1 (ตัวเลขเท่านั้น)", font=("Tahoma", 18, "bold"))
        self.lbl_write.pack(pady=10)

        vcmd = (self.register(self.validate_numbers), '%P')
        self.entry_write = ctk.CTkEntry(
            self.tab_write, 
            placeholder_text="กรอกรหัสพนักงาน (0-9)", 
            width=300,
            validate="key",
            validatecommand=vcmd,
            font=("Tahoma", 14)
        )
        self.entry_write.pack(pady=10)

        self.btn_write = ctk.CTkButton(self.tab_write, text="เขียนลงบัตร", command=self.start_write_thread, font=("Tahoma", 14))
        self.btn_write.pack(pady=10)

        self.write_log = ctk.CTkTextbox(self.tab_write, width=500, height=150, font=("Consolas", 12))
        self.write_log.pack(pady=10)

    def setup_footer(self):
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=20, pady=10)

        dev_info = f"Developed by: {self.DEVELOPER} | {self.COMPANY}"
        lbl_dev = ctk.CTkLabel(footer_frame, text=dev_info, font=("Arial", 10), text_color="gray")
        lbl_dev.pack(side="left")

        btn_info = ctk.CTkButton(footer_frame, text=f"Info {self.APP_VERSION}", 
                                 width=80, height=20, font=("Arial", 10),
                                 command=self.show_about_info)
        btn_info.pack(side="right")

    def show_about_info(self):
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

    def toggle_monitoring(self):
        if not self.is_monitoring:
            self.is_monitoring = True
            self.btn_monitor.configure(text="หยุดระบบ Scan", fg_color="red")
            self.read_status.configure(text="สถานะ: กำลังรอการแตะบัตร...", text_color="orange")
            threading.Thread(target=self.monitor_loop, daemon=True).start()
        else:
            self.is_monitoring = False
            self.btn_monitor.configure(text="เริ่มระบบ Scan", fg_color="green")
            self.read_status.configure(text="สถานะ: ปิดอยู่", text_color="gray")

    def monitor_loop(self):
        while self.is_monitoring:
            try:
                available_readers = readers()
                if len(available_readers) > 0:
                    reader = available_readers[0]
                    conn = reader.createConnection()
                    conn.connect()
                    
                    # Get UID
                    uid_data, sw1, sw2 = conn.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                    uid = toHexString(uid_data)

                    if uid != self.last_uid:
                        # Authenticate and Read Block 1
                        conn.transmit([0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
                        conn.transmit([0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00])
                        b_data, s1, s2 = conn.transmit([0xFF, 0xB0, 0x00, 0x01, 0x10])
                        
                        b_text = "".join([chr(x) if 32 <= x <= 126 else "" for x in b_data]).strip()
                        self.log_to_csv(uid, b_text)
                        self.last_uid = uid
                else:
                    self.last_uid = None
                    self.read_status.configure(text="สถานะ: ไม่พบเครื่องอ่านบัตร", text_color="red")
            except Exception:
                self.last_uid = None
            time.sleep(0.5)

    def log_to_csv(self, uid, data):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open('nfc_log.csv', 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([ts, uid, data])
            self.read_log.insert("0.0", f"[{ts}] UID: {uid} | Data: {data}\n")
        except Exception as e:
            print(f"CSV Log Error: {e}")

    def start_write_thread(self):
        data = self.entry_write.get()
        if not data: 
            messagebox.showwarning("Warning", "กรุณากรอกข้อมูลก่อนเขียนค่ะ")
            return
        self.btn_write.configure(state="disabled")
        threading.Thread(target=self.write_card, args=(data,), daemon=True).start()

    def write_card(self, text):
        try:
            r = readers()
            if len(r) == 0: 
                self.write_log.insert("0.0", "❌ ไม่พบเครื่องอ่านบัตร\n")
                return
            
            conn = r[0].createConnection()
            conn.connect()
            
            # Load Key & Authenticate Block 1
            conn.transmit([0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
            res, sw1, sw2 = conn.transmit([0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00])
            
            if sw1 == 0x90:
                payload = [ord(c) for c in text[:16]]
                payload += [0x00] * (16 - len(payload))
                res, w1, w2 = conn.transmit([0xFF, 0xD6, 0x00, 0x01, 0x10] + payload)
                
                if w1 == 0x90:
                    self.write_log.insert("0.0", f"✅ เขียนสำเร็จ: {text}\n")
                else:
                    self.write_log.insert("0.0", f"❌ เขียนล้มเหลว (w1={hex(w1)})\n")
            else:
                self.write_log.insert("0.0", f"❌ บัตรไม่รองรับ/Key ผิด\n")
        except Exception as e:
            self.write_log.insert("0.0", f"⚠️ Error: {str(e)}\n")
        finally:
            self.btn_write.configure(state="normal")

if __name__ == "__main__":
    app = NFCManagerApp()
    # ปรับ Scaling สำหรับหน้าจอความละเอียดต่ำใน Win 7
    app.tk.call('tk', 'scaling', 1.25)
    app.mainloop()