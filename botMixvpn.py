import os
import json
import time
import logging
import requests
import telebot
from telebot import types

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL = os.environ.get("CHANNEL_USERNAME", "@lamer42").strip()  # канал для проверки подписки
OPERATOR_ID = 6716592576
CHANNEL_LINK = "https://t.me/lamer42"
STICKER_PACK = "https://t.me/addstickers/MellstroySticker5"
SUB_URL = "https://raw.githubusercontent.com/Lamer1el/Trusa/refs/heads/main/sub.txt"

PHOTO_SUB  = "https://raw.githubusercontent.com/Lamer1el/Trusa/main/file_000000001aa4822f8121ce972c057ab3.png"
PHOTO_MENU = "https://raw.githubusercontent.com/Lamer1el/Trusa/main/file_0000000038d4822fa6ce954cedc7238e.png"
PHOTO_GET  = "https://raw.githubusercontent.com/Lamer1el/Trusa/main/file_00000000dfb481f488a0e9a61922e7fd.png"

# Сюда можно вставить file_id стикеров из пака, тогда они будут отправляться с сообщениями
STICKERS = []  # например: ["CAACAgIAAxkBAAE...", "CAACAgIAAxkBAAE..."]

if not BOT_TOKEN:
    raise SystemExit("❌ Не задана переменная окружения BOT_TOKEN")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mixvpn_data.json")
STATE = {}

DEFAULT_TEXTS = {
    "msg1": "Подпишитесь на наш канал📡 Ведь проект полностью бесплатный 🆓",
    "msg2": "Выберите действие🛠️",
    "msg3": "Ваша подписка: {sub}",
}


# ---------------- STORAGE ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "users": [],
        "reviews": [],
        "tickets": {},
        "next_ticket": 1,
        "texts": dict(DEFAULT_TEXTS),
    }


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DATA, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"save error: {e}")


DATA = load_data()
for k, v in DEFAULT_TEXTS.items():
    DATA["texts"].setdefault(k, v)


# ---------------- HELPERS ----------------
def is_subscribed(uid: int) -> bool:
    if not CHANNEL:
        return True
    try:
        m = bot.get_chat_member(CHANNEL, uid)
        return m.status in ("creator", "administrator", "member")
    except Exception as e:
        logging.warning(f"sub check error: {e}")
        return False


_sub_cache = {"text": None, "ts": 0}


def fetch_sub_text() -> str:
    now = time.time()
    if _sub_cache["text"] and now - _sub_cache["ts"] < 300:
        return _sub_cache["text"]
    try:
        r = requests.get(SUB_URL, timeout=10)
        if r.status_code == 200 and r.text.strip():
            _sub_cache["text"] = r.text.strip()
            _sub_cache["ts"] = now
            return _sub_cache["text"]
    except Exception as e:
        logging.warning(f"fetch sub: {e}")
    return _sub_cache["text"] or "@lamer42"


def safe_delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


# ---------------- KEYBOARDS ----------------
def kb_sub():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📡 Перейти", url=CHANNEL_LINK))
    kb.row(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
    return kb


def kb_menu():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🆘 Поддержка", callback_data="support"),
        types.InlineKeyboardButton("🎁 Получить подписку", callback_data="get_sub"),
    )
    kb.row(
        types.InlineKeyboardButton("✍️ Оставить отзыв", callback_data="leave_review"),
        types.InlineKeyboardButton("💬 Отзывы", callback_data="show_reviews"),
    )
    kb.row(types.InlineKeyboardButton("🔁 Подписаться ещё раз", callback_data="again"))
    kb.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    return kb


def kb_back(cb="back"):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⬅️ Назад", callback_data=cb))
    return kb


# ---------------- SENDERS ----------------
def send_photo_or_text(chat_id, photo, text, kb, sticker=False):
    msg = None
    try:
        msg = bot.send_photo(chat_id, photo, caption=text, reply_markup=kb)
    except Exception as e:
        logging.warning(f"photo err: {e}")
        msg = bot.send_message(chat_id, text, reply_markup=kb)
    if sticker and STICKERS:
        try:
            bot.send_sticker(chat_id, STICKERS[0])
        except Exception:
            pass
    return msg


def send_main(chat_id):
    send_photo_or_text(chat_id, PHOTO_SUB, DATA["texts"]["msg1"], kb_sub())


