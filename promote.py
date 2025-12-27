"""
╔══════════════════════════════════════════════════════════╗
║  Telegram Bot + Multi Userbot Manager with Telethon     ║
║  Fixed Version with Anti-Flood & Beautiful UI            ║
╚══════════════════════════════════════════════════════════╝

Masukkan API_ID, API_HASH, BOT_TOKEN, dan ADMIN_ID Anda di bawah
"""

import os
import asyncio
import json
import random
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError, 
    PasswordHashInvalidError,
    FloodWaitError,
    ChatWriteForbiddenError,
    UserBannedInChannelError
)
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
import logging

# ════════════════════════ KONFIGURASI ════════════════════════
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

# ════════════════════════ DATABASE FILES ════════════════════════
USERBOT_DB = "usr.json"
MESSAGES_DB = "msg.json"
SETTINGS_DB = "set.json"

# ════════════════════════ HELPER FUNCTIONS ════════════════════════
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

# ════════════════════════ GLOBAL VARIABLES ════════════════════════
bot = TelegramClient('bot_session', API_ID, API_HASH)
userbots = {}  # {user_id: {'client': client, 'session': string, 'active': bool}}
messages_list = []  # List of message links
settings = load_json(SETTINGS_DB) if os.path.exists(SETTINGS_DB) else {
    'delay': 0, 
    'active': False, 
    'report_chat': None,
    'group_delay': 3  # Delay 3 detik per grup (anti-flood)
}
temp_auth = {}  # Temporary storage for authentication
broadcast_running = False  # Flag untuk cek broadcast

# ════════════════════════ BOT MAIN MENU ════════════════════════
def get_main_menu():
    """Generate main menu buttons with beautiful formatting"""
    delay_status = f"{settings.get('delay', 0)} menit" if settings.get('delay', 0) > 0 else "Belum diset ⚠️"
    list_count = len(messages_list)
    active_count = len([u for u in userbots.values() if u['active']])
    total_count = len(userbots)
    
    buttons = [
        [Button.inline("➕ Tambah Userbot", b"add_ubot")],
        [Button.inline(f"⏱ Set Delay ({delay_status})", b"set_delay")],
        [Button.inline(f"📝 Add List ({list_count})", b"add_list")],
        [Button.inline(f"📋 Cek List ({list_count})", b"check_list")],
        [Button.inline("👥 Join Channel/Group", b"join_group")],
        [Button.inline("📢 Set Laporan Group", b"set_report")],
        [Button.inline(f"👤 Userbot ({active_count}/{total_count})", b"manage_ubots")],
        [Button.inline("📊 Status System", b"status")]
    ]
    
    # Tombol ON/OFF
    if settings.get('delay', 0) > 0 and list_count > 0:
        status_text = "🔴 OFF Broadcast" if settings.get('active', False) else "🟢 ON Broadcast"
        buttons.insert(4, [Button.inline(status_text, b"toggle_broadcast")])
    
    return buttons

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    buttons = get_main_menu()
    
    delay_text = f"`{settings.get('delay', 0)} menit`" if settings.get('delay', 0) > 0 else "`Belum diset ⚠️`"
    report_text = f"`{settings.get('report_chat_name', 'Belum diset ⚠️')}`"
    active_count = len([u for u in userbots.values() if u['active']])
    
    await event.respond(
        "╔═══════════════════════════════╗\n"
        "║  🤖 **MULTI USERBOT MANAGER**  ║\n"
        "╚═══════════════════════════════╝\n\n"
        f"👤 **Admin:** `{ADMIN_ID}`\n"
        f"📱 **Userbot Aktif:** `{active_count}/{len(userbots)}`\n"
        f"📝 **List Pesan:** `{len(messages_list)}`\n"
        f"⏱ **Delay:** {delay_text}\n"
        f"📢 **Laporan:** {report_text}\n"
        f"🔔 **Status:** `{'ON ✅' if settings.get('active', False) else 'OFF ❌'}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 **Pilih menu di bawah:**",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=b"back_main"))
