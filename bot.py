# bot.py - ربات کامل مدیریت سرمایه‌گذاری
import asyncio
import sqlite3
import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ======= تنظیمات ربات =======
BOT_TOKEN = os.getenv('BOT_TOKEN', '8222491315:AAHT4oj9Et9GiBEr_wJAlZ8kzxG2uMOr5DE')
ADMIN_TELEGRAM_ID = 6328795262  # تغییر به آیدی خودتان
ADMIN_PASSWORD = "54d36)(136697"

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======= اتصال دیتابیس =======
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

# ایجاد جداول
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    national_id TEXT,
    password TEXT,
    balance REAL DEFAULT 0,
    total_deposit REAL DEFAULT 0,
    total_profit REAL DEFAULT 0,
    total_withdrawal REAL DEFAULT 0,
    withdrawal_requests TEXT DEFAULT '',
    photo_receipt TEXT DEFAULT '',
    phone_number TEXT DEFAULT '',
    full_name TEXT DEFAULT '',
    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    type TEXT,
    amount REAL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    action TEXT,
    details TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    amount REAL,
    wallet_address TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# جدول جدید برای فیش‌های واریزی
cursor.execute("""
CREATE TABLE IF NOT EXISTS deposit_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    photo_file_id TEXT,
    amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending',
    admin_description TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# ======= کلاس وضعیت‌ها =======
class UserStates(StatesGroup):
    waiting_national_id = State()
    waiting_password = State()
    logged_in = State()
    admin_login = State()
    admin_menu = State()
    waiting_photo = State()
    waiting_withdrawal_amount = State()
    waiting_wallet_address = State()
    waiting_new_password = State()
    waiting_phone = State()
    waiting_full_name = State()
    
    # حالت‌های ادمین
    admin_manage_users = State()
    admin_receipts_menu = State()
    admin_withdrawals_menu = State()
    admin_confirm_receipt = State()
    admin_approve_withdrawal = State()
    admin_reject_withdrawal = State()
    admin_add_balance_user = State()
    admin_add_balance_amount = State()
    admin_edit_user = State()
    admin_edit_user_balance = State()
    admin_edit_user_info = State()
    
    # حالت‌های جدید برای دریافت مبلغ و توضیحات
    admin_receipt_amount = State()
    admin_receipt_description = State()
    admin_withdrawal_amount = State()
    admin_withdrawal_description = State()
    
    # حالت جدید برای منوی تراکنش‌ها
    viewing_transactions = State()

# ======= توابع کمکی =======
def safe_float(value):
    """تبدیل ایمن به float"""
    try:
        return float(value) if value else 0.0
    except (ValueError, TypeError):
        return 0.0

def create_user(telegram_id, national_id, password, full_name="", phone_number=""):
    try:
        cursor.execute("""
            INSERT INTO users (telegram_id, national_id, password, full_name, phone_number) 
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, national_id, password, full_name, phone_number))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_user(telegram_id):
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    return cursor.fetchone()

def get_all_users():
    cursor.execute("SELECT * FROM users ORDER BY id DESC")
    return cursor.fetchall()

def get_pending_deposit_receipts():
    """دریافت فیش‌های واریزی در انتظار تایید"""
    cursor.execute("""
        SELECT dr.*, u.national_id, u.full_name 
        FROM deposit_receipts dr 
        JOIN users u ON dr.telegram_id = u.telegram_id 
        WHERE dr.status = 'pending'
    """)
    return cursor.fetchall()

def get_pending_withdrawal_requests():
    cursor.execute("""
        SELECT wr.*, u.national_id, u.full_name 
        FROM withdrawal_requests wr 
        JOIN users u ON wr.telegram_id = u.telegram_id 
        WHERE wr.status = 'pending'
    """)
    return cursor.fetchall()

