import telebot
from telebot import types
import requests
import time
import secrets
import uuid
import re
import os
from functools import wraps
import socket

# نصيحة: قم بتغيير التوكن فوراً من BotFather لأنك نشرته علنياً
API_TOKEN = '8533004528:AAEDweERrJX6CbPCZtS_yN3KXTiyXPX7nyw'
bot = telebot.TeleBot(API_TOKEN)
NANA_BASE = "https://nanabanana.ai"

user_data = {}

def check_internet_connection():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def retry_on_disconnect(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for i in range(3):  # محاولة 3 مرات فقط لتجنب التعليق اللانهائي
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.RequestException, telebot.apihelper.ApiTelegramException) as e:
                print(f"خطأ في الاتصال: {e}، محاولة رقم {i+1}")
                time.sleep(5)
        return None
    return wrapper

def get_custom_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'x-token-type': 'access',
        'x-exp': str(int(time.time())),
        'x-iat': str(int(time.time())),
        'x-jti': secrets.token_hex(16),
        'x-user-id': str(uuid.uuid4()),
        'x-device-id': secrets.token_hex(8)
    }

def create_nana_session():
    client = requests.Session()
    # لتجنب مشاكل البروكسي في PythonAnywhere، نجبره على عدم استخدام بروكسي النظام
    client.proxies = {"http": None, "https": None}
    
    headers_mail = get_custom_headers()
    reg_payload = {
        'device_id': headers_mail['x-device-id'],
        'username': '',
        'reset_mail': True
    }
    
    try:
        # محاولة التسجيل في موقع البريد المؤقت
        reg_res_raw = client.post('https://admin.tempmail.support/api/register/', headers=headers_mail, json=reg_payload, timeout=15)
        if reg_res_raw.status_code != 200:
            print(f"خطأ من موقع البريد: {reg_res_raw.status_code}")
            return None
            
        reg_res = reg_res_raw.text
        email = re.search(r'"email":"([^"]+)"', reg_res).group(1)
        mail_token = re.search(r'"token":"([^"]+)"', reg_res).group(1)
        
        nana_headers = {
            'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
            'referer': f"{NANA_BASE}/"
        }
        
        # الحصول على CSRF
        csrf_resp = client.get(f"{NANA_BASE}/api/auth/csrf", headers=nana_headers, timeout=10).json()
        csrf = csrf_resp.get('csrfToken')
        
        # طلب كود التفعيل
        client.post(f"{NANA_BASE}/api/auth/email-verification", json={"email": email, "csrfToken": csrf}, headers=nana_headers, timeout=10)
        
        otp = None
        check_headers = headers_mail.copy()
        check_headers.update({'authorization': f'Bearer {mail_token}'})
        
        # فحص البريد بحثاً عن الكود
        for _ in range(10): # تقليل المحاولات قليلاً لتسريع العملية
            time.sleep(5)
            mail_res = client.get('https://admin.tempmail.support/api/mailbox/', headers=check_headers, params={'to_email': email}, timeout=10).text
            otp_match = re.search(r'\b\d{6}\b', mail_res)
            if otp_match:
                otp = otp_match.group(0)
                break        
        
        if otp:
            callback_data = {'email': email, 'code': otp, 'csrfToken': csrf, 'redirect': "false", 'callbackUrl': f"{NANA_BASE}/"}
            client.post(f"{NANA_BASE}/api/auth/callback/email-verification", data=callback_data, headers=nana_headers, timeout=10)
            return client
    except Exception as e:
        print(f"Error in session creation: {e}")
    return None

def wait_for_image(client, task_id):
    headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for _ in range(30):
        time.sleep(5)
        try:
            resp = client.post(f"{NANA_BASE}/api/image-generation-nano-banana/status", json={"taskId": task_id}, headers=headers, timeout=10).json()
            gen = resp.get("generations", [{}])[0]
            if gen.get("status") == "succeed":
                return gen.get("url")
            if gen.get("status") == "failed":
                return "failed"
        except:
            continue
    return None

