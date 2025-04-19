# === 🧱 БЛОК 1: Импорты, Конфигурация, База Данных ===

import logging
import sqlite3
from datetime import datetime, timedelta
from dateutil import parser as dateparser  # для гибкого парсинга дат

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    JobQueue
)

# === Токен и имя администратора ===
TOKEN = "7834717272:AAET3xhf3VkMV6PqQ2ClydpKEQDyD-PYt4I"
ADMIN_USERNAME = "prakhova"

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Подключение к базе данных ===
conn = sqlite3.connect("wishlist.db", check_same_thread=False)
c = conn.cursor()

# === Таблица товаров ===
c.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    price INTEGER,
    url TEXT,
    photo1 TEXT,
    photo2 TEXT,
    booked_by TEXT,
    booked_anonymously INTEGER DEFAULT 0,
    booked_at TEXT
)
""")

# === Таблица напоминаний ===
c.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    item_id INTEGER,
    remind_at TEXT,
    confirmed TEXT DEFAULT NULL,
    asked INTEGER DEFAULT 0
)
""")

# === Таблица логов (для админа) ===
c.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    user TEXT,
    item_id INTEGER,
    timestamp TEXT
)
""")

conn.commit()

# === 🔚 КОНЕЦ БЛОКА 1 ===
# === 🧱 БЛОК 2: Команда /start и Главное меню ===

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("$20", callback_data="price:20")],
        [InlineKeyboardButton("$50", callback_data="price:50")],
        [InlineKeyboardButton("$100", callback_data="price:100")],
        [InlineKeyboardButton("$200", callback_data="price:200")],
        [InlineKeyboardButton("$500", callback_data="price:500")],
        [InlineKeyboardButton("$1000", callback_data="price:1000")],
        [InlineKeyboardButton("> $1000", callback_data="price:above_1000")],
        [InlineKeyboardButton("💰 Enter manually", callback_data="manual_input")],
        [InlineKeyboardButton("📦 View All Items", callback_data="view_all")],
        [InlineKeyboardButton("📋 My Bookings", callback_data="my_bookings")],
        [InlineKeyboardButton("💸 Support Adriana", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎀 <b>Hi! This is Adriana Prakhova’s wishlist!</b> 🎀\n"
        "Want to make me smile with a gift 🎁?\n"
        "Choose your budget below 💸👇",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# Обработка кнопки "⬅️ Вернуться в меню"
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await start(update.callback_query, context)

# Обработка кнопки "⬅️ Вернуться к бюджету"
async def return_to_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await start(update.callback_query, context)

# === 🔚 КОНЕЦ БЛОКА 2 ===
# === 🧱 БЛОК 3: Добавление товара — Команда /add ===

# Этапы добавления товара
ADD_PHOTO1, ADD_PHOTO2, ADD_TITLE, ADD_DESC, ADD_PRICE, ADD_URL = range(6)

# Старт команды /add
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⛔ Only admin can add items.")
        return ConversationHandler.END

    await update.message.reply_text("📸 Send first photo of the item (or type 'skip'):")
    return ADD_PHOTO1

# Получение первого фото
async def add_photo1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["photo1"] = update.message.photo[-1].file_id
    else:
        context.user_data["photo1"] = None

    await update.message.reply_text("📸 Send second photo (or type 'skip'):")
    return ADD_PHOTO2

# Получение второго фото
async def add_photo2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["photo2"] = update.message.photo[-1].file_id
    else:
        context.user_data["photo2"] = None

    await update.message.reply_text("📝 Enter title of the item:")
    return ADD_TITLE

# Получение названия
async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("📄 Enter description of the item:")
    return ADD_DESC

# Получение описания
async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("💰 Enter price (in USD):")
    return ADD_PRICE

# Получение цены
async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
        context.user_data["price"] = price
        await update.message.reply_text("🔗 Enter purchase URL:")
        return ADD_URL
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for the price:")
        return ADD_PRICE

# Получение ссылки и сохранение товара
async def add_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["url"] = update.message.text

    c.execute("""
        INSERT INTO items (title, description, price, url, photo1, photo2)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        context.user_data["title"],
        context.user_data["description"],
        context.user_data["price"],
        context.user_data["url"],
        context.user_data["photo1"],
        context.user_data["photo2"]
    ))
    conn.commit()

    await update.message.reply_text("✅ Item successfully added!")
    return ConversationHandler.END