def send_menu(chat_id):
    send_photo_or_text(chat_id, PHOTO_MENU, DATA["texts"]["msg2"], kb_menu())


def send_get_sub(chat_id):
    sub = fetch_sub_text()
    text = DATA["texts"]["msg3"].format(sub=sub)
    send_photo_or_text(chat_id, PHOTO_GET, text, kb_back())


def notify_operator_ticket(tid, is_reply=False):
    t = DATA["tickets"].get(str(tid))
    if not t:
        return
    header = "📩 <b>Новое сообщение в тикете</b>" if is_reply else "📩 <b>Новый тикет</b>"
    text = (
        f"{header} #{tid}\n"
        f"👤 @{t['username']} (ID: <code>{t['user_id']}</code>)\n\n"
        f"💬 {t['messages'][-1]['text']}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"✍️ Ответить #{tid}", callback_data=f"reply_{tid}"))
    kb.row(types.InlineKeyboardButton(f"🔒 Закрыть #{tid}", callback_data=f"close_{tid}"))
    try:
        msg = bot.send_message(OPERATOR_ID, text, reply_markup=kb)
        t["notif_msg_id"] = msg.message_id
        save_data()
    except Exception as e:
        logging.error(f"notify op: {e}")


# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    if uid not in DATA["users"]:
        DATA["users"].append(uid)
        save_data()
    STATE.pop(uid, None)
    if is_subscribed(uid):
        send_menu(uid)
    else:
        send_main(uid)


@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if m.from_user.id != OPERATOR_ID:
        return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📨 Чаты", callback_data="adm_chats"))
    kb.row(types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    kb.row(types.InlineKeyboardButton("📝 Изменить тексты", callback_data="adm_texts"))
    kb.row(types.InlineKeyboardButton("🎨 Стикер-пак", url=STICKER_PACK))
    bot.send_message(m.chat.id, "🛠️ <b>Админ-панель MixVpn</b>", reply_markup=kb)


# ---------------- USER CALLBACKS ----------------
@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(c):
    uid = c.from_user.id
    if is_subscribed(uid):
        bot.answer_callback_query(c.id, "✅ Подписка подтверждена!")
        safe_delete(c.message.chat.id, c.message.message_id)
        send_menu(uid)
    else:
        bot.answer_callback_query(c.id, "❌ Вы ещё не подписались на канал!", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data == "back")
def cb_back(c):
    safe_delete(c.message.chat.id, c.message.message_id)
    STATE.pop(c.from_user.id, None)
    uid = c.from_user.id
    if is_subscribed(uid):
        send_menu(uid)
    else:
        send_main(uid)


@bot.callback_query_handler(func=lambda c: c.data == "again")
def cb_again(c):
    safe_delete(c.message.chat.id, c.message.message_id)
    send_main(c.from_user.id)


@bot.callback_query_handler(func=lambda c: c.data == "get_sub")
def cb_get_sub(c):
    safe_delete(c.message.chat.id, c.message.message_id)
    send_get_sub(c.from_user.id)


@bot.callback_query_handler(func=lambda c: c.data == "support")
def cb_support(c):
    safe_delete(c.message.chat.id, c.message.message_id)
    STATE[c.from_user.id] = "support"
    bot.send_message(
        c.from_user.id,
        "✍️ Напишите ваше сообщение для поддержки.\nОператор ответит вам в ближайшее время.",
        reply_markup=kb_back(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "leave_review")
def cb_leave_review(c):
    safe_delete(c.message.chat.id, c.message.message_id)
    STATE[c.from_user.id] = "review"
    bot.send_message(c.from_user.id, "✍️ Напишите ваш отзыв:", reply_markup=kb_back())


@bot.callback_query_handler(func=lambda c: c.data == "show_reviews")
def cb_show_reviews(c):
    safe_delete(c.message.chat.id, c.message.message_id)
    reviews = DATA.get("reviews", [])
    if not reviews:
        text = "💬 Пока нет отзывов. Будьте первым!"
    else:
        lines = ["💬 <b>Отзывы пользователей:</b>\n"]
        for i, r in enumerate(reviews[-15:], 1):
            lines.append(f"{i}. {r['user']}: {r['text']}")
        text = "\n".join(lines)
    bot.send_message(c.from_user.id, text, reply_markup=kb_back())


# ---------------- ADMIN CALLBACKS ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("reply_") and c.from_user.id == OPERATOR_ID)
def cb_op_reply(c):
    tid = c.data.split("_", 1)[1]
    STATE[OPERATOR_ID] = f"reply_{tid}"
    bot.answer_callback_query(c.id)
    bot.send_message(OPERATOR_ID, f"✍️ Напишите ответ для тикета #{tid}:")


@bot.callback_query_handler(func=lambda c: c.data.startswith("close_") and c.from_user.id == OPERATOR_ID)
def cb_op_close(c):
    tid = c.data.split("_", 1)[1]
    t = DATA["tickets"].get(tid)
    if t:
        t["status"] = "closed"
        save_data()
        try:
            bot.send_message(t["user_id"], "🔒 Ваш тикет закрыт. Спасибо за обращение!", reply_markup=kb_back())
        except Exception:
            pass
        bot.answer_callback_query(c.id, "✅ Тикет закрыт")
    else:
        bot.answer_callback_query(c.id, "Не найден")


@bot.callback_query_handler(func=lambda c: c.data == "adm_chats" and c.from_user.id == OPERATOR_ID)
def cb_adm_chats(c):
    bot.answer_callback_query(c.id)
    open_tickets = [(k, v) for k, v in DATA["tickets"].items() if v.get("status") == "open"]
    if not open_tickets:
        bot.send_message(OPERATOR_ID, "📭 Нет открытых чатов.")
        return
    for tid, t in open_tickets:
        last = t["messages"][-1]["text"] if t["messages"] else ""
        text = (
            f"📩 <b>Тикет #{tid}</b>\n"
            f"👤 @{t['username']} (ID: <code>{t['user_id']}</code>)\n\n💬 {last}"
        )
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton(f"✍️ Ответить #{tid}", callback_data=f"reply_{tid}"))
        kb.row(types.InlineKeyboardButton(f"🔒 Закрыть #{tid}", callback_data=f"close_{tid}"))
        bot.send_message(OPERATOR_ID, text, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast" and c.from_user.id == OPERATOR_ID)
def cb_adm_broadcast(c):
    bot.answer_callback_query(c.id)
    STATE[OPERATOR_ID] = "broadcast"
    bot.send_message(
        OPERATOR_ID,
        f"📢 Отправьте сообщение для рассылки.\n"
        f"Поддерживается: текст, фото, стикер, видео и т.д.\n\n"
        f"Стикер-пак: {STICKER_PACK}",
    )


@bot.callback_query_handler(func=lambda c: c.data == "adm_texts" and c.from_user.id == OPERATOR_ID)
def cb_adm_texts(c):
    bot.answer_callback_query(c.id)
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("1️⃣ Сообщение подписки", callback_data="edit_msg1"))
    kb.row(types.InlineKeyboardButton("2️⃣ Меню", callback_data="edit_msg2"))
    kb.row(types.InlineKeyboardButton("3️⃣ Получить подписку", callback_data="edit_msg3"))
    bot.send_message(OPERATOR_ID, "📝 Выберите текст для редактирования:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_") and c.from_user.id == OPERATOR_ID)
def cb_edit_start(c):
    key = c.data.split("_", 1)[1]
    STATE[OPERATOR_ID] = f"edit_{key}"
    bot.answer_callback_query(c.id)
    bot.send_message(
        OPERATOR_ID,
        f"📝 Текущий текст:\n\n{DATA['texts'].get(key, '')}\n\nОтправьте новый текст.",
    )


# ---------------- BROADCAST ----------------
def do_broadcast(m):
    sent = 0
    failed = 0
    for u in list(DATA.get("users", [])):
        try:
            bot.copy_message(u, m.chat.id, m.message_id)
            sent += 1
            time.sleep(0.05)
        except Exception:
            failed += 1
    bot.send_message(OPERATOR_ID, f"📢 Рассылка завершена.\n✅ Успешно: {sent}\n❌ Ошибок: {failed}")


# ---------------- MAIN MESSAGE HANDLER ----------------
@bot.message_handler(
    content_types=["text", "photo", "sticker", "voice", "video", "document", "audio", "animation"]
)
def handle_all(m):
    uid = m.from_user.id

    # ---- OPERATOR STATES ----
    if uid == OPERATOR_ID:
        st = STATE.get(OPERATOR_ID)

        if st and st.startswith("reply_"):
            tid = st.split("_", 1)[1]
            STATE.pop(OPERATOR_ID, None)
            t = DATA["tickets"].get(tid)
            if t:
                content = m.text or m.caption or "[вложение]"
                t["messages"].append({"from": "operator", "text": content})
                t["status"] = "open"
                save_data()
                try:
                    if m.content_type == "text":
                        bot.send_message(
                            t["user_id"],
                            f"💬 <b>Ответ поддержки:</b>\n{m.text}",
                            reply_markup=kb_back(),
                        )
                    else:
                        bot.send_message(t["user_id"], "💬 <b>Ответ поддержки:</b>", reply_markup=kb_back())
                        bot.copy_message(t["user_id"], m.chat.id, m.message_id)
                except Exception as e:
                    bot.send_message(OPERATOR_ID, f"❌ Не доставлено: {e}")
                    return
                bot.send_message(OPERATOR_ID, "✅ Отправлено.")
            return

        if st == "broadcast":
            STATE.pop(OPERATOR_ID, None)
            do_broadcast(m)
            return

        if st and st.startswith("edit_"):
            key = st.split("_", 1)[1]
            STATE.pop(OPERATOR_ID, None)
            if m.text:
                DATA["texts"][key] = m.text
                save_data()
                bot.send_message(OPERATOR_ID, "✅ Текст обновлён.")
            else:
                bot.send_message(OPERATOR_ID, "❌ Нужен именно текст.")
            return

        # Ответ оператора через reply на уведомление
        if m.reply_to_message:
            for tid, t in DATA["tickets"].items():
                if t.get("notif_msg_id") == m.reply_to_message.message_id:
                    content = m.text or m.caption or "[вложение]"
                    t["messages"].append({"from": "operator", "text": content})
                    save_data()
                    try:
                        if m.content_type == "text":
                            bot.send_message(
                                t["user_id"],
                                f"💬 <b>Ответ поддержки:</b>\n{m.text}",
                                reply_markup=kb_back(),
                            )
                        else:
                            bot.send_message(t["user_id"], "💬 <b>Ответ поддержки:</b>", reply_markup=kb_back())
                            bot.copy_message(t["user_id"], m.chat.id, m.message_id)
                    except Exception as e:
                        bot.send_message(OPERATOR_ID, f"❌ Не доставлено: {e}")
                    return
        # если оператор просто написал что-то — показываем админку
        cmd_admin(m)
        return

    # ---- USER STATES ----
    st = STATE.get(uid)

    if st == "support":
        STATE.pop(uid, None)
        text = m.text or m.caption or "[вложение]"

        open_tid = None
        for tid, t in DATA["tickets"].items():
            if t.get("user_id") == uid and t.get("status") == "open":
                open_tid = tid
                break

        if open_tid:
            t = DATA["tickets"][open_tid]
            t["messages"].append({"from": "user", "text": text})
            save_data()
            notify_operator_ticket(open_tid, is_reply=True)
        else:
            tid = DATA["next_ticket"]
            DATA["next_ticket"] += 1
            DATA["tickets"][str(tid)] = {
                "user_id": uid,
                "username": m.from_user.username or m.from_user.first_name or str(uid),
                "first_name": m.from_user.first_name or "",
                "status": "open",
                "messages": [{"from": "user", "text": text}],
                "notif_msg_id": None,
            }
            save_data()
            notify_operator_ticket(tid)

        bot.send_message(uid, "✅ Ваше сообщение отправлено в поддержку.", reply_markup=kb_back())
        return

    if st == "review":
        STATE.pop(uid, None)
        if m.text:
            DATA["reviews"].append({
                "user": ("@" + m.from_user.username) if m.from_user.username else (m.from_user.first_name or "Аноним"),
                "text": m.text,
                "ts": int(time.time()),
            })
            save_data()
            bot.send_message(uid, "🙏 Спасибо за отзыв!", reply_markup=kb_back())
        else:
            bot.send_message(uid, "❌ Отзыв должен быть текстом.", reply_markup=kb_back())
        return

    # ---- DEFAULT ----
    if is_subscribed(uid):
        send_menu(uid)
    else:
        send_main(uid)


# ---------------- RUN ----------------
if __name__ == "__main__":
    logging.info("🚀 MixVpn bot starting...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, none_stop=True)
        except Exception as e:
            logging.error(f"Polling crash: {e}")
            time.sleep(5)