async def back_main_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    buttons = get_main_menu()
    
    delay_text = f"`{settings.get('delay', 0)} menit`" if settings.get('delay', 0) > 0 else "`Belum diset ⚠️`"
    report_text = f"`{settings.get('report_chat_name', 'Belum diset ⚠️')}`"
    active_count = len([u for u in userbots.values() if u['active']])
    
    await event.edit(
        "╔═══════════════════════════════╗\n"
        "║  🤖 **MULTI USERBOT MANAGER**  ║\n"
        "╚═══════════════════════════════╝\n\n"
        f"👤 **Admin:** `{ADMIN_ID}`\n"
        f"📱 **Userbot Aktif:** `{active_count}/{len(userbots)}`\n"
        f"📝 **List Pesan:** `{len(messages_list)}`\n"
        f"⏱ **Delay:** {delay_text}\n"
        f"📢 **Laporan:** {report_text}\n"
        f"🔔 **Status:** `{'ON ✅' if settings.get('active', False) else 'OFF ❌'}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 **Pilih menu di bawah:**",
        buttons=buttons
    )

# ════════════════════════ MANAGE USERBOTS ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"manage_ubots"))
async def manage_ubots_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    if not userbots:
        await event.edit(
            "╔═══════════════════════════════╗\n"
            "║     ❌ **TIDAK ADA USERBOT**     ║\n"
            "╚═══════════════════════════════╝\n\n"
            "Tambah userbot terlebih dahulu!",
            buttons=[[Button.inline("🔙 Kembali", b"back_main")]]
        )
        return
    
    buttons = []
    text = "╔═══════════════════════════════╗\n"
    text += "║     👥 **MANAGE USERBOTS**      ║\n"
    text += "╚═══════════════════════════════╝\n\n"
    
    for user_id, ubot in userbots.items():
        try:
            user = await ubot['client'].get_me()
            name = user.first_name[:20]
            status = "✅" if ubot['active'] else "❌"
            buttons.append([
                Button.inline(f"{status} {name}", f"toggle_ubot_{user_id}".encode()),
                Button.inline("🗑", f"delete_ubot_{user_id}".encode())
            ])
        except:
            buttons.append([
                Button.inline(f"⚠️ ID {user_id}", f"delete_ubot_{user_id}".encode())
            ])
    
    buttons.append([Button.inline("🔙 Kembali", b"back_main")])
    
    await event.edit(text + "Klik untuk toggle ON/OFF atau hapus:", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=rb"toggle_ubot_(\d+)"))
async def toggle_ubot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    user_id = int(event.data.decode().split('_')[-1])
    
    if user_id in userbots:
        userbots[user_id]['active'] = not userbots[user_id]['active']
        save_userbots()
        status = "ON ✅" if userbots[user_id]['active'] else "OFF ❌"
        await event.answer(f"Userbot {status}", alert=True)
        
        # Refresh list
        await manage_ubots_handler(event)

@bot.on(events.CallbackQuery(pattern=rb"delete_ubot_(\d+)"))
async def delete_ubot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    user_id = int(event.data.decode().split('_')[-1])
    
    buttons = [
        [Button.inline("✅ Ya, Hapus", f"confirm_delete_ubot_{user_id}".encode())],
        [Button.inline("❌ Batal", b"manage_ubots")]
    ]
    
    await event.edit(
        "⚠️ **KONFIRMASI HAPUS**\n\n"
        f"Yakin ingin menghapus userbot `{user_id}`?",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=rb"confirm_delete_ubot_(\d+)"))
async def confirm_delete_ubot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    user_id = int(event.data.decode().split('_')[-1])
    
    if user_id in userbots:
        try:
            await userbots[user_id]['client'].disconnect()
        except:
            pass
        del userbots[user_id]
        save_userbots()
        await event.answer("✅ Userbot dihapus!", alert=True)
        await manage_ubots_handler(event)

# ════════════════════════ ADD USERBOT ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"add_ubot"))
async def add_ubot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    buttons = [
        [Button.inline("📱 Via Nomor Telepon", b"add_phone")],
        [Button.inline("📝 Via String Session", b"add_string")],
        [Button.inline("🔙 Kembali", b"back_main")]
    ]
    
    await event.edit(
        "╔═══════════════════════════════╗\n"
        "║   ➕ **TAMBAH USERBOT BARU**    ║\n"
        "╚═══════════════════════════════╝\n\n"
        "Pilih metode autentikasi:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=b"add_phone"))
async def add_phone_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "📱 **AUTENTIKASI VIA NOMOR**\n\n"
        "Silakan kirim nomor telepon dengan kode negara.\n\n"
        "**Contoh:** `+6281234567890`"
    )
    temp_auth[event.sender_id] = {'step': 'phone'}