# Обработка отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Canceled.")
    return ConversationHandler.END

# === ConversationHandler: /add ===
add_conv = ConversationHandler(
    entry_points=[CommandHandler("add", add_start)],
    states={
        ADD_PHOTO1: [MessageHandler(filters.PHOTO | filters.TEXT, add_photo1)],
        ADD_PHOTO2: [MessageHandler(filters.PHOTO | filters.TEXT, add_photo2)],
        ADD_TITLE: [MessageHandler(filters.TEXT, add_title)],
        ADD_DESC: [MessageHandler(filters.TEXT, add_desc)],
        ADD_PRICE: [MessageHandler(filters.TEXT, add_price)],
        ADD_URL: [MessageHandler(filters.TEXT, add_url)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# === 🔚 КОНЕЦ БЛОКА 3 ===
# === 🧱 БЛОК 4: Просмотр и фильтрация товаров ===

# Фильтрация по диапазону
PRICE_RANGES = {
    "$20": (0, 20),
    "$50": (21, 50),
    "$100": (51, 100),
    "$200": (101, 200),
    "$500": (201, 500),
    "$1000": (501, 1000),
    "> $1000": (1001, float("inf"))
}

# Обработка кнопки бюджета
async def price_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    query = update.callback_query.data
    price_key = query.split(":")[1]
    context.user_data["last_price_key"] = price_key  # для возврата

    min_price, max_price = PRICE_RANGES.get(f"${price_key}", (0, float("inf")))
    if price_key == "above_1000":
        min_price, max_price = 1001, float("inf")

    c.execute("SELECT * FROM items")
    all_items = c.fetchall()
    filtered = [
        item for item in all_items
        if item[3] is not None and min_price <= item[3] <= max_price
    ]

    if not filtered:
        await update.callback_query.message.reply_text("❌ No items found for this price range.")
        return

    for item in filtered:
        await send_item_card(update, context, item, is_callback=True)

# Ручной ввод бюджета
async def manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("💬 Please enter your budget manually (USD):")
    context.user_data["manual_budget"] = True

# Обработка текстового бюджета
async def handle_manual_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        c.execute("SELECT * FROM items WHERE price <= ?", (amount,))
        items = c.fetchall()
        if not items:
            await update.message.reply_text("❌ No items found under this amount.")
            return

        for item in items:
            await send_item_card(update, context, item, is_callback=False)

    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number.")

# Отправка карточки товара
async def send_item_card(update: Update, context: ContextTypes.DEFAULT_TYPE, item, is_callback=False):
    item_id, title, desc, price, url, photo1, photo2, booked_by, booked_anon, *_ = item

    # Состояние брони
    status = ""
    if booked_by:
        status = (
            "🛑 <b>ALREADY BOOKED</b>\n"
            if booked_anon else f"🛑 <b>BOOKED by @{booked_by}</b>\n"
        )

    caption = (
        f"{status}"
        f"<b>{title}</b>\n"
        f"💰 ${price}\n"
        f"{desc}\n\n"
        f"🔗 <a href='{url}'>Order Link</a>"
    )

    # Кнопки под товаром
    buttons = []
    if not booked_by:
        buttons.append([
            InlineKeyboardButton("📌 Book", callback_data=f"book:{item_id}"),
            InlineKeyboardButton("🕵️ Book anonymously", callback_data=f"bookanon:{item_id}")
        ])
    else:
        # Если забронировано — кнопка для админа "Подробнее"
        if update.effective_user.username == ADMIN_USERNAME:
            buttons.append([
                InlineKeyboardButton("📊 Details", callback_data=f"details:{item_id}")
            ])

    buttons.append([
        InlineKeyboardButton("⬅️ Back to menu", callback_data="back_to_menu")
    ])

    # Медиа (фото)
    media = []
    if photo1:
        media.append(InputMediaPhoto(media=photo1, caption=caption, parse_mode=ParseMode.HTML))
    if photo2:
        media.append(InputMediaPhoto(media=photo2))

    # Отправка
    if media:
        if is_callback:
            await update.callback_query.message.reply_media_group(media)
            await update.callback_query.message.reply_text("Choose an option below 👇", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_media_group(media)
            await update.message.reply_text("Choose an option below 👇", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        if is_callback:
            await update.callback_query.message.reply_text(
                caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await update.message.reply_text(
                caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
            )

# === 🔚 КОНЕЦ БЛОКА 4 ===
# === 🧱 БЛОК 5: Бронирование, Напоминания, Отмена ===

from datetime import timezone

REMINDER_OPTIONS = [
    ("1 day", 1),
    ("2 days", 2),
    ("7 days", 7),
    ("14 days", 14),
    ("1 month", 30)
]

# 📌 Обработка бронирования
async def book_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    query_data = update.callback_query.data
    anon = query_data.startswith("bookanon")
    item_id = int(query_data.split(":")[1])
    user = update.effective_user

    # Проверим, свободен ли товар
    c.execute("SELECT booked_by FROM items WHERE id = ?", (item_id,))
    res = c.fetchone()
    if res and res[0]:
        await update.callback_query.message.reply_text("❌ This item is already booked.")
        return

    # Обновляем базу
    c.execute("""
        UPDATE items SET booked_by = ?, booked_anonymously = ?, booked_at = ?
        WHERE id = ?
    """, (
        None if anon else user.username,
        1 if anon else 0,
        datetime.utcnow().isoformat(),
        item_id
    ))
    conn.commit()

    # Показываем кнопки напоминания
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"remind:{item_id}:{days}")]
        for label, days in REMINDER_OPTIONS
    ]
    buttons.append([
        InlineKeyboardButton("📅 Set custom date", callback_data=f"remind_custom:{item_id}")
    ])

    await update.callback_query.message.reply_text(
        "✅ Item booked!\n\n⏰ When should I remind you about it?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# 🔔 Напоминание по выбору кнопки
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, item_id, days = update.callback_query.data.split(":")
    item_id = int(item_id)
    days = int(days)
    user_id = update.effective_user.id

    remind_time = (datetime.now(timezone.utc) + timedelta(days=days)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    c.execute("""
        INSERT INTO reminders (user_id, item_id, remind_at)
        VALUES (?, ?, ?)
    """, (user_id, item_id, remind_time.isoformat()))
    conn.commit()

    await update.callback_query.message.reply_text(
        f"⏰ Reminder set! I will remind you on {remind_time.strftime('%Y-%m-%d at %H:%M')}.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add another reminder", callback_data=f"remind_custom:{item_id}")],
            [InlineKeyboardButton("🔁 Change date", callback_data=f"remind_custom:{item_id}")],
            [InlineKeyboardButton("⬅️ Back to menu", callback_data="back_to_menu")]
        ])
    )

# ❌ Отмена бронирования
async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    query_data = update.callback_query.data
    item_id = int(query_data.split(":")[1])
    user = update.effective_user

    # Проверка прав
    c.execute("SELECT booked_by FROM items WHERE id = ?", (item_id,))
    result = c.fetchone()
    if not result:
        await update.callback_query.message.reply_text("❌ Item not found.")
        return

    booked_by = result[0]
    is_admin = user.username == ADMIN_USERNAME

    if booked_by != user.username and not is_admin:
        await update.callback_query.message.reply_text("⛔ You cannot cancel someone else's booking.")
        return

    c.execute("UPDATE items SET booked_by = NULL, booked_anonymously = 0, booked_at = NULL WHERE id = ?", (item_id,))
    c.execute("DELETE FROM reminders WHERE item_id = ?", (item_id,))
    conn.commit()

    await update.callback_query.message.reply_text("✅ Booking canceled.")

# 🔁 Периодическая проверка напоминаний
async def check_reminders(app: Application):
    now = datetime.now(timezone.utc).isoformat()
    c.execute("SELECT id, user_id, item_id FROM reminders WHERE remind_at <= ? AND asked = 0", (now,))
    reminders = c.fetchall()

    for reminder_id, user_id, item_id in reminders:
        c.execute("SELECT title FROM items WHERE id = ?", (item_id,))
        item = c.fetchone()
        if item:
            await app.bot.send_message(user_id, f"⏰ Reminder! Did you buy: {item[0]}?", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data=f"confirm:yes:{item_id}:{reminder_id}")],
                [InlineKeyboardButton("❌ No", callback_data=f"confirm:no:{item_id}:{reminder_id}")]
            ]))
            c.execute("UPDATE reminders SET asked = 1 WHERE id = ?", (reminder_id,))
    conn.commit()

