import asyncio
import logging
import os
import re
import signal
import threading
import queue
from datetime import datetime

import discord
from discord import app_commands

logger = logging.getLogger(__name__)


class DiscordLogHandler(logging.Handler):
    """Custom logging handler to send pretty logs to Discord."""
    def __init__(self, discord_control):
        super().__init__()
        self.discord_control = discord_control

    def _prettify(self, msg):
        """Convert a raw log message into a pretty Discord message with emojis."""
        msg = re.sub(r'\x1b\[[0-9;]*m', '', msg)
        msg = re.sub(r'^\[[\w_]+\]:\s*', '', msg.strip())

        # Streamer Online
        m = re.search(r'Streamer\(username=(\w+).*?channel_points=([\d.]+\w*)\) is Online', msg)
        if m:
            return f"🟢 **{m.group(1)}** online oldu! — {m.group(2)} puan"

        # Streamer Offline
        m = re.search(r'Streamer\(username=(\w+).*?channel_points=([\d.]+\w*)\) is Offline', msg)
        if m:
            return f"🔴 **{m.group(1)}** offline oldu — {m.group(2)} puan"

        # Gained channel points
        m = re.search(r'\+(\d+)\s.*?Streamer\(username=(\w+).*?channel_points=([\d.]+\w*)\)', msg)
        if m:
            return f"💰 **{m.group(2)}** +{m.group(1)} puan → {m.group(3)}"

        # Claim bonus
        if "Claim" in msg and "bonus" in msg.lower():
            m = re.search(r'Streamer\(username=(\w+)', msg)
            name = m.group(1) if m else "?"
            return f"🎁 **{name}** bonus claim edildi!"

        # Watch streak
        if "Watch Streak" in msg or "watch streak" in msg:
            m = re.search(r'Streamer\(username=(\w+)', msg)
            name = m.group(1) if m else "?"
            return f"🔥 **{name}** watch streak!"

        # Prediction / Bet
        if "bet" in msg.lower() or "prediction" in msg.lower():
            if "won" in msg.lower() or "win" in msg.lower():
                return f"🏆 {msg.strip()}"
            elif "lose" in msg.lower() or "lost" in msg.lower():
                return f"💸 {msg.strip()}"
            return f"🎲 {msg.strip()}"

        # Drop claimed
        if "drop" in msg.lower() and "claim" in msg.lower():
            return f"🎁 {msg.strip()}"

        # Moment
        if "moment" in msg.lower():
            return f"⚡ {msg.strip()}"

        # Join IRC Chat
        if "Join IRC Chat" in msg:
            m = re.search(r'Join IRC Chat:\s*(\w+)', msg)
            if m:
                return f"💬 **{m.group(1)}** chat'e katılındı"
            return f"💬 {msg.strip()}"

        # Login
        if "login" in msg.lower():
            return f"🔐 {msg.strip()}"

        # Session start
        if "Start session" in msg:
            return f"🚀 {msg.strip()}"

        return msg.strip()

    def emit(self, record):
        if not self.discord_control.logging_enabled:
            return
        if not record.name.startswith("TwitchChannelPointsMiner"):
            return
        if record.levelno < logging.INFO:
            return

        try:
            raw_msg = record.getMessage()
            pretty = self._prettify(raw_msg)

            if record.levelno >= logging.ERROR:
                pretty = f"❌ **HATA:** {pretty}"
            elif record.levelno >= logging.WARNING:
                pretty = f"⚠️ {pretty}"

            self.discord_control.log_queue.put(pretty)
        except Exception:
            self.handleError(record)


