from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, MessageAction, TextMessage, TextSendMessage,ImageSendMessage, StickerSendMessage, LocationSendMessage, AudioSendMessage, VideoSendMessage
import datetime, threading, sqlite3, re

line_bot_api = LineBotApi("HypklMihoGXHzV9uLERGELx3LtxTNZUddpP/yHjaoUoqlUnCw4MIMp/izCAnkfUx3NVcrx7onVFuP/ooB22XDsmczOISSc76BOidcST+eu42c7GYcG0p2MRRgtJ7bIGr/rfV5nG8rmaeay1KmvMVTQdB04t89/1O/w1cDnyilFU=")
handler = WebhookHandler("941ad0fd9849de2a761031120d2626b1")

def init_db():
    conn = sqlite3.connect("message_log.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            timestamp TEXT,
            message TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_message_to_db(user_id, timestamp, message):
    conn = sqlite3.connect("message_log.db")
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, timestamp, message) VALUES (?, ?, ?)",
              (user_id, timestamp, message))
    conn.commit()
    conn.close()

def get_user_logs(user_id, limit=10):
    conn = sqlite3.connect("message_log.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, message FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    results = c.fetchall()
    conn.close()
    return results

init_db()

# Make a flask app
app = Flask(__name__)

@app.route("/", methods=["POST"])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Token or Secret is wrong.")
        abort(400)
    except LineBotApiError as e:
        app.logger.info("Error-log: " + str(e))
    return 'OK'

# LINE_CHANNEL
def send_delayed_message(user_id, message, delay):
    def task():
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text="Scheduled Message: " + message)
        )
    timer = threading.Timer(delay, task)
    timer.start()
    
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message = event.message.text
    reply_token = event.reply_token
    user_id = event.source.user_id
    now = datetime.datetime.now().isoformat()

    log_message_to_db(user_id, now, message)

    if message.strip().lower() == "/log":
        logs = get_user_logs(user_id)
        if logs:
            reply_lines = ["🗂️ 你的紀錄："]
            for idx, (ts, msg) in enumerate(logs, start=1):
                ts_fmt = datetime.datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
                reply_lines.append(f"{idx}. [{ts_fmt}] {msg}")
            reply_text = "\n".join(reply_lines)
        else:
            reply_text = "📭 目前沒有你的紀錄。"
    
        line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_text))
        return

    if message.strip().lower() == "hi":
        line_bot_api.reply_message(reply_token, TextSendMessage(text="Hi, 輸入開頭為時間格式 hh:mm:ss 的訊息"))
        return

    try:
        match = re.match(r"^\s*(\d{2}:\d{2}:\d{2})\s+(.*)", message)
        if match:
            time_str = match.group(1)
            content = match.group(2)

            scheduled_time = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
            now_dt = datetime.datetime.now()
            scheduled_dt = now_dt.replace(hour=scheduled_time.hour, minute=scheduled_time.minute, second=scheduled_time.second, microsecond=0)
            if scheduled_dt < now_dt:
                scheduled_dt += datetime.timedelta(days=1)

            delay = (scheduled_dt - now_dt).total_seconds()
            send_delayed_message(user_id, content, delay)

            line_bot_api.reply_message(reply_token, TextSendMessage(
                text=f"訊息已排程，將於 {scheduled_time.strftime('%H:%M:%S')} 發送。"
            ))
            return
    except Exception as e:
        line_bot_api.reply_message(reply_token, TextSendMessage(text="Time: " + str(event.timestamp) + "\nMessage: " + message))
        print("Error parsing time:", e)