@bot.on(events.CallbackQuery(pattern=b"add_string"))
async def add_string_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "📝 **AUTENTIKASI VIA STRING**\n\n"
        "Silakan kirim string session Anda atau kirim file session (.session)"
    )
    temp_auth[event.sender_id] = {'step': 'string'}

# ════════════════════════ SET DELAY ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"set_delay"))
async def set_delay_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "⏱ **SET DELAY BROADCAST**\n\n"
        "Silakan kirim delay dalam menit (minimal 1 menit).\n\n"
        "**Contoh:** `5` untuk 5 menit"
    )
    temp_auth[event.sender_id] = {'step': 'set_delay'}

# ════════════════════════ ADD LIST ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"add_list"))
async def add_list_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "📝 **ADD LIST PESAN**\n\n"
        "Silakan kirim link pesan dari grup/channel:\n\n"
        "**Format:**\n"
        "• Public: `https://t.me/namagroup/123`\n"
        "• Private: `https://t.me/c/1234567890/123`\n\n"
        "⚠️ Pastikan userbot sudah join ke channel/grup tersebut!"
    )
    temp_auth[event.sender_id] = {'step': 'add_list'}

# ════════════════════════ CHECK LIST ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"check_list"))
async def check_list_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    if not messages_list:
        await event.edit(
            "╔═══════════════════════════════╗\n"
            "║      ❌ **LIST KOSONG**         ║\n"
            "╚═══════════════════════════════╝\n\n"
            "Belum ada pesan di list.",
            buttons=[[Button.inline("🔙 Kembali", b"back_main")]]
        )
        return
    
    text = "╔═══════════════════════════════╗\n"
    text += "║      📋 **DAFTAR PESAN**        ║\n"
    text += "╚═══════════════════════════════╝\n\n"
    text += f"**Total:** `{len(messages_list)}` pesan\n\n"
    
    buttons = []
    for i, msg in enumerate(messages_list, 1):
        buttons.append([Button.inline(f"🗑 Hapus #{i}", f"delete_list_{i}".encode())])
    
    buttons.append([Button.inline("🗑 Hapus Semua", b"delete_all_list")])
    buttons.append([Button.inline("🔙 Kembali", b"back_main")])
    
    await event.edit(text, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=rb"delete_list_(\d+)"))
async def delete_list_item_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    index = int(event.data.decode().split('_')[-1]) - 1
    
    if 0 <= index < len(messages_list):
        messages_list.pop(index)
        save_messages()
        await event.answer(f"✅ Pesan #{index + 1} dihapus!", alert=True)
        
        # Refresh list
        await check_list_handler(event)
    else:
        await event.answer("❌ Pesan tidak ditemukan!", alert=True)

@bot.on(events.CallbackQuery(pattern=b"delete_all_list"))
async def delete_all_list_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    buttons = [
        [Button.inline("✅ Ya, Hapus Semua", b"confirm_delete_all")],
        [Button.inline("❌ Batal", b"check_list")]
    ]
    
    await event.edit(
        "⚠️ **KONFIRMASI HAPUS**\n\n"
        f"Yakin ingin menghapus semua `{len(messages_list)}` pesan dari list?",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(pattern=b"confirm_delete_all"))
async def confirm_delete_all_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    count = len(messages_list)
    messages_list.clear()
    save_messages()
    
    await event.edit(
        "✅ **SEMUA PESAN DIHAPUS**\n\n"
        f"Berhasil menghapus `{count}` pesan dari list.",
        buttons=[[Button.inline("🔙 Kembali", b"back_main")]]
    )

# ════════════════════════ TOGGLE BROADCAST ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"toggle_broadcast"))
async def toggle_broadcast_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    global broadcast_running
    
    if not settings.get('delay', 0) > 0:
        await event.answer("⚠️ Set delay dulu!", alert=True)
        return
    
    if not messages_list:
        await event.answer("⚠️ Tambah minimal 1 list pesan dulu!", alert=True)
        return
    
    active_ubots = [u for u in userbots.values() if u['active']]
    if not active_ubots:
        await event.answer("⚠️ Tidak ada userbot aktif!", alert=True)
        return
    
    settings['active'] = not settings.get('active', False)
    save_json(SETTINGS_DB, settings)
    
    if settings['active']:
        await event.answer("✅ Broadcast ON!", alert=True)
        if not broadcast_running:
            asyncio.create_task(broadcast_worker())
    else:
        await event.answer("❌ Broadcast OFF!", alert=True)
    
    await back_main_handler(event)