class DiscordControl(threading.Thread):
    """Discord bot with slash commands to control the Twitch Miner."""

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

        # Log streaming
        self.logging_enabled = False
        self.log_queue = queue.Queue()
        self.log_handler = DiscordLogHandler(self)
        logging.getLogger().addHandler(self.log_handler)

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(self.client)

        control = self

        # ── Auth check ────────────────────────────────────────────
        def auth_check(interaction: discord.Interaction) -> bool:
            if interaction.channel_id != control.channel_id:
                return False
            if control.authorized_user_id and interaction.user.id != control.authorized_user_id:
                return False
            return True

        # ── Slash Commands ────────────────────────────────────────

        @tree.command(name="status", description="Miner durumunu gösterir")
        @app_commands.check(auth_check)
        async def cmd_status(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_status())

        @tree.command(name="points", description="Kanal puanlarını gösterir")
        @app_commands.check(auth_check)
        async def cmd_points(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_points())

        @tree.command(name="online", description="Online yayıncıları gösterir")
        @app_commands.check(auth_check)
        async def cmd_online(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_online())

        @tree.command(name="uptime", description="Çalışma süresini gösterir")
        @app_commands.check(auth_check)
        async def cmd_uptime(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_uptime())

        @tree.command(name="stop", description="Miner'ı durdurur")
        @app_commands.check(auth_check)
        async def cmd_stop(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_stop())

        @tree.command(name="start", description="Miner'ı yeniden başlatır")
        @app_commands.check(auth_check)
        async def cmd_start(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_start())

        @tree.command(name="logs", description="Canlı logları aç/kapat")
        @app_commands.check(auth_check)
        async def cmd_logs(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_logs())

        # ── Bet Group ─────────────────────────────────────────────
        bet_group = app_commands.Group(name="bet", description="Kumar/prediction ayarları")

        @bet_group.command(name="toggle", description="Kumar sistemini aç/kapat")
        @app_commands.check(auth_check)
        async def bet_toggle(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_bet_toggle())

        @bet_group.command(name="status", description="Mevcut kumar ayarlarını göster")
        @app_commands.check(auth_check)
        async def bet_status(interaction: discord.Interaction):
            await interaction.response.send_message(control._cmd_bet_status())

        @bet_group.command(name="set", description="Kumar ayarlarını değiştir")
        @app_commands.describe(
            percentage="Bahis yüzdesi (1-100)",
            max_points="Maksimum bahis puanı",
            min_points="Minimum puan eşiği (altında bahse girmez)",
            strategy="Strateji: smart, percentage, high_odds, most_voted",
            delay="Bahis gecikmesi (saniye)",
        )
        @app_commands.check(auth_check)
        async def bet_set(
            interaction: discord.Interaction,
            percentage: int = None,
            max_points: int = None,
            min_points: int = None,
            strategy: str = None,
            delay: int = None,
        ):
            await interaction.response.send_message(
                control._cmd_bet_set(
                    percentage=percentage,
                    max_points=max_points,
                    min_points=min_points,
                    strategy=strategy,
                    delay=delay,
                )
            )

        tree.add_command(bet_group)

        # ── Account Group ─────────────────────────────────────────
        account_group = app_commands.Group(name="account", description="Hesap yönetimi komutları")

        @account_group.command(name="add", description="Yeni hesap ekle")
        @app_commands.describe(username="Twitch kullanıcı adı", password="Twitch şifresi")
        @app_commands.check(auth_check)
        async def account_add(interaction: discord.Interaction, username: str, password: str):
            result = control._cmd_account(["add", username, password])
            await interaction.response.send_message(result)

        @account_group.command(name="list", description="Kayıtlı hesapları listele")
        @app_commands.check(auth_check)
        async def account_list(interaction: discord.Interaction):
            result = control._cmd_account(["list"])
            await interaction.response.send_message(result)

        @account_group.command(name="remove", description="Hesap sil")
        @app_commands.describe(slot="Silinecek hesabın slot numarası")
        @app_commands.check(auth_check)
        async def account_remove(interaction: discord.Interaction, slot: int):
            result = control._cmd_account(["remove", str(slot)])
            await interaction.response.send_message(result)

        tree.add_command(account_group)

        # ── Channel Group ─────────────────────────────────────────
        channel_group = app_commands.Group(name="channel", description="Kanal yönetimi komutları")

        @channel_group.command(name="add", description="Yeni kanal ekle")
        @app_commands.describe(channel="Twitch kanal adı")
        @app_commands.check(auth_check)
        async def channel_add(interaction: discord.Interaction, channel: str):
            result = control._cmd_channel(["add", channel])
            await interaction.response.send_message(result)

        @channel_group.command(name="remove", description="Kanal sil")
        @app_commands.describe(channel="Twitch kanal adı")
        @app_commands.check(auth_check)
        async def channel_remove(interaction: discord.Interaction, channel: str):
            result = control._cmd_channel(["remove", channel])
            await interaction.response.send_message(result)

        @channel_group.command(name="list", description="Kanalları listele")
        @app_commands.check(auth_check)
        async def channel_list(interaction: discord.Interaction):
            result = control._cmd_channel(["list"])
            await interaction.response.send_message(result)

        tree.add_command(channel_group)

        # ── Error handler ─────────────────────────────────────────
        @tree.error
        async def on_app_command_error(interaction: discord.Interaction, error):
            if isinstance(error, app_commands.CheckFailure):
                return  # Silently ignore unauthorized
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ Hata: {error}")
                else:
                    await interaction.response.send_message(f"❌ Hata: {error}")
            except Exception:
                pass
            logger.error(f"Discord slash command error: {error}")

        # ── Events ────────────────────────────────────────────────
        @self.client.event
        async def on_ready():
            logger.info(f"Discord Control Bot logged in as {self.client.user}")
            # Sync slash commands to all guilds the bot is in
            for guild in self.client.guilds:
                try:
                    tree.copy_global_to(guild=guild)
                    await tree.sync(guild=guild)
                    logger.info(f"Slash commands synced to guild: {guild.name}")
                except Exception as e:
                    logger.error(f"Failed to sync commands to {guild.name}: {e}")

            channel = self.client.get_channel(control.channel_id)
            if channel:
                await channel.send(
                    "✅ Twitch Miner Discord botu başlatıldı!\n"
                    "Slash komutları kullanılabilir: `/status`, `/points`, `/logs` vb."
                )

        # Start log flushing task
        self.loop.create_task(self._log_loop())

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
                        if len(messages) >= 10:
                            break
                    except queue.Empty:
                        break

                if messages:
                    text = "\n".join(messages)
                    if len(text) > 1900:
                        text = text[:1900] + "\n... (truncated)"
                    try:
                        channel = self.client.get_channel(self.channel_id)
                        if channel:
                            await channel.send(text)
                    except Exception as e:
                        print(f"Failed to send log to Discord: {e}")

            if not self.logging_enabled and not self.log_queue.empty():
                try:
                    while not self.log_queue.empty():
                        self.log_queue.get_nowait()
                except Exception:
                    pass

            await asyncio.sleep(2)

    def stop(self):
        if self.client and self.loop:
            try:
                future = asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)
                future.result(timeout=5)
            except Exception as e:
                logger.error(f"Error closing Discord client: {e}")

    def send_sync(self, message):
        """Send a message from a non-async context (e.g. from login callback)."""
        if not self.client or not self.loop:
            return
        async def _send():
            channel = self.client.get_channel(self.channel_id)
            if channel:
                await channel.send(message)
        asyncio.run_coroutine_threadsafe(_send(), self.loop)

    # ── Command Logic ─────────────────────────────────────────────

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
        if self.config_manager:
            self.config_manager.clear_last_command_source()
        os.kill(os.getpid(), signal.SIGTERM)
        return "🔄 Miner yeniden başlatılıyor...\nPM2 otomatik olarak tekrar başlatacak."

    def _cmd_logs(self):
        self.logging_enabled = not self.logging_enabled
        if self.logging_enabled:
            return "📝 **Canlı Loglar açıldı!**\nKonsola düşen veriler buraya akacak."
        return "📝 **Canlı Loglar kapandı!**"

    def _cmd_bet_toggle(self):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."
        new_state = self.config_manager.toggle_predictions()
        if new_state:
            threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
            return (
                "🎲 **Kumar/Prediction sistemi AÇILDI!**\n"
                "Bot artık kanallarda bahislere girecek.\n"
                "🔄 Ayar uygulanması için yeniden başlatılıyor..."
            )
        else:
            threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
            return (
                "🚫 **Kumar/Prediction sistemi KAPATILDI!**\n"
                "Bot sadece izleme puanı ve claim yapacak.\n"
                "🔄 Ayar uygulanması için yeniden başlatılıyor..."
            )

    def _cmd_bet_status(self):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."
        bs = self.config_manager.get_bet_settings()
        enabled = bs.get("enabled", False)
        status_icon = "✅ AÇIK" if enabled else "❌ KAPALI"

        strategy_names = {
            "smart": "🧠 Smart",
            "percentage": "📊 Percentage",
            "high_odds": "📈 High Odds",
            "most_voted": "👥 Most Voted",
        }
        strategy = strategy_names.get(bs.get("strategy", "smart"), bs.get("strategy"))

        return (
            f"🎲 **Kumar Ayarları**\n\n"
            f"Durum: {status_icon}\n"
            f"Strateji: {strategy}\n"
            f"Bahis Yüzdesi: `%{bs.get('percentage', 5)}`\n"
            f"Max Bahis: `{bs.get('max_points', 50000):,}` puan\n"
            f"Min Puan Eşiği: `{bs.get('min_points', 20000):,}` puan\n"
            f"Gecikme: `{bs.get('delay', 6)}` saniye\n\n"
            f"💡 `/bet set` ile ayarları değiştirebilirsin.\n"
            f"💡 `/bet toggle` ile açıp kapatabilirsin."
        )

    def _cmd_bet_set(self, **kwargs):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."

        # Validate strategy
        if kwargs.get("strategy"):
            valid_strategies = ["smart", "percentage", "high_odds", "most_voted"]
            if kwargs["strategy"].lower() not in valid_strategies:
                return f"❌ Geçersiz strateji!\nGeçerli: {', '.join(valid_strategies)}"
            kwargs["strategy"] = kwargs["strategy"].lower()

        # Validate percentage
        if kwargs.get("percentage") is not None:
            if not (1 <= kwargs["percentage"] <= 100):
                return "❌ Yüzde 1-100 arası olmalı."

        result = self.config_manager.update_bet_settings(**kwargs)

        if "✅" in result:
            threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
            result += "\n🔄 Ayar uygulanması için yeniden başlatılıyor..."

        return result

    # ── Account Commands ──────────────────────────────────────────

    def _cmd_account(self, args):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."

        sub = args[0].lower()

        if sub == "add":
            username = args[1]
            password = args[2]
            slot, msg = self.config_manager.add_account(username, password)
            if slot:
                self.config_manager.set_last_command_source("discord")
                threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                return f"{msg}\n🔄 Otomatik yeniden başlatılıyor..."
            return msg

        elif sub == "list":
            accounts = self.config_manager.list_accounts()
            if not accounts:
                return "📭 Kayıtlı hesap yok.\n`/account add` ile ekle."
            active = self.config_manager.get_active_account()
            active_slot = active["slot"] if active else None

            lines = ["👤 **Kayıtlı Hesaplar**\n"]
            for acc in accounts:
                marker = " ⬅️ aktif" if acc["slot"] == active_slot else ""
                lines.append(f"**Slot {acc['slot']}**: `{acc['username']}`{marker}")
            return "\n".join(lines)

        elif sub == "remove":
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

        return "❓ Bilinmeyen alt komut."

    # ── Channel Commands ──────────────────────────────────────────

    def _cmd_channel(self, args):
        if not self.config_manager:
            return "❌ Config yöneticisi bağlı değil."

        sub = args[0].lower()

        if sub == "add":
            channel = args[1].lower().strip()
            msg = self.config_manager.add_channel(channel)
            if "✅" in msg:
                if self.config_manager.has_valid_config() or (self.miner and self.miner.running):
                    threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                    return f"{msg}\n🔄 Otomatik yeniden başlatılıyor..."
                return f"{msg}\n💡 Kanal eklendi. Hesap da ekleyince otomatik başlayacak."
            return msg

        elif sub == "remove":
            channel = args[1].lower().strip()
            msg = self.config_manager.remove_channel(channel)
            if "✅" in msg:
                threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                return f"{msg}\n🔄 Değişiklikler için yeniden başlatılıyor..."
            return msg

        elif sub == "list":
            channels = self.config_manager.list_channels()
            if not channels:
                return "📭 Kayıtlı kanal yok.\n`/channel add` ile ekle."

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

        return "❓ Bilinmeyen alt komut."
