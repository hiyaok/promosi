"""
Telegram Bot + Multi Userbot Manager with Telethon
Masukkan API_ID, API_HASH, BOT_TOKEN, dan ADMIN_ID Anda di bawah
"""

import os
import asyncio
import json
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
import logging

# ======================== KONFIGURASI ========================
API_ID = 38306865  # Ganti dengan API ID Anda
API_HASH = "e7948f749e507736348952323498613f"  # Ganti dengan API Hash Anda
BOT_TOKEN = "7782738957:AAFMup-SDCeb6A-0L9K5PU8oxy99TTrMJHA"  # Ganti dengan Bot Token Anda
ADMIN_ID = 5988451717  # Ganti dengan User ID admin Anda

# Setup logging
logging.basicConfig(
    format='[%(levelname)s] %(asctime)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== DATABASE FILES ========================
USERBOT_DB = "ushai.json"
MESSAGES_DB = "msg.json"
SETTINGS_DB = "setwoi.json"

# ======================== HELPER FUNCTIONS ========================
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

# ======================== GLOBAL VARIABLES ========================
bot = TelegramClient('bot_session', API_ID, API_HASH)
userbots = {}  # {user_id: {'client': client, 'session': string, 'active': bool, 'admin_id': int}}
messages_list = {}  # {admin_id: [{'id': int, 'message': message_obj}]}
settings = load_json(SETTINGS_DB) if os.path.exists(SETTINGS_DB) else {'delay': 1, 'active': False}
temp_auth = {}  # Temporary storage for authentication process

# ======================== BOT COMMANDS ========================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    buttons = [
        [Button.inline("➕ Tambah Ubot", b"add_ubot")],
        [Button.inline("🔄 On/Off All Ubot", b"toggle_ubots")],
        [Button.inline("👥 Join Ch/Grup", b"join_group")],
        [Button.inline("📊 Status", b"status")],
        [Button.inline("📢 Set Laporan Group", b"set_report")]
    ]
    
    await event.respond(
        "🤖 **Bot Userbot Manager**\n\n"
        f"👤 Admin: `{ADMIN_ID}`\n"
        f"📱 Userbot Aktif: `{len([u for u in userbots.values() if u['active']])}/{len(userbots)}`\n"
        f"🔔 Status: `{'ON' if settings.get('active', False) else 'OFF'}`\n"
        f"📢 Laporan: `{settings.get('report_chat', 'Belum diset')}`\n\n"
        "Pilih menu di bawah:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=b"add_ubot"))
async def add_ubot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ sok asik", alert=True)
        return
    
    buttons = [
        [Button.inline("📱 Via Nomor Telepon", b"add_phone")],
        [Button.inline("📝 Via String Session", b"add_string")],
        [Button.inline("🔙 Balik", b"back_main")]
    ]
    
    await event.edit(
        "➕ **Tambah Userbot Baru**\n\n"
        "Pilih metode autentikasi:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=b"add_phone"))
async def add_phone_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ apasi", alert=True)
        return
    
    await event.edit("📱 Silakan kirim nomor telepon (dengan kode negara, contoh: +6281234567890)")
    temp_auth[event.sender_id] = {'step': 'phone'}

@bot.on(events.CallbackQuery(pattern=b"add_string"))
async def add_string_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ apasi", alert=True)
        return
    
    await event.edit(
        "📝 **String Session**\n\n"
        "Silakan kirim string session Anda atau kirim file session (.session)"
    )
    temp_auth[event.sender_id] = {'step': 'string'}

@bot.on(events.NewMessage(func=lambda e: e.sender_id == ADMIN_ID and ADMIN_ID in temp_auth))
async def auth_process_handler(event):
    step_data = temp_auth[ADMIN_ID]
    step = step_data.get('step')
    
    if step == 'phone':
        phone = event.text.strip()
        if not phone.startswith('+'):
            await event.respond("❌ Nomor harus dimulai dengan + dan kode negara")
            return
        
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            await client.send_code_request(phone)
            temp_auth[ADMIN_ID] = {'step': 'code', 'phone': phone, 'client': client}
            await event.respond(f"✅ Kode OTP telah dikirim ke `{phone}`\n\nSilakan kirim kode OTP:")
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            del temp_auth[ADMIN_ID]
    
    elif step == 'code':
        code = event.text.strip()
        phone = step_data['phone']
        client = step_data['client']
        
        try:
            await client.sign_in(phone, code)
            session_string = client.session.save()
            
            # Save userbot
            user = await client.get_me()
            user_id = user.id
            
            userbots[user_id] = {
                'client': client,
                'session': session_string,
                'active': True,
                'admin_id': ADMIN_ID
            }
            
            # Save to file
            save_userbots()
            
            # Send session file
            session_file = f"session_{user_id}.session"
            with open(session_file, 'w') as f:
                f.write(session_string)
            
            await event.respond(
                f"✅ **Userbot Berhasil Ditambahkan!**\n\n"
                f"👤 Nama: `{user.first_name}`\n"
                f"🆔 ID: `{user_id}`\n"
                f"📱 Phone: `{phone}`\n\n"
                f"📝 **String Session:**\n`{session_string}`\n\n"
                f"💾 File session juga dikirim di bawah ini ⬇️"
            )
            
            # Send file with caption
            await event.respond(
                "💾 **File String Session**\n\n"
                "Simpan file ini dengan aman!",
                file=session_file
            )
            
            os.remove(session_file)
            del temp_auth[ADMIN_ID]
            
            # Start userbot
            await start_userbot_handlers(client, user_id)
            
        except SessionPasswordNeededError:
            temp_auth[ADMIN_ID] = {'step': 'password', 'phone': phone, 'client': client}
            await event.respond("🔐 Akun dilindungi 2FA. Silakan kirim password:")
        except PhoneCodeInvalidError:
            await event.respond("❌ Kode OTP salah! Silakan kirim kode yang benar:")
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            await client.disconnect()
            del temp_auth[ADMIN_ID]
    
    elif step == 'password':
        password = event.text.strip()
        phone = step_data['phone']
        client = step_data['client']
        
        try:
            await client.sign_in(password=password)
            session_string = client.session.save()
            
            user = await client.get_me()
            user_id = user.id
            
            userbots[user_id] = {
                'client': client,
                'session': session_string,
                'active': True,
                'admin_id': ADMIN_ID
            }
            
            save_userbots()
            
            session_file = f"session_{user_id}.session"
            with open(session_file, 'w') as f:
                f.write(session_string)
            
            await event.respond(
                f"✅ **Userbot Berhasil Ditambahkan!**\n\n"
                f"👤 Nama: `{user.first_name}`\n"
                f"🆔 ID: `{user_id}`\n"
                f"📱 Phone: `{phone}`\n\n"
                f"📝 **String Session:**\n`{session_string}`\n\n"
                f"💾 File session juga dikirim di bawah ini ⬇️"
            )
            
            # Send file with caption
            await event.respond(
                "💾 **File String Session**\n\n"
                "Simpan file ini dengan aman!",
                file=session_file
            )
            
            os.remove(session_file)
            del temp_auth[ADMIN_ID]
            
            await start_userbot_handlers(client, user_id)
            
        except PasswordHashInvalidError:
            await event.respond("❌ Password salah! Silakan kirim password yang benar:")
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            await client.disconnect()
            del temp_auth[ADMIN_ID]
    
    elif step == 'string':
        if event.file:
            # Handle file session
            file_path = await event.download_media()
            with open(file_path, 'r') as f:
                session_string = f.read().strip()
            os.remove(file_path)
        else:
            session_string = event.text.strip()
        
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                await event.respond("❌ String session tidak valid atau expired")
                await client.disconnect()
                del temp_auth[ADMIN_ID]
                return
            
            user = await client.get_me()
            user_id = user.id
            
            userbots[user_id] = {
                'client': client,
                'session': session_string,
                'active': True,
                'admin_id': ADMIN_ID
            }
            
            save_userbots()
            
            await event.respond(
                f"✅ **Userbot Berhasil Ditambahkan!**\n\n"
                f"👤 Nama: `{user.first_name}`\n"
                f"🆔 ID: `{user_id}`"
            )
            
            del temp_auth[ADMIN_ID]
            
            await start_userbot_handlers(client, user_id)
            
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            del temp_auth[ADMIN_ID]

@bot.on(events.CallbackQuery(pattern=b"toggle_ubots"))
async def toggle_ubots_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    settings['active'] = not settings.get('active', False)
    save_json(SETTINGS_DB, settings)
    
    status = "ON ✅" if settings['active'] else "OFF ❌"
    for user_id, ubot in userbots.items():
        ubot['active'] = settings['active']
    
    save_userbots()
    
    await event.answer(f"Status All Userbot: {status}", alert=True)
    await event.edit(
        f"🔄 **Status Updated**\n\n"
        f"All Userbot sekarang: **{status}**",
        buttons=[[Button.inline("🔙 Kembali", b"back_main")]]
    )

@bot.on(events.CallbackQuery(pattern=b"join_group"))
async def join_group_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "👥 **Join Channel/Group**\n\n"
        "Silakan kirim link channel atau group (public/private):\n"
        "Contoh: https://t.me/channel_name atau https://t.me/joinchat/xxxxx"
    )
    temp_auth[event.sender_id] = {'step': 'join'}

@bot.on(events.NewMessage(func=lambda e: e.sender_id == ADMIN_ID and ADMIN_ID in temp_auth and temp_auth[ADMIN_ID].get('step') == 'join'))
async def join_process_handler(event):
    link = event.text.strip()
    
    if 'joinchat' in link or '+' in link:
        # Private group/channel
        hash_code = link.split('/')[-1].replace('+', '')
        is_private = True
    else:
        # Public group/channel
        username = link.split('/')[-1].replace('@', '')
        is_private = False
    
    success_count = 0
    fail_count = 0
    
    for user_id, ubot in userbots.items():
        if not ubot['active']:
            continue
        
        try:
            client = ubot['client']
            if is_private:
                await client(ImportChatInviteRequest(hash_code))
            else:
                await client(JoinChannelRequest(username))
            success_count += 1
        except Exception as e:
            logger.error(f"Userbot {user_id} failed to join: {str(e)}")
            fail_count += 1
        
        await asyncio.sleep(2)  # Delay to avoid flood
    
    await event.respond(
        f"✅ **Join Completed**\n\n"
        f"Success: `{success_count}`\n"
        f"Failed: `{fail_count}`"
    )
    del temp_auth[ADMIN_ID]

@bot.on(events.CallbackQuery(pattern=b"status"))
async def status_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    status_text = f"📊 **Status Userbot**\n\n"
    status_text += f"🔔 Global: `{'ON' if settings.get('active', False) else 'OFF'}`\n"
    status_text += f"⏱ Delay: `{settings.get('delay', 1)} detik`\n\n"
    
    if not userbots:
        status_text += "❌ Tidak ada userbot"
    else:
        for user_id, ubot in userbots.items():
            try:
                user = await ubot['client'].get_me()
                name = user.first_name
                status = "✅ ON" if ubot['active'] else "❌ OFF"
                status_text += f"• `{name}` ({user_id}): {status}\n"
            except:
                status_text += f"• ID {user_id}: ⚠️ Error\n"
    
    await event.edit(status_text, buttons=[[Button.inline("🔙 Kembali", b"back_main")]])

@bot.on(events.CallbackQuery(pattern=b"back_main"))
async def back_main_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    buttons = [
        [Button.inline("➕ Tambah Userbot", b"add_ubot")],
        [Button.inline("🔄 On/Off All Userbot", b"toggle_ubots")],
        [Button.inline("👥 Join Channel/Group", b"join_group")],
        [Button.inline("📊 Status", b"status")],
        [Button.inline("📢 Set Laporan Group", b"set_report")]
    ]
    
    await event.edit(
        "🤖 **Bot Multi Userbot Manager**\n\n"
        f"👤 Admin: `{ADMIN_ID}`\n"
        f"📱 Userbot Aktif: `{len([u for u in userbots.values() if u['active']])}/{len(userbots)}`\n"
        f"🔔 Status: `{'ON' if settings.get('active', False) else 'OFF'}`\n"
        f"📢 Laporan: `{settings.get('report_chat', 'Belum diset')}`\n\n"
        "Pilih menu di bawah:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=b"set_report"))
async def set_report_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "📢 **Set Group Laporan**\n\n"
        "Silakan kirim link grup Telegram untuk menerima laporan:\n"
        "Contoh: https://t.me/nama_grup atau https://t.me/joinchat/xxxxx\n\n"
        "⚠️ Pastikan bot sudah masuk ke grup tersebut!"
    )
    temp_auth[event.sender_id] = {'step': 'set_report'}

@bot.on(events.NewMessage(func=lambda e: e.sender_id == ADMIN_ID and ADMIN_ID in temp_auth and temp_auth[ADMIN_ID].get('step') == 'set_report'))
async def set_report_process_handler(event):
    link = event.text.strip()
    
    try:
        # Extract username from link
        if 't.me/' in link:
            username = link.split('/')[-1].replace('@', '')
            
            # Try to get the chat
            chat = await bot.get_entity(username)
            settings['report_chat'] = chat.id
            settings['report_chat_name'] = getattr(chat, 'title', username)
            save_json(SETTINGS_DB, settings)
            
            # Join all userbots to report group
            success = 0
            for user_id, ubot in userbots.items():
                if not ubot['active']:
                    continue
                try:
                    await ubot['client'].get_entity(username)
                    success += 1
                except:
                    try:
                        await ubot['client'](JoinChannelRequest(username))
                        success += 1
                    except Exception as e:
                        logger.error(f"Userbot {user_id} failed to join report group: {str(e)}")
                await asyncio.sleep(2)
            
            await event.respond(
                f"✅ **Laporan Group Berhasil Diset!**\n\n"
                f"📢 Group: `{settings['report_chat_name']}`\n"
                f"🆔 ID: `{settings['report_chat']}`\n"
                f"👥 Userbot joined: `{success}/{len([u for u in userbots.values() if u['active']])}`"
            )
            
            # Send test message to report group
            await bot.send_message(
                settings['report_chat'],
                "✅ **Bot Siap Mengirim Laporan**\n\n"
                "Semua laporan broadcast akan dikirim ke grup ini."
            )
            
        else:
            await event.respond("❌ Format link tidak valid!")
    except Exception as e:
        await event.respond(f"❌ Error: {str(e)}\n\nPastikan bot sudah masuk ke grup tersebut!")
    
    del temp_auth[ADMIN_ID]

# ======================== USERBOT COMMANDS ========================
async def start_userbot_handlers(client, user_id):
    """Start handlers for a userbot"""
    
    @client.on(events.NewMessage(pattern=r'^\.add$', outgoing=True))
    async def add_message_handler(event):
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        if not event.is_reply:
            await event.edit("❌ Reply ke pesan yang ingin ditambahkan!")
            return
        
        replied = await event.get_reply_message()
        
        admin_id = ubot['admin_id']
        if admin_id not in messages_list:
            messages_list[admin_id] = []
        
        msg_id = len(messages_list[admin_id]) + 1
        messages_list[admin_id].append({
            'id': msg_id,
            'text': replied.text or '',
            'media': replied.media,
            'message_obj': replied
        })
        
        save_messages()
        await event.edit(f"✅ Pesan ditambahkan ke list (ID: {msg_id})")
    
    @client.on(events.NewMessage(pattern=r'^\.list$', outgoing=True))
    async def list_messages_handler(event):
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        admin_id = ubot['admin_id']
        msgs = messages_list.get(admin_id, [])
        
        if not msgs:
            await event.edit("❌ List kosong")
            return
        
        text = "📋 **Daftar Pesan:**\n\n"
        for msg in msgs:
            preview = msg['text'][:50] + "..." if len(msg['text']) > 50 else msg['text']
            text += f"{msg['id']}. {preview or '[Media]'}\n"
        
        await event.edit(text)
    
    @client.on(events.NewMessage(pattern=r'^\.delay (\d+)$', outgoing=True))
    async def delay_handler(event):
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        delay = int(event.pattern_match.group(1))
        settings['delay'] = delay
        save_json(SETTINGS_DB, settings)
        
        await event.edit(f"✅ Delay diset ke {delay} detik")
    
    @client.on(events.NewMessage(pattern=r'^\.del (\d+)$', outgoing=True))
    async def delete_message_handler(event):
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        msg_id = int(event.pattern_match.group(1))
        admin_id = ubot['admin_id']
        msgs = messages_list.get(admin_id, [])
        
        found = False
        for i, msg in enumerate(msgs):
            if msg['id'] == msg_id:
                msgs.pop(i)
                found = True
                break
        
        if found:
            # Re-index
            for i, msg in enumerate(msgs):
                msg['id'] = i + 1
            save_messages()
            await event.edit(f"✅ Pesan ID {msg_id} dihapus")
        else:
            await event.edit(f"❌ Pesan ID {msg_id} tidak ditemukan")
    
    @client.on(events.NewMessage(pattern=r'^\.delall$', outgoing=True))
    async def delete_all_handler(event):
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        admin_id = ubot['admin_id']
        messages_list[admin_id] = []
        save_messages()
        
        await event.edit("✅ Semua pesan dihapus")
    
    @client.on(events.NewMessage(pattern=r'^\.forward$', outgoing=True))
    async def forward_handler(event):
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        admin_id = ubot['admin_id']
        msgs = messages_list.get(admin_id, [])
        
        if not msgs:
            await event.edit("❌ List kosong")
            return
        
        await event.edit("🔄 Memulai forward ke semua grup...")
        
        delay = settings.get('delay', 1)
        dialogs = await client.get_dialogs()
        groups = [d for d in dialogs if d.is_group]
        
        total_sent = 0
        for msg_data in msgs:
            for group in groups:
                try:
                    if msg_data.get('message_obj'):
                        await client.forward_messages(group.id, msg_data['message_obj'])
                    else:
                        await client.send_message(group.id, msg_data['text'])
                    total_sent += 1
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"Failed to forward to {group.id}: {str(e)}")
        
        await event.respond(f"✅ Selesai! Total pesan dikirim: {total_sent}")