# ════════════════════════ SET REPORT GROUP ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"set_report"))
async def set_report_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "📢 **SET GROUP LAPORAN**\n\n"
        "Silakan kirim username atau link grup untuk laporan:\n\n"
        "**Format:**\n"
        "• Public: `@namagrup` atau `https://t.me/namagrup`\n"
        "• Private: `https://t.me/joinchat/xxxxx`\n\n"
        "⚠️ Pastikan bot sudah join ke grup tersebut!"
    )
    temp_auth[event.sender_id] = {'step': 'set_report'}

# ════════════════════════ JOIN GROUP ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"join_group"))
async def join_group_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    await event.edit(
        "👥 **JOIN CHANNEL/GROUP**\n\n"
        "Silakan kirim link channel atau group:\n\n"
        "**Contoh:**\n"
        "• `https://t.me/channel_name`\n"
        "• `https://t.me/joinchat/xxxxx`"
    )
    temp_auth[event.sender_id] = {'step': 'join'}

# ════════════════════════ STATUS ════════════════════════
@bot.on(events.CallbackQuery(pattern=b"status"))
async def status_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized", alert=True)
        return
    
    status_text = "╔═══════════════════════════════╗\n"
    status_text += "║    📊 **STATUS SYSTEM**        ║\n"
    status_text += "╚═══════════════════════════════╝\n\n"
    
    status_text += f"🔔 **Broadcast:** `{'ON ✅' if settings.get('active', False) else 'OFF ❌'}`\n"
    status_text += f"⏱ **Delay:** `{settings.get('delay', 0)} menit`\n"
    status_text += f"⏳ **Delay/Grup:** `{settings.get('group_delay', 3)} detik`\n"
    status_text += f"📝 **List:** `{len(messages_list)} pesan`\n"
    status_text += f"📢 **Laporan:** `{settings.get('report_chat_name', 'Belum diset')}`\n\n"
    
    status_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    status_text += "**👥 USERBOT:**\n\n"
    
    if not userbots:
        status_text += "❌ Tidak ada userbot\n"
    else:
        for user_id, ubot in userbots.items():
            try:
                user = await ubot['client'].get_me()
                name = user.first_name[:20]
                status = "✅ ON" if ubot['active'] else "❌ OFF"
                status_text += f"• `{name}` (ID: `{user_id}`): {status}\n"
            except:
                status_text += f"• ID `{user_id}`: ⚠️ Error\n"
    
    await event.edit(status_text, buttons=[[Button.inline("🔙 Kembali", b"back_main")]])

