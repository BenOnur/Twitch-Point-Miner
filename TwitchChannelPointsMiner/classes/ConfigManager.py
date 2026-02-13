# -*- coding: utf-8 -*-

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(Path().absolute(), "config.json")

DEFAULT_CONFIG = {
    "accounts": [],
    "channels": [],
    "active_account": None,
}


class ConfigManager:
    """Thread-safe persistent JSON configuration manager for accounts and channels."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or CONFIG_FILE
        self.lock = threading.Lock()
        self.config = self._load()

    def _load(self) -> dict:
        """Load config from file or create default."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Config loaded from {self.config_path}")
                # Merge with defaults for missing keys
                for key, value in DEFAULT_CONFIG.items():
                    if key not in data:
                        data[key] = value
                return data
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                return dict(DEFAULT_CONFIG)
        else:
            logger.info("No config found, creating default config.")
            self._save(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)

    def _save(self, data: dict = None):
        """Save config to file."""
        if data is None:
            data = self.config
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    # ── Account Management ──────────────────────────────────────

    def add_account(self, username: str, password: str) -> tuple:
        """Add a Twitch account. Returns (slot, message)."""
        with self.lock:
            # Check duplicate
            for acc in self.config["accounts"]:
                if acc["username"].lower() == username.lower():
                    return (None, f"'{username}' zaten ekli (Slot {acc['slot']}).")

            # Find next slot
            existing_slots = [a["slot"] for a in self.config["accounts"]]
            slot = 1
            while slot in existing_slots:
                slot += 1

            account = {
                "slot": slot,
                "username": username,
                "password": password,
            }
            self.config["accounts"].append(account)

            # Auto-set active if first account
            if self.config["active_account"] is None:
                self.config["active_account"] = slot

            self._save()
            return (slot, f"✅ Hesap eklendi: '{username}' (Slot {slot})")

    def remove_account(self, slot: int) -> str:
        """Remove account by slot number."""
        with self.lock:
            for i, acc in enumerate(self.config["accounts"]):
                if acc["slot"] == slot:
                    removed = self.config["accounts"].pop(i)
                    # Reset active if removed was active
                    if self.config["active_account"] == slot:
                        if self.config["accounts"]:
                            self.config["active_account"] = self.config["accounts"][0]["slot"]
                        else:
                            self.config["active_account"] = None
                    self._save()
                    return f"✅ Hesap silindi: '{removed['username']}' (Slot {slot})"
            return f"❌ Slot {slot} bulunamadı."

    def list_accounts(self) -> list:
        """Return list of accounts."""
        with self.lock:
            return list(self.config["accounts"])

    def get_active_account(self) -> dict:
        """Get the active account."""
        with self.lock:
            if self.config["active_account"] is None:
                return None
            for acc in self.config["accounts"]:
                if acc["slot"] == self.config["active_account"]:
                    return dict(acc)
            return None

    def set_active_account(self, slot: int) -> str:
        """Set active account by slot."""
        with self.lock:
            for acc in self.config["accounts"]:
                if acc["slot"] == slot:
                    self.config["active_account"] = slot
                    self._save()
                    return f"✅ Aktif hesap: '{acc['username']}' (Slot {slot})"
            return f"❌ Slot {slot} bulunamadı."

    # ── Channel Management ──────────────────────────────────────

    def add_channel(self, channel: str) -> str:
        """Add a channel to mine."""
        channel = channel.lower().strip()
        with self.lock:
            if channel in self.config["channels"]:
                return f"⚠️ '{channel}' zaten listede."
            self.config["channels"].append(channel)
            self._save()
            return f"✅ Kanal eklendi: '{channel}'"

    def remove_channel(self, channel: str) -> str:
        """Remove a channel from mining."""
        channel = channel.lower().strip()
        with self.lock:
            if channel in self.config["channels"]:
                self.config["channels"].remove(channel)
                self._save()
                return f"✅ Kanal kaldırıldı: '{channel}'"
            return f"❌ '{channel}' listede bulunamadı."

    def list_channels(self) -> list:
        """Return list of channels."""
        with self.lock:
            return list(self.config["channels"])

    def has_valid_config(self) -> bool:
        """Check if there's at least one account and one channel."""
        with self.lock:
            return (
                len(self.config["accounts"]) > 0
                and len(self.config["channels"]) > 0
                and self.config["active_account"] is not None
            )
