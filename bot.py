import asyncio
import logging
import sqlite3
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
import pytz
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# === AYARLAR ===
TOKEN = "8709665483:AAFdZBceYA0kLBBdjx-OMDePuzD_ySqjp8w"
CHAT_ID = "8243859152"
TIMEZONE = pytz.timezone("Europe/Istanbul")
DB_PATH = "/app/data/harcamalar.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# === VERİTABANI ===
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS harcamalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            tutar REAL,
            kategori TEXT,
            not_text TEXT
        )
    """)
    conn.commit()
    conn.close()

def kaydet_harcama(tutar, kategori, not_text=""):
    now = datetime.now(TIMEZONE)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO harcamalar (tarih, tutar, kategori, not_text) VALUES (?, ?, ?, ?)",
        (now.strftime("%Y-%m-%d"), tutar, kategori, not_text)
    )
    conn.commit()
    conn.close()

def gunluk_harcamalar(tarih=None):
    if not tarih:
        tarih = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT tutar, kategori, not_text FROM harcamalar WHERE tarih = ?", (tarih,)
    ).fetchall()
    conn.close()
    return rows

def haftalik_harcamalar():
    bugun = datetime.now(TIMEZONE)
    baslangic = (bugun - timedelta(days=bugun.weekday())).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT tarih, tutar, kategori FROM harcamalar WHERE tarih >= ?", (baslangic,)
    ).fetchall()
    conn.close()
    return rows

def aylik_harcamalar():
    bugun = datetime.now(TIMEZONE)
    baslangic = bugun.strftime("%Y-%m-01")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT tarih, tutar, kategori FROM harcamalar WHERE tarih >= ?", (baslangic,)
    ).fetchall()
    conn.close()
    return rows

# === KATEGORİ TAHMİN ===
KATEGORILER = {
    "🍽️ Yemek": ["yemek", "restaurant", "restoran", "döner", "kebap", "pizza", "burger", "kahvaltı", "öğle", "akşam", "lahmacun", "pide", "çorba", "izgara"],
    "☕ Kahve & İçecek": ["kahve", "coffee", "çay", "starbucks", "cafe", "kafe", "ayran", "su", "içecek", "meyve suyu"],
    "🛒 Market": ["market", "bim", "a101", "şok", "migros", "carrefour", "bakkal", "manav", "alışveriş", "gıda"],
    "⛽ Yakıt & Ulaşım": ["benzin", "mazot", "yakıt", "akaryakıt", "otobüs", "metro", "taksi", "uber", "servis", "otopark"],
    "🔧 Atölye & Malzeme": ["malzeme", "vida", "boya", "alet", "takım", "elektronik", "filament", "cnc", "kesici"],
    "💊 Sağlık": ["eczane", "ilaç", "doktor", "hastane", "vitamin", "takviye"],
    "👕 Giyim": ["giyim", "kıyafet", "ayakkabı", "mont", "pantolon", "tişört"],
    "🏠 Fatura & Ev": ["fatura", "elektrik", "su", "doğalgaz", "internet", "kira", "aidat"],
    "🎮 Eğlence": ["sinema", "oyun", "eğlence", "netflix", "spotify", "kitap"],
    "🏍️ Araç Bakım": ["yağ", "lastik", "servis", "oto", "araba", "motosiklet", "sigorta"],
    "📦 Kargo & Alışveriş": ["kargo", "trendyol", "hepsiburada", "amazon", "sipariş"],
}

def tahmin_kategori(metin):
    metin_lower = metin.lower()
    for kategori, anahtar_kelimeler in KATEGORILER.items():
        for kelime in anahtar_kelimeler:
            if kelime in metin_lower:
                return kategori
    return "💰 Diğer"

def ozet_olustur(rows, baslik):
    if not rows:
        return f"{baslik}\n\nHenüz harcama yok."
    
    kategori_toplam = defaultdict(float)
    toplam = 0
    for row in rows:
        tutar = row[1] if len(row) > 2 else row[0]
        kategori = row[2] if len(row) > 2 else row[1]
        kategori_toplam[kategori] += tutar
        toplam += tutar
    
    mesaj = f"{baslik}\n━━━━━━━━━━━━━━━\n"
    for kat, t in sorted(kategori_toplam.items(), key=lambda x: -x[1]):
        mesaj += f"{kat}: *{t:.0f} TL*\n"
    mesaj += f"━━━━━━━━━━━━━━━\n💳 *Toplam: {toplam:.0f} TL*"
    return mesaj

# === FITNESS MESAJLARI ===
SABAH_MESAJI = """🌅 *Günaydın! Yeni bir gün, yeni bir fırsat.*

