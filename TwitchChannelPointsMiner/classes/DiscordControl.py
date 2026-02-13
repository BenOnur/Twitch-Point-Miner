import asyncio
import logging
import os
import signal
import threading
import queue
from datetime import datetime

logger = logging.getLogger(__name__)


class DiscordLogHandler(logging.Handler):
    """Custom logging handler to send logs to Discord."""
    def __init__(self, discord_control):
        super().__init__()
        self.discord_control = discord_control

    def emit(self, record):
        if self.discord_control.logging_enabled:
            try:
                msg = self.format(record)
                self.discord_control.log_queue.put(msg)
            except Exception:
                self.handleError(record)


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
        
        # Log streaming variables
        self.logging_enabled = False
        self.log_queue = queue.Queue()
        self.log_handler = DiscordLogHandler(self)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Attach to root logger
        logging.getLogger().addHandler(self.log_handler)

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
        
        # Start log flushing task
        self.loop.create_task(self._log_loop())

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
            
    async def _log_loop(self):
        """Background task to flush logs to Discord."""
        while True:
            if self.logging_enabled and self.client and self.client.is_ready():
                messages = []
                while not self.log_queue.empty():
                    try:
                        messages.append(self.log_queue.get_nowait())
                        if len(messages) >= 10:  # Max 10 lines per batch to avoid huge messages
                            break
                    except queue.Empty:
                        break
                
                if messages:
                    text = "\n".join(messages)
                    # Split if too long (Discord limit 2000 chars)
                    if len(text) > 1900:
                        text = text[:1900] + "\n... (truncated)"
                    
                    try:
                        channel = self.client.get_channel(self.channel_id)
                        if channel:
                            await channel.send(f"```\n{text}\n```")
                    except Exception as e:
                        print(f"Failed to send log to Discord: {e}")
            
            # If disabled, clear queue to prevent memory buildup
            if not self.logging_enabled and not self.log_queue.empty():
                 try:
                     while not self.log_queue.empty():
                         self.log_queue.get_nowait()
                 except:
                     pass

            await asyncio.sleep(2)

    def stop(self):
        if self.client and self.loop:
            try:
                future = asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)
                future.result(timeout=5)
            except Exception as e:
                logger.error(f"Error checking Discord close future: {e}")

    def send_sync(self, message):
        """Send a message from a non-async context (e.g. from login callback)."""
        if not self.client or not self.loop:
            return
        async def _send():
            channel = self.client.get_channel(self.channel_id)
            if channel:
                await channel.send(message)
        asyncio.run_coroutine_threadsafe(_send(), self.loop)

    def _dispatch(self, cmd, args):
        simple = {
            "t!status": self._cmd_status,
            "t!points": self._cmd_points,
            "t!online": self._cmd_online,
            "t!uptime": self._cmd_uptime,
            "t!stop": self._cmd_stop,
            "t!start": self._cmd_start,
            "t!logs": self._cmd_logs,
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
            "`t!start` - Miner'ı yeniden başlat\n"
            "`t!logs` - Canlı logları aç/kapat\n\n"
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
        # Kaynak kaydını temizle - manuel start her zaman geneldir
        if self.config_manager:
            self.config_manager.clear_last_command_source()
        
        os.kill(os.getpid(), signal.SIGTERM)
        return "🔄 Miner yeniden başlatılıyor...\nPM2 otomatik olarak tekrar başlatacak."

    def _cmd_logs(self):
        self.logging_enabled = not self.logging_enabled
        status = "açıldı" if self.logging_enabled else "kapandı"
        if self.logging_enabled:
            return f"📝 **Canlı Loglar {status}!**\nKonsola düşen veriler (hata/bilgi) buraya akacak."
        else:
            return f"📝 **Canlı Loglar {status}!**"


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
                # Kaynağı kaydet ki 2FA kodu buraya gelsin
                self.config_manager.set_last_command_source("discord")
                # Mesajı gönderip öyle kapatmamız lazım, biraz bekleyebiliriz veya async task başlatabiliriz
                # Ancak burada basitçe return string yapıyoruz, bu mesaj gittikten sonra process kapanmalı.
                # Discord.py'da return edilen mesaj gönderildikten sonra process kapanması için 
                # dispatch'in sonucunu bekleyip işlem yapmamız gerekirdi ama şu anki yapı buna tam uygun değil.
                # O yüzden mesajı return edip, kısa bir gecikmeyle kapatmayı deneyebiliriz.
                # Veya kullanıcıya "başlatılıyor" deyip kapatırız.
                
                # En temiz yöntem: threading.Timer ile kapatmak
                threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                return f"{msg}\n🔄 Otomatik yeniden başlatılıyor..."
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
                 self.config_manager.clear_last_command_source()
                 threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                 return f"{msg}\n🔄 Değişiklikler için yeniden başlatılıyor..."
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
                if self.config_manager.has_valid_config() or (self.miner and self.miner.running):
                    # self.config_manager.set_last_command_source("discord") # Gerekirse
                    threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                    return f"{msg}\n🔄 Otomatik yeniden başlatılıyor..."
                else:
                    return f"{msg}\n💡 Kanal eklendi. Hesap da ekleyince otomatik başlayacak."
            return msg

        elif sub == "remove":
            if len(args) < 2:
                return "Kullanım: `t!channel remove <kanal>`"
            channel = args[1].lower().strip()
            msg = self.config_manager.remove_channel(channel)
            if "✅" in msg:
                threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                return f"{msg}\n🔄 Değişiklikler için yeniden başlatılıyor..."
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
