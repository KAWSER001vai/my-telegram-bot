# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import sys
import time
import psutil
import threading
import zipfile
import json
from telebot import types
from flask import Flask
from threading import Thread

# --- Configuration ---
TOKEN = '8241319689:AAGeQ_yEwv76AYvvDVvGvUZZuoJLtsSBQX0'  # আপনার বট টোকেন
OWNER_ID = 6048094235  # আপনার টেলিগ্রাম ইউজার আইডি

# Folder & Database Setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BOTS_DIR = os.path.join(BASE_DIR, 'my_bots')
USERS_FILE = os.path.join(BASE_DIR, 'allowed_users.json')
os.makedirs(BOTS_DIR, exist_ok=True)

# Global Users List Variable
allowed_users = []

# Load / Save Authorized Users
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return [OWNER_ID]
    return [OWNER_ID]

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(allowed_users, f)

allowed_users = load_users()
if OWNER_ID not in allowed_users:
    allowed_users.append(OWNER_ID)
    save_users()

# Process tracking
running_processes = {}  # {filename: subprocess.Popen}

bot = telebot.TeleBot(TOKEN)

# --- Keep Alive Flask Server ---
app = Flask('')

@app.route('/')
def home():
    return "shadow mini KAWSER's Hosting Server is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

keep_alive()

# --- Helper Functions ---
def is_owner(user_id):
    return user_id == OWNER_ID

def is_authorized(user_id):
    return user_id in allowed_users

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if is_owner(user_id):
        markup.add("📤 Upload File", "📂 My Files", "📊 System Status", "🛑 Stop All")
        markup.add("➕ Add User", "➖ Remove User")
    else:
        markup.add("📤 Upload File", "📂 My Files", "📊 System Status")
    return markup

# --- Auto Pip Installer ---
def auto_install_module(module_name, chat_id):
    bot.send_message(chat_id, f"🐍 Missing package `{module_name}` detected. Installing...", parse_mode='Markdown')
    cmd = [sys.executable, '-m', 'pip', 'install', module_name]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        bot.send_message(chat_id, f"✅ `{module_name}` installed successfully!")
        return True
    else:
        bot.send_message(chat_id, f"❌ Failed to install `{module_name}`.\n`{res.stderr[:300]}`", parse_mode='Markdown')
        return False

# --- Script Execution Thread ---
def run_script_thread(file_path, filename, chat_id):
    cmd = [sys.executable, file_path]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, cwd=BOTS_DIR)
    running_processes[filename] = proc
    
    bot.send_message(chat_id, f"🚀 `{filename}` is now running!", parse_mode='Markdown')
    
    # Check for early runtime errors
    time.sleep(3)
    if proc.poll() is not None:
        _, stderr = proc.communicate()
        if "ModuleNotFoundError" in stderr:
            import re
            match = re.search(r"No module named '(.+?)'", stderr)
            if match:
                missing_mod = match.group(1)
                if auto_install_module(missing_mod, chat_id):
                    run_script_thread(file_path, filename, chat_id)
                    return
        bot.send_message(chat_id, f"⚠️ Script `{filename}` stopped with error:\n```\n{stderr[:500]}\n```", parse_mode='Markdown')
        running_processes.pop(filename, None)

# --- Handlers ---
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        # অটোমেটিকভাবে ইউজারকে তার Chat ID দেখিয়ে দেওয়া হবে
        return bot.reply_to(
            message, 
            f"❌ **Unauthorized Access!**\n\n"
            f"আপনার ব্যবহারের অনুমতি নেই। বটের মালিককে আপনার **Chat ID** দিয়ে এক্সেস চান।\n\n"
            f"🆔 **Your Chat ID:** `{user_id}`", 
            parse_mode='Markdown'
        )
    
    user_type = "Owner" if is_owner(user_id) else "Authorized User"
    bot.reply_to(
        message, 
        f"👋 Welcome, **{message.from_user.first_name}** ({user_type})!\nYour Personal Hosting Manager is Ready.", 
        parse_mode='Markdown', 
        reply_markup=main_keyboard(user_id)
    )

@bot.message_handler(func=lambda message: message.text == "➕ Add User")
def add_user_start(message):
    if not is_owner(message.from_user.id): return
    msg = bot.reply_to(message, "👤 **নতুন ইউজারের Telegram Chat ID লিখুন:**", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_add_user)