# ════════════════════════ AUTH PROCESS ════════════════════════
@bot.on(events.NewMessage(func=lambda e: e.sender_id == ADMIN_ID and ADMIN_ID in temp_auth))
async def auth_process_handler(event):
    step_data = temp_auth.get(ADMIN_ID)
    if not step_data:
        return
    
    step = step_data.get('step')
    
    # Handle set delay
    if step == 'set_delay':
        try:
            delay = int(event.text.strip())
            if delay < 1:
                await event.respond("❌ Delay minimal 1 menit!")
                return
            
            settings['delay'] = delay
            save_json(SETTINGS_DB, settings)
            
            await event.respond(
                "✅ **DELAY BERHASIL DISET!**\n\n"
                f"⏱ Delay: `{delay} menit`\n"
                f"⏳ Delay per grup: `{settings.get('group_delay', 3)} detik`"
            )
            del temp_auth[ADMIN_ID]
        except ValueError:
            await event.respond("❌ Harap kirim angka yang valid!")
        return
    
    # Handle add list
    if step == 'add_list':
        link = event.text.strip()
        
        try:
            # Parse message link
            if '/c/' in link:
                parts = link.split('/')
                channel_id = int('-100' + parts[-2])
                message_id = int(parts[-1])
            else:
                parts = link.split('/')
                username = parts[-2].replace('@', '')
                message_id = int(parts[-1])
                
                entity = await bot.get_entity(username)
                channel_id = entity.id
            
            # Verify message exists
            try:
                msg = await bot.get_messages(channel_id, ids=message_id)
                if not msg:
                    await event.respond("❌ Pesan tidak ditemukan! Pastikan bot sudah join ke channel/grup.")
                    return
            except Exception as e:
                await event.respond(f"❌ Error: {str(e)}\nPastikan bot sudah join!")
                return
            
            # Add to list
            messages_list.append({
                'channel_id': channel_id,
                'message_id': message_id
            })
            save_messages()
            
            await event.respond(
                "✅ **PESAN BERHASIL DITAMBAHKAN!**\n\n"
                f"📝 Total list: `{len(messages_list)}`"
            )
            del temp_auth[ADMIN_ID]
            
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
        return
    
    # Handle set report
    if step == 'set_report':
        link = event.text.strip()
        
        try:
            if 't.me/' in link:
                if 'joinchat' in link or '+' in link:
                    hash_code = link.split('/')[-1].replace('+', '')
                    result = await bot(ImportChatInviteRequest(hash_code))
                    chat = result.chats[0]
                else:
                    username = link.split('/')[-1].replace('@', '')
                    chat = await bot.get_entity(username)
            else:
                username = link.replace('@', '')
                chat = await bot.get_entity(username)
            
            settings['report_chat'] = chat.id
            settings['report_chat_name'] = getattr(chat, 'title', username)
            save_json(SETTINGS_DB, settings)
            
            # Join all userbots
            success = 0
            for user_id, ubot in userbots.items():
                if not ubot['active']:
                    continue
                try:
                    await ubot['client'].get_entity(chat.id)
                    success += 1
                except:
                    try:
                        if hasattr(chat, 'username') and chat.username:
                            await ubot['client'](JoinChannelRequest(chat.username))
                        success += 1
                    except:
                        pass
                await asyncio.sleep(2)
            
            await event.respond(
                "✅ **LAPORAN GROUP BERHASIL DISET!**\n\n"
                f"📢 Group: `{settings['report_chat_name']}`\n"
                f"🆔 ID: `{settings['report_chat']}`\n"
                f"👥 Userbot joined: `{success}/{len([u for u in userbots.values() if u['active']])}`"
            )
            
            await bot.send_message(
                settings['report_chat'],
                "╔═══════════════════════════════╗\n"
                "║  ✅ **BOT SIAP KIRIM LAPORAN**  ║\n"
                "╚═══════════════════════════════╝\n\n"
                "Semua laporan broadcast akan dikirim ke grup ini."
            )
            
            del temp_auth[ADMIN_ID]
            
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            del temp_auth[ADMIN_ID]
        return
    
    # Handle join group
    if step == 'join':
        link = event.text.strip()
        
        if 'joinchat' in link or '+' in link:
            hash_code = link.split('/')[-1].replace('+', '')
            is_private = True
        else:
            if 't.me/' in link:
                username = link.split('/')[-1].replace('@', '')
            else:
                username = link.replace('@', '')
            is_private = False
        
        success_count = 0
        fail_count = 0
        
        status_msg = await event.respond("⏳ Sedang join...")
        
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
            except FloodWaitError as e:
                logger.warning(f"FloodWait {e.seconds}s for userbot {user_id}")
                await asyncio.sleep(e.seconds)
                fail_count += 1
            except Exception as e:
                logger.error(f"Userbot {user_id} failed: {str(e)}")
                fail_count += 1
            
            await asyncio.sleep(3)
        
        await status_msg.edit(
            "✅ **JOIN COMPLETED**\n\n"
            f"📊 Success: `{success_count}`\n"
            f"❌ Failed: `{fail_count}`"
        )
        del temp_auth[ADMIN_ID]
        return
    
    # Handle phone auth
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
            await event.respond(
                f"✅ **KODE OTP TERKIRIM**\n\n"
                f"📱 Nomor: `{phone}`\n\n"
                f"Silakan kirim kode OTP:"
            )
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            del temp_auth[ADMIN_ID]
        return
    
    # Handle code
    if step == 'code':
        code = event.text.strip()
        phone = step_data['phone']
        client = step_data['client']
        
        try:
            await client.sign_in(phone, code)
            session_string = client.session.save()
            
            user = await client.get_me()
            user_id = user.id
            
            userbots[user_id] = {
                'client': client,
                'session': session_string,
                'active': True
            }
            
            save_userbots()
            
            session_file = f"session_{user_id}.session"
            with open(session_file, 'w') as f:
                f.write(session_string)
            
            await event.respond(
                "╔═══════════════════════════════╗\n"
                "║ ✅ **USERBOT BERHASIL DITAMBAH** ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"👤 **Nama:** `{user.first_name}`\n"
                f"🆔 **ID:** `{user_id}`\n"
                f"📱 **Phone:** `{phone}`\n\n"
                f"📝 **String Session:**\n```\n{session_string}\n```\n\n"
                f"💾 File session dikirim di bawah ini ⬇️"
            )
            
            await event.respond(
                "💾 **FILE STRING SESSION**\n\n"
                "⚠️ Simpan file ini dengan aman!",
                file=session_file
            )
            
            os.remove(session_file)
            del temp_auth[ADMIN_ID]
            
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
        return
    
    # Handle password
    if step == 'password':
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
                'active': True
            }
            
            save_userbots()
            
            session_file = f"session_{user_id}.session"
            with open(session_file, 'w') as f:
                f.write(session_string)
            
            await event.respond(
                "╔═══════════════════════════════╗\n"
                "║ ✅ **USERBOT BERHASIL DITAMBAH** ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"👤 **Nama:** `{user.first_name}`\n"
                f"🆔 **ID:** `{user_id}`\n"
                f"📱 **Phone:** `{phone}`\n\n"
                f"📝 **String Session:**\n```\n{session_string}\n```\n\n"
                f"💾 File session dikirim di bawah ini ⬇️"
            )
            
            await event.respond(
                "💾 **FILE STRING SESSION**\n\n"
                "⚠️ Simpan file ini dengan aman!",
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
        return
    
    # Handle string session
    if step == 'string':
        if event.file:
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
                'active': True
            }
            
            save_userbots()
            
            await event.respond(
                "╔═══════════════════════════════╗\n"
                "║ ✅ **USERBOT BERHASIL DITAMBAH** ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"👤 **Nama:** `{user.first_name}`\n"
                f"🆔 **ID:** `{user_id}`"
            )
            
            del temp_auth[ADMIN_ID]
            
            await start_userbot_handlers(client, user_id)
            
        except Exception as e:
            await event.respond(f"❌ Error: {str(e)}")
            del temp_auth[ADMIN_ID]
        return

