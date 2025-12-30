import os
import io
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from PIL import Image
import imagehash
import numpy as np
import cv2
from collections import defaultdict
import json

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database penyimpanan hash gambar
class ImageDatabase:
    def __init__(self, db_file='image_hashes.json'):
        self.db_file = db_file
        self.data = self.load_db()
    
    def load_db(self):
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_db(self):
        with open(self.db_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_image(self, chat_id, user_id, username, message_id, hashes, timestamp):
        chat_key = str(chat_id)
        if chat_key not in self.data:
            self.data[chat_key] = []
        
        self.data[chat_key].append({
            'user_id': user_id,
            'username': username,
            'message_id': message_id,
            'phash': hashes['phash'],
            'dhash': hashes['dhash'],
            'ahash': hashes['ahash'],
            'whash': hashes['whash'],
            'timestamp': timestamp
        })
        self.save_db()
    
    def find_similar(self, chat_id, hashes, threshold=8):
        chat_key = str(chat_id)
        if chat_key not in self.data:
            return None
        
        target_phash = hashes['phash']
        target_dhash = hashes['dhash']
        target_ahash = hashes['ahash']
        target_whash = hashes['whash']
        
        for entry in reversed(self.data[chat_key]):
            try:
                stored_phash = entry['phash']
                stored_dhash = entry['dhash']
                stored_ahash = entry['ahash']
                stored_whash = entry['whash']
                
                # Hamming distance calculation
                phash_diff = self.hamming_distance(target_phash, stored_phash)
                dhash_diff = self.hamming_distance(target_dhash, stored_dhash)
                ahash_diff = self.hamming_distance(target_ahash, stored_ahash)
                whash_diff = self.hamming_distance(target_whash, stored_whash)
                
                # Weighted scoring system
                total_score = (
                    phash_diff * 2.5 +      # Perceptual hash paling penting
                    dhash_diff * 1.5 +      # Difference hash
                    ahash_diff * 1.0 +      # Average hash
                    whash_diff * 1.5        # Wavelet hash
                ) / 6.5
                
                logger.info(f"Comparison scores - phash: {phash_diff}, dhash: {dhash_diff}, ahash: {ahash_diff}, whash: {whash_diff}, total: {total_score:.2f}")
                
                if total_score <= threshold:
                    return entry
                    
            except Exception as e:
                logger.error(f"Error comparing hashes: {e}")
                continue
        
        return None
    
    @staticmethod
    def hamming_distance(hash1, hash2):
        """Calculate hamming distance between two hex strings"""
        if len(hash1) != len(hash2):
            return 999
        
        distance = 0
        for c1, c2 in zip(hash1, hash2):
            # Convert hex to binary and count different bits
            xor = int(c1, 16) ^ int(c2, 16)
            distance += bin(xor).count('1')
        
        return distance

# Advanced image processing
class ImageAnalyzer:
    @staticmethod
    def compute_hashes(image):
        """Compute multiple perceptual hashes untuk akurasi maksimal"""
        try:
            # Resize untuk konsistensi
            img_resized = image.resize((256, 256), Image.Resampling.LANCZOS)
            
            # Compute hashes dengan error handling
            phash = imagehash.phash(img_resized, hash_size=8)
            dhash = imagehash.dhash(img_resized, hash_size=8)
            ahash = imagehash.average_hash(img_resized, hash_size=8)
            whash = imagehash.whash(img_resized, hash_size=8)
            
            return {
                'phash': str(phash),
                'dhash': str(dhash),
                'ahash': str(ahash),
                'whash': str(whash)
            }
        except Exception as e:
            logger.error(f"Error computing hashes: {e}")
            raise
    
    @staticmethod
    def preprocess_image(image):
        """Preprocess image untuk handling crop dan transformasi"""
        try:
            # Auto-orient berdasarkan EXIF
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            logger.warning(f"Could not transpose image: {e}")
        
        # Convert ke RGB jika perlu
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image

# Bot handlers
db = ImageDatabase()
analyzer = ImageAnalyzer()

async def download_with_retry(bot, file_id, max_retries=3):
    """Download file dengan retry mechanism"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Download attempt {attempt + 1}/{max_retries}")
            file = await bot.get_file(file_id)
            photo_bytes = await file.download_as_bytearray()
            return photo_bytes
        except Exception as e:
            logger.warning(f"Download failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle foto yang dikirim ke bot atau grup"""
    try:
        # Handle both photo and document
        if update.message.photo:
            photo = update.message.photo[-1]  # Ambil resolusi tertinggi
        elif update.message.document:
            photo = update.message.document
        else:
            return
        
        user = update.message.from_user
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        
        logger.info(f"Processing photo from user {user.id} in chat {chat_id}")
        
        # Download foto dengan retry
        photo_bytes = await download_with_retry(context.bot, photo.file_id)
        
        # Process image
        image = Image.open(io.BytesIO(photo_bytes))
        image = analyzer.preprocess_image(image)
        
        # Compute hashes
        hashes = analyzer.compute_hashes(image)
        logger.info(f"Computed hashes: {hashes}")
        
        # Cek apakah gambar mirip dengan yang sudah ada
        similar = db.find_similar(chat_id, hashes, threshold=8)
        
        if similar:
            # Gambar mirip ditemukan!
            username = f"@{user.username}" if user.username else user.first_name
            original_username = similar['username']
            
            # Format pesan
            try:
                time_diff = datetime.now() - datetime.fromisoformat(similar['timestamp'])
                
                if time_diff.days > 0:
                    time_str = f"{time_diff.days} hari yang lalu"
                elif time_diff.seconds // 3600 > 0:
                    time_str = f"{time_diff.seconds // 3600} jam yang lalu"
                elif time_diff.seconds // 60 > 0:
                    time_str = f"{time_diff.seconds // 60} menit yang lalu"
                else:
                    time_str = "baru saja"
            except:
                time_str = "sebelumnya"
            
            reply_text = (
                f"🔍 {username}, gambar ini sepertinya pernah dikirim ke grup ini {time_str} "
                f"oleh {original_username}!\n\n"
                f"Gambar yang sama terdeteksi 🎯"
            )
            
            # Reply ke pesan asli
            await update.message.reply_text(
                reply_text,
                reply_to_message_id=message_id
            )
            
            logger.info(f"Duplicate detected: {username} in chat {chat_id}")
        else:
            logger.info(f"No duplicate found for image in chat {chat_id}")
        
        # Simpan hash gambar baru
        username = f"@{user.username}" if user.username else user.first_name
        db.add_image(
            chat_id=chat_id,
            user_id=user.id,
            username=username,
            message_id=message_id,
            hashes=hashes,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"Image saved to database for chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "Maaf, terjadi error saat memproses gambar 😅"
            )
        except:
            pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    welcome_text = (
        "👋 Halo! Saya bot deteksi gambar duplikat.\n\n"
        "🔍 Saya bisa mendeteksi gambar yang sama meskipun:\n"
        "• Di-crop\n"
        "• Di-resize\n"
        "• Di-compress\n"
        "• Diubah sedikit\n\n"
        "Cukup kirim gambar ke grup, dan saya akan memberitahu "
        "jika gambar tersebut pernah dikirim sebelumnya!\n\n"
        "Teknologi: Perceptual Hashing + Computer Vision 🚀"
    )
    await update.message.reply_text(welcome_text)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /clear - clear database untuk chat ini"""
    chat_id = str(update.message.chat_id)
    if chat_id in db.data:
        count = len(db.data[chat_id])
        db.data[chat_id] = []
        db.save_db()
        await update.message.reply_text(f"✅ Database cleared! {count} gambar dihapus dari chat ini.")
    else:
        await update.message.reply_text("ℹ️ Belum ada gambar tersimpan untuk chat ini.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /stats - lihat statistik"""
    chat_id = str(update.message.chat_id)
    if chat_id in db.data:
        count = len(db.data[chat_id])
        await update.message.reply_text(f"📊 Total gambar tersimpan: {count}")
    else:
        await update.message.reply_text("📊 Belum ada gambar tersimpan untuk chat ini.")

def main():
    """Start bot"""
    # Ganti dengan token bot Anda
    TOKEN = "6564736253:AAFny4rwOAAI0xJrmUC6egy9S9Ws7U_D0o0"
    
    # Custom request dengan timeout lebih panjang
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    
    # Create application dengan custom request
    application = Application.builder() \
        .token(TOKEN) \
        .request(request) \
        .build()
    
    # Add handlers
    from telegram.ext import CommandHandler
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    application.add_handler(MessageHandler(
        filters.PHOTO, 
        handle_photo
    ))
    application.add_handler(MessageHandler(
        filters.Document.IMAGE,
        handle_photo
    ))
    
    # Start bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