def update_user_balance(telegram_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id=?", (amount, telegram_id))
    conn.commit()

def set_user_balance(telegram_id, amount):
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id=?", (amount, telegram_id))
    conn.commit()

def add_transaction(telegram_id, type, amount, description, status='completed'):
    cursor.execute("""
        INSERT INTO transactions (telegram_id, type, amount, description, status) 
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, type, amount, description, status))
    conn.commit()

def get_user_transactions(telegram_id, limit=20):
    cursor.execute("""
        SELECT * FROM transactions 
        WHERE telegram_id=? 
        ORDER BY id DESC 
        LIMIT ?
    """, (telegram_id, limit))
    return cursor.fetchall()

def get_user_deposit_receipts(telegram_id, limit=10):
    cursor.execute("""
        SELECT * FROM deposit_receipts 
        WHERE telegram_id=? 
        ORDER BY id DESC 
        LIMIT ?
    """, (telegram_id, limit))
    return cursor.fetchall()

def get_user_withdrawal_requests(telegram_id, limit=10):
    cursor.execute("""
        SELECT * FROM withdrawal_requests 
        WHERE telegram_id=? 
        ORDER BY id DESC 
        LIMIT ?
    """, (telegram_id, limit))
    return cursor.fetchall()

def add_withdrawal_request(telegram_id, amount, wallet_address):
    cursor.execute("""
        INSERT INTO withdrawal_requests (telegram_id, amount, wallet_address) 
        VALUES (?, ?, ?)
    """, (telegram_id, amount, wallet_address))
    conn.commit()
    return cursor.lastrowid  # بازگشت شماره درخواست

def add_deposit_receipt(telegram_id, photo_file_id):
    """افزودن فیش واریزی جدید"""
    cursor.execute("""
        INSERT INTO deposit_receipts (telegram_id, photo_file_id) 
        VALUES (?, ?)
    """, (telegram_id, photo_file_id))
    conn.commit()
    return cursor.lastrowid  # بازگشت شماره فیش

def update_withdrawal_request(request_id, status):
    cursor.execute("UPDATE withdrawal_requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()

def update_deposit_receipt(receipt_id, amount, status, admin_description=""):
    """به‌روزرسانی وضعیت فیش واریزی"""
    cursor.execute("UPDATE deposit_receipts SET status = ?, amount = ?, admin_description = ? WHERE id = ?", 
                  (status, amount, admin_description, receipt_id))
    if status == 'approved':
        # افزایش موجودی کاربر
        cursor.execute("""
            UPDATE users 
            SET balance = balance + ?,
                total_deposit = total_deposit + ?
            WHERE telegram_id = (SELECT telegram_id FROM deposit_receipts WHERE id = ?)
        """, (amount, amount, receipt_id))
    conn.commit()

def update_user_profile(telegram_id, full_name="", phone_number="", national_id=""):
    if full_name and phone_number and national_id:
        cursor.execute("UPDATE users SET full_name = ?, phone_number = ?, national_id = ? WHERE telegram_id=?", 
                      (full_name, phone_number, national_id, telegram_id))
    elif full_name and phone_number:
        cursor.execute("UPDATE users SET full_name = ?, phone_number = ? WHERE telegram_id=?", 
                      (full_name, phone_number, telegram_id))
    elif full_name and national_id:
        cursor.execute("UPDATE users SET full_name = ?, national_id = ? WHERE telegram_id=?", 
                      (full_name, national_id, telegram_id))
    elif phone_number and national_id:
        cursor.execute("UPDATE users SET phone_number = ?, national_id = ? WHERE telegram_id=?", 
                      (phone_number, national_id, telegram_id))
    elif full_name:
        cursor.execute("UPDATE users SET full_name = ? WHERE telegram_id=?", (full_name, telegram_id))
    elif phone_number:
        cursor.execute("UPDATE users SET phone_number = ? WHERE telegram_id=?", (phone_number, telegram_id))
    elif national_id:
        cursor.execute("UPDATE users SET national_id = ? WHERE telegram_id=?", (national_id, telegram_id))
    conn.commit()

def update_user_password(telegram_id, new_password):
    cursor.execute("UPDATE users SET password = ? WHERE telegram_id=?", (new_password, telegram_id))
    conn.commit()

def log_action(telegram_id, action, details=""):
    cursor.execute("INSERT INTO logs (telegram_id, action, details) VALUES (?, ?, ?)", 
                  (telegram_id, action, details))
    conn.commit()

def get_transaction_stats(telegram_id):
    """آمار تراکنش‌های کاربر"""
    # شمارش تراکنش‌های واریز تکمیل شده
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE telegram_id=? AND type='deposit' AND status='completed'", (telegram_id,))
    deposit_count = cursor.fetchone()[0] or 0
    
    # شمارش تراکنش‌های برداشت تکمیل شده
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE telegram_id=? AND type='withdrawal' AND status='completed'", (telegram_id,))
    withdrawal_count = cursor.fetchone()[0] or 0
    
    total_transactions = deposit_count + withdrawal_count
    
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE telegram_id=? AND type='deposit' AND status='completed'", (telegram_id,))
    total_deposit = safe_float(cursor.fetchone()[0])
    
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE telegram_id=? AND type='withdrawal' AND status='completed'", (telegram_id,))
    total_withdrawal = safe_float(cursor.fetchone()[0])
    
    cursor.execute("SELECT COUNT(*) FROM deposit_receipts WHERE telegram_id=? AND status='pending'", (telegram_id,))
    pending_deposits = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM withdrawal_requests WHERE telegram_id=? AND status='pending'", (telegram_id,))
    pending_withdrawals = cursor.fetchone()[0] or 0
    
    return {
        'total_deposit': total_deposit,
        'total_withdrawal': total_withdrawal,
        'total_transactions': total_transactions,
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'deposit_count': deposit_count,
        'withdrawal_count': withdrawal_count
    }

# ======= منوها =======
def user_menu_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="در صورت بروز خطا از منوی سمت راست بالا تلگرام گفتگو را پاک کنید و دوباره وارد ربات شوید")],
            [KeyboardButton(text="📊 پروفایل و موجودی")],
            [KeyboardButton(text="💵 آپلود فیش واریزی")],
            [KeyboardButton(text="💳 نحوه واریز و سرمایه‌گذاری")],
            [KeyboardButton(text="📈 سود و سرمایه‌گذاری")],
            [KeyboardButton(text="🏦 درخواست برداشت")],
            [KeyboardButton(text="📋 تراکنش‌ها")],
            [KeyboardButton(text="👤 ویرایش پروفایل"), KeyboardButton(text="🔑 تغییر رمز عبور")],
            [KeyboardButton(text="🔄 شروع مجدد"), KeyboardButton(text="🚪 خروج")]
            
        ],
        resize_keyboard=True
    )
    return markup

def admin_menu_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 مدیریت کاربران")],
            [KeyboardButton(text="✅ تایید فیش‌ها"), KeyboardButton(text="💳 مدیریت برداشت‌ها")],
            [KeyboardButton(text="💰 افزایش موجودی"), KeyboardButton(text="📊 آمار و گزارش‌ها")],
            [KeyboardButton(text="📜 لاگ سیستم"), KeyboardButton(text="🚪 خروج از مدیریت")]
        ],
        resize_keyboard=True
    )
    return markup

def admin_users_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 لیست تمام کاربران")],
            [KeyboardButton(text="🔍 جستجوی کاربر"), KeyboardButton(text="✏️ ویرایش کاربر")],
            [KeyboardButton(text="📊 آمار کاربران")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )
    return markup

def admin_edit_user_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 تغییر موجودی")],
            [KeyboardButton(text="👤 تغییر اطلاعات کاربر")],
            [KeyboardButton(text="🔙 بازگشت به مدیریت کاربران")]
        ],
        resize_keyboard=True
    )
    return markup

def admin_receipts_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 مشاهده فیش‌های انتظار")],
            [KeyboardButton(text="✅ تایید فیش"), KeyboardButton(text="❌ رد فیش")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )
    return markup

def admin_withdrawals_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 مشاهده درخواست‌ها")],
            [KeyboardButton(text="✅ تایید برداشت"), KeyboardButton(text="❌ رد برداشت")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )
    return markup

def cancel_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ لغو عملیات")]
        ],
        resize_keyboard=True
    )
    return markup

def transactions_markup():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 واریزها"), KeyboardButton(text="📤 برداشت‌ها")],
            #[KeyboardButton(text="📊 آمار تراکنش‌ها"), KeyboardButton(text="📋 همه تراکنش‌ها")],
            [KeyboardButton(text="📊 آمار تراکنش‌ها")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )
    return markup

# ======= راه‌اندازی ربات =======
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ======= هندلر استارت =======
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_TELEGRAM_ID:
        await message.answer("🔐 رمز عبور ادمین را وارد کنید:")
        await state.set_state(UserStates.admin_login)
        return

    user = get_user(message.from_user.id)
    if user:
        await message.answer("🔐 زبان گوشی یا سیستم لطفا انگلیسی باشد \n لطفاً رمز عبور خود را وارد کنید:")
        await state.set_state(UserStates.waiting_password)
    else:
        await message.answer("👋 به ربات مدیریت سرمایه‌گذاری خوش آمدید!\nزبان گوشی یا سیستم لطفا انگلیسی باشد\n\n👤 برای ثبت نام، کد ملی خود را وارد کنید:")
        await state.set_state(UserStates.waiting_national_id)

# ======= ثبت نام =======
@dp.message(UserStates.waiting_national_id)
async def register_user(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
        
    national_id = message.text.strip()
    if not national_id.isdigit() or len(national_id) != 10:
        await message.answer("❌ کد ملی باید 10 رقم باشد. دوباره وارد کنید:")
        return
    
    password = "pass" + national_id[-4:]
    success = create_user(message.from_user.id, national_id, password)
    if success:
        await message.answer(
            f"✅ ثبت نام موفق\n\n"
            f"🔐 رمز عبور شما: {password}\n"
            f"⚠️ این رمز را یادداشت کنید\n\n"
            f"لطفاً رمز عبور را وارد کنید:"
        )
        await state.set_state(UserStates.waiting_password)
        log_action(message.from_user.id, "ثبت نام جدید", f"کد ملی: {national_id}")
    else:
        await message.answer("❌ \nزبان گوشی یا سیستم لطفا انگلیسی باشد\nکاربر قبلاً ثبت نام کرده است. لطفاً رمز عبور خود را وارد کنید:")
        await state.set_state(UserStates.waiting_password)

# ======= ورود کاربر =======
@dp.message(UserStates.waiting_password)
async def login_user(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
        
    password = message.text.strip()
    user = get_user(message.from_user.id)
    if user and password == user[3]:
        cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE telegram_id=?", (message.from_user.id,))
        conn.commit()
        
        await message.answer(f"✅ ورود موفق\n\n👋 سلام {user[11] or 'کاربر'} عزیز!", reply_markup=user_menu_markup())
        await message.answer(f"نکته:\n1-.میزان سرمایه گذاری حداقل 30 تتر برای شروع سودآوری نیاز است\n2-شروع برداشت تتر از ربات سرمایه گذاری یکماه پس از شروع سودآوری امکان پذیر است.\n3-درخواستهای قبل از یکماه از شروع سودآوری توسط ادمین رد خواهد شد.\n4-جهت یادگیری و خبرهای مهم در خصوص ربات و سود سرمایه گذاری پیج ایسنتا ربات را دنبال کنید.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        log_action(message.from_user.id, "ورود موفق")
    else:
        await message.answer("❌ رمز اشتباه. دوباره تلاش کنید.رمز صحیح را وارد نمایید:")

# ======= ورود ادمین =======
@dp.message(UserStates.admin_login)
async def admin_login(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
        
    if message.text == ADMIN_PASSWORD and message.from_user.id == ADMIN_TELEGRAM_ID:
        await message.answer("✅ ورود به بخش مدیریت", reply_markup=admin_menu_markup())
        await state.set_state(UserStates.admin_menu)
        log_action(message.from_user.id, "ورود ادمین موفق")
    else:
        await message.answer("❌ رمز اشتباه. دوباره تلاش کنید.رمز صحیح را وارد نمایید:")

# ======= منوی اصلی ادمین =======
@dp.message(UserStates.admin_menu)
async def handle_admin_menu(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "👥 مدیریت کاربران":
        await message.answer("مدیریت کاربران", reply_markup=admin_users_markup())
        await state.set_state(UserStates.admin_manage_users)
        
    elif text == "✅ تایید فیش‌ها":
        await message.answer("مدیریت فیش‌های واریزی", reply_markup=admin_receipts_markup())
        await state.set_state(UserStates.admin_receipts_menu)
        
    elif text == "💳 مدیریت برداشت‌ها":
        await message.answer("مدیریت درخواست‌های برداشت", reply_markup=admin_withdrawals_markup())
        await state.set_state(UserStates.admin_withdrawals_menu)
        
    elif text == "💰 افزایش موجودی":
        await message.answer("🆔 آیدی تلگرام کاربر را وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_add_balance_user)
        
    elif text == "📊 آمار و گزارش‌ها":
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM deposit_receipts WHERE status = 'pending'")
        pending_receipts = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM withdrawal_requests WHERE status = 'pending'")
        pending_withdrawals = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = safe_float(cursor.fetchone()[0])
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='deposit' AND status='completed'")
        total_deposits = safe_float(cursor.fetchone()[0])
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='withdrawal' AND status='completed'")
        total_withdrawals = safe_float(cursor.fetchone()[0])
        
        stats_text = f"""
📊 آمار کلی سیستم

👥 کاربران کل: {total_users}
📥 فیش‌های در انتظار: {pending_receipts}
💳 برداشت‌های در انتظار: {pending_withdrawals}
💰 مجموع موجودی: {total_balance:,.0f} Tether
📥 مجموع واریزها: {total_deposits:,.0f} Tether
📤 مجموع برداشت‌ها: {total_withdrawals:,.0f} Tether
        """
        await message.answer(stats_text)
        
    elif text == "📜 لاگ سیستم":
        cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 15")
        logs = cursor.fetchall()
        if logs:
            log_text = "📜 آخرین ۱۵ لاگ:\n\n"
            for log in logs:
                log_text += f"👤 {log[1]} - {log[2]}\n📝 {log[3]}\n⏰ {log[4][:16]}\n\n"
            await message.answer(log_text)
        else:
            await message.answer("📜 لاگی وجود ندارد")
            
    elif text == "🚪 خروج از مدیریت":
        await message.answer("👋 با موفقیت از مدیریت خارج شدید.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        
    else:
        await message.answer("❌ گزینه نامعتبر")

# ======= منوی مدیریت فیش‌ها =======
@dp.message(UserStates.admin_receipts_menu)
async def handle_admin_receipts_menu(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "📋 مشاهده فیش‌های انتظار":
        receipts = get_pending_deposit_receipts()
        if receipts:
            for receipt in receipts:
                amount = safe_float(receipt[3])
                try:
                    await message.answer_photo(
                        receipt[2],
                        caption=f"📋 فیش واریزی #{receipt[0]}\n\n👤 کاربر: {receipt[8] or 'نامشخص'}\n🆔 آیدی: {receipt[1]}\n🆔 کد ملی: {receipt[7] or 'نامشخص'}\n💰 مبلغ پیشنهادی: {amount:,.0f} Tether\n📅 تاریخ: {receipt[6][:16]}"
                    )
                except Exception as e:
                    await message.answer(f"📋 فیش واریزی #{receipt[0]} (خطا در نمایش عکس)\n\n👤 کاربر: {receipt[8] or 'نامشخص'}\n🆔 آیدی: {receipt[1]}\n🆔 کد ملی: {receipt[7] or 'نامشخص'}\n💰 مبلغ پیشنهادی: {amount:,.0f} Tether\n📅 تاریخ: {receipt[6][:16]}")
        else:
            await message.answer("✅ هیچ فیشی برای تایید وجود ندارد")
            
    elif text == "✅ تایید فیش":
        await message.answer("🔢 شماره فیش را وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_confirm_receipt)
        
    elif text == "❌ رد فیش":
        await message.answer("🔢 شماره فیش را وارد کنید:", reply_markup=cancel_markup())
        # استفاده از همان state برای سادگی
        await state.set_state(UserStates.admin_confirm_receipt)
        await state.update_data(reject_mode=True)
        
    elif text == "🔙 بازگشت به منوی اصلی":
        await message.answer("منوی اصلی", reply_markup=admin_menu_markup())
        await state.set_state(UserStates.admin_menu)
        
    else:
        await message.answer("❌ گزینه نامعتبر")

# ======= تایید یا رد فیش - مرحله اول (دریافت شماره فیش) =======
@dp.message(UserStates.admin_confirm_receipt)
async def handle_confirm_receipt(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_receipts_markup())
        await state.set_state(UserStates.admin_receipts_menu)
        return
        
    try:
        receipt_id = int(message.text)
        
        # بررسی وجود فیش
        cursor.execute("SELECT * FROM deposit_receipts WHERE id = ?", (receipt_id,))
        receipt = cursor.fetchone()
        
        if not receipt:
            await message.answer("❌ فیش یافت نشد. شماره صحیح وارد کنید:")
            return
        
        data = await state.get_data()
        reject_mode = data.get('reject_mode', False)
        
        if reject_mode:
            # رد فیش
            update_deposit_receipt(receipt_id, 0, 'rejected')
            await message.answer(
                f"❌ فیش رد شد\n\n"
                f"🔢 شماره: #{receipt_id}\n"
                f"👤 کاربر: {receipt[1]}",
                reply_markup=admin_receipts_markup()
            )
            await state.set_state(UserStates.admin_receipts_menu)
            log_action(message.from_user.id, "رد فیش", f"فیش: {receipt_id}")
            
            # اطلاع به کاربر
            try:
                await bot.send_message(receipt[1], f"❌ فیش واریزی #{receipt_id} شما رد شد.")
            except:
                pass
        else:
            # تایید فیش - دریافت مبلغ
            await state.update_data(receipt_id=receipt_id)
            await message.answer("💰 مبلغ واریزی را به Tether وارد کنید:", reply_markup=cancel_markup())
            await state.set_state(UserStates.admin_receipt_amount)
            
    except ValueError:
        await message.answer("❌ شماره فیش باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= تایید فیش - مرحله دوم (دریافت مبلغ) =======
@dp.message(UserStates.admin_receipt_amount)
async def handle_receipt_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_receipts_markup())
        await state.set_state(UserStates.admin_receipts_menu)
        return
        
    try:
        amount = safe_float(message.text)
        if amount <= 0:
            await message.answer("❌ مبلغ باید بیشتر از صفر باشد. لطفاً مجدداً وارد کنید:")
            return
            
        await state.update_data(amount=amount)
        await message.answer("📝 توضیحات برای کاربر (اختیاری):", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_receipt_description)
            
    except ValueError:
        await message.answer("❌ مبلغ باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= تایید فیش - مرحله سوم (دریافت توضیحات) =======
@dp.message(UserStates.admin_receipt_description)
async def handle_receipt_description(message: types.Message, state: FSMContext):
    description = message.text
    data = await state.get_data()
    receipt_id = data['receipt_id']
    amount = data['amount']
    
    # تایید فیش
    admin_desc = description if description and description != "❌ لغو عملیات" else ""
    update_deposit_receipt(receipt_id, amount, 'approved', admin_desc)
    
    # اضافه کردن تراکنش
    cursor.execute("SELECT telegram_id FROM deposit_receipts WHERE id = ?", (receipt_id,))
    receipt = cursor.fetchone()
    user_id = receipt[0]
    
    transaction_description = f"تایید فیش واریزی #{receipt_id}"
    if admin_desc:
        transaction_description += f" - {admin_desc}"
    
    add_transaction(user_id, 'deposit', amount, transaction_description, 'completed')
    
    await message.answer(
        f"✅ فیش تایید شد\n\n"
        f"🔢 شماره: #{receipt_id}\n"
        f"💰 مبلغ: {amount:,.0f} Tether\n"
        f"📝 توضیحات: {admin_desc if admin_desc else 'بدون توضیح'}\n"
        f"👤 کاربر: {user_id}",
        reply_markup=admin_receipts_markup()
    )
    await state.set_state(UserStates.admin_receipts_menu)
    log_action(message.from_user.id, "تایید فیش", f"فیش: {receipt_id}, مبلغ: {amount}")
    
    # اطلاع به کاربر
    try:
        user = get_user(user_id)
        message_text = f"✅ فیش واریزی #{receipt_id} شما تایید شد و {amount:,.0f} Tether به موجودی شما اضافه گردید."
        if admin_desc:
            message_text += f"\n📝 توضیحات مدیر: {admin_desc}"
        
        await bot.send_message(user_id, message_text)
    except:
        await message.answer(f"⚠️ کاربر {user_id} از ربات مسدود کرده است.")

# ======= منوی مدیریت برداشت‌ها =======
@dp.message(UserStates.admin_withdrawals_menu)
async def handle_admin_withdrawals_menu(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "📋 مشاهده درخواست‌ها":
        requests = get_pending_withdrawal_requests()
        if requests:
            for req in requests:
                amount = safe_float(req[2])
                await message.answer(
                    f"💳 درخواست برداشت #{req[0]}\n\n"
                    f"👤 کاربر: {req[7] or 'نامشخص'}\n"
                    f"🆔 آیدی: {req[1]}\n"
                    f"🆔 کد ملی: {req[6] or 'نامشخص'}\n"
                    f"💰 مبلغ درخواستی: {amount:,.0f} Tether\n"
                    f"🔗 آدرس: {req[3]}\n"
                    f"📅 تاریخ: {req[5][:16]}"
                )
        else:
            await message.answer("✅ هیچ درخواست برداشتی در انتظار نیست")
            
    elif text == "✅ تایید برداشت":
        await message.answer("🔢 شماره درخواست برداشت را وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_approve_withdrawal)
        
    elif text == "❌ رد برداشت":
        await message.answer("🔢 شماره درخواست برداشت را وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_reject_withdrawal)
        
    elif text == "🔙 بازگشت به منوی اصلی":
        await message.answer("منوی اصلی", reply_markup=admin_menu_markup())
        await state.set_state(UserStates.admin_menu)
        
    else:
        await message.answer("❌ گزینه نامعتبر")

# ======= تایید برداشت - مرحله اول (دریافت شماره درخواست) =======
@dp.message(UserStates.admin_approve_withdrawal)
async def handle_approve_withdrawal(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_withdrawals_markup())
        await state.set_state(UserStates.admin_withdrawals_menu)
        return
        
    try:
        request_id = int(message.text)
        
        # بررسی وجود درخواست
        cursor.execute("SELECT * FROM withdrawal_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        
        if not req:
            await message.answer("❌ درخواست برداشت یافت نشد. شماره صحیح وارد کنید:")
            return
        
        await state.update_data(request_id=request_id)
        await message.answer("💰 مبلغ برداشت را به Tether وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_withdrawal_amount)
            
    except ValueError:
        await message.answer("❌ شماره درخواست باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= تایید برداشت - مرحله دوم (دریافت مبلغ) =======
@dp.message(UserStates.admin_withdrawal_amount)
async def handle_withdrawal_amount_admin(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_withdrawals_markup())
        await state.set_state(UserStates.admin_withdrawals_menu)
        return
        
    try:
        amount = safe_float(message.text)
        if amount <= 0:
            await message.answer("❌ مبلغ باید بیشتر از صفر باشد. لطفاً مجدداً وارد کنید:")
            return
            
        await state.update_data(amount=amount)
        await message.answer("📝 توضیحات برای کاربر (اختیاری):", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_withdrawal_description)
            
    except ValueError:
        await message.answer("❌ مبلغ باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= تایید برداشت - مرحله سوم (دریافت توضیحات) =======
@dp.message(UserStates.admin_withdrawal_description)
async def handle_withdrawal_description(message: types.Message, state: FSMContext):
    description = message.text
    data = await state.get_data()
    request_id = data['request_id']
    amount = data['amount']
    
    # تایید برداشت
    update_withdrawal_request(request_id, 'approved')
    
    # اضافه کردن تراکنش
    cursor.execute("SELECT telegram_id, amount FROM withdrawal_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()
    user_id = req[0]
    requested_amount = req[1]
    
    transaction_description = f"تایید برداشت #{request_id}"
    if description and description != "❌ لغو عملیات":
        transaction_description += f" - {description}"
    
    add_transaction(user_id, 'withdrawal', amount, transaction_description, 'completed')
    
    # کاهش موجودی کاربر
    cursor.execute("UPDATE users SET balance = balance - ?, total_withdrawal = total_withdrawal + ? WHERE telegram_id = ?", 
                  (amount, amount, user_id))
    conn.commit()
    
    await message.answer(
        f"✅ درخواست برداشت تایید شد\n\n"
        f"🔢 شماره: #{request_id}\n"
        f"💰 مبلغ درخواستی: {safe_float(requested_amount):,.0f} Tether\n"
        f"💰 مبلغ پرداختی: {amount:,.0f} Tether\n"
        f"📝 توضیحات: {description if description and description != '❌ لغو عملیات' else 'بدون توضیح'}\n"
        f"👤 کاربر: {user_id}",
        reply_markup=admin_withdrawals_markup()
    )
    await state.set_state(UserStates.admin_withdrawals_menu)
    log_action(message.from_user.id, "تایید برداشت", f"درخواست: {request_id}, مبلغ: {amount}")
    
    # اطلاع به کاربر
    try:
        message_text = f"✅ درخواست برداشت #{request_id} شما تایید شد.\n💰 مبلغ پرداختی: {amount:,.0f} Tether"
        if description and description != "❌ لغو عملیات":
            message_text += f"\n📝 توضیحات مدیر: {description}"
        
        await bot.send_message(user_id, message_text)
    except:
        pass

# ======= رد برداشت =======
@dp.message(UserStates.admin_reject_withdrawal)
async def handle_reject_withdrawal(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_withdrawals_markup())
        await state.set_state(UserStates.admin_withdrawals_menu)
        return
        
    try:
        request_id = int(message.text)
        
        # بررسی وجود درخواست
        cursor.execute("SELECT * FROM withdrawal_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        
        if not req:
            await message.answer("❌ درخواست برداشت یافت نشد. شماره صحیح وارد کنید:")
            return
        
        update_withdrawal_request(request_id, 'rejected')
        add_transaction(req[1], 'withdrawal', req[2], f'رد برداشت #{request_id} توسط ادمین', 'rejected')
        
        await message.answer(
            f"❌ درخواست برداشت رد شد\n\n"
            f"🔢 شماره: #{request_id}\n"
            f"💰 مبلغ درخواستی: {safe_float(req[2]):,.0f} Tether\n"
            f"👤 کاربر: {req[1]}",
            reply_markup=admin_withdrawals_markup()
        )
        await state.set_state(UserStates.admin_withdrawals_menu)
        log_action(message.from_user.id, "رد برداشت", f"درخواست: {request_id}")
        
        # اطلاع به کاربر
        try:
            await bot.send_message(req[1], f"❌ درخواست برداشت #{request_id} شما به مبلغ {safe_float(req[2]):,.0f} Tether رد شد.")
        except:
            pass
            
    except ValueError:
        await message.answer("❌ شماره درخواست باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= افزایش موجودی - مرحله اول (دریافت آیدی کاربر) =======
@dp.message(UserStates.admin_add_balance_user)
async def handle_add_balance_user(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_menu_markup())
        await state.set_state(UserStates.admin_menu)
        return
        
    try:
        user_id = int(message.text)
        user = get_user(user_id)
        
        if not user:
            await message.answer("❌ کاربر یافت نشد. لطفاً آیدی صحیح وارد کنید:")
            return
        
        await state.update_data(selected_user=user_id)
        await message.answer(
            f"💰 مبلغ افزایش موجودی را برای کاربر زیر وارد کنید (Tether):\n\n"
            f"👤 کاربر: {user[11] or 'نامشخص'}\n"
            f"🆔 آیدی: {user_id}",
            reply_markup=cancel_markup()
        )
        await state.set_state(UserStates.admin_add_balance_amount)
            
    except ValueError:
        await message.answer("❌ آیدی باید یک عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= افزایش موجودی - مرحله دوم (دریافت مبلغ) =======
@dp.message(UserStates.admin_add_balance_amount)
async def handle_add_balance_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_menu_markup())
        await state.set_state(UserStates.admin_menu)
        return
        
    try:
        amount = safe_float(message.text)
        data = await state.get_data()
        user_id = data.get('selected_user')
        
        if amount <= 0:
            await message.answer("❌ مبلغ باید بیشتر از صفر باشد. لطفاً مجدداً وارد کنید:")
            return
        
        user = get_user(user_id)
        update_user_balance(user_id, amount)
        add_transaction(user_id, 'deposit', amount, 'افزایش موجودی توسط ادمین', 'completed')
        
        await message.answer(
            f"✅ موجودی کاربر افزایش یافت\n\n"
            f"👤 کاربر: {user[11] or 'نامشخص'}\n"
            f"🆔 آیدی: {user_id}\n"
            f"💰 مبلغ: {amount:,.0f} Tether",
            reply_markup=admin_menu_markup()
        )
        await state.set_state(UserStates.admin_menu)
        log_action(message.from_user.id, "افزایش موجودی", f"کاربر: {user_id}, مبلغ: {amount}")
        
        # اطلاع به کاربر
        try:
            await bot.send_message(user_id, f"✅ موجودی شما به میزان {amount:,.0f} Tether افزایش یافت.")
        except:
            pass
            
    except ValueError:
        await message.answer("❌ مبلغ باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= مدیریت کاربران ادمین =======
@dp.message(UserStates.admin_manage_users)
async def handle_admin_users(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "📋 لیست تمام کاربران":
        users = get_all_users()
        if users:
            for user in users[:10]:
                balance = safe_float(user[4])
                status = "✅ فعال" if user[14] else "❌ غیرفعال"
                user_text = f"""
👤 کاربر #{user[0]}
🆔 آیدی تلگرام: {user[1]}
📛 نام: {user[11] or 'تعیین نشده'}
📞 تلفن: {user[10] or 'تعیین نشده'}
🆔 کد ملی: {user[2]}
💰 موجودی: {balance:,.0f} Tether
📅 عضویت: {user[12][:10]}
🔍 وضعیت: {status}
                """
                await message.answer(user_text)
                
            if len(users) > 10:
                await message.answer(f"📋 نمایش 10 کاربر از {len(users)} کاربر")
        else:
            await message.answer("👥 هیچ کاربری وجود ندارد")
            
    elif text == "🔍 جستجوی کاربر":
        await message.answer("🆔 آیدی تلگرام کاربر را وارد کنید:", reply_markup=cancel_markup())
        await state.update_data(search_mode=True)
        
    elif text == "✏️ ویرایش کاربر":
        await message.answer("🆔 آیدی تلگرام کاربر را وارد کنید:", reply_markup=cancel_markup())
        await state.update_data(edit_mode=True)
        
    elif text == "📊 آمار کاربران":
        cursor.execute("SELECT COUNT(*), SUM(balance), AVG(balance) FROM users")
        stats = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(registration_date) = DATE('now')")
        today_reg = cursor.fetchone()[0] or 0
        
        total_balance = safe_float(stats[1])
        avg_balance = safe_float(stats[2])
        
        stats_text = f"""
📊 آمار کاربران

👥 تعداد کل کاربران: {stats[0] or 0}
💰 مجموع موجودی: {total_balance:,.0f} Tether
📊 میانگین موجودی: {avg_balance:,.0f} Tether
📈 ثبت نام امروز: {today_reg}
        """
        await message.answer(stats_text)
        
    elif text == "🔙 بازگشت به منوی اصلی":
        await message.answer("منوی اصلی", reply_markup=admin_menu_markup())
        await state.set_state(UserStates.admin_menu)
        
    else:
        data = await state.get_data()
        if data.get('search_mode'):
            try:
                user_id = int(message.text)
                user = get_user(user_id)
                if user:
                    balance = safe_float(user[4])
                    status = "✅ فعال" if user[14] else "❌ غیرفعال"
                    user_text = f"""
👤 کاربر #{user[0]}
🆔 آیدی تلگرام: {user[1]}
📛 نام: {user[11] or 'تعیین نشده'}
📞 تلفن: {user[10] or 'تعیین نشده'}
🆔 کد ملی: {user[2]}
💰 موجودی: {balance:,.0f} Tether
📅 عضویت: {user[12][:10]}
🔍 وضعیت: {status}
                    """
                    await message.answer(user_text)
                else:
                    await message.answer("❌ کاربر یافت نشد.")
            except ValueError:
                await message.answer("❌ آیدی باید عددی باشد.")
            await state.update_data(search_mode=False)
            
        elif data.get('edit_mode'):
            try:
                user_id = int(message.text)
                user = get_user(user_id)
                if user:
                    balance = safe_float(user[4])
                    status = "✅ فعال" if user[14] else "❌ غیرفعال"
                    user_text = f"""
👤 کاربر #{user[0]}
🆔 آیدی تلگرام: {user[1]}
📛 نام: {user[11] or 'تعیین نشده'}
📞 تلفن: {user[10] or 'تعیین نشده'}
🆔 کد ملی: {user[2]}
💰 موجودی: {balance:,.0f} Tether
📅 عضویت: {user[12][:10]}
🔍 وضعیت: {status}
                    """
                    await message.answer(user_text, reply_markup=admin_edit_user_markup())
                    await state.update_data(edit_user_id=user_id)
                    await state.set_state(UserStates.admin_edit_user)
                else:
                    await message.answer("❌ کاربر یافت نشد.")
            except ValueError:
                await message.answer("❌ آیدی باید عددی باشد.")
            await state.update_data(edit_mode=False)
        else:
            await message.answer("❌ گزینه نامعتبر")

# ======= ویرایش کاربر =======
@dp.message(UserStates.admin_edit_user)
async def handle_admin_edit_user(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "💰 تغییر موجودی":
        await message.answer("💰 موجودی جدید را وارد کنید (Tether):", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_edit_user_balance)
        
    elif text == "👤 تغییر اطلاعات کاربر":
        await message.answer("📛 نام جدید کاربر را وارد کنید (برای عدم تغییر، '-' وارد کنید):", reply_markup=cancel_markup())
        await state.set_state(UserStates.admin_edit_user_info)
        
    elif text == "🔙 بازگشت به مدیریت کاربران":
        await message.answer("مدیریت کاربران", reply_markup=admin_users_markup())
        await state.set_state(UserStates.admin_manage_users)
        
    else:
        await message.answer("❌ گزینه نامعتبر")

# ======= تغییر موجودی کاربر =======
@dp.message(UserStates.admin_edit_user_balance)
async def handle_admin_edit_user_balance(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_edit_user_markup())
        await state.set_state(UserStates.admin_edit_user)
        return
        
    try:
        new_balance = safe_float(message.text)
        data = await state.get_data()
        user_id = data.get('edit_user_id')
        
        if new_balance < 0:
            await message.answer("❌ موجودی نمی‌تواند منفی باشد. لطفاً مجدداً وارد کنید:")
            return
        
        set_user_balance(user_id, new_balance)
        user = get_user(user_id)
        
        await message.answer(
            f"✅ موجودی کاربر با موفقیت تغییر یافت\n\n"
            f"👤 کاربر: {user[11] or 'نامشخص'}\n"
            f"🆔 آیدی: {user_id}\n"
            f"💰 موجودی جدید: {new_balance:,.0f} Tether",
            reply_markup=admin_edit_user_markup()
        )
        await state.set_state(UserStates.admin_edit_user)
        log_action(message.from_user.id, "تغییر موجودی کاربر", f"کاربر: {user_id}, موجودی جدید: {new_balance}")
        
    except ValueError:
        await message.answer("❌ مبلغ باید عدد باشد. لطفاً مجدداً وارد کنید:")

# ======= تغییر اطلاعات کاربر =======
@dp.message(UserStates.admin_edit_user_info)
async def handle_admin_edit_user_info(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_edit_user_markup())
        await state.set_state(UserStates.admin_edit_user)
        return
        
    new_full_name = message.text.strip()
    data = await state.get_data()
    user_id = data.get('edit_user_id')
    
    await state.update_data(new_full_name=new_full_name)
    await message.answer("📞 شماره تلفن جدید را وارد کنید (برای عدم تغییر، '-' وارد کنید):", reply_markup=cancel_markup())

@dp.message(UserStates.admin_edit_user_info)
async def handle_admin_edit_user_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_edit_user_markup())
        await state.set_state(UserStates.admin_edit_user)
        return
        
    new_phone = message.text.strip()
    data = await state.get_data()
    user_id = data.get('edit_user_id')
    new_full_name = data.get('new_full_name')
    
    await state.update_data(new_phone=new_phone)
    await message.answer("🆔 کد ملی جدید را وارد کنید (برای عدم تغییر، '-' وارد کنید):", reply_markup=cancel_markup())

@dp.message(UserStates.admin_edit_user_info)
async def handle_admin_edit_user_national_id(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=admin_edit_user_markup())
        await state.set_state(UserStates.admin_edit_user)
        return
        
    new_national_id = message.text.strip()
    data = await state.get_data()
    user_id = data.get('edit_user_id')
    new_full_name = data.get('new_full_name')
    new_phone = data.get('new_phone')
    
    # آماده‌سازی داده‌ها برای به‌روزرسانی
    update_data = {}
    if new_full_name != '-':
        update_data['full_name'] = new_full_name
    if new_phone != '-':
        update_data['phone_number'] = new_phone
    if new_national_id != '-':
        update_data['national_id'] = new_national_id
    
    # به‌روزرسانی پروفایل کاربر
    update_user_profile(user_id, 
                       update_data.get('full_name', ''), 
                       update_data.get('phone_number', ''), 
                       update_data.get('national_id', ''))
    
    user = get_user(user_id)
    
    await message.answer(
        f"✅ اطلاعات کاربر با موفقیت تغییر یافت\n\n"
        f"👤 کاربر: {user[11] or 'نامشخص'}\n"
        f"🆔 آیدی: {user_id}\n"
        f"📛 نام: {user[11] or 'تعیین نشده'}\n"
        f"📞 تلفن: {user[10] or 'تعیین نشده'}\n"
        f"🆔 کد ملی: {user[2]}",
        reply_markup=admin_edit_user_markup()
    )
    await state.set_state(UserStates.admin_edit_user)
    log_action(message.from_user.id, "تغییر اطلاعات کاربر", f"کاربر: {user_id}")

# ======= منوی کاربر =======
@dp.message(UserStates.logged_in)
async def handle_user_menu(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user = get_user(message.from_user.id)
    
    if text == "📊 پروفایل و موجودی":
        balance = safe_float(user[4])
        total_deposit = safe_float(user[5])
        total_withdrawal = safe_float(user[8])
        total_profit = safe_float(user[6])
        
        profile_text = f"""
👤 پروفایل کاربری:

🆔 آیدی تلگرام: {user[1]}
📛 نام کامل: {user[11] or 'تعیین نشده'}
📞 تلفن: {user[10] or 'تعیین نشده'}
🆔 کد ملی: {user[2]}
💰 موجودی: {balance:,.0f} Tether
📥 مجموع واریز: {total_deposit:,.0f} Tether
📤 مجموع برداشت: {total_withdrawal:,.0f} Tether
💸 سود کل: {total_profit:,.0f} Tether
📅 تاریخ ثبت نام: {user[12][:10] if user[12] else 'نامشخص'}
        """
        await message.answer(profile_text)

    elif text == "💵 آپلود فیش واریزی":
        await message.answer("• آدرس کیف پول جهت انتقال تتر در شبکهTRC20:", reply_markup=cancel_markup())
        await message.answer("TXkkpoPZRQZYXr7FYC9NFjxwhN1eccdRUu", reply_markup=cancel_markup())
        await message.answer("📸 لطفاً عکس فیش واریزی را ارسال کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.waiting_photo)
        
    elif text == "💳 نحوه واریز و سرمایه‌گذاری":
        guide_text = """
📋 راهنمای کامل واریز و سرمایه‌گذاری:

مرحله ۱: 🏦 آماده‌سازی مبلغ
• مبلغ مورد نظر برای سرمایه‌گذاری را به تومان آماده کنید

مرحله ۲: 💰 خرید تتر (USDT)
• به یکی از صرافی‌های معتبر ایرانی مراجعه کنید
• مبلغ تومانی خود را به تتر تبدیل کنید
• مطمئن شوید شبکه انتقال TRC20 باشد

مرحله ۳: 🔐 دریافت آدرس کیف پول
• آدرس کیف پول تتر (TRC20) ما:
<code>TXkkpoPZRQZYXr7FYC9NFjxwhN1eccdRUu</code>
• روی آدرس کلیک کنید تا کپی شود
• آدرس دریافتی را در صرافی وارد کنید

مرحله ۴: 📤 انتقال تتر
• تترها را به آدرس دریافتی انتقال دهید
• حتماً از شبکه TRC20 استفاده کنید
• فیلم آموزش ثبت نام و انتقال تتر به کیف پول 
   <code>https://www.aparat.com/v/cgqslmp</code>
• روی آدرس کلید کنید تا کپی شود میتوانید در مرورگر فیلم را از آپارات ببینید

مرحله ۵: 📸 آپلود فیش
• پس از انتقال و تایید انتقال در صرافی فیش واریزی که شاملTXID میباشدرا بعنوان عکس ذخیره کنید و آماده ارسال نمایید
• به بخش «آپلود فیش واریزی» مراجعه کنید
• عکس فیش را آپلود کنید

مرحله ۶: ⏳ انتظار برای تایید
• پس از آپلود فیش، منتظر تایید ادمین باشید
• پس از تایید، موجودی شما به روز می‌شود

💰 اطلاعات سرمایه‌گذاری:
• سود ماهیانه: 20% 
• حداقل سرمایه گذاری: 30 تتر معادل حدودا 3 میلیون تومان میباشد
• شروع سود دهی با رسیدن واریز شما به مبلغ 30 تتر آغاز میشود 
• پرداخت سود : 30 روز پس از شروع سرمایه گذاری و هر 30 روز میباشد درخواستهای قبل از 30 روز رد میشوند

⚠️ نکات مهم:
• فقط از شبکه TRC20 استفاده کنید
• از صحت آدرس کیف پول اطمینان حاصل کنید
• پس از واریز حتماً فیش را آپلود کنید
• در صورت مشکل در واریز یا برداشت متنی نوشته و تبدیل به عکس نمایید و بعنوان فیش واریز آپلود نمایید

برای شروع، به بخش «آپلود فیش واریزی» مراجعه کنید.
        """
        await message.answer(guide_text, parse_mode='HTML')
        
    elif text == "📈 سود و سرمایه‌گذاری":
        balance = safe_float(user[4])
        total_profit = safe_float(user[6])
        profit = balance * 0.2
        
        profit_text = f"""
📈 وضعیت سوددهی:

💰 موجودی فعلی: {balance:,.0f} Tether
💵 سود ماهیانه: {profit:,.0f} Tether
📊 سود کل: {total_profit:,.0f} Tether
🎯 درصد سود: 20% ماهیانه
        """
        await message.answer(profit_text)
        
    elif text == "🏦 درخواست برداشت":
        await message.answer("💳 مقدار برداشت را به Tether وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.waiting_withdrawal_amount)
        
    elif text == "📋 تراکنش‌ها":
        await message.answer("📊 مدیریت تراکنش‌ها", reply_markup=transactions_markup())
        await state.set_state(UserStates.viewing_transactions)
        
    elif text == "👤 ویرایش پروفایل":
        await message.answer("📛 نام کامل خود را وارد کنید:", reply_markup=cancel_markup())
        await state.set_state(UserStates.waiting_full_name)
        
    elif text == "🔑 تغییر رمز عبور":
        await message.answer("🔐 رمز جدید را وارد کنید (حداقل ۴ کاراکتر):", reply_markup=cancel_markup())
        await state.set_state(UserStates.waiting_new_password)
        
    elif text == "🚪 خروج":
        await message.answer("👋 با موفقیت خارج شدید.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
    elif text == "🔄 شروع مجدد":
        await message.answer("🔄 ربات از نو شروع شد.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        await cmd_start(message, state)
        
    else:
        await message.answer("❌ گزینه نامعتبر")

# ======= منوی تراکنش‌ها =======
@dp.message(UserStates.viewing_transactions)
async def handle_transactions_menu(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    
    if text == "📥 واریزها":
        deposits = get_user_deposit_receipts(user_id, 10)
        if deposits:
            deposits_text = "📥 آخرین واریزها:\n\n"
            for deposit in deposits:
                status_icon = "✅" if deposit[4] == 'approved' else "⏳" if deposit[4] == 'pending' else "❌"
                amount = safe_float(deposit[3])
                status_text = "تایید شده" if deposit[4] == 'approved' else "در انتظار" if deposit[4] == 'pending' else "رد شده"
                
                deposits_text += f"{status_icon} واریز #{deposit[0]}\n"
                deposits_text += f"💰 مبلغ: {amount:,.0f} Tether\n"
                deposits_text += f"📊 وضعیت: {status_text}\n"
                
                if deposit[5]:  # admin_description
                    deposits_text += f"📝 توضیحات: {deposit[5]}\n"
                
                deposits_text += f"📅 تاریخ: {deposit[6][:16]}\n\n"
            
            await message.answer(deposits_text)
        else:
            await message.answer("📭 هیچ واریزی یافت نشد.")
            
    elif text == "📤 برداشت‌ها":
        withdrawals = get_user_withdrawal_requests(user_id, 10)
        if withdrawals:
            withdrawals_text = "📤 آخرین برداشت‌ها:\n\n"
            for withdrawal in withdrawals:
                status_icon = "✅" if withdrawal[4] == 'approved' else "⏳" if withdrawal[4] == 'pending' else "❌"
                amount = safe_float(withdrawal[2])
                status_text = "تایید شده" if withdrawal[4] == 'approved' else "در انتظار" if withdrawal[4] == 'pending' else "رد شده"
                
                withdrawals_text += f"{status_icon} برداشت #{withdrawal[0]}\n"
                withdrawals_text += f"💰 مبلغ: {amount:,.0f} Tether\n"
                withdrawals_text += f"📊 وضعیت: {status_text}\n"
                withdrawals_text += f"🔗 آدرس: {withdrawal[3][:20]}...\n"
                withdrawals_text += f"📅 تاریخ: {withdrawal[5][:16]}\n\n"
            
            await message.answer(withdrawals_text)
        else:
            await message.answer("📭 هیچ برداشتی یافت نشد.")
            
    elif text == "📊 آمار تراکنش‌ها":
        stats = get_transaction_stats(user_id)
        stats_text = f"""
📊 آمار تراکنش‌های شما:

📈 تعداد کل تراکنش‌ها: {stats['total_transactions']}
📥 تعداد واریزها: {stats['deposit_count']}
📤 تعداد برداشت‌ها: {stats['withdrawal_count']}
📥 مجموع واریزها: {stats['total_deposit']:,.0f} Tether
📤 مجموع برداشت‌ها: {stats['total_withdrawal']:,.0f} Tether
⏳ واریزهای در انتظار: {stats['pending_deposits']}
⏳ برداشت‌های در انتظار: {stats['pending_withdrawals']}
        """
        await message.answer(stats_text)
        
    elif text == "📋 همه تراکنش‌ها":
        transactions = get_user_transactions(user_id, 15)
        if transactions:
            transactions_text = "📋 آخرین تراکنش‌ها:\n\n"
            for t in transactions:
                status_icon = "✅" if t[6] == 'completed' else "⏳" if t[6] == 'pending' else "❌"
                type_icon = "💵" if t[3] == 'deposit' else "💳"
                amount = safe_float(t[4])
                
                transactions_text += f"{status_icon}{type_icon} {t[3]}\n"
                transactions_text += f"💰 مبلغ: {amount:,.0f} Tether\n"
                transactions_text += f"📝 توضیحات: {t[5]}\n"
                transactions_text += f"📅 تاریخ: {t[7][:16]}\n\n"
            
            await message.answer(transactions_text)
        else:
            await message.answer("📭 هیچ تراکنشی یافت نشد.")
            
    elif text == "🔙 بازگشت به منوی اصلی":
        await message.answer("منوی اصلی", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        
    else:
        await message.answer("❌ گزینه نامعتبر")

# ======= دریافت عکس فیش =======
@dp.message(UserStates.waiting_photo)
async def handle_photo_upload(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        return
        
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        # اضافه کردن فیش به جدول deposit_receipts
        receipt_id = add_deposit_receipt(message.from_user.id, photo_file_id)
        
        add_transaction(message.from_user.id, 'deposit', 0, f'آپلود فیش واریزی #{receipt_id} - در انتظار تایید', 'pending')
        
        await message.answer(
            f"✅ فیش واریزی با موفقیت آپلود شد\n\n"
            f"🔢 شماره فیش: #{receipt_id}\nتایید فیش ممکن است 24 ساعت طول بکشد\n\n"
            f"⏳ منتظر تایید ادمین باشید", 
            reply_markup=user_menu_markup()
        )
        await state.set_state(UserStates.logged_in)
        log_action(message.from_user.id, "آپلود فیش واریزی", f"شماره فیش: {receipt_id}")
        
        # اطلاع به ادمین
        try:
            user = get_user(message.from_user.id)
            await bot.send_message(
                ADMIN_TELEGRAM_ID,
                f"📥 فیش واریزی جدید #{receipt_id}\n\n👤 کاربر: {user[11] or 'نامشخص'}\n🆔 آیدی: {message.from_user.id}\n🆔 کد ملی: {user[2]}"
            )
        except:
            pass
    else:
        await message.answer("❌ لطفاً یک عکس ارسال کنید:")

# ======= دریافت مقدار برداشت =======
@dp.message(UserStates.waiting_withdrawal_amount)
async def handle_withdrawal_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        return
        
    try:
        amount = safe_float(message.text)
        user = get_user(message.from_user.id)
        balance = safe_float(user[4])
        
        if amount <= 0:
            await message.answer("❌ مقدار باید بیشتر از صفر باشد:")
            return
            
        if balance >= amount:
            await message.answer("🔗 آدرس ولت Tether (TRC20) خود را وارد کنید:", reply_markup=cancel_markup())
            await state.update_data(withdrawal_amount=amount)
            await state.set_state(UserStates.waiting_wallet_address)
        else:
            await message.answer(f"❌ موجودی کافی نیست. موجودی شما: {balance:,.0f} Tether\n\nمقدار جدید وارد کنید:")
            
    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید:")

@dp.message(UserStates.waiting_wallet_address)
async def handle_wallet_address(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        return
        
    wallet_address = message.text.strip()
    data = await state.get_data()
    amount = data['withdrawal_amount']
    
    if len(wallet_address) < 10:
        await message.answer("❌ آدرس ولت نامعتبر است. دوباره وارد کنید:")
        return
    
    request_id = add_withdrawal_request(message.from_user.id, amount, wallet_address)
    add_transaction(message.from_user.id, 'withdrawal', amount, f'درخواست برداشت #{request_id} - در انتظار تایید', 'pending')
    
    await message.answer(
        f"✅ درخواست برداشت شما ثبت شد\n\n"
        f"🔢 شماره درخواست: #{request_id}\n"
        f"💳 مبلغ: {amount:,.0f} Tether\n"
        f"🔗 آدرس: {wallet_address}\n\n"
        f"⏳ منتظر تایید ادمین باشید",
        reply_markup=user_menu_markup()
    )
    await state.set_state(UserStates.logged_in)
    log_action(message.from_user.id, "ثبت درخواست برداشت", f"شماره: {request_id}, مبلغ: {amount}")
    
    # اطلاع به ادمین
    try:
        user = get_user(message.from_user.id)
        await bot.send_message(
            ADMIN_TELEGRAM_ID,
            f"📤 درخواست برداشت جدید #{request_id}\n\n👤 کاربر: {user[11] or 'نامشخص'}\n🆔 آیدی: {message.from_user.id}\n🆔 کد ملی: {user[2]}\n💰 مبلغ: {amount:,.0f} Tether"
        )
    except:
        pass

# ======= تغییر رمز عبور =======
@dp.message(UserStates.waiting_new_password)
async def handle_password_change(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        return
        
    new_password = message.text.strip()
    if len(new_password) < 4:
        await message.answer("❌ رمز باید حداقل ۴ کاراکتر باشد:")
        return
        
    update_user_password(message.from_user.id, new_password)
    await message.answer("✅ رمز عبور با موفقیت تغییر یافت", reply_markup=user_menu_markup())
    await state.set_state(UserStates.logged_in)
    log_action(message.from_user.id, "تغییر رمز عبور")

# ======= ویرایش پروفایل =======
@dp.message(UserStates.waiting_full_name)
async def handle_full_name(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        return
        
    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer("❌ نام باید حداقل ۲ کاراکتر باشد:")
        return
        
    await state.update_data(full_name=full_name)
    await message.answer("📞 شماره تلفن خود را وارد کنید:", reply_markup=cancel_markup())
    await state.set_state(UserStates.waiting_phone)

@dp.message(UserStates.waiting_phone)
async def handle_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ لغو عملیات":
        await message.answer("❌ عملیات لغو شد.", reply_markup=user_menu_markup())
        await state.set_state(UserStates.logged_in)
        return
        
    phone = message.text.strip()
    data = await state.get_data()
    full_name = data['full_name']
    
    update_user_profile(message.from_user.id, full_name, phone)
    
    await message.answer(
        f"✅ پروفایل با موفقیت به روز شد\n\n"
        f"📛 نام: {full_name}\n"
        f"📞 تلفن: {phone}",
        reply_markup=user_menu_markup()
    )
    await state.set_state(UserStates.logged_in)
    log_action(message.from_user.id, "ویرایش پروفایل", f"نام: {full_name}, تلفن: {phone}")

# ======= هندلر ریستارت =======
@dp.message(lambda message: "ریستارت" in message.text.lower() or "restart" in message.text.lower())
async def handle_restart(message: types.Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)

# ======= هندلر پیش‌فرض =======
@dp.message()
async def handle_default(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    # اگر کاربر در حالت لاگین باشد و پیام نامعتبر بفرستد
    if current_state == UserStates.logged_in:
        await message.answer("❌ گزینه نامعتبر. لطفاً از منوی زیر استفاده کنید:", reply_markup=user_menu_markup())
    elif current_state == UserStates.admin_menu:
        await message.answer("❌ گزینه نامعتبر. لطفاً از منوی مدیریت استفاده کنید:", reply_markup=admin_menu_markup())
    else:
        # در سایر حالت‌ها ربات را ریستارت کن
        await message.answer("🔄 ربات ریستارت شد...")
        await state.clear()
        await cmd_start(message, state)

# ======= راه‌اندازی ربات =======
async def main():
    print("🤖 ربات کامل مدیریت سرمایه‌گذاری فعال شد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())