# ════════════════════════ USERBOT HANDLERS ════════════════════════
async def start_userbot_handlers(client, user_id):
    """Start handlers for a userbot"""
    
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_reply and e.is_group))
    async def auto_reply_group_handler(event):
        """Auto reply when someone replies to userbot's message in group"""
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        try:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.sender_id == user_id:
                sender = await event.get_sender()
                sender_name = sender.first_name if sender.first_name else "someone"
                
                await event.reply(
                    f"Halo kak {sender_name}, untuk lebih lanjut silahkan hubungi @hiyaok aja yaaaah ka! Thank u! 😍"
                )
        except Exception as e:
            logger.error(f"Auto reply group error for userbot {user_id}: {str(e)}")
    
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def auto_reply_dm_handler(event):
        """Auto reply when someone DMs the userbot"""
        ubot = userbots.get(user_id)
        if not ubot or not ubot['active']:
            return
        
        if event.sender_id == ADMIN_ID:
            return
        
        try:
            sender = await event.get_sender()
            sender_name = sender.first_name if sender.first_name else "someone"
            
            await event.respond(
                f"Halo kak {sender_name}, untuk lebih lanjut silahkan hubungi @hiyaok aja yaaaah ka! Thank u! 😍"
            )
        except Exception as e:
            logger.error(f"Auto reply DM error for userbot {user_id}: {str(e)}")