━━━━━━━━━━━━━━━
☕ *SABAH KAHVALTISI*
━━━━━━━━━━━━━━━
• 200g yoğurt + chia/keten tohumu
• 60g beyaz peynir
• Domates, salatalık, yeşil biber
• 1-2 dilim ekmek veya avuç ceviz
• Şekersiz kahve / limonlu su

💧 *Su hedefi: 2.5-3 litre bugün*

Dükkan yolunda sahil kenarından geç, 10 dakika yürü! 🚶"""

OGLE_MESAJI = """🌞 *Öğle vakti — yakıt zamanı!*

━━━━━━━━━━━━━━━
🥗 *ÖĞLE YEMEĞİ*
━━━━━━━━━━━━━━━
🐟 *Ton balığı günüyse:*
• 1 kutu ton balığı + bol yeşillik salata
• Zeytinyağı + limon sos

🫘 *Baklagil günüyse:*
• Mercimek çorbası veya nohut/fasulye
• Yanında yoğurt + yeşil salata"""

IKINDI_MESAJI = """⏰ *16:00 — Ara öğün vakti (açsan)*

• 1 bardak ayran + avuç fındık/ceviz
veya
• 150g yoğurt + mevsim meyvesi

💪 Spor günüyse akşam yemeğini hafif tut!"""

AKSAM_MESAJI = """🌙 *Akşam — dükkan kapandı, şimdi sen zamanı!*

━━━━━━━━━━━━━━━
🍽️ *AKŞAM YEMEĞİ*
━━━━━━━━━━━━━━━
• Zeytinyağlı sebze yemeği + yoğurt
• Haftada 1 gün: ızgara kıyma/köfte

━━━━━━━━━━━━━━━
🏃 *SPOR (Sal/Per/Cum)*
━━━━━━━━━━━━━━━
1. 5 dk ısınma
2. 25-30 dk interval: 2 dk yürü → 1 dk koş
3. 5-10 dk soğuma

🚴 *Hafta sonu:* 50-60 dk sahil bisikleti
Sessiz dip dalga... 🌊"""

SPOR_TAKVIMI = {
    0: "Pazartesi — 🛌 Dinlenme günü.",
    1: "Salı — 🏃 AKŞAM KOŞUSU! 40 dk interval.",
    2: "Çarşamba — 🍖 Kırmızı et günü. Dinlenme.",
    3: "Perşembe — 🏃 AKŞAM KOŞUSU! 40 dk interval.",
    4: "Cuma — 🏃 AKŞAM KOŞUSU! Haftanın son koşusu!",
    5: "Cumartesi — 🚴 SABAH BİSİKLETİ! 50-60 dk.",
    6: "Pazar — 🌿 Tam dinlenme.",
}

# === MESAJ GÖNDER ===
async def send_message(bot, text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
        logger.info(f"Mesaj gönderildi: {text[:50]}...")
    except TelegramError as e:
        logger.error(f"Hata: {e}")

# === GELEN MESAJ İŞLE ===
async def mesaj_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.chat_id) != CHAT_ID:
        return
    
    metin = update.message.text.strip()
    bot = context.bot
    
    # Komutlar
    if metin.lower() in ["/ozet", "özet", "ozet"]:
        rows = gunluk_harcamalar()
        await send_message(bot, ozet_olustur([(r[0], r[1], r[2]) for r in rows] if rows else [], "📊 *Bugünkü Harcamalar*"))
        return
    
    if metin.lower() in ["/hafta", "hafta", "haftalık", "haftalik"]:
        rows = haftalik_harcamalar()
        await send_message(bot, ozet_olustur(rows, "📊 *Bu Haftaki Harcamalar*"))
        return
    
    if metin.lower() in ["/ay", "ay", "aylık", "aylik"]:
        rows = aylik_harcamalar()
        await send_message(bot, ozet_olustur(rows, "📊 *Bu Ayki Harcamalar*"))
        return

    if metin.lower() in ["/yardim", "yardım", "yardim", "/help"]:
        yardim = """🤖 *OtagDaily Bot — Komutlar*

━━━━━━━━━━━━━━━
💸 *Harcama Ekle*
Sadece tutarı yaz:
`45` → "45 TL harcama"
`kahve 30` → ipucu ile daha doğru tahmin