# ✅ Обработка ответа на "Купили ли вы товар?"
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, answer, item_id, reminder_id = update.callback_query.data.split(":")
    item_id = int(item_id)
    reminder_id = int(reminder_id)

    if answer == "yes":
        c.execute("UPDATE items SET booked_by = NULL, booked_anonymously = 0, booked_at = NULL WHERE id = ?", (item_id,))
        c.execute("DELETE FROM reminders WHERE item_id = ?", (item_id,))
        msg = "🎉 Great! Hope it made her smile."
    else:
        msg = "😊 Okay, I’ll remind you again later."

    c.execute("UPDATE reminders SET confirmed = ?, sent = 1 WHERE id = ?", (answer, reminder_id))
    conn.commit()

    await update.callback_query.message.reply_text(msg)

# ⏳ Автоснятие брони через 12ч без ответа
async def auto_cancel_unconfirmed(app: Application):
    check_time = (datetime.utcnow() - timedelta(hours=12)).isoformat()
    c.execute("SELECT item_id FROM reminders WHERE asked = 1 AND confirmed IS NULL AND remind_at <= ?", (check_time,))
    items_to_cancel = c.fetchall()

    for (item_id,) in items_to_cancel:
        c.execute("UPDATE items SET booked_by = NULL, booked_anonymously = 0, booked_at = NULL WHERE id = ?", (item_id,))
        c.execute("DELETE FROM reminders WHERE item_id = ?", (item_id,))
    conn.commit()

