import os
import httpx
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

user_directions = {}

DIRECTIONS = {
    "en_uz": ("🇺🇸 English", "🇺🇿 O'zbek", "en", "uz"),
    "uz_en": ("🇺🇿 O'zbek", "🇺🇸 English", "uz", "en"),
    "auto":  ("🔄 Avtomatik", "aniqlanadi", None, None),
}

# Bir nechta bepul LibreTranslate serverlari (biri ishlamasa keyingisi)
LIBRE_SERVERS = [
    "https://libretranslate.com",
    "https://translate.terraprint.co",
    "https://lt.vern.cc",
]


def direction_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇺🇸 English → 🇺🇿 O'zbek", callback_data="dir_en_uz")],
        [InlineKeyboardButton("🇺🇿 O'zbek → 🇺🇸 English", callback_data="dir_uz_en")],
        [InlineKeyboardButton("🔄 Avtomatik aniqlash",      callback_data="dir_auto")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def translate_text(text: str, from_lang: str, to_lang: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        for server in LIBRE_SERVERS:
            try:
                r = await client.post(
                    f"{server}/translate",
                    json={"q": text, "source": from_lang, "target": to_lang, "format": "text"},
                    headers={"Content-Type": "application/json"},
                )
                data = r.json()
                if "translatedText" in data:
                    return data["translatedText"]
            except Exception:
                continue

        # Zaxira: Google Translate (API keysiz)
        r = await client.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": from_lang,
                "tl": to_lang,
                "dt": "t",
                "q": text,
            },
        )
        result = r.json()
        translated = "".join(part[0] for part in result[0] if part[0])
        return translated


async def detect_language(text: str) -> str:
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    total = sum(1 for c in text if c.isalpha())
    if total == 0:
        return "en"
    return "en" if latin / total > 0.7 else "uz"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_directions.pop(update.effective_user.id, None)
    await update.message.reply_text(
        "👋 Salom! Men *Tarjimon Bot* — English ↔ O'zbek tarjima qilaman.\n\n"
        "Qaysi yo'nalishda tarjima qilishimni tanlang:",
        parse_mode="Markdown",
        reply_markup=direction_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Buyruqlar:*\n"
        "/start — Botni qayta ishga tushirish\n"
        "/lang  — Tarjima yo'nalishini o'zgartirish\n"
        "/help  — Yordam\n\n"
        "So'z yoki gap yuboring — tarjima qilib beraman!",
        parse_mode="Markdown",
    )


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Tarjima yo'nalishini tanlang:",
        reply_markup=direction_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    key = query.data.replace("dir_", "")
    if key not in DIRECTIONS:
        return

    user_directions[query.from_user.id] = key
    from_label, to_label = DIRECTIONS[key][0], DIRECTIONS[key][1]

    await query.edit_message_text(
        f"✅ *{from_label} → {to_label}* tanlandi!\n\n"
        "Endi tarjima qilmoqchi bo'lgan so'z yoki gapni yuboring. 📝\n"
        "Yo'nalishni o'zgartirish uchun /lang buyrug'ini yuboring.",
        parse_mode="Markdown",
    )


async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_directions:
        await update.message.reply_text(
            "Avval tarjima yo'nalishini tanlang:",
            reply_markup=direction_keyboard(),
        )
        return

    direction = user_directions[user_id]
    info = DIRECTIONS[direction]
    msg = await update.message.reply_text("⏳ Tarjima qilinmoqda...")

    try:
        if direction == "auto":
            detected = await detect_language(text)
            if detected == "en":
                from_lang, to_lang = "en", "uz"
                from_label, to_label = "🇺🇸 English", "🇺🇿 O'zbek"
            else:
                from_lang, to_lang = "uz", "en"
                from_label, to_label = "🇺🇿 O'zbek", "🇺🇸 English"
        else:
            from_lang, to_lang = info[2], info[3]
            from_label, to_label = info[0], info[1]

        translation = await translate_text(text, from_lang, to_lang)

        await msg.edit_text(
            f"📝 *Asl matn:*\n{text}\n\n"
            f"✅ *Tarjima ({from_label} → {to_label}):*\n{translation}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {str(e)}")


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN topilmadi! .env faylini tekshiring.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CommandHandler("lang",  lang_command))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^dir_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_message))

    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()