@bot.message_handler(commands=['start'])
def welcome(message):
    user_data[message.chat.id] = {}
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("🎨 تعديل صورة (Image to Image)")
    btn2 = types.KeyboardButton("✍️ إنشاء من نص (Text to Image)")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "اهلا بك في بوت nanabanana المصحح", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🎨 تعديل صورة (Image to Image)")
def ask_photo(message):
    user_data[message.chat.id] = {'state': 'WAITING_PHOTO'}
    bot.send_message(message.chat.id, "حسناً، أرسل الصورة التي تريد تعديلها أولاً.")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.chat.id in user_data and user_data[message.chat.id].get('state') == 'WAITING_PHOTO':
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_path = f"img_{message.chat.id}.jpg"
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
        
        user_data[message.chat.id]['path'] = file_path
        user_data[message.chat.id]['state'] = 'WAITING_PROMPT'
        bot.send_message(message.chat.id, "وصلت الصورة! الآن أرسل لي وصف التعديل.")

@bot.message_handler(func=lambda m: True)
def handle_text_and_prompts(message):
    chat_id = message.chat.id
    text = message.text
    if chat_id in user_data and user_data[chat_id].get('state') == 'WAITING_PROMPT':
        process_generation(message, text, user_data[chat_id].get('path'))
        user_data[chat_id] = {}
    elif text == "✍️ إنشاء من نص (Text to Image)":
        user_data[chat_id] = {'state': 'WAITING_TEXT_ONLY'}
        bot.send_message(chat_id, "اكتب وصف الصورة التي تريد إنشائها.")
    elif chat_id in user_data and user_data[chat_id].get('state') == 'WAITING_TEXT_ONLY':
        process_generation(message, text)
        user_data[chat_id] = {}

def process_generation(message, prompt, file_path=None):
    sent_msg = bot.send_message(message.chat.id, "⏳ جاري تهيئة الجلسة... (قد يستغرق دقيقة)")
    
    session = create_nana_session()
    if not session:
        bot.edit_message_text("❌ فشل الاتصال بالمزود. يرجى المحاولة لاحقاً.", message.chat.id, sent_msg.message_id)
        if file_path and os.path.exists(file_path): os.remove(file_path)
        return

    img_urls = []
    if file_path:
        try:
            bot.edit_message_text("📤 جاري رفع الصورة...", message.chat.id, sent_msg.message_id)
            with open(file_path, 'rb') as f:
                up_res = session.post(f"{NANA_BASE}/api/upload", files={'file': (file_path, f, 'image/jpeg')}, timeout=20).json()
            img_urls = [up_res.get('url')]
            os.remove(file_path)
        except:
            bot.edit_message_text("❌ فشل رفع الصورة.", message.chat.id, sent_msg.message_id)
            return

    bot.edit_message_text("🚀 جاري معالجة الذكاء الاصطناعي...", message.chat.id, sent_msg.message_id)
    
    payload = {
        "prompt": prompt,
        "image_urls": img_urls,
        "output_format": "png", "width": 1024, "height": 1024, "steps": 20, "is_public": False
    }
    
    try:
        gen_res = session.post(f"{NANA_BASE}/api/image-generation-nano-banana/create", json=payload, timeout=20).json()
        task_id = gen_res.get("task_id")
        final_link = wait_for_image(session, task_id)
        
        if final_link and final_link != "failed":
            bot.send_photo(message.chat.id, final_link, caption=f"✅ تم الإنتهاء!\n الوصف: {prompt}")
            bot.delete_message(message.chat.id, sent_msg.message_id)
        else:
            bot.edit_message_text("❌ انتهى الوقت أو فشل التوليد.", message.chat.id, sent_msg.message_id)
    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text("❌ حدث خطأ غير متوقع.", message.chat.id, sent_msg.message_id)

def polling_with_retry():
    print("البوت يعمل الآن...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"خطأ في البولينج: {e}")
            time.sleep(10)

if __name__ == "__main__":
    polling_with_retry()
