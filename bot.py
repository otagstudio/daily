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
DB_PATH = "/app/data/veriler.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# === VERİTABANI ===
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS harcamalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT, tutar REAL, kategori TEXT, not_text TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gunluk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT UNIQUE,
            kilo REAL,
            kosu_mesafe REAL,
            kosu_sure INTEGER,
            yedikleri TEXT,
            gunce TEXT,
            ruh_hali INTEGER
        )
    """)
    conn.commit()
    conn.close()

# === HARCAMA DB ===
def kaydet_harcama(tutar, kategori, not_text=""):
    now = datetime.now(TIMEZONE)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO harcamalar (tarih, tutar, kategori, not_text) VALUES (?, ?, ?, ?)",
                 (now.strftime("%Y-%m-%d"), tutar, kategori, not_text))
    conn.commit()
    conn.close()

def gunluk_harcamalar(tarih=None):
    if not tarih:
        tarih = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT tutar, kategori, not_text FROM harcamalar WHERE tarih = ?", (tarih,)).fetchall()
    conn.close()
    return rows

def haftalik_harcamalar():
    bugun = datetime.now(TIMEZONE)
    baslangic = (bugun - timedelta(days=bugun.weekday())).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT tarih, tutar, kategori FROM harcamalar WHERE tarih >= ?", (baslangic,)).fetchall()
    conn.close()
    return rows

def aylik_harcamalar():
    bugun = datetime.now(TIMEZONE)
    baslangic = bugun.strftime("%Y-%m-01")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT tarih, tutar, kategori FROM harcamalar WHERE tarih >= ?", (baslangic,)).fetchall()
    conn.close()
    return rows

# === GÜNLÜK DB ===
def kaydet_gunluk(tarih, alan, deger):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"INSERT OR IGNORE INTO gunluk (tarih) VALUES (?)", (tarih,))
    conn.execute(f"UPDATE gunluk SET {alan} = ? WHERE tarih = ?", (deger, tarih))
    conn.commit()
    conn.close()

def gunluk_veri(tarih=None):
    if not tarih:
        tarih = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM gunluk WHERE tarih = ?", (tarih,)).fetchone()
    conn.close()
    return row

def haftalik_gunluk():
    bugun = datetime.now(TIMEZONE)
    baslangic = (bugun - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM gunluk WHERE tarih >= ? ORDER BY tarih", (baslangic,)).fetchall()
    conn.close()
    return rows

def aylik_gunluk():
    bugun = datetime.now(TIMEZONE)
    baslangic = bugun.strftime("%Y-%m-01")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM gunluk WHERE tarih >= ? ORDER BY tarih", (baslangic,)).fetchall()
    conn.close()
    return rows

# === KATEGORİ TAHMİN ===
KATEGORILER = {
    "🍽️ Yemek": ["yemek", "restoran", "döner", "kebap", "pizza", "burger", "kahvaltı", "lahmacun", "pide", "çorba"],
    "☕ Kahve & İçecek": ["kahve", "coffee", "çay", "starbucks", "cafe", "kafe", "ayran"],
    "🛒 Market": ["market", "bim", "a101", "şok", "migros", "carrefour", "bakkal", "manav", "alışveriş"],
    "⛽ Yakıt & Ulaşım": ["benzin", "mazot", "yakıt", "otobüs", "metro", "taksi", "uber", "otopark"],
    "🔧 Atölye & Malzeme": ["malzeme", "vida", "boya", "alet", "elektronik", "filament", "cnc"],
    "💊 Sağlık": ["eczane", "ilaç", "doktor", "hastane", "vitamin"],
    "🏠 Fatura & Ev": ["fatura", "elektrik", "doğalgaz", "internet", "kira", "aidat"],
    "🏍️ Araç Bakım": ["yağ", "lastik", "servis", "oto", "motosiklet", "sigorta"],
    "📦 Kargo & Alışveriş": ["kargo", "trendyol", "hepsiburada", "amazon", "sipariş"],
}

def tahmin_kategori(metin):
    metin_lower = metin.lower()
    for kategori, kelimeler in KATEGORILER.items():
        for kelime in kelimeler:
            if kelime in metin_lower:
                return kategori
    return "💰 Diğer"

def ozet_olustur(rows, baslik, kolon=1):
    if not rows:
        return f"{baslik}\n\nHenüz kayıt yok."
    kategori_toplam = defaultdict(float)
    toplam = 0
    for row in rows:
        tutar = row[kolon]
        kategori = row[kolon + 1]
        kategori_toplam[kategori] += tutar
        toplam += tutar
    mesaj = f"{baslik}\n━━━━━━━━━━━━━━━\n"
    for kat, t in sorted(kategori_toplam.items(), key=lambda x: -x[1]):
        mesaj += f"{kat}: *{t:.0f} TL*\n"
    mesaj += f"━━━━━━━━━━━━━━━\n💳 *Toplam: {toplam:.0f} TL*"
    return mesaj

# === SAĞLIK ANALİZİ ===
def haftalik_saglik_raporu(rows):
    if not rows:
        return "📊 Bu hafta henüz check-in yok."

    kilolar = [r[2] for r in rows if r[2]]
    mesafeler = [r[3] for r in rows if r[3]]
    sureler = [r[4] for r in rows if r[4]]
    ruh_halleri = [r[7] for r in rows if r[7]]

    mesaj = "📊 *Haftalık Sağlık Raporu*\n━━━━━━━━━━━━━━━\n"

    if kilolar:
        mesaj += f"⚖️ *Kilo:* {kilolar[0]:.1f} → {kilolar[-1]:.1f} kg"
        fark = kilolar[-1] - kilolar[0]
        mesaj += f" ({'▼' if fark < 0 else '▲'}{abs(fark):.1f} kg)\n"

    if mesafeler:
        mesaj += f"🏃 *Toplam koşu:* {sum(mesafeler):.1f} km ({len(mesafeler)} gün)\n"
        mesaj += f"📏 *Ortalama mesafe:* {sum(mesafeler)/len(mesafeler):.1f} km\n"

    if sureler:
        toplam_sure = sum(sureler)
        mesaj += f"⏱️ *Toplam süre:* {toplam_sure} dk\n"

    kosusuz = 7 - len(mesafeler)
    mesaj += f"✅ *Koşulan gün:* {len(mesafeler)}/7\n"
    if kosusuz > 0:
        mesaj += f"😴 *Dinlenme günü:* {kosusuz}\n"

    if ruh_halleri:
        ort_ruh = sum(ruh_halleri) / len(ruh_halleri)
        emoji = "😄" if ort_ruh >= 4 else "🙂" if ort_ruh >= 3 else "😐" if ort_ruh >= 2 else "😔"
        mesaj += f"\n{emoji} *Ortalama ruh hali:* {ort_ruh:.1f}/5"

    mesaj += "\n━━━━━━━━━━━━━━━\n_Sessiz dip dalga devam ediyor_ 🌊"
    return mesaj

# === CHECKIN DURUMU (konuşma state) ===
checkin_state = {}

async def checkin_baslat(bot):
    tarih = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    checkin_state["aktif"] = True
    checkin_state["adim"] = 1
    checkin_state["tarih"] = tarih
    await send_message(bot, """🌙 *Günlük Check-in Zamanı!*

