#!/bin/bash

# Renkler
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}[*] Twitch Miner Kurulumu Baslatiliyor...${NC}"

# 1. Sistem Guncelleme
echo -e "${BLUE}[*] Sistem paketleri guncelleniyor...${NC}"
sudo apt update && sudo apt upgrade -y

# 2. Python ve PIP Kurulumu
echo -e "${BLUE}[*] Python3 ve PIP kuruluyor...${NC}"
sudo apt install python3 python3-pip python3-venv git -y

# 3. Node.js ve PM2 Kurulumu (Eger yoksa)
if ! command -v pm2 &> /dev/null; then
    echo -e "${BLUE}[*] Node.js ve PM2 kuruluyor...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
    sudo npm install -g pm2
else
    echo -e "${GREEN}[+] PM2 zaten kurulu.${NC}"
fi

# 4. Repo Klonlama (YOKSA)
if [ ! -d "Twitch-Point-Miner" ]; then
    echo -e "${BLUE}[*] Repo klonlaniyor...${NC}"
    # BURAYA KENDİ REPO ADRESİNİ YAZACAKSIN
    git clone https://github.com/BenOnur/Twitch-Point-Miner.git
else
    echo -e "${GREEN}[+] Repo zaten var. Guncelleniyor...${NC}"
    cd Twitch-Point-Miner
    git pull
    cd ..
fi

cd Twitch-Point-Miner

# 5. Virtual Environment Kurulumu
if [ ! -d "venv" ]; then
    echo -e "${BLUE}[*] Virtual Environment olusturuluyor...${NC}"
    python3 -m venv venv
fi

# 6. Bagimliliklari Yukle
echo -e "${BLUE}[*] Python kutuphaneleri yukleniyor...${NC}"
./venv/bin/pip install -r requirements.txt

# 7. .env Dosyasi Kontrolu
if [ ! -f ".env" ]; then
    echo -e "${BLUE}[!] .env dosyasi bulunamadi! Lutfen olusturun.${NC}"
    echo "Ornek:"
    echo "TELEGRAM_TOKEN=..."
    echo "TELEGRAM_CHAT_ID=..."
    echo "DISCORD_TOKEN=..."
    echo "DISCORD_CHANNEL_ID=..."
    exit 1
fi

# 8. PM2 ile Baslat
echo -e "${BLUE}[*] PM2 ile baslatiliyor...${NC}"
# pm2 start ecosystem.config.js --interpreter ./venv/bin/python3
pm2 start ecosystem.config.js --interpreter $(pwd)/venv/bin/python3

# 9. PM2 Kaydet
pm2 save
pm2 startup | tail -n 1 | bash

echo -e "${GREEN}[+] Kurulum Tamamlandi!${NC}"
echo -e "${GREEN}[+] Loglari izlemek icin: pm2 logs twitch-miner${NC}"
