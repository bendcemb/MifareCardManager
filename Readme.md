
<!-- การทำงานของ read_all.py -->
ข้าม Block 0: ซึ่งปกติจะแก้ไขไม่ได้และเป็นข้อมูลโรงงาน
ข้าม Sector Trailers: บล็อกที่ 3, 7, 11, 15... (จนถึง 63) จะไม่ถูกนำมาบันทึก เพราะไม่มีข้อมูลพนักงานอยู่ในนั้นแน่นอน
Clean Text: ข้อมูลจะถูก strip() เอาช่องว่างออก และถ้าบล็อกไหนว่างจะใส่ - แทน เพื่อให้ในไฟล์ Excel ของคุณดูสะอาดและตรง Column เสมอ
ข้อมูลในไฟล์ CSV จะเรียงจาก Block 1, 2, 4, 5, 6, 8, 9, 10... ไปเรื่อยๆ เหมาะมากสำหรับการสำรวจว่าบัตรพนักงานของคุณแอบเก็บข้อมูลไว้ที่ช่องไหนบ้าง




<!-- run ข้อมูล .exe -->
python -m PyInstaller --noconfirm --onefile --windowed --collect-all customtkinter Write_Card.py


echo venv/ > .gitignore
echo build/ >> .gitignore
echo dist/ >> .gitignore
echo __pycache__/ >> .gitignore
echo *.spec >> .gitignore




echo "# employeecard" >> README.md
git init
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/bppbendcemb/employeecard.git
git push -u origin main


# 1. เช็คดูว่า Git เห็นไฟล์อะไรบ้าง (ตอนนี้ไฟล์ venv หรือ build ควรจะหายไปจากรายการแล้ว)
git status

# 2. เพิ่มไฟล์ทั้งหมดเข้า Stage
git add .

# 3. บันทึกประวัติครั้งแรก
git commit -m "Initial commit: NFC Employee Manager with SQLite and SN conversion"