━━━━━━━━━━━━━━━
İstersen tek seferde yaz:
`74.5kg 5.2km 28dk mercimek çorbası iyi bir gündü`

Ya da adım adım gidelim 👇

1️⃣ *Tartı kilonu yaz* (örn: `74.5`)
_(koşmadıysan veya tartılmadıysan 'geç' yaz)_""")

async def checkin_isle(bot, metin, tarih):
    adim = checkin_state.get("adim", 1)

    # Tek seferde hepsini yazdıysa
    if adim == 1:
        kilo_esle = re.search(r'(\d+[.,]\d+)\s*kg', metin)
        mesafe_esle = re.search(r'(\d+[.,]\d+)\s*km', metin)
        sure_esle = re.search(r'(\d+)\s*dk', metin)

        if kilo_esle or mesafe_esle:
            if kilo_esle:
                kaydet_gunluk(tarih, "kilo", float(kilo_esle.group(1).replace(',', '.')))
            if mesafe_esle:
                kaydet_gunluk(tarih, "kosu_mesafe", float(mesafe_esle.group(1).replace(',', '.')))
            if sure_esle:
                kaydet_gunluk(tarih, "kosu_sure", int(sure_esle.group(1)))

            # Geri kalanı günce olarak kaydet
            temiz = re.sub(r'\d+[.,]\d+\s*kg|\d+[.,]\d+\s*km|\d+\s*dk', '', metin).strip()
            if temiz:
                kaydet_gunluk(tarih, "yedikleri", temiz)

            checkin_state["adim"] = 5
            await send_message(bot, "✅ Kaydedildi! Son olarak:\n\n5️⃣ *Bugün nasıldı? Ruh halini 1-5 ver* (1=kötü, 5=harika)\nBir de kısaca içini dök ✍️")
            return

    if adim == 1:
        if metin.lower() != "geç":
            try:
                kilo = float(metin.replace(',', '.').replace('kg', '').strip())
                kaydet_gunluk(tarih, "kilo", kilo)
                await send_message(bot, f"⚖️ {kilo} kg kaydedildi.\n\n2️⃣ *Koştu musun?* Mesafe ve süre yaz\n_(örn: `5.2km 28dk` ya da `koşmadım`)_")
            except:
                await send_message(bot, "Anlamadım, tekrar yaz (örn: `74.5`) ya da `geç` yaz.")
                return
        else:
            await send_message(bot, "2️⃣ *Koştu musun?* Mesafe ve süre yaz\n_(örn: `5.2km 28dk` ya da `koşmadım`)_")
        checkin_state["adim"] = 2

    elif adim == 2:
        if metin.lower() not in ["koşmadım", "kosmadim", "geç", "gec"]:
            mesafe_esle = re.search(r'(\d+[.,]\d+)\s*km', metin)
            sure_esle = re.search(r'(\d+)\s*dk', metin)
            if mesafe_esle:
                kaydet_gunluk(tarih, "kosu_mesafe", float(mesafe_esle.group(1).replace(',', '.')))
            if sure_esle:
                kaydet_gunluk(tarih, "kosu_sure", int(sure_esle.group(1)))
            await send_message(bot, "🏃 Koşu kaydedildi!\n\n3️⃣ *Bugün ne yedin?* Kısaca yaz")
        else:
            await send_message(bot, "3️⃣ *Bugün ne yedin?* Kısaca yaz")
        checkin_state["adim"] = 3

    elif adim == 3:
        kaydet_gunluk(tarih, "yedikleri", metin)
        await send_message(bot, "🍽️ Kaydedildi!\n\n4️⃣ *Bugün nasıldı? Ruh halini 1-5 ver*\n_(1=berbat, 3=orta, 5=harika)_\nBir de kısaca içini dök ✍️")
        checkin_state["adim"] = 4

    elif adim in [4, 5]:
        sayi_esle = re.search(r'[1-5]', metin)
        if sayi_esle:
            ruh = int(sayi_esle.group())
            kaydet_gunluk(tarih, "ruh_hali", ruh)
        gunce = re.sub(r'^[1-5]\s*', '', metin).strip()
        if gunce:
            kaydet_gunluk(tarih, "gunce", gunce)

        checkin_state["aktif"] = False
        checkin_state["adim"] = 0

        emoji = "😄" if (sayi_esle and int(sayi_esle.group()) >= 4) else "🙂" if (sayi_esle and int(sayi_esle.group()) >= 3) else "💪"
        await send_message(bot, f"{emoji} *Check-in tamamlandı!*\n\nBugünkü her şey kaydedildi. Yarın daha güçlü! 🌊\n\n_Haftalık rapor Cumartesi akşamı gelecek._")

# === FITNESS MESAJLARI ===
SABAH_MESAJI = """🌅 *Günaydın! Yeni bir gün, yeni bir fırsat.*

