import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup

TOKEN = "8533004528:AAEDweERrJX6CbPCZtS_yN3KXTiyXPX7nyw"
bot = telebot.TeleBot(TOKEN)
user_states = {}

def get_tiktok_video(tiktok_url):
    try:
        url = "https://savetik.co/api/ajaxSearch"
        payload = {'q': tiktok_url, 'lang': 'ar', 'cftoken': ''}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        data = response.json()
        
        if data.get('status') != 'ok':
            return None
        
        html = data.get('data')
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        video_tag = soup.find('video')
        
        if not video_tag:
            return None
        
        video_url = video_tag.get('data-src')
        if not video_url:
            return None
        
        return video_url
        
    except Exception as e:
        print(f"Error: {e}")
        return None

@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id, "أرسل رابط فيديو TikTok")
    user_states[message.chat.id] = 'waiting'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'waiting')
def process_link(message):
    chat_id = message.chat.id
    url = message.text
    
    if 'tiktok.com' not in url and 'vt.tiktok' not in url:
        bot.send_message(chat_id, "أرسل رابط TikTok صالح")
        return
    
    msg = bot.send_message(chat_id, "جاري البحث عن الفيديو...")
    
    video_url = get_tiktok_video(url)
    
    if video_url:
        bot.delete_message(chat_id, msg.message_id)
        bot.send_video(chat_id, video_url, caption="تم الحميل بنجاح")
    else:
        bot.edit_message_text("لم يتم العثور على الفيديو", chat_id, msg.message_id)
    
    user_states[chat_id] = None

@bot.message_handler(func=lambda m: True)
def default_handler(message):
    if message.chat.id not in user_states:
        user_states[message.chat.id] = 'waiting'
    
    if user_states[message.chat.id] == 'waiting':
        process_link(message)
bot.polling()