# ════════════════════════ BROADCAST WORKER ════════════════════════
async def broadcast_worker():
    """Background worker for broadcasting messages with anti-flood"""
    global broadcast_running
    broadcast_running = True
    
    logger.info("🚀 Broadcast worker started!")
    
    while settings.get('active', False):
        if not messages_list:
            await asyncio.sleep(60)
            continue
        
        active_ubots = {uid: ubot for uid, ubot in userbots.items() if ubot['active']}
        
        if not active_ubots:
            logger.warning("⚠️ No active userbots!")
            await asyncio.sleep(60)
            continue
        
        # Assign random messages to each userbot
        used_messages = []
        ubot_messages = {}
        
        for user_id in active_ubots.keys():
            available = [m for m in messages_list if m not in used_messages]
            
            if not available:
                used_messages.clear()
                available = messages_list.copy()
            
            selected = random.choice(available)
            used_messages.append(selected)
            ubot_messages[user_id] = selected
        
        # Send start report
        report_chat = settings.get('report_chat')
        if report_chat:
            try:
                report_text = (
                    "╔═══════════════════════════════╗\n"
                    "║   📤 **BROADCAST DIMULAI**     ║\n"
                    "╚═══════════════════════════════╝\n\n"
                    f"⏰ **Waktu:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    f"👥 **Userbot Aktif:** `{len(active_ubots)}`\n"
                    f"📝 **Total List:** `{len(messages_list)}`\n"
                    f"⏱ **Delay:** `{settings.get('delay', 0)} menit`\n"
                    f"⏳ **Delay/Grup:** `{settings.get('group_delay', 3)} detik`\n"
                )
                await bot.send_message(report_chat, report_text)
            except Exception as e:
                logger.error(f"Failed to send start report: {str(e)}")
        
        # Broadcast each userbot
        for user_id, ubot in active_ubots.items():
            client = ubot['client']
            msg_data = ubot_messages[user_id]
            
            try:
                user_info = await client.get_me()
                user_name = user_info.first_name
            except:
                user_name = f"ID {user_id}"
            
            # Get source message
            try:
                source_msg = await client.get_messages(
                    msg_data['channel_id'],
                    ids=msg_data['message_id']
                )
                
                if not source_msg:
                    logger.error(f"❌ Message not found for userbot {user_id}")
                    continue
                
            except Exception as e:
                logger.error(f"❌ Failed to get source message for userbot {user_id}: {str(e)}")
                continue
            
            # Get all groups
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group]
            
            if not groups:
                logger.warning(f"⚠️ Userbot {user_id} has no groups!")
                continue
            
            success_groups = []
            failed_groups = []
            flood_wait_total = 0
            
            # Forward to all groups with delay
            for group in groups:
                try:
                    await client.forward_messages(group.id, source_msg)
                    success_groups.append({
                        'name': group.title,
                        'id': group.id
                    })
                    logger.info(f"✅ Sent to {group.title}")
                    
                except FloodWaitError as e:
                    flood_wait_total += e.seconds
                    logger.warning(f"⏳ FloodWait {e.seconds}s for {group.title}")
                    await asyncio.sleep(e.seconds)
                    
                    # Retry after flood wait
                    try:
                        await client.forward_messages(group.id, source_msg)
                        success_groups.append({
                            'name': group.title,
                            'id': group.id
                        })
                    except Exception as retry_error:
                        failed_groups.append({
                            'name': group.title,
                            'id': group.id,
                            'error': str(retry_error)
                        })
                
                except ChatWriteForbiddenError:
                    error_msg = "Tidak bisa kirim pesan (muted/restricted)"
                    failed_groups.append({
                        'name': group.title,
                        'id': group.id,
                        'error': error_msg
                    })
                    logger.error(f"❌ {group.title}: {error_msg}")
                
                except UserBannedInChannelError:
                    error_msg = "User banned di channel"
                    failed_groups.append({
                        'name': group.title,
                        'id': group.id,
                        'error': error_msg
                    })
                    logger.error(f"❌ {group.title}: {error_msg}")
                
                except Exception as e:
                    error_msg = str(e)
                    failed_groups.append({
                        'name': group.title,
                        'id': group.id,
                        'error': error_msg
                    })
                    logger.error(f"❌ Failed to send to {group.title}: {error_msg}")
                
                # Anti-flood delay
                await asyncio.sleep(settings.get('group_delay', 3))
            
            # Send report per userbot
            if report_chat:
                try:
                    success_rate = (len(success_groups) / len(groups) * 100) if groups else 0
                    
                    report_text = (
                        "╔═══════════════════════════════╗\n"
                        "║   📊 **LAPORAN USERBOT**       ║\n"
                        "╚═══════════════════════════════╝\n\n"
                        f"👤 **Userbot:** `{user_name}`\n"
                        f"🆔 **ID:** `{user_id}`\n"
                        f"📊 **Total Grup:** `{len(groups)}`\n\n"
                        f"✅ **BERHASIL:** `{len(success_groups)}` ({success_rate:.1f}%)\n"
                        f"❌ **GAGAL:** `{len(failed_groups)}`\n"
                    )
                    
                    if flood_wait_total > 0:
                        report_text += f"⏳ **Total FloodWait:** `{flood_wait_total}s`\n"
                    
                    report_text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    
                    # Success groups (max 10)
                    if success_groups:
                        report_text += "✅ **GRUP BERHASIL:**\n"
                        for i, grp in enumerate(success_groups[:10], 1):
                            report_text += f"{i}. {grp['name'][:30]}\n"
                        if len(success_groups) > 10:
                            report_text += f"   ... +{len(success_groups) - 10} grup lainnya\n"
                        report_text += "\n"
                    
                    # Failed groups (max 10)
                    if failed_groups:
                        report_text += "❌ **GRUP GAGAL:**\n"
                        for i, grp in enumerate(failed_groups[:10], 1):
                            error_short = grp['error'][:40] + "..." if len(grp['error']) > 40 else grp['error']
                            report_text += f"{i}. {grp['name'][:25]}\n   └─ `{error_short}`\n"
                        if len(failed_groups) > 10:
                            report_text += f"   ... +{len(failed_groups) - 10} error lainnya\n"
                    
                    await bot.send_message(report_chat, report_text)
                    
                except Exception as e:
                    logger.error(f"Failed to send userbot report: {str(e)}")
            
            # Delay between userbots
            await asyncio.sleep(5)
        
        # Send final report
        if report_chat:
            try:
                await bot.send_message(
                    report_chat,
                    "╔═══════════════════════════════╗\n"
                    "║   🎉 **BROADCAST SELESAI**     ║\n"
                    "╚═══════════════════════════════╝\n\n"
                    f"✅ **Completed:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    f"👥 **Total Userbot:** `{len(active_ubots)}`\n"
                    f"⏭ **Next broadcast:** `{settings.get('delay', 0)} menit lagi`"
                )
            except Exception as e:
                logger.error(f"Failed to send final report: {str(e)}")
        
        # Wait for next broadcast
        delay_seconds = settings.get('delay', 1) * 60
        logger.info(f"⏳ Waiting {delay_seconds} seconds for next broadcast...")
        await asyncio.sleep(delay_seconds)
    
    broadcast_running = False
    logger.info("🛑 Broadcast worker stopped!")