def process_add_user(message):
    global allowed_users
    try:
        new_id = int(message.text.strip())
        if new_id in allowed_users:
            bot.reply_to(message, "⚠️ এই ইউজারটি আগে থেকেই যুক্ত আছে।")
        else:
            allowed_users.append(new_id)
            save_users()
            bot.reply_to(message, f"✅ Chat ID `{new_id}` সফলভাবে যুক্ত করা হয়েছে!", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ ভুল Chat ID! দয়া করে শুধুমাত্র সংখ্যা পাঠাবেন।")

@bot.message_handler(func=lambda message: message.text == "➖ Remove User")
def remove_user_start(message):
    if not is_owner(message.from_user.id): return
    users_list = [str(u) for u in allowed_users if u != OWNER_ID]
    if not users_list:
        return bot.reply_to(message, "ℹ️ বর্তমানে কোনো সাব-ইউজার নেই।")
    
    msg = bot.reply_to(message, f"👥 **ইউজার সরাতে তার Chat ID পাঠাও:**\n\nবর্তমান ইউজারসমূহ:\n`" + "\n".join(users_list) + "`", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_remove_user)

def process_remove_user(message):
    global allowed_users
    try:
        rem_id = int(message.text.strip())
        if rem_id in allowed_users and rem_id != OWNER_ID:
            allowed_users.remove(rem_id)
            save_users()
            bot.reply_to(message, f"✅ Chat ID `{rem_id}` কে সফলভাবে রিমুভ করা হয়েছে!", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ ইউজার খুঁজে পাওয়া যায়নি অথবা অনাকাঙ্ক্ষিত আইডি।")
    except ValueError:
        bot.reply_to(message, "❌ ভুল Chat ID! দয়া করে শুধুমাত্র সংখ্যা পাঠাবেন।")

@bot.message_handler(func=lambda message: message.text == "📊 System Status")
def system_status(message):
    if not is_authorized(message.from_user.id): return
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    active = len(running_processes)
    bot.reply_to(message, f"⚙️ **System Status:**\n\n🖥 CPU Usage: {cpu}%\n💾 RAM Usage: {ram}%\n🔄 Running Scripts: {active}", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text in ["📤 Upload File", "Upload File"])
def upload_instruction(message):
    if not is_authorized(message.from_user.id): return
    bot.reply_to(message, "📤 সরাসরি যেকোনো `.py` বা `.zip` ফাইল এই চ্যাটে সেন্ড করুন।", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📂 My Files")
def list_files(message):
    if not is_authorized(message.from_user.id): return
    files = [f for f in os.listdir(BOTS_DIR) if f.endswith('.py')]
    if not files:
        return bot.reply_to(message, "📂 No `.py` files uploaded yet.")
    
    for f in files:
        status = "🟢 Running" if f in running_processes and running_processes[f].poll() is None else "🔴 Stopped"
        markup = types.InlineKeyboardMarkup()
        
        if status == "🟢 Running":
            stop_btn = types.InlineKeyboardButton("🛑 Stop Script", callback_data=f"stop_{f}")
            markup.add(stop_btn)
        else:
            run_btn = types.InlineKeyboardButton("▶️ Run Script", callback_data=f"run_{f}")
            del_btn = types.InlineKeyboardButton("🗑 Delete File", callback_data=f"del_{f}")
            markup.add(run_btn, del_btn)
            
        bot.send_message(message.chat.id, f"📄 **File:** `{f}`\n**Status:** {status}", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if not is_authorized(call.from_user.id):
        return bot.answer_callback_query(call.id, "Access Denied!", show_alert=True)
        
    filename = call.data.split('_', 1)[1]
    filepath = os.path.join(BOTS_DIR, filename)

    if call.data.startswith("run_"):
        if filename in running_processes and running_processes[filename].poll() is None:
            bot.answer_callback_query(call.id, "Already Running!")
        else:
            threading.Thread(target=run_script_thread, args=(filepath, filename, call.message.chat.id)).start()
            bot.answer_callback_query(call.id, "Starting script...")

    elif call.data.startswith("stop_"):
        if filename in running_processes:
            running_processes[filename].terminate()
            running_processes.pop(filename, None)
            bot.answer_callback_query(call.id, "Script stopped.")
            bot.edit_message_text(f"📄 **File:** `{filename}`\n**Status:** 🔴 Stopped", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

    elif call.data.startswith("del_"):
        if filename in running_processes:
            running_processes[filename].terminate()
            running_processes.pop(filename, None)
        if os.path.exists(filepath):
            os.remove(filepath)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "File deleted.")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not is_authorized(message.from_user.id): return
    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name

    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        return bot.reply_to(message, "❌ Only `.py` or `.zip` files are allowed!")

    downloaded_file = bot.download_file(file_info.file_path)
    file_path = os.path.join(BOTS_DIR, file_name)

    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    if file_name.endswith('.zip'):
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(BOTS_DIR)
            os.remove(file_path)
            bot.reply_to(message, f"📦 `{file_name}` extracted successfully!\nGo to **📂 My Files** to run your `.py` files.", parse_mode='Markdown')
        except Exception as e:
            bot.reply_to(message, f"❌ Failed to extract zip file: {e}")
    else:
        bot.reply_to(message, f"✅ `{file_name}` uploaded successfully!\nGo to **📂 My Files** to run it.", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🛑 Stop All")
def stop_all(message):
    if not is_owner(message.from_user.id): 
        return bot.reply_to(message, "❌ Only Owner can stop all scripts!")
    
    count = 0
    for name, proc in list(running_processes.items()):
        proc.terminate()
        running_processes.pop(name, None)
        count += 1
    bot.reply_to(message, f"🛑 Stopped {count} running script(s).")

# Bot Infinity Polling Setup
if __name__ == "__main__":
    bot.infinity_polling()