# === 🔚 КОНЕЦ БЛОКА 5 ===
# === 🧱 БЛОК 6: Редактирование товара — Команда /edit ===

EDIT_SELECT_ITEM, EDIT_SELECT_FIELD, EDIT_ENTER_NEW = range(20, 23)

# Старт команды /edit
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⛔ Only admin can use /edit.")
        return ConversationHandler.END

    c.execute("SELECT id, title FROM items")
    items = c.fetchall()
    if not items:
        await update.message.reply_text("❌ No items to edit.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(f"{title} (ID {item_id})", callback_data=f"edit_item:{item_id}")]
        for item_id, title in items
    ]

    await update.message.reply_text(
        "🛠️ Select item to edit:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return EDIT_SELECT_ITEM

# Выбор товара
async def edit_choose_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = int(update.callback_query.data.split(":")[1])
    context.user_data["edit_item_id"] = item_id

    buttons = [
        [InlineKeyboardButton("✏️ Title", callback_data="edit_field:title")],
        [InlineKeyboardButton("📄 Description", callback_data="edit_field:description")],
        [InlineKeyboardButton("💰 Price", callback_data="edit_field:price")],
        [InlineKeyboardButton("🔗 URL", callback_data="edit_field:url")],
        [InlineKeyboardButton("📸 Photo 1", callback_data="edit_field:photo1")],
        [InlineKeyboardButton("📸 Photo 2", callback_data="edit_field:photo2")],
        [InlineKeyboardButton("⬅️ Back to menu", callback_data="back_to_menu")]
    ]

    await update.callback_query.message.reply_text(
        "⚙️ What do you want to edit?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return EDIT_SELECT_FIELD

# Выбор поля
async def edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    field = update.callback_query.data.split(":")[1]
    context.user_data["edit_field"] = field

    if field.startswith("photo"):
        await update.callback_query.message.reply_text("📸 Send new photo:")
    else:
        await update.callback_query.message.reply_text("✏️ Send new value:")

    return EDIT_ENTER_NEW

# Сохранение значения
async def edit_save_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item_id = context.user_data["edit_item_id"]
    field = context.user_data["edit_field"]

    if field.startswith("photo") and update.message.photo:
        value = update.message.photo[-1].file_id
    else:
        value = update.message.text

    c.execute(f"UPDATE items SET {field} = ? WHERE id = ?", (value, item_id))
    conn.commit()

    await update.message.reply_text(
        f"✅ {field.capitalize()} updated successfully.\n\n"
        "Do you want to edit something else?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit another field", callback_data=f"edit_item:{item_id}")],
            [InlineKeyboardButton("⬅️ Back to menu", callback_data="back_to_menu")]
        ])
    )
    return ConversationHandler.END

