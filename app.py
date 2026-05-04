import asyncio
import os
import re
from pathlib import Path
from rubpy import Client

# --- تنظیمات ---
SESSION = "my_session"
PASSWORD = "@Amir1387" # رمز عبور ادمین شدن
# --- پایان تنظیمات ---

ADMINS = set()
WAITING_PASSWORD = set()
TARGET_GUID = None

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = Client(SESSION)


def extract_join_code(text):
    """از متن پیام، کد لینک جوین را استخراج می‌کند"""
    m = re.search(r'joing/([A-Za-z0-9]+)', text or "")
    return m.group(1) if m else None


def get_guid_from_join(res):
    """
    GUID را از پاسخ دریافتی با استفاده از روش دسترسی به صفات (Attribute Access) استخراج می‌کند.
    """
    try:
        if hasattr(res, "group") and hasattr(res.group, "group_guid"):
            guid = res.group.group_guid
            if guid:
                return guid

        if hasattr(res, "chat_update") and hasattr(res.chat_update, "object_guid"):
            guid = res.chat_update.object_guid
            if guid:
                return guid

    except Exception as e:
        print(f"GUID ERROR: خطا در پردازش پاسخ جوین: {type(e).__name__} - {e}")

    return None


async def create_vc(guid):
    """برای گروه یا کانال ویس چت می‌سازد"""
    try:
        if guid.startswith("g") and hasattr(app, "create_group_voice_chat"):
            return await app.create_group_voice_chat(guid)
        elif guid.startswith("c") and hasattr(app, "create_channel_voice_chat"):
            return await app.create_channel_voice_chat(guid)
        elif hasattr(app, "create_voice_chat"):
            return await app.create_voice_chat(guid)
    except Exception as e:
        print(f"VC ERROR: {e}")
    return None


@app.on_message_updates()
async def handler(message):
    global TARGET_GUID

    try:
        text = getattr(message, "text", "") or ""
        chat_guid = getattr(message, "chat_guid", None) or getattr(message, "object_guid", "")
        author_guid = getattr(message, "author_guid", "")

        # --- احراز هویت در پیوی ---
        if isinstance(chat_guid, str) and chat_guid.startswith("u"):
            if text.lower() == "admin":
                WAITING_PASSWORD.add(author_guid)
                await message.reply("🔐 رمز را ارسال کن")
                return
            if author_guid in WAITING_PASSWORD:
                WAITING_PASSWORD.remove(author_guid)
                if text == PASSWORD:
                    ADMINS.add(author_guid)
                    await message.reply("✅ ادمین شدی!")
                else:
                    await message.reply("❌ رمز اشتباه بود!")
                return

        # --- جوین با لینک ---
        join_code = extract_join_code(text)
        if join_code:
            if author_guid not in ADMINS:
                await message.reply("⛔️ فقط ادمین می‌تواند ربات را به گروه اضافه کند.")
                return
            try:
                res = await app.join_chat(join_code)
                guid = get_guid_from_join(res)
                
                if guid:
                    TARGET_GUID = guid
                    await message.reply(f"✅ عضو شدم و گروه هدف تنظیم شد:\n`{TARGET_GUID}`")
                else:
                    await message.reply("✅ عضو شدم ولی GUID در پاسخ دریافتی پیدا نشد.")
            except Exception as e:
                await message.reply(f"❌ خطا در join:\n`{e}`")
            return

        # --- دستورات فقط برای ادمین ---
        if author_guid not in ADMINS:
            return

        # --- دستورات داخل گروه ---
        if not isinstance(chat_guid, str) or not chat_guid.startswith("g"):
            return

        if text.lower() == "set":
            TARGET_GUID = chat_guid
            await message.reply(f"✅ این گروه به عنوان هدف تنظیم شد:\n`{TARGET_GUID}`")
            return

        if text.lower() == "start vc":
            if not TARGET_GUID:
                await message.reply("❌ ابتدا باید با دستور `set` یا ارسال لینک، گروه هدف را مشخص کنید.")
                return
            ok = await create_vc(TARGET_GUID)
            if ok:
                await message.reply("✅ ویس‌چت ساخته شد.")
            else:
                await message.reply("❌ خطا در ساخت ویس‌چت. (ممکن است از قبل ویس‌چت فعال باشد)")
            return

        # +++ بخش پخش موزیک (اصلاح نهایی و قطعی) +++
        if TARGET_GUID == chat_guid:
            file_object = getattr(message, "file_inline", None) or getattr(message, "file", None)
            
            if not file_object:
                return

            path = None
            try:
                temp_path = DOWNLOAD_DIR / f"{message.message_id}.ogg"
                
                await message.reply("📥 در حال دانلود موزیک...")
                path = await app.download(file_object, str(temp_path))

                if not path:
                    await message.reply("❌ دانلود فایل ناموفق بود.")
                    return

                await message.reply("🎧 در حال اتصال و پخش موزیک...")

                # <<<<<==== این تنها خط لازم برای پخش است ====>>>>>
                await app.voice_chat_player(chat_guid=TARGET_GUID, media=path)
                # <<<<<==== پایان اصلاح ====>>>>>
                
            except Exception as e:
                await message.reply(f"❌ خطا در دانلود یا پخش موزیک:\n`{e}`")
            finally:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError as e:
                        print(f"Error removing file {path}: {e}")
        # +++ پایان بخش پخش موزیک +++

    except Exception as e:
        print(f"MAIN ERROR: {type(e).__name__} - {e}")
        try:
            await message.reply(f"❌ یک خطای پیش‌بینی نشده در ربات رخ داد:\n`{e}`")
        except:
            pass


print("🤖 Bot Started...")
app.run()