# ════════════════════════ PERSISTENCE FUNCTIONS ════════════════════════
def save_userbots():
    """Save userbots to file"""
    data = {}
    for user_id, ubot in userbots.items():
        data[str(user_id)] = {
            'session': ubot['session'],
            'active': ubot['active']
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
                'active': ubot_data['active']
            }
        except Exception as e:
            logger.error(f"Failed to load userbot {user_id_str}: {str(e)}")

def save_messages():
    """Save messages list to file"""
    save_json(MESSAGES_DB, messages_list)

def load_messages():
    """Load messages from file"""
    global messages_list
    data = load_json(MESSAGES_DB)
    if isinstance(data, list):
        messages_list = data
    else:
        messages_list = []

# ════════════════════════ MAIN FUNCTION ════════════════════════
async def main():
    """Main function"""
    logger.info("="*50)
    logger.info("🚀 Starting Multi Userbot Manager...")
    logger.info("="*50)
    
    # Load data
    load_userbots()
    load_messages()
    
    # Start bot
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot started!")
    
    # Start all userbots
    for user_id, ubot in userbots.items():
        try:
            client = ubot['client']
            await client.connect()
            if await client.is_user_authorized():
                await start_userbot_handlers(client, user_id)
                logger.info(f"✅ Userbot {user_id} started!")
            else:
                logger.warning(f"⚠️ Userbot {user_id} not authorized")
        except Exception as e:
            logger.error(f"❌ Failed to start userbot {user_id}: {str(e)}")
    
    # Start broadcast worker if active
    if settings.get('active', False) and messages_list:
        asyncio.create_task(broadcast_worker())
        logger.info("✅ Broadcast worker started!")
    
    logger.info("="*50)
    logger.info("🎉 All systems running!")
    logger.info("="*50)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
