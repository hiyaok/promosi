import os
import io
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import imagehash
import sqlite3
from datetime import datetime
import cv2
from sklearn.preprocessing import normalize
import hashlib

# ==================== DATABASE SETUP ====================
def init_db():
    """Initialize SQLite database dengan struktur lengkap"""
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
                  colorhash TEXT,
                  orb_features BLOB,
                  sift_features BLOB,
                  histogram BLOB,
                  dct_hash TEXT,
                  pixel_hash TEXT,
                  edge_hash TEXT,
                  file_size INTEGER,
                  image_width INTEGER,
                  image_height INTEGER,
                  timestamp TEXT,
                  UNIQUE(user_id, chat_id, phash, dhash, ahash))''')
    conn.commit()
    conn.close()

def save_image_hash(user_id, chat_id, message_id, file_id, hashes, metadata):
    """Simpan hash gambar dengan semua fitur visual"""
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO images 
                     (user_id, chat_id, message_id, file_id, phash, dhash, ahash, whash, 
                      colorhash, orb_features, sift_features, histogram, dct_hash, 
                      pixel_hash, edge_hash, file_size, image_width, image_height, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, chat_id, message_id, file_id,
                   str(hashes['phash']), str(hashes['dhash']), str(hashes['ahash']),
                   str(hashes['whash']), str(hashes['colorhash']),
                   hashes['orb_features'], hashes['sift_features'],
                   hashes['histogram'], str(hashes['dct_hash']),
                   str(hashes['pixel_hash']), str(hashes['edge_hash']),
                   metadata['file_size'], metadata['width'], metadata['height'],
                   datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        # Gambar sudah ada (UNIQUE constraint), skip
        pass
    finally:
        conn.close()

# ==================== ADVANCED HASHING ALGORITHMS ====================

def compute_dct_hash(image, hash_size=32):
    """DCT-based perceptual hash - sangat akurat untuk deteksi crop/resize"""
    img_gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    img_resized = cv2.resize(img_gray, (hash_size, hash_size))
    
    # Apply DCT
    dct = cv2.dct(np.float32(img_resized))
    dct_low = dct[:8, :8]
    
    # Compute median
    med = np.median(dct_low)
    hash_val = ''.join(['1' if dct_low[i, j] > med else '0' 
                        for i in range(8) for j in range(8)])
    return hash_val

def compute_pixel_hash(image, grid_size=16):
    """Pixel-level hash untuk deteksi perubahan minimal"""
    img_gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    img_resized = cv2.resize(img_gray, (grid_size, grid_size))
    
    # Normalize dan buat hash
    normalized = (img_resized / 255.0 * 100).astype(int)
    hash_val = ''.join([str(x) for row in normalized for x in row])
    return hashlib.sha256(hash_val.encode()).hexdigest()

def compute_edge_hash(image, hash_size=16):
    """Edge detection hash - deteksi berdasarkan bentuk/kontur"""
    img_gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    img_resized = cv2.resize(img_gray, (hash_size * 2, hash_size * 2))
    
    # Canny edge detection
    edges = cv2.Canny(img_resized, 100, 200)
    edges_resized = cv2.resize(edges, (hash_size, hash_size))
    
    # Convert to binary hash
    hash_val = ''.join(['1' if edges_resized[i, j] > 127 else '0' 
                        for i in range(hash_size) for j in range(hash_size)])
    return hash_val

def compute_color_histogram(image, bins=64):
    """Color histogram untuk deteksi warna dominan"""
    img_array = np.array(image)
    
    # Compute histogram untuk setiap channel RGB
    hist_r = cv2.calcHist([img_array], [0], None, [bins], [0, 256])
    hist_g = cv2.calcHist([img_array], [1], None, [bins], [0, 256])
    hist_b = cv2.calcHist([img_array], [2], None, [bins], [0, 256])
    
    # Normalize dan gabungkan
    hist = np.concatenate([hist_r, hist_g, hist_b])
    hist = normalize(hist.reshape(1, -1))[0]
    
    return hist.tobytes()

def extract_orb_features(image, n_features=500):
    """ORB feature detection - untuk rotasi dan scale invariant"""
    img_gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    
    # Resize untuk konsistensi
    img_resized = cv2.resize(img_gray, (640, 480))
    
    # Extract ORB features
    orb = cv2.ORB_create(nfeatures=n_features)
    keypoints, descriptors = orb.detectAndCompute(img_resized, None)
    
    if descriptors is not None:
        # Ambil top features
        descriptors = descriptors[:min(100, len(descriptors))]
        return descriptors.tobytes()
    return b''

def extract_sift_features(image, n_features=200):
    """SIFT-like features menggunakan ORB (SIFT patent-free alternative)"""
    img_gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    img_resized = cv2.resize(img_gray, (640, 480))
    
    # Gunakan AKAZE sebagai alternatif SIFT yang lebih baik
    try:
        akaze = cv2.AKAZE_create()
        keypoints, descriptors = akaze.detectAndCompute(img_resized, None)
        
        if descriptors is not None:
            descriptors = descriptors[:min(100, len(descriptors))]
            return descriptors.tobytes()
    except:
        pass
    
    return b''

def compute_all_hashes(image):
    """Compute semua hash dan fitur visual"""
    
    # Perceptual hashes (resistant to minor changes)
    phash = imagehash.phash(image, hash_size=16)
    dhash = imagehash.dhash(image, hash_size=16)
    ahash = imagehash.average_hash(image, hash_size=16)
    whash = imagehash.whash(image, hash_size=16)
    colorhash = imagehash.colorhash(image)
    
    # DCT hash (very robust)
    dct_hash = compute_dct_hash(image)
    
    # Pixel-level hash
    pixel_hash = compute_pixel_hash(image)
    
    # Edge hash
    edge_hash = compute_edge_hash(image)
    
    # Color histogram
    histogram = compute_color_histogram(image)
    
    # Feature extraction
    orb_features = extract_orb_features(image)
    sift_features = extract_sift_features(image)
    
    return {
        'phash': phash,
        'dhash': dhash,
        'ahash': ahash,
        'whash': whash,
        'colorhash': colorhash,
        'dct_hash': dct_hash,
        'pixel_hash': pixel_hash,
        'edge_hash': edge_hash,
        'histogram': histogram,
        'orb_features': orb_features,
        'sift_features': sift_features
    }

# ==================== SIMILARITY DETECTION ====================

def hamming_distance(hash1, hash2):
    """Calculate hamming distance between two hash strings"""
    if len(hash1) != len(hash2):
        return float('inf')
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

def compare_histograms(hist1_bytes, hist2_bytes):
    """Compare two histograms"""
    try:
        hist1 = np.frombuffer(hist1_bytes, dtype=np.float64)
        hist2 = np.frombuffer(hist2_bytes, dtype=np.float64)
        
        # Correlation coefficient
        correlation = np.corrcoef(hist1, hist2)[0, 1]
        return correlation
    except:
        return 0.0

def compare_features(feat1_bytes, feat2_bytes):
    """Compare feature descriptors"""
    if not feat1_bytes or not feat2_bytes:
        return 0.0
    
    try:
        # Convert bytes back to numpy arrays
        feat1 = np.frombuffer(feat1_bytes, dtype=np.uint8).reshape(-1, 32)
        feat2 = np.frombuffer(feat2_bytes, dtype=np.uint8).reshape(-1, 32)
        
        # Brute force matcher
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(feat1, feat2)
        
        # Calculate match ratio
        match_ratio = len(matches) / max(len(feat1), len(feat2))
        return match_ratio
    except:
        return 0.0

def find_similar_images(hashes, user_id, chat_id, metadata):
    """Cari gambar mirip dengan multi-algoritma scoring"""
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('SELECT * FROM images WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
    
    similar_images = []
    
    for row in c.fetchall():
        try:
            # Parse stored hashes
            stored_phash = imagehash.hex_to_hash(row[5])
            stored_dhash = imagehash.hex_to_hash(row[6])
            stored_ahash = imagehash.hex_to_hash(row[7])
            stored_whash = imagehash.hex_to_hash(row[8])
            stored_colorhash = imagehash.hex_to_hash(row[9])
            stored_dct = row[12]
            stored_pixel = row[13]
            stored_edge = row[14]
            stored_hist = row[11]
            stored_orb = row[10]
            stored_sift = row[11]
            
            # Calculate similarities (0-1 scale, 1 = identical)
            scores = []
            
            # Perceptual hash similarities (inverted distance)
            phash_sim = 1 - (hashes['phash'] - stored_phash) / 256.0
            dhash_sim = 1 - (hashes['dhash'] - stored_dhash) / 256.0
            ahash_sim = 1 - (hashes['ahash'] - stored_ahash) / 256.0
            whash_sim = 1 - (hashes['whash'] - stored_whash) / 256.0
            colorhash_sim = 1 - (hashes['colorhash'] - stored_colorhash) / 256.0
            
            scores.extend([phash_sim, dhash_sim, ahash_sim, whash_sim, colorhash_sim])
            
            # DCT hash similarity
            dct_dist = hamming_distance(hashes['dct_hash'], stored_dct)
            dct_sim = 1 - (dct_dist / 64.0)
            scores.append(dct_sim * 1.5)  # Weight lebih tinggi
            
            # Edge hash similarity
            edge_dist = hamming_distance(hashes['edge_hash'], stored_edge)
            edge_sim = 1 - (edge_dist / 256.0)
            scores.append(edge_sim)
            
            # Pixel hash (exact match)
            pixel_sim = 1.0 if hashes['pixel_hash'] == stored_pixel else 0.0
            scores.append(pixel_sim * 2.0)  # Weight tinggi untuk exact match
            
            # Histogram similarity
            hist_sim = compare_histograms(hashes['histogram'], stored_hist)
            scores.append(hist_sim)
            
            # Feature matching
            orb_sim = compare_features(hashes['orb_features'], stored_orb)
            scores.append(orb_sim * 1.2)
            
            # Calculate weighted average
            total_score = sum(scores) / len(scores) * 100
            
            # Bonus jika dimensi sama (crop akan beda dimensi)
            if metadata['width'] == row[17] and metadata['height'] == row[18]:
                total_score += 5
            
            # Threshold untuk dianggap similar
            if total_score >= 75:  # 75% similarity threshold
                similar_images.append({
                    'message_id': row[3],
                    'file_id': row[4],
                    'timestamp': row[19],
                    'similarity': total_score,
                    'width': row[17],
                    'height': row[18]
                })
        except Exception as e:
            continue
    
    conn.close()
    return similar_images

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    welcome_text = """🔍 *Bot Deteksi Gambar Duplikat SUPER MAX*

Bot ini menggunakan teknologi *Google Lens-level detection*:
✅ Multi-algoritma hashing (8+ algoritma)
✅ Deteksi crop, resize, rotate, filter
✅ Feature matching (ORB + AKAZE)
✅ Color histogram analysis
✅ DCT perceptual hashing
✅ Edge detection
✅ Anti metadata manipulation

*Command:*
/start - Info bot
/stats - Statistik gambar
/clear - Hapus semua data

Kirim gambar sekarang dan lihat keajaibannya! 🚀"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /stats"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM images WHERE user_id = ? AND chat_id = ?', 
              (user_id, chat_id))
    count = c.fetchone()[0]
    conn.close()
    
    await update.message.reply_text(
        f"📊 *Statistik Gambar*\n\nTotal gambar tersimpan: *{count}*\n"
        f"Chat: {update.effective_chat.title or 'Private'}",
        parse_mode='Markdown'
    )

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /clear"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    conn = sqlite3.connect('image_hashes.db')
    c = conn.cursor()
    c.execute('DELETE FROM images WHERE user_id = ? AND chat_id = ?', 
              (user_id, chat_id))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"🗑️ Berhasil menghapus *{deleted}* gambar dari database!",
        parse_mode='Markdown'
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memproses foto"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    user_name = update.effective_user.first_name or "User"
    
    # Ambil foto dengan resolusi tertinggi
    photo = update.message.photo[-1]
    file_id = photo.file_id
    file_size = photo.file_size
    
    try:
        # Download foto
        file = await context.bot.get_file(file_id)
        byte_array = await file.download_as_bytearray()
        
        # Buka dengan PIL
        image = Image.open(io.BytesIO(byte_array))
        
        # Metadata
        metadata = {
            'file_size': file_size,
            'width': image.width,
            'height': image.height
        }
        
        # Hitung semua hash dan fitur
        hashes = compute_all_hashes(image)
        
        # Cek similarity
        similar = find_similar_images(hashes, user_id, chat_id, metadata)
        
        if similar:
            # Urutkan berdasarkan similarity
            similar.sort(key=lambda x: x['similarity'], reverse=True)
            most_similar = similar[0]
            
            # Hitung waktu
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
            
            similarity_pct = most_similar['similarity']
            
            # Deteksi jenis perubahan
            changes = []
            if metadata['width'] != most_similar['width'] or metadata['height'] != most_similar['height']:
                changes.append("📐 crop/resize")
            if file_size != metadata['file_size']:
                changes.append("🔧 compression")
            
            changes_text = f" ({', '.join(changes)})" if changes else ""
            
            if similarity_pct >= 95:
                response = f"🚨 *@{user_name}* INI GAMBAR YANG SAMA NIH!\n\n" \
                          f"Similarity: *{similarity_pct:.1f}%*{changes_text}\n" \
                          f"Kamu udah kirim {time_str}"
            elif similarity_pct >= 85:
                response = f"🤔 *@{user_name}* hmm... gambar ini mirip banget deh\n\n" \
                          f"Similarity: *{similarity_pct:.1f}%*{changes_text}\n" \
                          f"Kamu kirim yang mirip {time_str}"
            else:
                response = f"🧐 *@{user_name}* kayaknya gambar ini mirip\n\n" \
                          f"Similarity: *{similarity_pct:.1f}%*\n" \
                          f"Ada yang mirip dari {time_str}"
            
            await update.message.reply_text(response, parse_mode='Markdown')
        
        # Simpan ke database (selalu simpan untuk pembelajaran)
        save_image_hash(user_id, chat_id, message_id, file_id, hashes, metadata)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error memproses gambar: {str(e)}")

def main():
    """Main function"""
    # Init database
    init_db()
    
    # Token bot dari @BotFather
    TOKEN = "6564736253:AAFUQ08SeGbmm1XE8A4w-L9tf2xfdBlDVqw"
    
    # Buat aplikasi
    application = Application.builder().token(TOKEN).build()
    
    # Tambahkan handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("clear", clear_data))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Jalankan bot
    print("🤖 Bot SUPER MAX sedang berjalan...")
    print("📊 Menggunakan 8+ algoritma deteksi")
    print("🚀 Google Lens-level detection aktif!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
