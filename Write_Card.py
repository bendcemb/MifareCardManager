import customtkinter as ctk
from smartcard.System import readers
from smartcard.util import toHexString
import threading
import csv
import re
import sqlite3
import sys
from datetime import datetime
import time
from tkinter import messagebox, filedialog
import os

import tkinter as tk
from tkinter import ttk
import webbrowser

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class NFCManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- APP CONFIGURATION ---
        self.APP_VERSION = "v1.3.0"
        self.DEVELOPER = "Bendcemb Software Team"
        self.COMPANY = "bCloud Co., Ltd."
        self.LICENCE = "Commercial Licence (Proprietary)"
        self.PHONE = "091-825-3266"
        self.CONTACT = "bendcemb@gmail.com"

        self.title(f"Mifare Card Manager - {self.APP_VERSION}")
        self.geometry("1240x740")
        
        self.last_uid = None
        self.is_monitoring = True

        # กำหนดพาธฐานข้อมูลให้อยู่ข้างไฟล์ .exe หรือ .py เสมอ
        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.db_map = {}  # เก็บคู่ ชื่อที่แสดง -> พาธไฟล์ .db
        self.db_path = os.path.join(self.base_dir, "card_history.db")
        self.ensure_default_databases()
        self.init_db()

        # --- UI Layout ---
        # 1. ส่วน Footer ล่างสุด
        self.setup_footer()

        # 2. Block สำหรับปุ่มทั้งแถบล่างสุด (เต็มความกว้างหน้าจอ)
        self.frame_bottom_buttons = ctk.CTkFrame(self)
        self.frame_bottom_buttons.pack(side="bottom", fill="x", padx=10, pady=(6, 4))

        # 3. พื้นที่หลักด้านบน (แบ่ง ซ้าย: เลือกฐานข้อมูลบนซ้าย + ตารางประวัติ | ขวา: กล่องแสดงสถานะบนขวา + กล่องแสดงแจ้งผลงาน)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        # ฝั่งซ้าย: ด้านบนเป็นแถบเลือกฐานข้อมูล และด้านล่างเป็นตารางประวัติเลขการ์ดที่เขียนไปแล้ว
        self.left_panel = ctk.CTkFrame(self.main_container, fg_color="transparent", width=560)
        self.left_panel.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=0)

        self.frame_db_top = ctk.CTkFrame(self.left_panel)
        self.frame_db_top.pack(fill="x", pady=(0, 8))

        self.frame_history = ctk.CTkFrame(self.left_panel)
        self.frame_history.pack(fill="both", expand=True, pady=(0, 0))

        # ฝั่งขวา: กล่องแสดงสถานะ (รวมสถานะอ่านบัตร + เลขล่าสุด + แจ้งผลการเขียนไว้ในกล่องเดียว)
        self.right_panel = ctk.CTkFrame(self.main_container, fg_color="transparent", width=640)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(6, 0), pady=0)

        self.frame_read = ctk.CTkFrame(self.right_panel)
        self.frame_read.pack(fill="both", expand=True, pady=(0, 0))

        # เปิดใช้งานรันเลขถัดไปอัตโนมัติและบันทึก CSV ในพื้นหลังโดยไม่ต้องแสดง Checkbox
        self.auto_next_var = ctk.BooleanVar(value=True)
        self.check_var = ctk.BooleanVar(value=True)
        self.is_blank_card_ready = False

        self.setup_db_top_box(self.frame_db_top)
        self.setup_history_panel(self.frame_history)
        self.setup_status_box(self.frame_read)
        self.setup_bottom_button_block(self.frame_bottom_buttons)

        # โหลดตารางประวัติและเลขล่าสุดจากฐานข้อมูล พร้อมตั้งเลขถัดไปให้อัตโนมัติ
        self.refresh_last_card_info(auto_fill_next=True)

        # เริ่มสแกนอัตโนมัติทันทีที่เปิดแอป
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    # --- DATABASE METHODS (SQLite) ---
    def init_db(self, target_path=None):
        """สร้างตารางเก็บประวัติการเขียนบัตรใน SQLite"""
        db_file = target_path or self.db_path
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS card_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    serial_number TEXT NOT NULL,
                    card_id TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_card_id ON card_history(card_id)")
            conn.commit()

    def ensure_default_databases(self):
        """สร้างฐานข้อมูลหลัก (card_history.db) และฐานข้อมูลทดสอบ (test.db) พร้อมข้อมูลตัวอย่าง"""
        prod_db = os.path.join(self.base_dir, "card_history.db")
        test_db = os.path.join(self.base_dir, "test.db")

        self.init_db(prod_db)
        self.init_db(test_db)

        # ถ้า test.db ยังว่างอยู่ ให้ใส่ข้อมูลตัวอย่างไว้ทดสอบการเลือกและรันเลขต่อทันที
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM card_history")
            count = cursor.fetchone()[0]
            if count == 0:
                sample_rows = [
                    ("2026-11-11 09:00:12", "97 28 7A 4A", "1249523863", "69001"),
                    ("2026-11-11 09:05:44", "A3 14 8B 2C", "0747312291", "69002"),
                    ("2026-11-11 09:12:18", "B1 55 9C 3D", "1033655729", "69003"),
                    ("2026-11-11 09:20:05", "C4 89 1E 5F", "1595877828", "69004"),
                    ("2026-11-11 09:30:50", "D8 32 4F 7A", "2052010712", "69005"),
                ]
                cursor.executemany(
                    "INSERT INTO card_history (created_at, uid, serial_number, card_id) VALUES (?, ?, ?, ?)",
                    sample_rows
                )
                conn.commit()

        # ถ้าอยู่ระหว่างพัฒนา (.py) ให้คัดลอก test.db ไปไว้ในโฟลเดอร์ dist ด้วย (ถ้ามี)
        dist_dir = os.path.join(self.base_dir, "dist")
        if os.path.isdir(dist_dir):
            dist_test_db = os.path.join(dist_dir, "test.db")
            self.init_db(dist_test_db)
            with sqlite3.connect(dist_test_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM card_history")
                if cursor.fetchone()[0] == 0:
                    cursor.executemany(
                        "INSERT INTO card_history (created_at, uid, serial_number, card_id) VALUES (?, ?, ?, ?)",
                        [
                            ("2026-11-11 09:00:12", "97 28 7A 4A", "1249523863", "69001"),
                            ("2026-11-11 09:05:44", "A3 14 8B 2C", "0747312291", "69002"),
                            ("2026-11-11 09:12:18", "B1 55 9C 3D", "1033655729", "69003"),
                            ("2026-11-11 09:20:05", "C4 89 1E 5F", "1595877828", "69004"),
                            ("2026-11-11 09:30:50", "D8 32 4F 7A", "2052010712", "69005"),
                        ]
                    )
                    conn.commit()

    def get_available_databases(self):
        """ค้นหาไฟล์ .db ทั้งหมดในโฟลเดอร์โปรแกรมเพื่อแสดงในปุ่มเลือกฐานข้อมูล"""
        self.db_map.clear()
        priority_files = ["card_history.db", "test.db"]
        for fname in priority_files:
            fpath = os.path.join(self.base_dir, fname)
            if os.path.isfile(fpath):
                label = f"{fname} (ใช้งานจริง)" if fname == "card_history.db" else f"{fname} (สำหรับทดสอบ)"
                self.db_map[label] = fpath

        for fname in sorted(os.listdir(self.base_dir)):
            if fname.lower().endswith((".db", ".sqlite", ".sqlite3")) and fname not in priority_files:
                fpath = os.path.join(self.base_dir, fname)
                if os.path.isfile(fpath):
                    self.db_map[fname] = fpath

        # หากผู้ใช้เลือกไฟล์จากโฟลเดอร์อื่นไว้ ให้คงไว้ในรายการด้วย
        if self.db_path and os.path.abspath(self.db_path) not in [os.path.abspath(p) for p in self.db_map.values()]:
            custom_label = f"{os.path.basename(self.db_path)} (ภายนอก)"
            self.db_map[custom_label] = self.db_path

        return list(self.db_map.keys())

    def get_label_for_db_path(self, target_path):
        target_abs = os.path.abspath(target_path)
        for label, path in self.db_map.items():
            if os.path.abspath(path) == target_abs:
                return label
        return os.path.basename(target_path)

    def clear_status_box(self):
        """ล้างข้อความในกล่องแสดงสถานะและรีเซ็ตสถานะการอ่านบัตร"""
        if hasattr(self, "read_log"):
            self.read_log.delete("0.0", "end")
        if hasattr(self, "read_status"):
            self.read_status.configure(
                text="สถานะ: กำลังรอการแตะบัตร...",
                text_color="orange"
            )
        self.last_uid = None
        self.set_write_button_ready(False)

    def _activate_database(self, db_path, refresh_options=False):
        """ตั้งค่าฐานข้อมูลที่เลือก ล้างกล่องสถานะ และโหลดข้อมูลล่าสุด"""
        self.db_path = db_path
        self.init_db(self.db_path)
        if refresh_options and hasattr(self, "db_option_menu"):
            options = self.get_available_databases()
            self.db_option_menu.configure(values=options)
            self.db_option_var.set(self.get_label_for_db_path(self.db_path))
        self.clear_status_box()
        self.update_db_indicator()
        self.refresh_last_card_info(auto_fill_next=True)

    def switch_database(self, selected_label):
        """สลับฐานข้อมูลเมื่อเลือกจากเมนู Dropdown"""
        if selected_label in self.db_map:
            self._activate_database(self.db_map[selected_label])

    def browse_database_file(self):
        """ปุ่มเลือกไฟล์ฐานข้อมูล (.db) จากเครื่อง"""
        file_path = filedialog.askopenfilename(
            title="เลือกไฟล์ฐานข้อมูล SQLite",
            initialdir=self.base_dir,
            filetypes=[("SQLite Database", "*.db *.sqlite *.sqlite3"), ("All Files", "*.*")]
        )
        if file_path:
            self._activate_database(file_path, refresh_options=True)

    def create_new_database(self):
        """ปุ่มสร้างไฟล์ฐานข้อมูลใหม่"""
        dialog = ctk.CTkInputDialog(
            text="กรอกชื่อฐานข้อมูลใหม่ (เช่น branch2 หรือ test2):",
            title="สร้างฐานข้อมูลใหม่"
        )
        db_name = dialog.get_input()
        if not db_name or not db_name.strip():
            return
        db_name = db_name.strip()
        if not db_name.lower().endswith(".db"):
            db_name += ".db"
        new_path = os.path.join(self.base_dir, db_name)
        self._activate_database(new_path, refresh_options=True)

    def update_db_indicator(self):
        """อัปเดตสีและข้อความแจ้งเตือนฐานข้อมูลที่กำลังใช้งาน"""
        db_filename = os.path.basename(self.db_path)
        if hasattr(self, "lbl_active_db"):
            if db_filename.lower() == "test.db":
                self.lbl_active_db.configure(
                    text=f"🧪 กำลังใช้ฐานข้อมูลทดสอบ: {db_filename}",
                    text_color="#E67E22"
                )
            else:
                self.lbl_active_db.configure(
                    text=f"🗄️ ฐานข้อมูลปัจจุบัน: {db_filename}",
                    text_color="#2FA572"
                )

    def save_to_db(self, ts, uid, serial_dec, card_id):
        """บันทึกประวัติการเขียนลงฐานข้อมูล SQLite"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO card_history (created_at, uid, serial_number, card_id) VALUES (?, ?, ?, ?)",
                (ts, uid, serial_dec, card_id)
            )
            conn.commit()

    @staticmethod
    def _card_id_sort_key(card_id_val):
        """สร้างคีย์จัดเรียง Card ID แบบธรรมชาติ (รองรับทั้งตัวเลขล้วนและตัวอักษรผสมตัวเลข)"""
        text = str(card_id_val or "").strip()
        parts = [p for p in re.split(r"(\d+)", text) if p]
        return tuple((0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts)

    def _read_csv_rows(self, file_path):
        """อ่านไฟล์ CSV โดยรองรับทั้ง UTF-8 (รวม BOM) และภาษาไทย Windows (CP874)"""
        for enc in ("utf-8-sig", "cp874", "tis-620"):
            try:
                with open(file_path, "r", newline="", encoding=enc) as f:
                    return list(csv.reader(f))
            except UnicodeDecodeError:
                continue
        raise ValueError("ไม่สามารถอ่านการเข้ารหัสตัวอักษรของไฟล์ CSV ได้")

    def import_csv_to_db(self):
        """นำเข้าข้อมูลจากไฟล์ CSV เข้าสู่ฐานข้อมูลปัจจุบัน"""
        file_path = filedialog.askopenfilename(
            title="เลือกไฟล์ CSV เพื่อนำเข้าข้อมูล",
            initialdir=self.base_dir,
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            raw_rows = self._read_csv_rows(file_path)
        except Exception as e:
            messagebox.showerror("อ่านไฟล์ไม่สำเร็จ", f"ไม่สามารถเปิดไฟล์ CSV ได้:\n{e}")
            return

        rows = [[cell.strip() for cell in r] for r in raw_rows if any(cell.strip() for cell in r)]
        if not rows:
            messagebox.showwarning("ไฟล์ว่าง", "ไม่พบข้อมูลในไฟล์ CSV ที่เลือก")
            return

        # ตรวจสอบ Header อัตโนมัติ
        header_lower = [c.lower() for c in rows[0]]
        col_map = {}
        header_aliases = {
            "created_at": {"date", "timestamp", "created_at", "time", "datetime", "วันที่", "เวลา"},
            "uid": {"uid", "card_uid"},
            "serial_number": {"serial number", "serial_number", "sn", "serial"},
            "card_id": {"card id", "card_id", "block_1_data", "card", "emp_id", "employee_id", "รหัสพนักงาน", "เลขบัตร", "id"},
        }
        for idx, col_name in enumerate(header_lower):
            for field, aliases in header_aliases.items():
                if col_name in aliases and field not in col_map:
                    col_map[field] = idx

        has_header = "card_id" in col_map or len(col_map) >= 2
        data_rows = rows[1:] if has_header else rows

        if not data_rows:
            messagebox.showwarning("ไม่มีข้อมูล", "ไฟล์ CSV มีเฉพาะหัวตาราง ไม่มีแถวข้อมูล")
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records_to_insert = []
        skipped_invalid = 0
        skipped_dup = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT card_id FROM card_history")
            existing_ids = {str(r[0]).strip() for r in cursor.fetchall()}

            for r in data_rows:
                if has_header and "card_id" in col_map:
                    card_id = r[col_map["card_id"]] if col_map["card_id"] < len(r) else ""
                    created_at = r[col_map["created_at"]] if "created_at" in col_map and col_map["created_at"] < len(r) else now_str
                    uid = r[col_map["uid"]] if "uid" in col_map and col_map["uid"] < len(r) else "-"
                    serial_num = r[col_map["serial_number"]] if "serial_number" in col_map and col_map["serial_number"] < len(r) else ""
                else:
                    # กรณีไม่มี Header มาตรฐาน: รองรับ 1, 2, 3 หรือ 4+ คอลัมน์
                    if len(r) >= 4:
                        created_at, uid, serial_num, card_id = r[0], r[1], r[2], r[3]
                    elif len(r) == 3:
                        created_at, uid, card_id = r[0], r[1], r[2]
                        serial_num = ""
                    elif len(r) == 2:
                        created_at, uid, serial_num, card_id = now_str, r[0], "", r[1]
                    else:
                        created_at, uid, serial_num, card_id = now_str, "-", "", r[0]

                card_id = card_id.strip()
                if not card_id or card_id in {"-", "(Empty/Null)", "(ว่าง)"}:
                    skipped_invalid += 1
                    continue

                if card_id in existing_ids:
                    skipped_dup += 1
                    continue

                created_at = created_at.strip() or now_str
                uid = uid.strip() or "-"
                serial_num = serial_num.strip()
                if not serial_num:
                    if uid != "-" and len(uid.replace(" ", "")) >= 8:
                        conv = self.hex_to_decimal_serial(uid)
                        serial_num = conv if conv != "Error" else "-"
                    else:
                        serial_num = "-"

                records_to_insert.append((created_at, uid, serial_num, card_id))
                existing_ids.add(card_id)

            if records_to_insert:
                # เรียงจากเลข Card ID น้อยไปมากก่อนบันทึก เพื่อให้เลขมากสุดได้ id ล่าสุดและอยู่ด้านบนสุดเมื่อแสดงผล
                records_to_insert.sort(key=lambda rec: self._card_id_sort_key(rec[3]))
                cursor.executemany(
                    "INSERT INTO card_history (created_at, uid, serial_number, card_id) VALUES (?, ?, ?, ?)",
                    records_to_insert
                )
                conn.commit()

        imported_count = len(records_to_insert)
        self.refresh_last_card_info(auto_fill_next=True)

        csv_name = os.path.basename(file_path)
        db_name = os.path.basename(self.db_path)
        if hasattr(self, "read_log"):
            ts_short = datetime.now().strftime("%H:%M:%S")
            self.read_log.insert(
                "0.0",
                f"[{ts_short}] 📥 นำเข้า CSV '{csv_name}' -> {db_name}: สำเร็จ {imported_count} รายการ (ซ้ำ {skipped_dup}, ข้าม {skipped_invalid})\n"
            )

        messagebox.showinfo(
            "นำเข้า CSV เสร็จสิ้น",
            f"ไฟล์: {csv_name}\n"
            f"ฐานข้อมูล: {db_name}\n\n"
            f"• นำเข้าสำเร็จ: {imported_count} รายการ\n"
            f"• ข้ามรายการเลขซ้ำ: {skipped_dup} รายการ\n"
            f"• ข้ามแถวว่าง/ไม่สมบูรณ์: {skipped_invalid} รายการ"
        )

    def get_last_written_record(self):
        """ดึงข้อมูลการเขียนบัตรรายการที่มี Card ID สูงสุดจากฐานข้อมูล"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, created_at, uid, serial_number, card_id FROM card_history"
            )
            rows = cursor.fetchall()
        if not rows:
            return None
        return max(rows, key=lambda r: (self._card_id_sort_key(r[4]), r[0]))

    def find_existing_card_id(self, card_id):
        """ตรวจสอบว่า Card ID นี้เคยถูกเขียนไปแล้วหรือยัง"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, created_at, uid, serial_number, card_id FROM card_history WHERE card_id = ? ORDER BY id DESC LIMIT 1",
                (card_id,)
            )
            return cursor.fetchone()

    def increment_card_id(self, card_id_str, step=1):
        """บวกเลข Card ID ถัดไป โดยคงจำนวนหลักและเลข 0 นำหน้าไว้เหมือนเดิม (เช่น 00099 -> 00100)"""
        if not card_id_str or not card_id_str.isdigit():
            return ""
        width = len(card_id_str)
        next_val = max(0, int(card_id_str) + step)
        return f"{next_val:0{width}d}"

    def set_entry_value(self, value_str):
        """กำหนดค่าในช่องกรอกรหัสบัตรอย่างปลอดภัย"""
        self.entry_write.delete(0, "end")
        if value_str:
            self.entry_write.insert(0, str(value_str))

    def refresh_last_card_info(self, auto_fill_next=False):
        """อัปเดตตารางด้านซ้าย ป้ายแสดงเลขล่าสุดที่เขียน และใส่เลขถัดไปลงช่องกรอกหากเปิดใช้งาน"""
        if hasattr(self, "history_tree"):
            self.load_history_table()

        last_rec = self.get_last_written_record()
        if last_rec:
            _, created_at, uid, _, last_card_id = last_rec
            next_card_id = self.increment_card_id(last_card_id, 1)
            self.lbl_last_card.configure(
                text=f"เลขล่าสุดที่เขียน: {last_card_id}  (เวลา {created_at})   ➜   เลขถัดไป: {next_card_id}",
                text_color="#2FA572"
            )
            if auto_fill_next and next_card_id:
                self.set_entry_value(next_card_id)
        else:
            self.lbl_last_card.configure(
                text="ประวัติฐานข้อมูล: ยังไม่มีประวัติการเขียนบัตร",
                text_color="gray"
            )
            if auto_fill_next:
                self.set_entry_value("")

    def load_next_from_last(self):
        """ปุ่มดึงเลขล่าสุดจากฐานข้อมูลมารันเป็นเลขถัดไป (+1)"""
        last_rec = self.get_last_written_record()
        if not last_rec:
            messagebox.showinfo("ยังไม่มีประวัติ", "ยังไม่มีประวัติเลขบัตรในฐานข้อมูล กรุณากรอกเลขเริ่มต้นครั้งแรกก่อน")
            return
        last_card_id = last_rec[4]
        next_card_id = self.increment_card_id(last_card_id, 1)
        self.set_entry_value(next_card_id)
        self.refresh_last_card_info(auto_fill_next=False)

    def step_current_entry(self, step):
        """ปุ่มเพิ่ม/ลดเลขในช่องกรอกปัจจุบันทีละ 1"""
        curr = self.entry_write.get().strip()
        if curr.isdigit():
            self.set_entry_value(self.increment_card_id(curr, step))
        else:
            self.load_next_from_last()

    def setup_history_panel(self, parent):
        """แผงด้านซ้าย: แสดงตารางประวัติเลขการ์ดที่เขียนไปแล้ว"""
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(8, 2))

        lbl_title = ctk.CTkLabel(
            header_frame,
            text="ประวัติเลขการ์ดที่เขียนไปแล้ว",
            font=("TH Sarabun New", 20, "bold")
        )
        lbl_title.pack(side="left")

        self.lbl_history_count = ctk.CTkLabel(
            header_frame,
            text="ทั้งหมด 0 รายการ",
            font=("Tahoma", 11),
            text_color="gray"
        )
        self.lbl_history_count.pack(side="right")

        self.lbl_active_db = ctk.CTkLabel(
            parent,
            text="",
            font=("Tahoma", 11, "bold"),
            anchor="w"
        )
        self.lbl_active_db.pack(fill="x", padx=14, pady=(0, 4))
        self.update_db_indicator()

        # แถบค้นหา
        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.history_search_var = tk.StringVar()
        self.entry_search_history = ctk.CTkEntry(
            search_frame,
            textvariable=self.history_search_var,
            placeholder_text="ค้นหา Card ID / UID / Serial Number...",
            font=("Tahoma", 12),
            height=30
        )
        self.entry_search_history.pack(fill="x", expand=True)

        # ตาราง Treeview (แยกคอลัมน์ Card ID ไว้ขวาสุดและใช้ฟอนต์ตัวหนากว่าคอลัมน์อื่น)
        table_container = tk.Frame(parent, bd=0, highlightthickness=0)
        table_container.pack(fill="both", expand=True, padx=12, pady=(2, 4))

        style = ttk.Style()
        style.configure("History.Treeview", font=("Consolas", 10), rowheight=26)
        style.configure("History.Treeview.Heading", font=("Tahoma", 10, "bold"))
        style.configure("CardID.Treeview", font=("Consolas", 11, "bold"), rowheight=26)
        style.configure("CardID.Treeview.Heading", font=("Tahoma", 10, "bold"))

        columns = ("id", "created_at", "uid", "serial_number", "card_id")
        self.history_tree = ttk.Treeview(
            table_container,
            columns=columns,
            displaycolumns=("id", "created_at", "uid", "serial_number"),
            show="headings",
            selectmode="browse",
            style="History.Treeview"
        )
        self.history_tree.heading("id", text="#")
        self.history_tree.heading("created_at", text="วัน-เวลาที่เขียน")
        self.history_tree.heading("uid", text="UID")
        self.history_tree.heading("serial_number", text="SN (10 หลัก)")

        self.history_tree.column("id", width=45, anchor="center")
        self.history_tree.column("created_at", width=135, anchor="center")
        self.history_tree.column("uid", width=110, anchor="center")
        self.history_tree.column("serial_number", width=115, anchor="center")

        self.card_id_tree = ttk.Treeview(
            table_container,
            columns=("card_id",),
            show="headings",
            selectmode="browse",
            style="CardID.Treeview"
        )
        self.card_id_tree.heading("card_id", text="Card ID")
        self.card_id_tree.column("card_id", width=105, anchor="center")

        def sync_scroll(*args):
            self.history_tree.yview(*args)
            self.card_id_tree.yview(*args)

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=sync_scroll)

        def on_left_yscroll(first, last):
            scrollbar.set(first, last)
            self.card_id_tree.yview_moveto(first)

        def on_right_yscroll(first, last):
            scrollbar.set(first, last)
            self.history_tree.yview_moveto(first)

        self.history_tree.configure(yscrollcommand=on_left_yscroll)
        self.card_id_tree.configure(yscrollcommand=on_right_yscroll)

        def on_mousewheel(event):
            delta = int(-1 * (event.delta / 120))
            self.history_tree.yview_scroll(delta, "units")
            self.card_id_tree.yview_scroll(delta, "units")
            return "break"

        self.history_tree.bind("<MouseWheel>", on_mousewheel)
        self.card_id_tree.bind("<MouseWheel>", on_mousewheel)

        self.history_tree.pack(side="left", fill="both", expand=True)
        self.card_id_tree.pack(side="left", fill="y")
        scrollbar.pack(side="right", fill="y")

        # คลิกเลือกแถวในตารางเพื่อนำเลขนั้นมารันเลขถัดไป (+1) ทันที
        self.history_tree.bind("<<TreeviewSelect>>", lambda e: self.on_history_row_selected(source="left"))
        self.card_id_tree.bind("<<TreeviewSelect>>", lambda e: self.on_history_row_selected(source="right"))

        lbl_hint = ctk.CTkLabel(
            parent,
            text="💡 คลิกเลือกแถวในตารางเพื่อนำเลขนั้นมารันเลขถัดไป (+1) อัตโนมัติ",
            font=("Tahoma", 11),
            text_color="gray"
        )
        lbl_hint.pack(pady=(2, 8))

        self.history_search_var.trace_add("write", lambda *_: self.load_history_table())
        self.load_history_table()

    def on_history_row_selected(self, source="left"):
        """เมื่อคลิกเลือกแถวในตารางประวัติ ให้ซิงค์การเลือกทั้งสองฝั่งและนำเลข Card ID มาบวก +1 ใส่ช่องเขียนทันที"""
        if source == "right":
            sel = self.card_id_tree.selection()
            if sel and self.history_tree.selection() != sel:
                self.history_tree.selection_set(sel)
        else:
            sel = self.history_tree.selection()
            if sel and self.card_id_tree.selection() != sel:
                self.card_id_tree.selection_set(sel)

        if not sel:
            return
        vals = self.history_tree.item(sel[0], "values")
        if len(vals) >= 5:
            selected_card_id = str(vals[4])
            next_id = self.increment_card_id(selected_card_id, 1)
            if next_id:
                self.set_entry_value(next_id)

    def load_history_table(self):
        """โหลดข้อมูลจาก SQLite มาแสดงในตารางด้านซ้าย (คอลัมน์ Card ID อยู่ขวาสุดและตัวหนา)"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        if hasattr(self, "card_id_tree"):
            for item in self.card_id_tree.get_children():
                self.card_id_tree.delete(item)

        kw = self.history_search_var.get().strip() if hasattr(self, "history_search_var") else ""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if kw:
                like_kw = f"%{kw}%"
                cursor.execute(
                    """SELECT id, created_at, uid, serial_number, card_id
                       FROM card_history
                       WHERE card_id LIKE ? OR uid LIKE ? OR serial_number LIKE ?
                       ORDER BY id DESC""",
                    (like_kw, like_kw, like_kw)
                )
            else:
                cursor.execute(
                    "SELECT id, created_at, uid, serial_number, card_id FROM card_history ORDER BY id DESC"
                )
            rows = cursor.fetchall()
        # เรียงข้อมูลตาม Card ID จากมากไปน้อย (เลขมากสุดอยู่ด้านบน)
        rows.sort(key=lambda r: (self._card_id_sort_key(r[4]), r[0]), reverse=True)
        for r in rows:
            row_iid = str(r[0])
            self.history_tree.insert("", "end", iid=row_iid, values=r)
            if hasattr(self, "card_id_tree"):
                self.card_id_tree.insert("", "end", iid=row_iid, values=(r[4],))
        if hasattr(self, "lbl_history_count"):
            self.lbl_history_count.configure(text=f"ทั้งหมด {len(rows)} รายการ")

    def delete_selected_history(self):
        """ลบรายการที่เลือกออกจากฐานข้อมูล"""
        sel = self.history_tree.selection()
        if not sel:
            messagebox.showwarning("เลือกรายการ", "กรุณาคลิกเลือกรายการที่ต้องการลบในตารางด้านซ้ายก่อนครับ")
            return
        vals = self.history_tree.item(sel[0], "values")
        rec_id, _, _, _, card_id_val = vals
        if messagebox.askyesno("ยืนยันการลบ", f"ต้องการลบประวัติ Card ID '{card_id_val}' (ลำดับ #{rec_id}) หรือไม่?"):
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM card_history WHERE id = ?", (rec_id,))
                conn.commit()
            self.refresh_last_card_info(auto_fill_next=False)

    def setup_db_top_box(self, parent):
        """กล่องเลือกฐานข้อมูลไว้ด้านบนซ้าย"""
        db_row = ctk.CTkFrame(parent, fg_color="transparent")
        db_row.pack(fill="x", padx=12, pady=8)

        lbl_db = ctk.CTkLabel(db_row, text="เลือกฐานข้อมูล:", font=("Tahoma", 12, "bold"))
        lbl_db.pack(side="left", padx=(0, 6))

        db_options = self.get_available_databases()
        self.db_option_var = ctk.StringVar(value=self.get_label_for_db_path(self.db_path))
        self.db_option_menu = ctk.CTkOptionMenu(
            db_row,
            variable=self.db_option_var,
            values=db_options,
            width=210,
            height=32,
            font=("Tahoma", 12),
            command=self.switch_database
        )
        self.db_option_menu.pack(side="left", padx=4)

        btn_browse_db = ctk.CTkButton(
            db_row,
            text="เลือกไฟล์ DB...",
            width=100,
            height=32,
            fg_color="#1F6AA5",
            font=("Tahoma", 12),
            command=self.browse_database_file
        )
        btn_browse_db.pack(side="left", padx=4)

        btn_new_db = ctk.CTkButton(
            db_row,
            text="+ สร้าง DB",
            width=85,
            height=32,
            fg_color="#2FA572",
            hover_color="#248259",
            font=("Tahoma", 12),
            command=self.create_new_database
        )
        btn_new_db.pack(side="left", padx=4)

    def setup_status_box(self, parent):
        """กล่องแสดงสถานะ (อยู่บนขวา เต็มพื้นที่ฝั่งขวา)"""
        self.lbl_read = ctk.CTkLabel(
            parent,
            text="อ่าน / เขียนบัตร Mifare",
            font=("TH Sarabun New", 20, "bold")
        )
        self.lbl_read.pack(pady=(8, 2))

        self.read_status = ctk.CTkLabel(
            parent,
            text="สถานะ: กำลังรอการแตะบัตร...",
            font=("Tahoma", 13, "bold"),
            text_color="orange"
        )
        self.read_status.pack(pady=(0, 2))

        self.lbl_last_card = ctk.CTkLabel(
            parent,
            text="ประวัติฐานข้อมูล: กำลังโหลด...",
            font=("Tahoma", 12, "bold"),
            text_color="gray"
        )
        self.lbl_last_card.pack(pady=(0, 6))

        self.read_log = ctk.CTkTextbox(parent, width=540, height=340, font=("Consolas", 12))
        self.read_log.pack(padx=12, pady=(0, 12), fill="both", expand=True)

    def set_write_button_ready(self, is_ready):
        """เปลี่ยนสีปุ่มเขียนลงบัตร: สีเขียวเมื่อมีบัตรว่างพร้อมเขียน / สีแดงแสดง 'ยังไม่พร้อมเขียน' เมื่อไม่มีบัตรว่าง"""
        self.is_blank_card_ready = is_ready
        if not hasattr(self, "btn_write"):
            return
        if is_ready:
            self.btn_write.configure(
                fg_color="#2FA572",
                hover_color="#248259",
                text="เขียนลงบัตร"
            )
        else:
            self.btn_write.configure(
                fg_color="#C0392B",
                hover_color="#962D22",
                text="ยังไม่พร้อมเขียน"
            )

    def validate_numbers(self, P):
        if P == "" or P.isdigit():
            return True
        return False

    def setup_bottom_button_block(self, parent):
        """Block สำหรับปุ่มทั้งแถบล่างสุด: ซ้ายสุด=ลบรายการที่เลือก | กลาง=ปุ่ม - ช่องเขียนข้อมูล ปุ่ม + | ขวาสุด=เขียนลงบัตร"""
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # ชิดซ้ายสุด: ปุ่มลบรายการที่เลือก และปุ่มนำเข้า CSV
        btn_del_row = ctk.CTkButton(
            inner,
            text="ลบรายการที่เลือก",
            fg_color="#C0392B",
            hover_color="#962D22",
            font=("Tahoma", 13, "bold"),
            width=140,
            height=40,
            command=self.delete_selected_history
        )
        btn_del_row.pack(side="left", padx=(0, 6))

        btn_import_csv = ctk.CTkButton(
            inner,
            text="นำเข้า CSV...",
            fg_color="#2980B9",
            hover_color="#1F618D",
            font=("Tahoma", 13, "bold"),
            width=120,
            height=40,
            command=self.import_csv_to_db
        )
        btn_import_csv.pack(side="left", padx=(0, 8))

        # ชิดขวาสุด: ปุ่มเขียนลงบัตร (เริ่มต้นเป็นสีแดง แสดงข้อความ 'ยังไม่พร้อมเขียน')
        self.btn_write = ctk.CTkButton(
            inner,
            text="ยังไม่พร้อมเขียน",
            fg_color="#C0392B",
            hover_color="#962D22",
            font=("Tahoma", 15, "bold"),
            width=210,
            height=40,
            command=self.start_write_thread
        )
        self.btn_write.pack(side="right", padx=(8, 0))

        # ตรงกลาง: ปุ่ม -  |  [ ช่องเขียนข้อมูล Card ID ]  |  ปุ่ม +
        center_group = ctk.CTkFrame(inner, fg_color="transparent")
        center_group.pack(side="top")

        lbl_card_id = ctk.CTkLabel(
            center_group,
            text="Card ID:",
            font=("Tahoma", 13, "bold")
        )
        lbl_card_id.pack(side="left", padx=(0, 6))

        btn_minus = ctk.CTkButton(
            center_group,
            text="-",
            width=50,
            height=38,
            font=("Tahoma", 18, "bold"),
            command=lambda: self.step_current_entry(-1)
        )
        btn_minus.pack(side="left", padx=4)

        vcmd = (self.register(self.validate_numbers), '%P')
        self.entry_write = ctk.CTkEntry(
            center_group,
            placeholder_text="กรอกรหัสพนักงาน (0-9)",
            width=260,
            height=38,
            font=("Consolas", 18, "bold"),
            justify="center",
            validate="key",
            validatecommand=vcmd
        )
        self.entry_write.pack(side="left", padx=6)

        btn_plus = ctk.CTkButton(
            center_group,
            text="+",
            width=50,
            height=38,
            font=("Tahoma", 18, "bold"),
            command=lambda: self.step_current_entry(1)
        )
        btn_plus.pack(side="left", padx=4)

    def setup_footer(self):
        """ส่วนแสดงข้อมูลผู้พัฒนาและ Licence ด้านล่างแอป"""
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=20, pady=10)

        # ข้อมูลฝั่งซ้าย
        dev_info = f"Developed by: {self.DEVELOPER} | {self.COMPANY} | {self.CONTACT}"
        lbl_dev = ctk.CTkLabel(footer_frame, text=dev_info, font=("Arial", 11), text_color="gray")
        lbl_dev.pack(side="left")

        # ข้อมูลฝั่งขวา (Version & Info Button)
        btn_info = ctk.CTkButton(footer_frame, text=f"Info {self.APP_VERSION}", 
                                 width=80, height=20, font=("Arial", 10),
                                 command=self.show_about_info)
        btn_info.pack(side="right")

    # def show_about_info(self):
    #     """แสดงหน้าต่าง Pop-up ข้อมูลลิขสิทธิ์และการติดต่อ"""
    #     about_text = (
    #         f"Software: Mifare Card Manager\n"
    #         f"Version: {self.APP_VERSION}\n\n"
    #         f"Developer: {self.DEVELOPER}\n"
    #         f"Company: {self.COMPANY}\n"
    #         f"Licence: {self.LICENCE}\n"
    #         f"Contact: {self.CONTACT}\n"
    #         f"Phone: {self.PHONE}\n\n"
            
    #         f"© 2026 {self.COMPANY}. All Rights Reserved."
    #     )
    #     messagebox.showinfo("About Application", about_text)
    


    def show_about_info(self):
        """แสดงหน้าต่าง Pop-up ข้อมูลลิขสิทธิ์และการติดต่อ (คัดลอกได้ / คลิกลิงก์ได้)"""

        # 1. สร้างหน้าต่าง Pop-up ใหม่
        about_win = tk.Toplevel(self)
        about_win.title("About Application")
        about_win.geometry("400x320")
        about_win.resizable(False, False)
        about_win.grab_set()  # บังคับให้จัดการหน้าต่างนี้ก่อนกลับไปหน้าหลัก

        # 2. ส่วนข้อมูลทั่วไป (สามารถลากคลุมเพื่อคัดลอกได้)
        general_text = (
            f"Software: Mifare Card Manager\n"
            f"Version: {self.APP_VERSION}\n\n"
            f"Developer: {self.DEVELOPER}\n"
            f"Company: {self.COMPANY}\n"
            f"Licence: {self.LICENCE}\n"
        )

        txt_area = tk.Text(about_win, wrap="word", height=7, background=about_win.cget("background"), 
                           borderwidth=0, highlightthickness=0, font=("Helvetica", 10))
        txt_area.insert("1.0", general_text)
        txt_area.configure(state="disabled")  # อ่านและคัดลอกได้อย่างเดียว ห้ามแก้ไขข้อมูล
        txt_area.pack(padx=20, pady=(15, 0), fill="x")

        # 3. ส่วนข้อมูลติดต่อและอีเมล (ทำเป็น Link สีฟ้าและมีเส้นใต้)
        contact_frame = ttk.Frame(about_win)
        contact_frame.pack(padx=20, pady=5, fill="x")

        # ฟังก์ชันสำหรับเปิด Email Client หรือ Web Browser เมื่อมีการคลิก
        def open_link(url):
            webbrowser.open(url)

        # แสดงข้อความ Contact: และตัวลิงก์อีเมล
        lbl_contact_title = ttk.Label(contact_frame, text="Contact: ", font=("Helvetica", 10))
        lbl_contact_title.pack(side="left")
        
        lbl_email_link = tk.Label(contact_frame, text=self.CONTACT, fg="blue", cursor="hand2", 
                                  font=("Helvetica", 10, "underline"))
        lbl_email_link.pack(side="left")
        # ผูกเหตุการณ์คลิกเมาส์ซ้าย เพื่อเปิดโปรแกรมส่งอีเมลอัตโนมัติ
        lbl_email_link.bind("<Button-1>", lambda e: open_link(f"mailto:{self.CONTACT}"))

        # 4. ส่วนข้อมูลเบอร์โทรศัพท์และลิขสิทธิ์
        footer_text = (
            f"\nPhone: {self.PHONE}\n\n"
            f"© 2026 {self.COMPANY}. All Rights Reserved."
        )
        
        txt_footer = tk.Text(about_win, wrap="word", height=4, background=about_win.cget("background"), 
                             borderwidth=0, highlightthickness=0, font=("Helvetica", 10))
        txt_footer.insert("1.0", footer_text)
        txt_footer.configure(state="disabled")
        txt_footer.pack(padx=20, pady=0, fill="x")

        # 5. ปุ่มปิดหน้าต่าง Pop-up
        btn_close = ttk.Button(about_win, text="OK", command=about_win.destroy, width=10)
        btn_close.pack(side="bottom", pady=15)


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

                    # อ่าน Data ใน Block 1 (Card ID)
                    conn.transmit([0xFF, 0x82, 0x00, 0x00, 0x06, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
                    _, auth_sw1, _ = conn.transmit([0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, 0x01, 0x60, 0x00])
                    b_data, s1, s2 = conn.transmit([0xFF, 0xB0, 0x00, 0x01, 0x10])
                    b_text = "".join([chr(x) if 32 <= x <= 126 else "" for x in b_data]).strip() if s1 == 0x90 else ""

                    # ตรวจสอบว่าเป็นบัตรว่างพร้อมเขียนหรือไม่ (Auth ผ่าน และ Block 1 ยังไม่มีข้อความ)
                    is_blank = (auth_sw1 == 0x90 and s1 == 0x90 and b_text == "")
                    if is_blank != self.is_blank_card_ready:
                        self.after(0, lambda ready=is_blank: self.set_write_button_ready(ready))

                    if uid_hex != self.last_uid:
                        # คำนวณ Serial 10 หลัก
                        serial_dec = self.hex_to_decimal_serial(uid_hex)
                        ts = datetime.now().strftime('%H:%M:%S')
                        card_display = b_text if b_text else "(บัตรว่างพร้อมเขียน)"
                        log_msg = f"[{ts}] 📖 อ่านบัตร | UID: {uid_hex} | SN: {serial_dec} | Card ID: {card_display}\n"
                        
                        self.read_log.insert("0.0", log_msg)
                        if is_blank:
                            self.read_status.configure(
                                text=f"สถานะ: 🟢 พบบัตรว่างพร้อมเขียน! (UID: {uid_hex})",
                                text_color="#2FA572"
                            )
                        else:
                            self.read_status.configure(
                                text=f"สถานะ: พบบัตรมีข้อมูลแล้ว UID: {uid_hex} | Card ID ในบัตร: {card_display}",
                                text_color="#E67E22"
                            )

                        # ไม่เขียนทับเลขที่กำลังรันอยู่ เว้นแต่ช่องกรอกยังว่างเปล่าและไม่ได้เปิดโหมดรันเลขถัดไปอัตโนมัติ
                        if not self.auto_next_var.get() and not self.entry_write.get().strip() and b_text.isdigit():
                            self.set_entry_value(b_text)

                        self.last_uid = uid_hex
                else:
                    if self.is_blank_card_ready:
                        self.after(0, lambda: self.set_write_button_ready(False))
                    self.last_uid = None
                    self.read_status.configure(text="สถานะ: ไม่พบเครื่องอ่านบัตร (กรุณาเสียบเครื่องอ่าน)", text_color="red")
            except Exception:
                if self.is_blank_card_ready:
                    self.after(0, lambda: self.set_write_button_ready(False))
                if self.last_uid is not None:
                    self.read_status.configure(text="สถานะ: กำลังรอการแตะบัตร...", text_color="orange")
                self.last_uid = None
            time.sleep(0.5)

    def log_to_csv(self, ts, date_str, uid, serial_dec, card_id):
        filename = os.path.join(self.base_dir, f'write_card_{date_str}.csv')
        file_exists = os.path.isfile(filename)
        
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "UID", "Serial Number", "Card ID"])
            writer.writerow([ts, uid, serial_dec, card_id])

    def start_write_thread(self):
        data = self.entry_write.get().strip()
        if not data:
            messagebox.showwarning("แจ้งเตือน", "กรุณากรอกรหัสพนักงาน/เลขบัตรก่อนเขียนครับ")
            return

        # ตรวจสอบเลขซ้ำในฐานข้อมูลก่อนเขียน เพื่อลดปัญหาพิมพ์ซ้ำ/เขียนซ้ำ
        existing = self.find_existing_card_id(data)
        if existing:
            _, prev_time, prev_uid, prev_sn, _ = existing
            confirm = messagebox.askyesno(
                "แจ้งเตือนเลขบัตรซ้ำ!",
                f"เลข Card ID '{data}' เคยถูกเขียนไปแล้วในฐานข้อมูล!\n\n"
                f"• วันที่เขียน: {prev_time}\n"
                f"• UID เดิม: {prev_uid}\n"
                f"• SN เดิม: {prev_sn}\n\n"
                f"คุณต้องการเขียนเลข '{data}' ซ้ำลงบัตรใบนี้หรือไม่?"
            )
            if not confirm:
                return

        self.btn_write.configure(state="disabled")
        threading.Thread(target=self.write_card, args=(data,), daemon=True).start()

    def write_card(self, text):
        try:
            r = readers()
            if len(r) == 0:
                self.read_log.insert("0.0", "❌ ไม่พบเครื่องอ่านบัตร\n")
                return
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
                    now = datetime.now()
                    ts = now.strftime('%Y-%m-%d %H:%M:%S')
                    time_only = now.strftime('%H:%M:%S')
                    date_str = now.strftime('%Y-%m-%d')

                    # 1. บันทึกลงฐานข้อมูล SQLite เสมอเพื่อเก็บประวัติเลขที่เขียนไปแล้ว
                    self.save_to_db(ts, uid_hex, serial_dec, text)

                    # 2. บันทึกลงไฟล์ CSV รายวัน
                    if self.check_var.get():
                        self.log_to_csv(ts, date_str, uid_hex, serial_dec, text)

                    log_entry = f"[{time_only}] ✅ เขียนสำเร็จ | Card ID: {text} | UID: {uid_hex} | SN: {serial_dec}\n"
                    self.read_log.insert("0.0", log_entry)
                    self.read_status.configure(
                        text=f"สถานะ: ✅ เขียน Card ID '{text}' สำเร็จ! (กรุณาเปลี่ยนบัตรใบถัดไป)",
                        text_color="#2FA572"
                    )

                    # เมื่อเขียนลงบัตรแล้ว บัตรใบนี้ไม่ว่างอีกต่อไป -> เปลี่ยนปุ่มเป็นสีแดงจนกว่าจะวางบัตรว่างใบใหม่
                    self.after(0, lambda: self.set_write_button_ready(False))

                    # 3. อัปเดตตารางด้านซ้ายและรันเลขถัดไป (+1) อัตโนมัติ
                    self.after(0, lambda: self.refresh_last_card_info(auto_fill_next=self.auto_next_var.get()))
                else:
                    self.read_log.insert("0.0", f"❌ เขียนล้มเหลว | UID: {uid_hex} | SN: {serial_dec}\n")
            else:
                self.read_log.insert("0.0", f"❌ บัตรไม่รองรับ/Key ผิด\n")
        except Exception as e:
            self.read_log.insert("0.0", f"⚠️ กรุณาวางบัตรบนเครื่องอ่านก่อนกดเขียน ({str(e)})\n")
        finally:
            self.btn_write.configure(state="normal")


if __name__ == "__main__":
    app = NFCManagerApp()
    app.mainloop()