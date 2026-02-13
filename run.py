# -*- coding: utf-8 -*-
import logging
import os
import signal
import sys
import time
import threading

# Fix Windows console encoding for emoji/unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from colorama import Fore
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.entities.Bet import (
    Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode
)
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.ConfigManager import ConfigManager

# ============================================================
# .env DOSYASINDAN TOKEN'LARI OKU
# ============================================================

def load_env(path=".env"):
    """Basit .env dosyası okuyucu (python-dotenv gerektirmez)"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

load_env()

TELEGRAM_CONFIG = {
    "token": os.environ.get("TELEGRAM_TOKEN", ""),
    "chat_id": int(os.environ.get("TELEGRAM_CHAT_ID", "0")),
}

DISCORD_CONFIG = {
    "token": os.environ.get("DISCORD_TOKEN", ""),
    "channel_id": int(os.environ.get("DISCORD_CHANNEL_ID", "0")),
    # "authorized_user_id": int(os.environ.get("DISCORD_AUTHORIZED_USER_ID", "0")),
}

# ============================================================
# CONFIG'DEN HESAP VE KANALLARI OKU
# ============================================================

config = ConfigManager()
account = config.get_active_account()
channels = config.list_channels()

if not account or not channels:
    # Hesap veya kanal yoksa sadece kontrol botlarını başlat
    print("=" * 60)
    print("⚠️  Hesap veya kanal bulunamadı!")
    print("Telegram/Discord'dan aşağıdaki komutları kullan:")
    print("  /account add <kullanıcı> <şifre>")
    print("  /channel add <kanal>")
    print("  /start  (ekledikten sonra)")
    print("=" * 60)

    # Start control bots in standalone mode
    from TwitchChannelPointsMiner.classes.TelegramControl import TelegramControl
    from TwitchChannelPointsMiner.classes.DiscordControl import DiscordControl

    telegram_bot = TelegramControl(
        token=TELEGRAM_CONFIG["token"],
        chat_id=TELEGRAM_CONFIG["chat_id"],
        miner=None,
        config_manager=config,
    )
    telegram_bot.start()

    discord_bot = DiscordControl(
        token=DISCORD_CONFIG["token"],
        channel_id=DISCORD_CONFIG["channel_id"],
        authorized_user_id=DISCORD_CONFIG.get("authorized_user_id"),
        miner=None,
        config_manager=config,
    )
    discord_bot.start()

    # Keep alive
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        print("\nKapatılıyor...")
        sys.exit(0)

else:
    # ============================================================
    # Kumar ayarlarini config'den oku
    bet_cfg = config.get_bet_settings()
    predictions_enabled = bet_cfg.get("enabled", False)

    STRATEGY_MAP = {
        "smart": Strategy.SMART,
        "percentage": Strategy.PERCENTAGE,
        "high_odds": Strategy.HIGH_ODDS,
        "most_voted": Strategy.MOST_VOTED,
    }

    bet_config = BetSettings(
        strategy=STRATEGY_MAP.get(bet_cfg.get("strategy", "smart"), Strategy.SMART),
        percentage=bet_cfg.get("percentage", 5),
        percentage_gap=bet_cfg.get("percentage_gap", 20),
        max_points=bet_cfg.get("max_points", 50000),
        stealth_mode=True,
        delay_mode=DelayMode.FROM_END,
        delay=bet_cfg.get("delay", 6),
        minimum_points=bet_cfg.get("min_points", 20000),
        filter_condition=FilterCondition(
            by=OutcomeKeys.TOTAL_USERS,
            where=Condition.LTE,
            value=800
        )
    ) if predictions_enabled else BetSettings()

    twitch_miner = TwitchChannelPointsMiner(
        username=account["username"],
        password=account["password"],
        claim_drops_startup=False,
        priority=[
            Priority.STREAK,
            Priority.DROPS,
            Priority.ORDER
        ],
        enable_analytics=False,
        disable_ssl_cert_verification=False,
        telegram_control_config=TELEGRAM_CONFIG,
        discord_control_config=DISCORD_CONFIG,
        logger_settings=LoggerSettings(
            save=True,
            console_level=logging.INFO,
            console_username=False,
            auto_clear=True,
            time_zone="Europe/Istanbul",
            file_level=logging.DEBUG,
            emoji=True,
            less=False,
            colored=True,
            color_palette=ColorPalette(
                STREAMER_online="GREEN",
                streamer_offline="red",
                BET_wiN=Fore.MAGENTA
            ),
        ),
        streamer_settings=StreamerSettings(
            make_predictions=predictions_enabled,
            follow_raid=True,
            claim_drops=True,
            claim_moments=True,
            watch_streak=True,
            community_goals=False,
            chat=ChatPresence.ONLINE,
            bet=bet_config,
        )
    )

    twitch_miner.mine(
        channels,
        followers=False,
        followers_order=FollowersOrder.ASC
    )
