import asyncio
import logging
from datetime import datetime
import pytz
from telegram import Bot
from telegram.error import TelegramError

# === AYARLAR ===
TOKEN = "8709665483:AAFdZBceYA0kLBBdjx-OMDePuzD_ySqjp8w"
CHAT_ID = "8243859152"
TIMEZONE = pytz.timezone("Europe/Istanbul")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# === GÜNLÜK MESAJLAR ===

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
Bugün ne var?

🐟 *Ton balığı günüyse:*
• 1 kutu ton balığı + bol yeşillik salata
• Zeytinyağı + limon sos
• 1 dilim ekmek

🫘 *Baklagil günüyse:*
• Mercimek çorbası veya nohut/fasulye
• Yanında yoğurt + yeşil salata

☕ Öğleden sonra şekersiz iced kahven hazır olsun!"""

IKINDI_MESAJI = """⏰ *16:00 — Ara öğün vakti (açsan)*

• 1 bardak ayran
• Avuç içi fındık/ceviz

veya

• 150g yoğurt + mevsim meyvesi

━━━━━━━━━━━━━━━
💪 *Bu akşam spor var mı?*
Varsa şimdiden hazırlan, akşam yemeğini hafif tut!"""

AKSAM_MESAJI = """🌙 *Akşam — dükkan kapandı, şimdi sen zamanı!*

━━━━━━━━━━━━━━━
🍽️ *AKŞAM YEMEĞİ*
━━━━━━━━━━━━━━━
• Zeytinyağlı sebze yemeği
• Yanında yoğurt
• Haftada 1 gün: ızgara kıyma/köfte

━━━━━━━━━━━━━━━
🏃 *SPOR PLANI (Sal/Per/Cum)*
━━━━━━━━━━━━━━━
1. 5 dk ısınma yürüyüşü
2. 25-30 dk interval: 2 dk hızlı yürü → 1 dk koş
3. 5-10 dk soğuma

🚴 *Hafta sonu:* 50-60 dk sahil bisikleti

Sessiz dip dalga... 🌊 Her gün biraz daha güçlü."""

GECE_MESAJI = """⭐ *Günü kapat — özet zamanı*

Bugün nasıldı?

✅ Su içtin mi? (2.5-3L)
✅ Öğünlerini tutturabildin mi?
✅ Spor günüyse çıktın mı?

Mükemmel olmak zorunda değilsin.
*Sadece dün olduğundan bir adım ileri.*

Yarın için küçük bir hedef belirle ve uyu. 💤

━━━━━━━━━━━━━━━
_Sessiz dip dalga — görünmez ama durdurulamaz_ 🌊"""

# === HAFTALIK SPOR TAKVİMİ ===
SPOR_TAKVIMI = {
    0: "Pazartesi — 🛌 Dinlenme günü. Kas kendini yeniler.",
    1: "Salı — 🏃 AKŞAM KOŞUSU! Sahile git, 40 dk interval.",
    2: "Çarşamba — 🍖 Kırmızı et günü yapabilirsin. Dinlenme.",
    3: "Perşembe — 🏃 AKŞAM KOŞUSU! Sahile git, 40 dk interval.",
    4: "Cuma — 🏃 AKŞAM KOŞUSU! Haftanın son koşusu, bitir!",
    5: "Cumartesi — 🚴 SABAH BİSİKLETİ! 50-60 dk sahil turu.",
    6: "Pazar — 🌿 Tam dinlenme. Beyin ve vücut şarj oluyor.",
}

# === MESAJ GÖNDER ===
async def send_message(bot: Bot, text: str):
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"Mesaj gönderildi: {text[:50]}...")
    except TelegramError as e:
        logger.error(f"Hata: {e}")

# === ZAMANLAYICI ===
async def scheduler(bot: Bot):
    logger.info("Bot başladı, mesajlar bekleniyor...")
    sent_today = {}

    while True:
        now = datetime.now(TIMEZONE)
        saat = now.hour
        dakika = now.minute
        gun = now.weekday()
        tarih = now.date()

        def gonder_mi(key, hedef_saat, hedef_dakika=0):
            if saat == hedef_saat and dakika == hedef_dakika:
                if sent_today.get(f"{tarih}_{key}"):
                    return False
                sent_today[f"{tarih}_{key}"] = True
                return True
            return False

        if gonder_mi("sabah", 7, 0):
            spor_notu = SPOR_TAKVIMI.get(gun, "")
            await send_message(bot, SABAH_MESAJI + f"\n\n📅 *Bugün:* {spor_notu}")

        elif gonder_mi("ogle", 12, 30):
            await send_message(bot, OGLE_MESAJI)

        elif gonder_mi("ikindi", 16, 0):
            await send_message(bot, IKINDI_MESAJI)

        elif gonder_mi("aksam", 21, 30):
            await send_message(bot, AKSAM_MESAJI)

        elif gonder_mi("gece", 23, 0):
            await send_message(bot, GECE_MESAJI)

        await asyncio.sleep(30)

# === ANA FONKSİYON ===
async def main():
    bot = Bot(token=TOKEN)
    me = await bot.get_me()
    logger.info(f"Bot aktif: @{me.username}")
    await send_message(bot, "🤖 *Fitness Bot aktif!*\n\nSabah 07:00'den itibaren günlük mesajlarını alacaksın. Haydi başlayalım! 💪🌊")
    await scheduler(bot)

if __name__ == "__main__":
    asyncio.run(main())