━━━━━━━━━━━━━━━
📊 *Raporlar*
`özet` → bugünkü harcamalar
`hafta` → bu haftaki harcamalar
`ay` → bu ayki harcamalar

━━━━━━━━━━━━━━━
⏰ *Otomatik Mesajlar*
07:00 — Kahvaltı & spor planı
12:30 — Öğle hatırlatıcısı
16:00 — Ara öğün
21:30 — Akşam & spor rutini
23:00 — Günlük özet"""
        await send_message(bot, yardim)
        return

    # Sayı içeriyor mu? → Harcama kaydı
    sayi_esle = re.search(r'\d+([.,]\d+)?', metin)
    if sayi_esle:
        tutar = float(sayi_esle.group().replace(',', '.'))
        kategori = tahmin_kategori(metin)
        kaydet_harcama(tutar, kategori, metin)
        await send_message(bot, f"✅ *{tutar:.0f} TL* kaydedildi\n📁 Kategori: {kategori}\n\n_Özet için 'özet' yaz_")
        return

    # Anlaşılamadı
    await send_message(bot, "❓ Anlamadım. Harcama için tutar yaz (örn: `85`)\nYardım için `yardım` yaz.")

# === GECE ÖZETİ ===
async def gece_ozeti(bot):
    now = datetime.now(TIMEZONE)
    rows = gunluk_harcamalar()
    
    if rows:
        toplam = sum(r[0] for r in rows)
        harcama_ozet = f"\n\n💳 *Bugün toplam harcama: {toplam:.0f} TL*\nDetay için 'özet' yaz."
    else:
        harcama_ozet = "\n\n💳 Bugün harcama kaydı yok."

    mesaj = f"""⭐ *Günü kapat — özet zamanı*

✅ Su içtin mi? (2.5-3L)
✅ Öğünlerini tutturabildin mi?
✅ Spor günüyse çıktın mı?

Mükemmel olmak zorunda değilsin.
*Sadece dün olduğundan bir adım ileri.*{harcama_ozet}

━━━━━━━━━━━━━━━
_Sessiz dip dalga — görünmez ama durdurulamaz_ 🌊"""
    await send_message(bot, mesaj)

    # Pazartesi ise haftalık özet de gönder
    if now.weekday() == 0:
        rows_hafta = haftalik_harcamalar()
        await send_message(bot, ozet_olustur(rows_hafta, "📊 *Bu Haftaki Harcamalar*"))

    # Ayın son günü ise aylık özet gönder
    son_gun = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if now.day == son_gun.day:
        rows_ay = aylik_harcamalar()
        await send_message(bot, ozet_olustur(rows_ay, "📊 *Bu Ayki Harcamalar*"))

# === ZAMANLAYICI ===
async def scheduler(bot):
    logger.info("Bot başladı, mesajlar bekleniyor...")
    sent_today = {}

    while True:
        now = datetime.now(TIMEZONE)
        saat = now.hour
        dakika = now.minute
        gun = now.weekday()
        tarih = now.date()

        def gonder_mi(key, h, m=0):
            if saat == h and dakika == m:
                k = f"{tarih}_{key}"
                if sent_today.get(k):
                    return False
                sent_today[k] = True
                return True
            return False

        if gonder_mi("sabah", 7):
            spor_notu = SPOR_TAKVIMI.get(gun, "")
            await send_message(bot, SABAH_MESAJI + f"\n\n📅 *Bugün:* {spor_notu}")
        elif gonder_mi("ogle", 12, 30):
            await send_message(bot, OGLE_MESAJI)
        elif gonder_mi("ikindi", 16):
            await send_message(bot, IKINDI_MESAJI)
        elif gonder_mi("aksam", 21, 30):
            await send_message(bot, AKSAM_MESAJI)
        elif gonder_mi("gece", 23):
            await gece_ozeti(bot)

        await asyncio.sleep(30)

# === ANA FONKSİYON ===
async def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isle))
    
    bot = app.bot
    me = await bot.get_me()
    logger.info(f"Bot aktif: @{me.username}")
    
    await send_message(bot, """🤖 *OtagDaily Bot güncellendi!*

Artık harcama takibi de yapabilirsin 💸

Harcama eklemek için sadece tutar yaz:
`45` veya `kahve 30` veya `market 250`

Komutlar için `yardım` yaz 👋""")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    await scheduler(bot)

if __name__ == "__main__":
    asyncio.run(main())
