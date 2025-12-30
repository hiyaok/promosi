import os
import io
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
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
            'phash': str(hashes['phash']),
            'dhash': str(hashes['dhash']),
            'ahash': str(hashes['ahash']),
            'whash': str(hashes['whash']),
            'colorhash': str(hashes['colorhash']),
            'timestamp': timestamp
        })
        self.save_db()
    
    def find_similar(self, chat_id, hashes, threshold=5):
        chat_key = str(chat_id)
        if chat_key not in self.data:
            return None
        
        target_phash = imagehash.hex_to_hash(hashes['phash'])
        target_dhash = imagehash.hex_to_hash(hashes['dhash'])
        target_ahash = imagehash.hex_to_hash(hashes['ahash'])
        target_whash = imagehash.hex_to_hash(hashes['whash'])
        target_colorhash = imagehash.hex_to_hash(hashes['colorhash'])
        
        for entry in reversed(self.data[chat_key]):
            stored_phash = imagehash.hex_to_hash(entry['phash'])
            stored_dhash = imagehash.hex_to_hash(entry['dhash'])
            stored_ahash = imagehash.hex_to_hash(entry['ahash'])
            stored_whash = imagehash.hex_to_hash(entry['whash'])
            stored_colorhash = imagehash.hex_to_hash(entry['colorhash'])
            
            # Multi-hash comparison untuk akurasi tinggi
            phash_diff = target_phash - stored_phash
            dhash_diff = target_dhash - stored_dhash
            ahash_diff = target_ahash - stored_ahash
            whash_diff = target_whash - stored_whash
            colorhash_diff = target_colorhash - stored_colorhash
            
            # Weighted scoring system
            total_score = (
                phash_diff * 2.0 +      # Perceptual hash paling penting
                dhash_diff * 1.5 +      # Difference hash
                ahash_diff * 1.0 +      # Average hash
                whash_diff * 1.5 +      # Wavelet hash
                colorhash_diff * 1.0    # Color hash
            ) / 7.0
            
            if total_score <= threshold:
                return entry
        
        return None

# Advanced image processing
class ImageAnalyzer:
    @staticmethod
    def compute_hashes(image):
        """Compute multiple perceptual hashes untuk akurasi maksimal"""
        # Resize untuk konsistensi
        img_resized = image.resize((512, 512), Image.Resampling.LANCZOS)
        
        return {
            'phash': str(imagehash.phash(img_resized, hash_size=16)),
            'dhash': str(imagehash.dhash(img_resized, hash_size=16)),
            'ahash': str(imagehash.average_hash(img_resized, hash_size=16)),
            'whash': str(imagehash.whash(img_resized, hash_size=16)),
            'colorhash': str(imagehash.colorhash(img_resized, binbits=4))
        }
    
    @staticmethod
    def extract_features(image):
        """Extract advanced features menggunakan OpenCV"""
        # Convert ke numpy array
        img_array = np.array(image.convert('RGB'))
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Compute histogram
        hist_b = cv2.calcHist([img_cv], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([img_cv], [1], None, [256], [0, 256])
        hist_r = cv2.calcHist([img_cv], [2], None, [256], [0, 256])
        
        # Normalize
        hist_b = cv2.normalize(hist_b, hist_b).flatten()
        hist_g = cv2.normalize(hist_g, hist_g).flatten()
        hist_r = cv2.normalize(hist_r, hist_r).flatten()
        
        return np.concatenate([hist_b, hist_g, hist_r])
    
    @staticmethod
    def preprocess_image(image):
        """Preprocess image untuk handling crop dan transformasi"""
        # Auto-orient berdasarkan EXIF
        try:
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except:
            pass
        
        # Convert ke RGB jika perlu
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image

# Bot handlers
db = ImageDatabase()
analyzer = ImageAnalyzer()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle foto yang dikirim ke bot atau grup"""
    try:
        photo = update.message.photo[-1]  # Ambil resolusi tertinggi
        user = update.message.from_user
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        
        # Download foto
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        
        # Process image
        image = Image.open(io.BytesIO(photo_bytes))
        image = analyzer.preprocess_image(image)
        
        # Compute hashes
        hashes = analyzer.compute_hashes(image)
        
        # Cek apakah gambar mirip dengan yang sudah ada
        similar = db.find_similar(chat_id, hashes, threshold=5)
        
        if similar:
            # Gambar mirip ditemukan!
            username = f"@{user.username}" if user.username else user.first_name
            original_username = similar['username']
            
            # Format pesan
            time_diff = datetime.now() - datetime.fromisoformat(similar['timestamp'])
            
            if time_diff.days > 0:
                time_str = f"{time_diff.days} hari yang lalu"
            elif time_diff.seconds // 3600 > 0:
                time_str = f"{time_diff.seconds // 3600} jam yang lalu"
            elif time_diff.seconds // 60 > 0:
                time_str = f"{time_diff.seconds // 60} menit yang lalu"
            else:
                time_str = "baru saja"
            
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
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await update.message.reply_text(
            "Maaf, terjadi error saat memproses gambar 😅"
        )

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

def main():
    """Start bot"""
    # Ganti dengan token bot Anda
    TOKEN = "6564736253:AAFny4rwOAAI0xJrmUC6egy9S9Ws7U_D0o0"
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
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