━━━━━━━━━━━━━━━
☕ *SABAH KAHVALTISI*
━━━━━━━━━━━━━━━
• 200g yoğurt + chia/keten tohumu
• 60g beyaz peynir
• Domates, salatalık, yeşil biber
• Şekersiz kahve / limonlu su

💧 *Su hedefi: 2.5-3 litre bugün*
Dükkan yolunda sahil kenarından geç, 10 dk yürü! 🚶"""

OGLE_MESAJI = """🌞 *Öğle vakti — yakıt zamanı!*

🐟 *Ton balığı günüyse:*
• 1 kutu ton + bol yeşillik salata + zeytinyağı

🫘 *Baklagil günüyse:*
• Mercimek çorbası veya nohut/fasulye + yoğurt"""

IKINDI_MESAJI = """⏰ *16:00 — Ara öğün (açsan)*

• 1 bardak ayran + avuç fındık
veya
• 150g yoğurt + meyve

💪 Spor günüyse akşam yemeğini hafif tut!"""

AKSAM_MESAJI = """🌙 *Akşam — şimdi sen zamanı!*

🍽️ Zeytinyağlı sebze + yoğurt
🥩 Haftada 1: ızgara kıyma/köfte

━━━━━━━━━━━━━━━
🏃 *SPOR (Sal/Per/Cum)*
1. 5 dk ısınma
2. 25-30 dk interval: 2dk yürü → 1dk koş
3. 5-10 dk soğuma