# ======================== PERSISTENCE FUNCTIONS ========================
def save_userbots():
    """Save userbots to file"""
    data = {}
    for user_id, ubot in userbots.items():
        data[str(user_id)] = {
            'session': ubot['session'],
            'active': ubot['active'],
            'admin_id': ubot['admin_id']
        }
    save_json(USERBOT_DB, data)

def load_userbots():
    """Load userbots from file"""
    data = load_json(USERBOT_DB)
    for user_id_str, ubot_data in data.items():
        try:
            client = TelegramClient(
                StringSession(ubot_data['session']),
                API_ID,
                API_HASH
            )
            userbots[int(user_id_str)] = {
                'client': client,
                'session': ubot_data['session'],
                'active': ubot_data['active'],
                'admin_id': ubot_data['admin_id']
            }
        except Exception as e:
            logger.error(f"Failed to load userbot {user_id_str}: {str(e)}")

def save_messages():
    """Save messages list to file"""
    data = {}
    for admin_id, msgs in messages_list.items():
        data[str(admin_id)] = [
            {'id': msg['id'], 'text': msg['text']} 
            for msg in msgs
        ]
    save_json(MESSAGES_DB, data)

def load_messages():
    """Load messages from file"""
    data = load_json(MESSAGES_DB)
    for admin_id_str, msgs in data.items():
        messages_list[int(admin_id_str)] = msgs

# ======================== MAIN FUNCTION ========================
async def main():
    """Main function"""
    logger.info("Starting bot...")
    
    # Load data
    load_userbots()
    load_messages()
    
    # Start bot
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started!")
    
    # Start all userbots
    for user_id, ubot in userbots.items():
        try:
            client = ubot['client']
            await client.connect()
            if await client.is_user_authorized():
                await start_userbot_handlers(client, user_id)
                logger.info(f"Userbot {user_id} started!")
            else:
                logger.warning(f"Userbot {user_id} not authorized")
        except Exception as e:
            logger.error(f"Failed to start userbot {user_id}: {str(e)}")
    
    logger.info("All systems running!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
