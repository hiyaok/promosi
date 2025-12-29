import os
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import imagehash
import sqlite3
from datetime import datetime

# Database setup
def init_db():
    """Initialize SQLite database untuk menyimpan hash gambar"""
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS images
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  chat_id INTEGER,
                  message_id INTEGER,
                  file_id TEXT,
                  phash TEXT,
                  dhash TEXT,
                  ahash TEXT,
                  whash TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

def save_image_hash(user_id, chat_id, message_id, file_id, hashes):
    """Simpan hash gambar ke database"""
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('''INSERT INTO images (user_id, chat_id, message_id, file_id, phash, dhash, ahash, whash, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, chat_id, message_id, file_id, 
               str(hashes['phash']), str(hashes['dhash']), 
               str(hashes['ahash']), str(hashes['whash']),
               datetime.now().isoformat()))
    conn.commit()
    conn.close()

def find_similar_images(hashes, user_id, chat_id, threshold=5):
    """Cari gambar yang mirip dengan threshold tertentu"""
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    # Cari di chat yang sama dan user yang sama
    c.execute('SELECT * FROM images WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
    
    similar_images = []
    for row in c.fetchall():
        stored_phash = imagehash.hex_to_hash(row[5])
        stored_dhash = imagehash.hex_to_hash(row[6])
        stored_ahash = imagehash.hex_to_hash(row[7])
        stored_whash = imagehash.hex_to_hash(row[8])
        
        # Hitung hamming distance untuk setiap algoritma
        phash_diff = hashes['phash'] - stored_phash
        dhash_diff = hashes['dhash'] - stored_dhash
        ahash_diff = hashes['ahash'] - stored_ahash
        whash_diff = hashes['whash'] - stored_whash
        
        # Rata-rata dari semua hash
        avg_diff = (phash_diff + dhash_diff + ahash_diff + whash_diff) / 4
        
        if avg_diff <= threshold:
            similar_images.append({
                'message_id': row[3],
                'file_id': row[4],
                'timestamp': row[9],
                'difference': avg_diff,
                'user_id': row[1]
            })
    
    conn.close()
    return similar_images

def compute_image_hashes(image):
    """Hitung berbagai jenis hash untuk akurasi maksimal"""
    return {
        'phash': imagehash.phash(image, hash_size=16),  # Perceptual hash
        'dhash': imagehash.dhash(image, hash_size=16),  # Difference hash
        'ahash': imagehash.average_hash(image, hash_size=16),  # Average hash
        'whash': imagehash.whash(image, hash_size=16)  # Wavelet hash
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    welcome_text = """🔍 *Bot Deteksi Gambar Duplikat*

Kirim gambar ke saya, dan saya akan:
✅ Memeriksa apakah gambar tersebut sudah pernah dikirim
✅ Memberitahu jika gambar sama atau mirip
✅ Menyimpan semua gambar untuk perbandingan

*Perintah:*
/start - Tampilkan pesan ini
/stats - Lihat statistik gambar
/clear - Hapus semua data gambar

Sekarang kirim gambar pertama Anda!"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /stats"""
    user_id = update.effective_user.id
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM images WHERE user_id = ?', (user_id,))
    count = c.fetchone()[0]
    conn.close()
    
    await update.message.reply_text(f"📊 Anda telah mengirim *{count}* gambar", parse_mode='Markdown')

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /clear"""
    user_id = update.effective_user.id
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('DELETE FROM images WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("🗑️ Semua data gambar Anda telah dihapus!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memproses foto yang dikirim"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    user_name = update.effective_user.first_name
    
    # Ambil foto dengan resolusi tertinggi
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # Download foto
    file = await context.bot.get_file(file_id)
    byte_array = await file.download_as_bytearray()
    
    # Buka dengan PIL
    image = Image.open(io.BytesIO(byte_array))
    
    # Hitung hash
    hashes = compute_image_hashes(image)
    
    # Cek apakah ada gambar mirip
    similar = find_similar_images(hashes, user_id, chat_id, threshold=5)
    
    if similar:
        # Urutkan berdasarkan similarity (difference terkecil)
        similar.sort(key=lambda x: x['difference'])
        most_similar = similar[0]
        
        # Hitung berapa lama sejak gambar pertama
        from datetime import datetime
        first_time = datetime.fromisoformat(most_similar['timestamp'])
        now = datetime.now()
        time_diff = now - first_time
        
        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60
        
        if days > 0:
            time_str = f"{days} hari yang lalu"
        elif hours > 0:
            time_str = f"{hours} jam yang lalu"
        elif minutes > 0:
            time_str = f"{minutes} menit yang lalu"
        else:
            time_str = "baru saja"
        
        if most_similar['difference'] == 0:
            response = f"🤨 @{user_name if user_name else 'User'} ini gambar yang sama nih!\n\nKamu udah kirim gambar ini {time_str}"
        elif most_similar['difference'] <= 3:
            response = f"🤔 @{user_name if user_name else 'User'} hmm... gambar ini mirip banget sama yang kemarin deh\n\nKamu kirim yang mirip {time_str}"
        else:
            response = f"🧐 @{user_name if user_name else 'User'} kayaknya gambar ini mirip deh\n\nAda yang mirip dari {time_str}"
        
        # Reply ke message user
        await update.message.reply_text(response)
    
    # Simpan hash ke database (tetap simpan meski duplikat, untuk tracking)
    save_image_hash(user_id, chat_id, message_id, file_id, hashes)

def main():
    """Main function untuk menjalankan bot"""
    # Inisialisasi database
    init_db()
    
    # Ganti dengan token bot Anda dari @BotFather
    TOKEN = "6564736253:AAFUQ08SeGbmm1XE8A4w-L9tf2xfdBlDVqw"
    
    # Buat aplikasi
    application = Application.builder().token(TOKEN).build()
    
    # Tambahkan handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("clear", clear_data))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Jalankan bot
    print("🤖 Bot sedang berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
