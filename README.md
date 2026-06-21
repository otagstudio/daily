# 🏃 Otağ Fitness Bot

Günlük beslenme ve spor hatırlatıcısı — Telegram üzerinden çalışır.

## Mesaj Saatleri
| Saat | İçerik |
|------|--------|
| 07:00 | Günaydın + Kahvaltı + Günün spor planı |
| 12:30 | Öğle yemeği hatırlatıcısı |
| 16:00 | Ara öğün |
| 21:30 | Akşam yemeği + Spor rutini |
| 23:00 | Günlük özet + Motivasyon |

## Railway'e Kurulum (Ücretsiz)

### 1. GitHub'a yükle
- github.com'da hesap aç (varsa giriş yap)
- Yeni repository oluştur: `fitness-bot`
- Bu 3 dosyayı yükle: `bot.py`, `requirements.txt`, `railway.toml`

### 2. Railway hesabı aç
- railway.app → "Start a New Project"
- "Deploy from GitHub repo" seç
- fitness-bot reposunu seç

### 3. Environment Variables ekle
Railway dashboard → Variables sekmesi:
```
TELEGRAM_TOKEN = senin_token_buraya
CHAT_ID = senin_chat_id_buraya
```

### 4. Deploy et
Railway otomatik başlatır. Telegram'dan "Bot aktif!" mesajı gelirse kurulum tamam!

## Token Yenileme (Güvenlik)
BotFather → /mybots → botunu seç → API Token → Revoke
Yeni token'ı Railway Variables'a güncelle.