# === ConversationHandler: /edit ===
edit_conv = ConversationHandler(
    entry_points=[CommandHandler("edit", edit_start)],
    states={
        EDIT_SELECT_ITEM: [CallbackQueryHandler(edit_choose_item, pattern="^edit_item:")],
        EDIT_SELECT_FIELD: [CallbackQueryHandler(edit_choose_field, pattern="^edit_field:")],
        EDIT_ENTER_NEW: [MessageHandler(filters.TEXT | filters.PHOTO, edit_save_field)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# === 🔚 КОНЕЦ БЛОКА 6 ===
# === 🧱 БЛОК 7: Поддержка Adriana — "Support" ===

# 📦 Меню поддержки
async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    keyboard = [
        [InlineKeyboardButton("💵 Send USDT (TRC20)", callback_data="donate_usdt")],
        [InlineKeyboardButton("💵 Send USDC (Solana)", callback_data="donate_usdc")],
        [InlineKeyboardButton("⬅️ Back to menu", callback_data="back_to_menu")]
    ]
    await update.callback_query.message.reply_text(
        "💖 Wanna make Adriana smile with a donation?\nChoose a crypto option below 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# 💰 USDT (TRC20)
async def donate_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    usdt_address = "TA8oM8VHaCnTxi2j7ckBksRkwfUbbHjcbn"
    qr_url = "https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl=" + usdt_address

    await update.callback_query.message.reply_photo(
        photo=qr_url,
        caption=f"💸 <b>Send USDT (TRC20)</b>\n\n<code>{usdt_address}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to support", callback_data="support")]
        ])
    )

# 💰 USDC (Solana)
async def donate_usdc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    usdc_address = "Ex3ruwZDhYSUMiuvDFWBHhvoifW8U4fGjzWHcyQ2nHvT"
    qr_url = "https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl=" + usdc_address

    await update.callback_query.message.reply_photo(
        photo=qr_url,
        caption=f"💸 <b>Send USDC (Solana)</b>\n\n<code>{usdc_address}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to support", callback_data="support")]
        ])
    )

# === 🔚 КОНЕЦ БЛОКА 7 ===
# === 🧱 БЛОК 8: Подробности брони, Логирование, “Подробнее” для Админа ===

# 📄 Запись в лог
def log_action(action: str, user: str, item_id: int):
    timestamp = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO logs (action, user, item_id, timestamp) VALUES (?, ?, ?, ?)",
        (action, user, item_id, timestamp)
    )
    conn.commit()

# 📊 Подробнее (доступно только админу)
async def admin_item_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = int(update.callback_query.data.split(":")[1])

    # Получаем информацию о товаре
    c.execute("SELECT title, booked_by, booked_anonymously, booked_at FROM items WHERE id = ?", (item_id,))
    item = c.fetchone()

    if not item:
        await update.callback_query.message.reply_text("❌ Item not found.")
        return

    title, booked_by, anon, booked_at = item
    c.execute("SELECT remind_at, confirmed FROM reminders WHERE item_id = ?", (item_id,))
    reminders = c.fetchall()

    msg = f"📊 <b>Details for:</b> {title}\n"
    msg += f"👤 Booked by: {'Anonymous' if anon else '@' + booked_by if booked_by else '—'}\n"
    msg += f"⏱️ Booked at: {booked_at or '—'}\n\n"

    if reminders:
        for remind_at, confirmed in reminders:
            status = (
                "✅ Confirmed" if confirmed == "yes" else
                "❌ Declined" if confirmed == "no" else
                "⌛ Waiting"
            )
            msg += f"🔔 Reminder at {remind_at[:16]} — {status}\n"
    else:
        msg += "🔔 No active reminders.\n"

    await update.callback_query.message.reply_text(
        msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to menu", callback_data="back_to_menu")]
        ])
    )

