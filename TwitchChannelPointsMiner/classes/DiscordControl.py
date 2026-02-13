# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import signal
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class DiscordControl(threading.Thread):
    """Discord bot that listens for commands to control the Twitch Miner."""

    def __init__(self, token: str, channel_id: int, authorized_user_id: int = None,
                 miner=None, config_manager=None):
        super().__init__()
        self.daemon = True
        self.name = "DiscordControl Thread"

        self.token = token
        self.channel_id = int(channel_id)
        self.authorized_user_id = int(authorized_user_id) if authorized_user_id else None
        self.miner = miner
        self.config_manager = config_manager
        self.loop = None
        self.client = None

    def run(self):
        try:
            import discord
        except ImportError:
            logger.error("discord.py is not installed! Run: pip install discord.py")
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        control = self

        @self.client.event
        async def on_ready():
            logger.info(f"Discord Control Bot logged in as {self.client.user}")
            channel = self.client.get_channel(control.channel_id)
            if channel:
                await channel.send("✅ Twitch Miner Discord kontrol botu başlatıldı!\n`t!help` yazarak komutları görebilirsin.")

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return
            if message.channel.id != control.channel_id:
                return
            if control.authorized_user_id and message.author.id != control.authorized_user_id:
                return

            text = message.content.strip()
            if not text.startswith("t!"):
                return

            parts = text.split()
            cmd = parts[0].lower()
            args = parts[1:]

            try:
                result = control._dispatch(cmd, args)
                if result:
                    await message.channel.send(result)
            except Exception as e:
                await message.channel.send(f"❌ Hata: {e}")
                logger.error(f"Discord command error ({cmd}): {e}")

        try:
            self.loop.run_until_complete(self.client.start(self.token))
        except Exception as e:
            logger.error(f"Discord Control Bot error: {e}")

    def stop(self):
        if self.client and self.loop:
            asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)

    def _dispatch(self, cmd, args):
        simple = {
            "t!status": self._cmd_status,
            "t!points": self._cmd_points,
            "t!online": self._cmd_online,
            "t!uptime": self._cmd_uptime,
            "t!stop": self._cmd_stop,
            "t!start": self._cmd_start,
            "t!help": self._cmd_help,
        }

        if cmd in simple:
            return simple[cmd]()

        if cmd == "t!account":
            return self._cmd_account(args)
        if cmd == "t!channel":
            return self._cmd_channel(args)

        return f"❓ Bilinmeyen komut: `{cmd}`\n`t!help` yazarak komutları görebilirsin."

    # ── Simple Commands ─────────────────────────────────────────

    def _cmd_help(self):
        return (
            "🎮 **Twitch Miner Kontrol Komutları**\n\n"
            "**Genel:**\n"
            "`t!status` - Miner durumu\n"
            "`t!points` - Kanal puanları\n"
            "`t!online` - Online yayıncılar\n"
            "`t!uptime` - Çalışma süresi\n"
            "`t!stop` - Miner'ı durdur\n"
            "`t!start` - Miner'ı yeniden başlat\n\n"
            "**Hesap Yönetimi:**\n"
            "`t!account add <kullanıcı> <şifre>`\n"
            "`t!account list`\n"
            "`t!account remove <slot>`\n\n"
            "**Kanal Yönetimi:**\n"
            "`t!channel add <kanal>`\n"
            "`t!channel remove <kanal>`\n"
            "`t!channel list`"
        )

    def _cmd_status(self):
        if not self.miner or not self.miner.running:
            active = self.config_manager.get_active_account() if self.config_manager else None
            channels = self.config_manager.list_channels() if self.config_manager else []
            msg = "📊 **Miner Durumu**\n\nDurum: 🛑 Durdu\n"
            if active:
                msg += f"Aktif hesap: `{active['username']}`\n"
            msg += f"Kayıtlı kanal: {len(channels)}"
            return msg

        total = len(self.miner.streamers)
        online = sum(1 for s in self.miner.streamers if s.is_online)

        return (
            f"📊 **Miner Durumu**\n\n"
            f"Durum: ✅ Çalışıyor\n"
            f"Kullanıcı: `{self.miner.username}`\n"
            f"Toplam yayıncı: {total}\n"
            f"Online: {online}\n"
            f"Session: `{self.miner.session_id[:8]}...`"
        )

    def _cmd_points(self):
        if not self.miner or not self.miner.streamers:
            return "📭 Aktif miner veya yayıncı yok."

        lines = ["💰 **Kanal Puanları**\n"]
        for s in self.miner.streamers:
            status = "🟢" if s.is_online else "🔴"
            points = f"{s.channel_points:,}" if s.channel_points else "?"
            lines.append(f"{status} **{s.username}**: {points}")
        return "\n".join(lines)

    def _cmd_online(self):
        if not self.miner or not self.miner.streamers:
            return "📭 Aktif miner veya yayıncı yok."

        online_streamers = [s for s in self.miner.streamers if s.is_online]
        if not online_streamers:
            return "📭 Şu an online yayıncı yok."

        lines = [f"🟢 **Online Yayıncılar ({len(online_streamers)})**\n"]
        for s in online_streamers:
            points = f"{s.channel_points:,}" if s.channel_points else "?"
            lines.append(f"• **{s.username}** — {points} puan")
        return "\n".join(lines)

    def _cmd_uptime(self):
        if not self.miner or not self.miner.start_datetime:
            return "❌ Miner çalışmıyor."

        uptime = datetime.now() - self.miner.start_datetime
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"⏱ **Çalışma Süresi**\n{hours} saat, {minutes} dakika, {seconds} saniye"

    def _cmd_stop(self):
        if not self.miner or not self.miner.running:
            return "⚠️ Miner zaten durmuş."
        os.kill(os.getpid(), signal.SIGTERM)
        return "🛑 Miner durduruluyor..."

    def _cmd_start(self):
        os.kill(os.getpid(), signal.SIGTERM)
        return "🔄 Miner yeniden başlatılıyor...\nPM2 otomatik olarak tekrar başlatacak."

    # ── Account Commands ────────────────────────────────────────

    def _cmd_account(self, args):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."

        if not args:
            return "Kullanım:\n`t!account add <kullanıcı> <şifre>`\n`t!account list`\n`t!account remove <slot>`"

        sub = args[0].lower()

        if sub == "add":
            if len(args) < 3:
                return "Kullanım: `t!account add <kullanıcı> <şifre>`"
            username = args[1]
            password = args[2]
            slot, msg = self.config_manager.add_account(username, password)
            if slot:
                msg += "\n💡 Değişikliklerin geçerli olması için `t!start` ile yeniden başlat."
            return msg

        elif sub == "list":
            accounts = self.config_manager.list_accounts()
            if not accounts:
                return "📭 Kayıtlı hesap yok.\n`t!account add <kullanıcı> <şifre>` ile ekle."
            active = self.config_manager.get_active_account()
            active_slot = active["slot"] if active else None

            lines = ["👤 **Kayıtlı Hesaplar**\n"]
            for acc in accounts:
                marker = " ⬅️ aktif" if acc["slot"] == active_slot else ""
                lines.append(f"**Slot {acc['slot']}**: `{acc['username']}`{marker}")
            return "\n".join(lines)

        elif sub == "remove":
            if len(args) < 2:
                return "Kullanım: `t!account remove <slot>`"
            try:
                slot = int(args[1])
            except ValueError:
                return "❌ Slot numarası sayı olmalı."
            msg = self.config_manager.remove_account(slot)
            if "✅" in msg:
                msg += "\n💡 Değişikliklerin geçerli olması için `t!start` ile yeniden başlat."
            return msg

        return "Kullanım:\n`t!account add <kullanıcı> <şifre>`\n`t!account list`\n`t!account remove <slot>`"

    # ── Channel Commands ────────────────────────────────────────

    def _cmd_channel(self, args):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."

        if not args:
            return "Kullanım:\n`t!channel add <kanal>`\n`t!channel remove <kanal>`\n`t!channel list`"

        sub = args[0].lower()

        if sub == "add":
            if len(args) < 2:
                return "Kullanım: `t!channel add <kanal>`"
            channel = args[1].lower().strip()
            msg = self.config_manager.add_channel(channel)
            if "✅" in msg:
                msg += "\n💡 Değişikliklerin geçerli olması için `t!start` ile yeniden başlat."
            return msg

        elif sub == "remove":
            if len(args) < 2:
                return "Kullanım: `t!channel remove <kanal>`"
            channel = args[1].lower().strip()
            msg = self.config_manager.remove_channel(channel)
            if "✅" in msg:
                msg += "\n💡 Değişikliklerin geçerli olması için `t!start` ile yeniden başlat."
            return msg

        elif sub == "list":
            channels = self.config_manager.list_channels()
            if not channels:
                return "📭 Kayıtlı kanal yok.\n`t!channel add <kanal>` ile ekle."

            lines = [f"📺 **Mining Kanalları ({len(channels)})**\n"]
            if self.miner and self.miner.streamers:
                online_names = {s.username.lower() for s in self.miner.streamers if s.is_online}
                for ch in channels:
                    status = "🟢" if ch.lower() in online_names else "🔴"
                    lines.append(f"{status} {ch}")
            else:
                for ch in channels:
                    lines.append(f"• {ch}")
            return "\n".join(lines)

        return "Kullanım:\n`t!channel add <kanal>`\n`t!channel remove <kanal>`\n`t!channel list`"