🚴 *Hafta sonu:* 50-60 dk sahil bisikleti
Sessiz dip dalga... 🌊"""

SPOR_TAKVIMI = {
    0: "Pazartesi — 🛌 Dinlenme",
    1: "Salı — 🏃 AKŞAM KOŞUSU! 40 dk interval",
    2: "Çarşamba — 🍖 Kırmızı et günü, dinlenme",
    3: "Perşembe — 🏃 AKŞAM KOŞUSU! 40 dk interval",
    4: "Cuma — 🏃 AKŞAM KOŞUSU! Haftanın sonu!",
    5: "Cumartesi — 🚴 SABAH BİSİKLETİ! 50-60 dk",
    6: "Pazar — 🌿 Tam dinlenme",
}

# === MESAJ GÖNDER ===
async def send_message(bot, text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
        logger.info(f"Mesaj: {text[:50]}...")
    except TelegramError as e:
        logger.error(f"Hata: {e}")

# === GELEN MESAJ İŞLE ===
async def mesaj_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.chat_id) != CHAT_ID:
        return

    metin = update.message.text.strip()
    bot = context.bot
    tarih = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    # Check-in aktifse oraya yönlendir
    if checkin_state.get("aktif"):
        await checkin_isle(bot, metin, tarih)
        return

    # Komutlar
    if metin.lower() in ["özet", "ozet", "/ozet"]:
        rows = gunluk_harcamalar()
        await send_message(bot, ozet_olustur([(r[0], r[1], r[2]) for r in rows] if rows else [], "📊 *Bugünkü Harcamalar*", 0) if rows else "Bugün harcama kaydı yok.")
        return

    if metin.lower() in ["hafta", "haftalık", "haftalik", "/hafta"]:
        rows = haftalik_harcamalar()
        await send_message(bot, ozet_olustur(rows, "📊 *Bu Haftaki Harcamalar*"))
        return

    if metin.lower() in ["ay", "aylık", "aylik", "/ay"]:
        rows = aylik_harcamalar()
        await send_message(bot, ozet_olustur(rows, "📊 *Bu Ayki Harcamalar*"))
        return

    if metin.lower() in ["sağlık", "saglik", "/saglik", "rapor"]:
        rows = haftalik_gunluk()
        await send_message(bot, haftalik_saglik_raporu(rows))
        return

    if metin.lower() in ["checkin", "check-in", "/checkin", "günce", "gunce"]:
        await checkin_baslat(bot)
        return

    if metin.lower() in ["yardım", "yardim", "/yardim", "/help"]:
        await send_message(bot, """🤖 *OtagDaily Bot — Komutlar*

