# -*- coding: utf-8 -*-

import logging
import os
import signal
import threading
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class TelegramControl(threading.Thread):
    """Telegram bot that listens for commands to control the Twitch Miner."""

    def __init__(self, token: str, chat_id: int, miner=None, config_manager=None):
        super().__init__()
        self.daemon = True
        self.name = "TelegramControl Thread"

        self.token = token
        self.chat_id = int(chat_id)
        self.miner = miner
        self.config_manager = config_manager
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
        self.running = False

    def run(self):
        """Main polling loop."""
        self.running = True
        logger.info("Telegram Control Bot started! Listening for commands...")
        self.send_message("✅ Twitch Miner Telegram kontrol botu başlatıldı!\n/help yazarak komutları görebilirsin.")

        # Flush old messages first
        self._flush_pending_updates()

        while self.running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._handle_update(update)
            except Exception as e:
                logger.error(f"Telegram Control polling error: {e}")
            time.sleep(2)

    def stop(self):
        self.running = False

    def _flush_pending_updates(self):
        try:
            resp = requests.get(
                f"{self.base_url}/getUpdates",
                params={"timeout": 0, "offset": -1},
                timeout=10,
            )
            data = resp.json()
            if data.get("ok") and data.get("result"):
                self.last_update_id = data["result"][-1]["update_id"] + 1
        except Exception:
            pass

    def _get_updates(self):
        try:
            resp = requests.get(
                f"{self.base_url}/getUpdates",
                params={"timeout": 30, "offset": self.last_update_id},
                timeout=35,
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("result", [])
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            logger.debug(f"Telegram getUpdates error: {e}")
        return []

    def _handle_update(self, update):
        self.last_update_id = update["update_id"] + 1

        message = update.get("message")
        if not message:
            return

        from_chat_id = message.get("chat", {}).get("id")
        if from_chat_id != self.chat_id:
            logger.warning(f"Unauthorized Telegram access from chat_id: {from_chat_id}")
            return

        text = message.get("text", "").strip()
        if not text or not text.startswith("/"):
            return

        parts = text.split()
        cmd = parts[0].split("@")[0].lower()
        args = parts[1:]

        try:
            self._dispatch(cmd, args)
        except Exception as e:
            self.send_message(f"❌ Hata: {e}")
            logger.error(f"Telegram command error ({cmd}): {e}")

    def _dispatch(self, cmd, args):
        # Simple commands
        simple = {
            "/status": self._cmd_status,
            "/points": self._cmd_points,
            "/online": self._cmd_online,
            "/uptime": self._cmd_uptime,
            "/stop": self._cmd_stop,
            "/start": self._cmd_start,
            "/help": self._cmd_help,
        }

        if cmd in simple:
            simple[cmd]()
            return

        # Compound commands: /account, /channel
        if cmd == "/account":
            self._cmd_account(args)
            return
        if cmd == "/channel":
            self._cmd_channel(args)
            return

        self.send_message(f"❓ Bilinmeyen komut: {cmd}\n/help yazarak komutları görebilirsin.")

    def send_message(self, text: str):
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                data={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Telegram send error: {e}")

    # ── Simple Commands ─────────────────────────────────────────

    def _cmd_help(self):
        msg = (
            "🎮 <b>Twitch Miner Kontrol Komutları</b>\n\n"
            "<b>Genel:</b>\n"
            "/status - Miner durumu\n"
            "/points - Kanal puanları\n"
            "/online - Online yayıncılar\n"
            "/uptime - Çalışma süresi\n"
            "/stop - Miner'ı durdur\n"
            "/start - Miner'ı yeniden başlat\n\n"
            "<b>Hesap Yönetimi:</b>\n"
            "/account add &lt;kullanıcı&gt; &lt;şifre&gt;\n"
            "/account list\n"
            "/account remove &lt;slot&gt;\n\n"
            "<b>Kanal Yönetimi:</b>\n"
            "/channel add &lt;kanal&gt;\n"
            "/channel remove &lt;kanal&gt;\n"
            "/channel list\n\n"
            "/help - Bu mesaj"
        )
        self.send_message(msg)

    def _cmd_status(self):
        if not self.miner or not self.miner.running:
            active = self.config_manager.get_active_account() if self.config_manager else None
            channels = self.config_manager.list_channels() if self.config_manager else []
            status = "🛑 Durdu"
            msg = f"📊 <b>Miner Durumu</b>\n\nDurum: {status}\n"
            if active:
                msg += f"Aktif hesap: <code>{active['username']}</code>\n"
            msg += f"Kayıtlı kanal: {len(channels)}"
            self.send_message(msg)
            return

        total = len(self.miner.streamers)
        online = sum(1 for s in self.miner.streamers if s.is_online)

        msg = (
            f"📊 <b>Miner Durumu</b>\n\n"
            f"Durum: ✅ Çalışıyor\n"
            f"Kullanıcı: <code>{self.miner.username}</code>\n"
            f"Toplam yayıncı: {total}\n"
            f"Online: {online}\n"
            f"Session: <code>{self.miner.session_id[:8]}...</code>"
        )
        self.send_message(msg)

    def _cmd_points(self):
        if not self.miner or not self.miner.streamers:
            self.send_message("📭 Aktif miner veya yayıncı yok.")
            return

        lines = ["💰 <b>Kanal Puanları</b>\n"]
        for s in self.miner.streamers:
            status = "🟢" if s.is_online else "🔴"
            points = f"{s.channel_points:,}" if s.channel_points else "?"
            lines.append(f"{status} <b>{s.username}</b>: {points}")

        self.send_message("\n".join(lines))

    def _cmd_online(self):
        if not self.miner or not self.miner.streamers:
            self.send_message("📭 Aktif miner veya yayıncı yok.")
            return

        online_streamers = [s for s in self.miner.streamers if s.is_online]
        if not online_streamers:
            self.send_message("📭 Şu an online yayıncı yok.")
            return

        lines = [f"🟢 <b>Online Yayıncılar ({len(online_streamers)})</b>\n"]
        for s in online_streamers:
            points = f"{s.channel_points:,}" if s.channel_points else "?"
            lines.append(f"• <b>{s.username}</b> — {points} puan")

        self.send_message("\n".join(lines))

    def _cmd_uptime(self):
        if not self.miner or not self.miner.start_datetime:
            self.send_message("❌ Miner çalışmıyor.")
            return

        uptime = datetime.now() - self.miner.start_datetime
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        self.send_message(
            f"⏱ <b>Çalışma Süresi</b>\n"
            f"{hours} saat, {minutes} dakika, {seconds} saniye"
        )

    def _cmd_stop(self):
        if not self.miner or not self.miner.running:
            self.send_message("⚠️ Miner zaten durmuş.")
            return
        self.send_message("🛑 Miner durduruluyor...")
        os.kill(os.getpid(), signal.SIGTERM)

    def _cmd_start(self):
        # Kaynak kaydını temizle - manuel start her zaman geneldir veya kayıt gerekmez
        # Ancak 2FA beklentisi varsa manuel startta kaynak belirtilebilir.
        # Kullanıcı isteği: "account add komutu kimden girildiyse onu takip et"
        # Bu yüzden manuel start'ta kaynak belirtmiyoruz veya var olanı koruyoruz.
        if self.config_manager:
            # Manuel start'ta kaynağı temizleyelim ki yanlış yere gitmesin
            self.config_manager.clear_last_command_source()

        self.send_message(
            "🔄 Miner yeniden başlatılıyor...\n"
            "PM2 otomatik olarak tekrar başlatacak."
        )
        os.kill(os.getpid(), signal.SIGTERM)

    # ── Account Commands ────────────────────────────────────────

    def _cmd_account(self, args):
        if not self.config_manager:
            self.send_message("❌ Config yöneticisi bağlı değil.")
            return

        if not args:
            self.send_message("Kullanım:\n/account add &lt;kullanıcı&gt; &lt;şifre&gt;\n/account list\n/account remove &lt;slot&gt;")
            return

        sub = args[0].lower()

        if sub == "add":
            if len(args) < 3:
                self.send_message("Kullanım: /account add <kullanıcı> <şifre>")
                return
            username = args[1]
            password = args[2]
            slot, msg = self.config_manager.add_account(username, password)
            self.send_message(msg)
            if slot:
                self.send_message("🔄 Otomatik yeniden başlatılıyor...")
                # Kaynağı kaydet ki 2FA kodu buraya gelsin
                self.config_manager.set_last_command_source("telegram")
                os.kill(os.getpid(), signal.SIGTERM)

        elif sub == "list":
            accounts = self.config_manager.list_accounts()
            if not accounts:
                self.send_message("📭 Kayıtlı hesap yok.\n/account add &lt;kullanıcı&gt; &lt;şifre&gt; ile ekle.")
                return
            active = self.config_manager.get_active_account()
            active_slot = active["slot"] if active else None

            lines = ["👤 <b>Kayıtlı Hesaplar</b>\n"]
            for acc in accounts:
                marker = " ⬅️ aktif" if acc["slot"] == active_slot else ""
                lines.append(f"<b>Slot {acc['slot']}</b>: <code>{acc['username']}</code>{marker}")
            self.send_message("\n".join(lines))

        elif sub == "remove":
            if len(args) < 2:
                self.send_message("Kullanım: /account remove &lt;slot&gt;")
                return
            try:
                slot = int(args[1])
            except ValueError:
                self.send_message("❌ Slot numarası sayı olmalı.")
                return
            msg = self.config_manager.remove_account(slot)
            self.send_message(msg)
            if "✅" in msg:
                self.send_message("🔄 Değişiklikler için yeniden başlatılıyor...")
                self.config_manager.clear_last_command_source()
                os.kill(os.getpid(), signal.SIGTERM)

        else:
            self.send_message("Kullanım:\n/account add &lt;kullanıcı&gt; &lt;şifre&gt;\n/account list\n/account remove &lt;slot&gt;")

    # ── Channel Commands ────────────────────────────────────────

    def _cmd_channel(self, args):
        if not self.config_manager:
            self.send_message("❌ Config yöneticisi bağlı değil.")
            return

        if not args:
            self.send_message("Kullanım:\n/channel add &lt;kanal&gt;\n/channel remove &lt;kanal&gt;\n/channel list")
            return

        sub = args[0].lower()

        if sub == "add":
            if len(args) < 2:
                self.send_message("Kullanım: /channel add &lt;kanal&gt;")
                return
            channel = args[1].lower().strip()
            msg = self.config_manager.add_channel(channel)
            self.send_message(msg)
            if "✅" in msg:
                # Kanal ekleyince de restart atalım (özellikle ilk kurulumda önemli)
                if self.config_manager.has_valid_config() or (self.miner and self.miner.running):
                    self.send_message("🔄 Otomatik yeniden başlatılıyor...")
                    # Kanal ekleme genellikle 2FA gerektirmez ama tutarlılık için kaynak belirtilebilir
                    # self.config_manager.set_last_command_source("telegram")
                    os.kill(os.getpid(), signal.SIGTERM)
                else:
                    self.send_message("💡 Kanal eklendi. Hesap da ekleyince otomatik başlayacak.")

        elif sub == "remove":
            if len(args) < 2:
                self.send_message("Kullanım: /channel remove &lt;kanal&gt;")
                return
            channel = args[1].lower().strip()
            msg = self.config_manager.remove_channel(channel)
            self.send_message(msg)
            if "✅" in msg:
                self.send_message("🔄 Değişiklikler için yeniden başlatılıyor...")
                os.kill(os.getpid(), signal.SIGTERM)

        elif sub == "list":
            channels = self.config_manager.list_channels()
            if not channels:
                self.send_message("📭 Kayıtlı kanal yok.\n/channel add &lt;kanal&gt; ile ekle.")
                return

            lines = [f"📺 <b>Mining Kanalları ({len(channels)})</b>\n"]

            # If miner is running, show online status
            if self.miner and self.miner.streamers:
                online_names = {s.username.lower() for s in self.miner.streamers if s.is_online}
                for ch in channels:
                    status = "🟢" if ch.lower() in online_names else "🔴"
                    lines.append(f"{status} {ch}")
            else:
                for ch in channels:
                    lines.append(f"• {ch}")

            self.send_message("\n".join(lines))

        else:
            self.send_message("Kullanım:\n/channel add &lt;kanal&gt;\n/channel remove &lt;kanal&gt;\n/channel list")
