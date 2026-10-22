<div align="center">

# Twitch Point Miner

**Twitch kanal puanı otomasyonu · Discord ve Telegram üzerinden yönetim**

Kanal listesini düzenle, puanları takip et ve canlı logları uzaktan izle.

[Kurulum](#kurulum) · [Komutlar](#komutlar) · [VDS ve PM2](#vds-ve-pm2) · [Sınırlar](#bilinen-davranışlar-ve-sınırlar) · [Kaynak proje](#kaynak-proje-ve-lisans)

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-kontrol-5865F2?style=flat-square&logo=discord&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-kontrol-26A5E4?style=flat-square&logo=telegram&logoColor=white)
[![Lisans](https://img.shields.io/badge/License-GPL--3.0-blue?style=flat-square)](LICENSE)

</div>

## Bu sürümün farkı

Bu repo, [rdavydov/Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) tabanına **uzaktan kontrol ve VDS üzerinde işletim** ekleyen bir uyarlamadır. Kanal puanı toplama motoru kaynak projeden gelir; bu repodaki ek çalışmalar hesap/kanal yönetimi, kontrol botları, log aktarımı ve dağıtım araçlarına odaklanır.

| Eklenen katman | Ne sağlar? |
| --- | --- |
| **Discord kontrolü** | Slash komutlarıyla durum, puan, kanal ve hesap yönetimi |
| **Telegram kontrolü** | Belirlenen sohbetten durum sorgulama, hesap ve kanal işlemleri |
| **Canlı log aktarımı** | Discord ve Telegram için ayrı aç/kapat kontrolü |
| **Kalıcı yapılandırma** | Hesaplar, aktif hesap, kanal listesi ve prediction ayarlarını yerel JSON'da saklama |
| **Prediction yönetimi** | Discord'dan ayarları görüntüleme, değiştirme ve açıp kapatma |
| **VDS araçları** | PM2 yapılandırması ve Linux kurulum betiği |
| **Windows başlangıcı** | Sanal ortamı hazırlayan ve uygulamayı çalıştıran `start.bat` |

Hesap listesi birden fazla kayıt saklayabilir; **bir miner süreci aynı anda tek aktif Twitch hesabını kullanır.**

## Nasıl çalışır?

`run.py`, yerel yapılandırmadaki aktif hesap ve kanallarla miner'ı başlatır. Hesap veya kanal yoksa önce kontrol botları çalışır; yapılandırma tamamlandıktan sonra süreç yeniden başlatılır.

- Prediction işlemleri varsayılan olarak **kapalıdır**.
- Analytics web sunucusu varsayılan olarak **kapalıdır**.
- Discord canlı logları başlangıçta açık, Telegram canlı logları kapalıdır.
- Twitch tarafındaki puan, raid ve drop işleyişi kaynak motorun davranışına ve Twitch servislerinin uyumluluğuna bağlıdır. Kesintisiz çalışma veya belirli bir puan getirisi garanti edilmez.

## Kurulum

Git ve sanal ortam oluşturabilen Python 3 gerekir. Bağımlılıklar [requirements.txt](requirements.txt) dosyasındadır. Bu README yenilemesinde yeni bir Python/platform uyumluluk testi yapılmamıştır.

### 1. Repoyu indir

```bash
git clone https://github.com/BenOnur/Twitch-Point-Miner.git
cd Twitch-Point-Miner
```

### 2. Sanal ortam ve bağımlılıklar

**Linux:**

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

**Windows / PowerShell:**

```powershell
py -3 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Kontrol botunu yapılandır

Proje kökünde `.env` oluştur. Kullanacağın platformun alanlarını doldur; diğer platformun token'ını boş, sayısal kimliğini `0` bırakabilirsin.

```dotenv
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=0
DISCORD_TOKEN=
DISCORD_CHANNEL_ID=0
```

Örneğin Telegram kullanacaksan bot token'ını ve **yalnız sana ait özel sohbetin** sayısal kimliğini yaz. Discord kullanacaksan bot token'ını ve erişimi kısıtlı kontrol kanalının kimliğini yaz; botu slash komutlarını kullanabilecek şekilde sunucuna ekle.

`run.py` içindeki basit `.env` okuyucusu tırnakları kaldırmaz. Değerleri `KEY=value` biçiminde, tırnaksız yaz.

### 4. Hesap ve kanalları hazırla

Hesap parolasını bir sohbet komutuna yazmak yerine, ilk çalıştırmadan önce proje kökünde **yerel** `config.json` oluşturabilirsin:

```json
{
  "accounts": [
    {
      "slot": 1,
      "username": "TWITCH_KULLANICI_ADI",
      "password": "YALNIZ_YEREL_DOSYAYA_YAZ"
    }
  ],
  "active_account": 1,
  "channels": ["YAYINCI_KULLANICI_ADI"],
  "enable_analytics": false,
  "bet_settings": {
    "enabled": false
  }
}
```

Eksik prediction ayarları kodun varsayılanlarıyla tamamlanır. Kanal listesinde URL yerine yayıncı kullanıcı adını kullan.

**Hesap parolaları `config.json` içinde düz metin tutulur.** Bu dosyayı, `.env` dosyasını, oturum çerezlerini ve logları paylaşma veya Git'e ekleme; dosya erişimini kendi kullanıcınla sınırla.

### 5. Çalıştır

Proje kökünden:

```bash
# Linux
./venv/bin/python run.py
```

```powershell
# Windows
.\venv\Scripts\python.exe run.py
```

Windows'ta alternatif olarak [start.bat](start.bat) kullanılabilir. Bu dosya eksik sanal ortamı oluşturur ve ilk kurulumda bağımlılıkları yükler; PM2 gibi otomatik yeniden başlatma sağlamaz.

## Komutlar

Discord'da slash komutlarını arayüzden seç; Telegram'da mesaj olarak gönder.

| Komut | Discord | Telegram | İşlev |
| --- | :---: | :---: | --- |
| `/status` | ✓ | ✓ | Miner durumunu gösterir |
| `/points` | ✓ | ✓ | Kanal puanlarını gösterir |
| `/online` | ✓ | ✓ | Çevrimiçi yayıncıları listeler |
| `/uptime` | ✓ | ✓ | Çalışma süresini gösterir |
| `/logs` | ✓ | ✓ | İlgili platformun canlı loglarını açar/kapatır |
| `/account list` | ✓ | ✓ | Kayıtlı hesapları listeler |
| `/account add` | ✓ | ✓ | Kullanıcı adı ve parola ile hesap kaydeder |
| `/account remove` | ✓ | ✓ | Slot numarasıyla hesap siler |
| `/channel list` | ✓ | ✓ | Kanal listesini gösterir |
| `/channel add` | ✓ | ✓ | Yayıncı ekler |
| `/channel remove` | ✓ | ✓ | Yayıncı kaldırır |
| `/start` | ✓ | ✓ | Süreci yeniden başlatılmak üzere sonlandırır |
| `/stop` | ✓ | ✓ | Çalışan miner sürecini sonlandırır |
| `/bet status` | ✓ | — | Prediction ayarlarını gösterir |
| `/bet toggle` | ✓ | — | Prediction işlemlerini açar/kapatır |
| `/bet set` | ✓ | — | Prediction parametrelerini değiştirir |
| `/help` | — | ✓ | Telegram komut yardımını gösterir |

Telegram örnekleri:

```text
/channel add yayinci_adi
/channel list
/account list
/logs
```

Hesap/kanal ve prediction değişiklikleri yeniden başlatma tetikleyebilir. Kalıcı ayarları değiştirmeden önce aşağıdaki süreç yönetimi davranışını oku.

## VDS ve PM2

[ecosystem.config.js](ecosystem.config.js), `twitch-miner` adlı süreci otomatik yeniden başlatmayla çalıştırır. Python bağımlılıklarını ve Node.js/PM2'yi hazırladıktan sonra, **proje kökünden**:

```bash
pm2 start ecosystem.config.js --interpreter "$(pwd)/venv/bin/python3"
pm2 logs twitch-miner --lines 50
pm2 save
```

Açılışta başlatma için `pm2 startup` çalıştır ve PM2'nin ürettiği sistemine uygun komutu uygula; ardından `pm2 save` çalıştır.

| İşlem | Komut |
| --- | --- |
| Durumu gör | `pm2 status twitch-miner` |
| Yeniden başlat | `pm2 restart twitch-miner` |
| Kalıcı olarak durdur | `pm2 stop twitch-miner` |
| Logları izle | `pm2 logs twitch-miner` |

[setup_vds.sh](setup_vds.sh) bir kurulum yardımcısıdır; sistem paketlerini günceller ve PM2 yoksa Node.js 18 kurulum yolunu kullanır. Güncel ortamına uygunluğunu incelemeden çalıştırma. Yukarıdaki elle kurulum adımları daha kontrollü bir başlangıç sağlar.

## Bilinen davranışlar ve sınırlar

- **Bot komutları servis yöneticisi değildir.** `/start` ve `/stop` süreçte `SIGTERM` kullanır. PM2 otomatik yeniden başlatma açıkken `/stop` sonrasında da uygulama tekrar açılabilir. Kalıcı durdurma için `pm2 stop twitch-miner` kullan. Elle çalıştırmada süreci kendin tekrar başlatmalısın.
- **Discord yetkisi varsayılan olarak kanal bazlıdır.** Kontrol kanalına erişen kişiler komut kullanabilir. Kullanıcı bazlı ek kontrol sınıfta vardır; ancak `run.py` içindeki `authorized_user_id` yapılandırması yorum satırındadır. Yalnız bir ortam değişkeni eklemek bu kontrolü etkinleştirmez.
- **Telegram yetkisi sohbet kimliğine dayanır.** Ortak bir grubu kontrol sohbeti yapmak yerine kişisel özel sohbet kullan.
- **Analytics'i açarsan ağ erişimini sınırla.** `run.py` web sunucusunu `0.0.0.0:5000` üzerinde başlatır. Bu portu doğrudan internete açma.
- Twitch giriş akışı ve özel servis uçları değişebilir. Eski bir commit'in bugün çalıştığı varsayılmamalıdır; bu dokümantasyon güncellemesi canlı Twitch oturumu testi içermez.

## Kod haritası

| Dosya | Sorumluluk |
| --- | --- |
| [run.py](run.py) | Giriş noktası, ortam değişkenleri ve miner kurulumu |
| [ConfigManager.py](TwitchChannelPointsMiner/classes/ConfigManager.py) | Hesaplar, kanallar ve prediction ayarları |
| [DiscordControl.py](TwitchChannelPointsMiner/classes/DiscordControl.py) | Discord slash komutları ve log aktarımı |
| [TelegramControl.py](TwitchChannelPointsMiner/classes/TelegramControl.py) | Telegram komutları ve log aktarımı |
| [ecosystem.config.js](ecosystem.config.js) | PM2 süreç tanımı |
| [example.py](example.py) | Kaynak motor için alternatif kullanım örneği |

## Kaynak proje ve lisans

Bu uyarlama, [rdavydov/Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) üzerine kuruludur. Kaynak zincirindeki [Tkd-Alex](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2) ve [gottagofaster236](https://github.com/gottagofaster236/Twitch-Channel-Points-Miner) projelerine de teşekkürler.

Bu repodaki uzaktan kontrol, yapılandırma ve VDS ekleri **BenOnur** tarafından geliştirilmiştir. Lisans metni [LICENSE](LICENSE) dosyasındadır (**GNU GPL v3**).