# 🗂️ Просмотр логов (команда /logs)
async def view_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⛔ Access denied.")
        return

    c.execute("SELECT action, user, item_id, timestamp FROM logs ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()

    if not rows:
        await update.message.reply_text("🧾 No logs found.")
        return

    msg = "🗂 <b>Last 10 actions:</b>\n\n"
    for action, user, item_id, timestamp in rows:
        msg += f"🔹 {action} | {user} | item {item_id} | {timestamp[:16]}\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# === 🔚 КОНЕЦ БЛОКА 8 ===
# === 🧱 БЛОК 9: Callback-и, JobQueue, Main() и запуск ===

def build_application() -> Application:
    app = ApplicationBuilder().token(TOKEN).build()

    # === Команды ===
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_start))
    app.add_handler(CommandHandler("edit", edit_start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("logs", view_logs))

    # === Conversation: /add ===
    app.add_handler(add_conv)

    # === Conversation: /edit ===
    app.add_handler(edit_conv)

    # === Callback-и ===
    app.add_handler(CallbackQueryHandler(price_filter, pattern="^price:"))
    app.add_handler(CallbackQueryHandler(manual_input, pattern="^manual_input$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\d+$"), handle_manual_budget))

    app.add_handler(CallbackQueryHandler(book_item, pattern="^bookanon:|^book:"))
    app.add_handler(CallbackQueryHandler(set_reminder, pattern="^remind:"))
    app.add_handler(CallbackQueryHandler(cancel_booking, pattern="^cancel:"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(return_to_budget, pattern="^back_to_budget$"))

    app.add_handler(CallbackQueryHandler(support_menu, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(donate_usdt, pattern="^donate_usdt$"))
    app.add_handler(CallbackQueryHandler(donate_usdc, pattern="^donate_usdc$"))

    app.add_handler(CallbackQueryHandler(admin_item_details, pattern="^details:"))
    app.add_handler(CallbackQueryHandler(confirm_purchase, pattern="^confirm:"))

    return app


# ✅ Инициализация задач
async def initialize_jobs(application: Application):
    application.job_queue.run_repeating(check_reminders, interval=60)
    application.job_queue.run_repeating(auto_cancel_unconfirmed, interval=3600)


# ⏰ Проверка напоминаний
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc).isoformat()
    app = context.application

    c.execute("SELECT id, user_id, item_id FROM reminders WHERE remind_at <= ? AND asked = 0", (now,))
    reminders = c.fetchall()

    for reminder_id, user_id, item_id in reminders:
        c.execute("SELECT title FROM items WHERE id = ?", (item_id,))
        item = c.fetchone()
        if item:
            await app.bot.send_message(user_id, f"⏰ Reminder! Did you buy: {item[0]}?", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data=f"confirm:yes:{item_id}:{reminder_id}")],
                [InlineKeyboardButton("❌ No", callback_data=f"confirm:no:{item_id}:{reminder_id}")]
            ]))
            c.execute("UPDATE reminders SET asked = 1 WHERE id = ?", (reminder_id,))
    conn.commit()


# ⏳ Авто-снятие брони
async def auto_cancel_unconfirmed(context: ContextTypes.DEFAULT_TYPE):
    check_time = (datetime.utcnow() - timedelta(hours=12)).isoformat()
    c.execute("SELECT item_id FROM reminders WHERE asked = 1 AND confirmed IS NULL AND remind_at <= ?", (check_time,))
    items = c.fetchall()

    for (item_id,) in items:
        c.execute("UPDATE items SET booked_by = NULL, booked_anonymously = 0, booked_at = NULL WHERE id = ?", (item_id,))
        c.execute("DELETE FROM reminders WHERE item_id = ?", (item_id,))
    conn.commit()


# === 🚀 Запуск бота (совместимо с Windows, PTB 20+) ===
if __name__ == "__main__":
    import asyncio

    async def main():
        app = build_application()
        await initialize_jobs(app)
        print("🚀 Bot is running... Press Ctrl+C to stop.")
        await app.run_polling()

    asyncio.run(main())

# === 🔚 КОНЕЦ БЛОКА 9 ===





