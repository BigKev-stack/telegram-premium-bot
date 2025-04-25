import asyncio
import aiosqlite
from datetime import datetime, timedelta, timezone  # Import timezone
import logging  # Import logging
import re      # Import regular expression
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError  # Import specific exception

# Your bot credentials
BOT_TOKEN = "7691163178:AAHJ1PFIDtTE7iojK2K5sHTBZy4TOJYLNZk"   
ADMIN_ID = 1065875318
DB_NAME = "users.db"
TILL_NUMBER = "4061858"
PREMIUM_LINK = "https://t.me/+nrmygcREchsxZTc0"
PREMIUM_GROUP_ID = -4725687500
# Define plans
PLANS = {
    'plan_5min': {"label": "🔹 5min - Ksh 50", "price": 50, "duration": timedelta(minutes=5)},
    'plan_1week': {"label": "🔸 1 Week - Ksh 100", "price": 100, "duration": timedelta(weeks=1)},
    'plan_3weeks': {"label": "🔸 3 Weeks - Ksh 300", "price": 300, "duration": timedelta(weeks=3)},
    'plan_1month': {"label": "💎 1 Month - Ksh 500", "price": 500, "duration": timedelta(weeks=4)},
}

# Configure logging
logging.basicConfig(filename='bot.log', level=logging.ERROR,  # Log errors to 'bot.log'
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize database
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, plan TEXT, amount INTEGER, status TEXT, expires_at TEXT)"
        )
        await db.commit()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(plan["label"], callback_data=code)] for code, plan in PLANS.items()
    ]
    await update.message.reply_text(
        "🔞 *ONLY FANS LEAKS NAKURU*\n\n🔥 Choose your subscription plan below to continue:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# Plan selection
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['plan'] = query.data
    await query.edit_message_text("📞 Please enter your phone number manually (e.g. 0712345678):")

# Manual phone number input
async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = update.message.text.strip()
    plan_code = context.user_data.get('plan')

    if plan_code not in PLANS:
        await update.message.reply_text("❌ Invalid plan selected. Please use /start.")
        logging.error(f"Invalid plan selected by user {user_id}.")
        return

    # Validate phone number (example - adjust regex as needed)
    if not re.match(r"^\d{10}$", phone):
        await update.message.reply_text("❌ Invalid phone number format. Please enter a 10-digit number.")
        logging.warning(f"Invalid phone number format from user {user_id}: {phone}")
        return

    price = PLANS[plan_code]["price"]

    await update.message.reply_text(
        f"✅ Phone Number Saved: {phone}\n\n"
        f"💳 Please pay *Ksh {price}* to *Till Number: {TILL_NUMBER}* (Buy Goods).\n"
        "After payment, send /paid to activate your subscription.",
        parse_mode="Markdown"
    )

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, phone, plan, amount, status) VALUES (?, ?, ?, ?, ?)",
                (user_id, phone, plan_code, price, "Pending")
            )
            await db.commit()
        logging.info(f"User {user_id} data saved to database (Pending).")
    except aiosqlite.Error as e:
        await update.message.reply_text(f"❌ Database error: {e}")
        logging.error(f"Database error saving user {user_id}: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing phone number: {e}")
        logging.exception(f"Unexpected error processing phone number from user {user_id}: {e}")

# /paid command to confirm payment
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = datetime.now(tz=timezone.utc)  # Use UTC for consistency

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT plan, expires_at FROM users WHERE user_id = ?", (user_id,)) as cursor:
            record = await cursor.fetchone()

        if not record:
            await update.message.reply_text("❌ No active session found. Please use /start.")
            return

        plan_code, old_expiry = record
        duration = PLANS[plan_code]["duration"]

        if old_expiry:
            try:
                old_time = datetime.strptime(old_expiry, "%Y-%m-%d %H:%M:%S")
                old_time = old_time.replace(tzinfo=timezone.utc) # Ensure old_time is timezone-aware
                new_expiry = old_time + duration if old_time > now else now + duration
            except ValueError:
                new_expiry = now + duration
                logging.error(f"Error parsing old expiry time for user {user_id}: {old_expiry}")
        else:
            new_expiry = now + duration

        expiry_str = new_expiry.strftime('%A, %B %d, %Y %I:%M %p %Z%z')

        await db.execute(
            "UPDATE users SET status = 'Active', expires_at = ? WHERE user_id = ?",
            (new_expiry.strftime("%Y-%m-%d %H:%M:%S"), user_id)
        )
        await db.commit()

    # Send confirmation + Join Channel link
    keyboard = [[InlineKeyboardButton("JOIN CHANNEL", url=PREMIUM_LINK)]]
    await update.message.reply_text(
        f"""🎉 Payment confirmed for *{plan_code.replace('_', ' ').title()}*!
✅ Access activated.

🕒 Your subscription is valid until: *{expiry_str}*.

🔗 Click below to join the premium channel:
""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

    # Schedule auto-removal
    asyncio.create_task(schedule_expiry(user_id, new_expiry))

# Auto-remove after expiration
async def schedule_expiry(user_id, expiry_time):
    now = datetime.now(tz=timezone.utc)  # Use UTC for consistency
    delay = (expiry_time - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)

    from telegram import Bot
    bot = Bot(BOT_TOKEN)
    try:
        await bot.ban_chat_member(PREMIUM_GROUP_ID, user_id)
        await bot.unban_chat_member(PREMIUM_GROUP_ID, user_id)
        logging.info(f"Successfully auto-removed user {user_id} from premium channel.")
    except TelegramError as e:
        logging.error(f"Telegram error auto-kicking user {user_id}: {e}")
    except Exception as e:
        logging.exception(f"Unexpected error auto-kicking user {user_id}: {e}")

# /status command
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT plan, status, expires_at FROM users WHERE user_id = ?", (user_id,)) as cursor:
            record = await cursor.fetchone()

    if record:
        plan, status, expires = record
        await update.message.reply_text(
            f"""🧾 Plan: *{plan.replace('_', ' ').title()}*
📌 Status: *{status}*
⏰ Expires: *{expires}*""",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("🔍 No active subscription found.")

# Main entry
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler))
    app.add_handler(CommandHandler("paid", paid))
    app.add_handler(CommandHandler("status", status))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())