━━━━━━━━━━━━━━━
💸 *Harcama Ekle*
Sadece tutar yaz: `85` veya `kahve 30`

📊 *Raporlar*
`özet` → bugünkü harcamalar
`hafta` → haftalık harcamalar
`ay` → aylık harcamalar
`sağlık` → haftalık sağlık raporu

📓 *Günce & Check-in*
`günce` → manuel check-in başlat

━━━━━━━━━━━━━━━
⏰ *Otomatik Mesajlar*
07:00 — Kahvaltı & spor planı
12:30 — Öğle hatırlatıcısı
16:00 — Ara öğün
21:30 — Akşam & spor
23:00 — Günlük check-in
Cumartesi 21:00 — Haftalık rapor""")
        return

    # Sayı → harcama
    sayi_esle = re.search(r'\b\d+([.,]\d+)?\b', metin)
    if sayi_esle and not any(x in metin.lower() for x in ['kg', 'km', 'dk']):
        tutar = float(sayi_esle.group().replace(',', '.'))
        kategori = tahmin_kategori(metin)
        kaydet_harcama(tutar, kategori, metin)
        await send_message(bot, f"✅ *{tutar:.0f} TL* kaydedildi\n📁 {kategori}\n\n_Özet için 'özet' yaz_")
        return

    await send_message(bot, "❓ Anlamadım. `yardım` yaz komutları görmek için.")

# === ZAMANLAYICI ===
async def scheduler(bot):
    logger.info("Scheduler başladı...")
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
            await send_message(bot, SABAH_MESAJI + f"\n\n📅 *Bugün:* {SPOR_TAKVIMI.get(gun, '')}")

        elif gonder_mi("ogle", 12, 30):
            await send_message(bot, OGLE_MESAJI)

        elif gonder_mi("ikindi", 16):
            await send_message(bot, IKINDI_MESAJI)

        elif gonder_mi("aksam", 21, 30):
            await send_message(bot, AKSAM_MESAJI)

        elif gonder_mi("checkin", 23):
            await checkin_baslat(bot)

        # Cumartesi 21:00 haftalık rapor
        elif gonder_mi("haftalik_rapor", 21) and gun == 5:
            rows_saglik = haftalik_gunluk()
            await send_message(bot, haftalik_saglik_raporu(rows_saglik))
            rows_harcama = haftalik_harcamalar()
            await send_message(bot, ozet_olustur(rows_harcama, "💳 *Haftalık Harcama Raporu*"))

        await asyncio.sleep(30)

# === ANA FONKSİYON ===
async def main():
    init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isle))

    bot = app.bot
    me = await bot.get_me()
    logger.info(f"Bot aktif: @{me.username}")

    await send_message(bot, """🤖 *OtagDaily Bot v2 aktif!*

Yeni özellikler:
📓 Her gece 23:00 günlük check-in
⚖️ Kilo takibi
🏃 Koşu mesafe & süre
🍽️ Ne yediğin
😊 Ruh hali günlüğü
📊 Cumartesi haftalık rapor

`yardım` yaz tüm komutları gör 👋""")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await scheduler(bot)

if __name__ == "__main__":
    asyncio.run(main())
