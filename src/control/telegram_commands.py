"""Telegram command handlers for dynamic price configuration."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional, Dict, Tuple

from .. import storage


class TelegramCommandHandler:
    """Handler for Telegram commands that update settings dynamically."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def handle_prices(self) -> str:
        """
        Handle /prices command: list all current reference prices.
        Returns a formatted message suitable for Telegram.
        """
        settings = storage.list_all_settings(self.conn)
        
        if not settings:
            return "📊 No prices configured yet."
        
        lines = ["📊 Current Prices:"]
        for key in sorted(settings.keys()):
            value, ts_utc, actor = settings[key]
            lines.append(f"  • {key}: {value}€ (by {actor})")
        
        return "\n".join(lines)

    def handle_setprice(self, args: list[str], actor: str = "telegram") -> str:
        """
        Handle /setprice <key> <value> command: update a price setting.
        
        Args:
            args: Command arguments (should be [key, value])
            actor: Actor name for audit trail
            
        Returns:
            A response message suitable for Telegram.
        """
        if len(args) < 2:
            return "❌ Usage: /setprice <key> <value>"
        
        key = args[0]
        value = args[1]
        
        # Validate key format (no product-specific logic, just pattern)
        if not self._is_valid_key(key):
            return f"❌ Invalid key format: {key}. Use format like 'product_name/good_price_eur'"
        
        # Try to parse value as float (most prices are floats)
        try:
            float_value = float(value)
            value = str(float_value)
        except ValueError:
            # If not a float, just store as-is (allow arbitrary values)
            pass
        
        try:
            storage.set_setting(self.conn, key=key, value=value, actor=actor)
            return f"✅ Updated: {key} = {value}€"
        except Exception as e:
            return f"❌ Error updating setting: {str(e)}"

    def _is_valid_key(self, key: str) -> bool:
        """
        Validate setting key format.
        No hard-coded product logic, but basic format validation.
        """
        # Allow alphanumeric, underscore, hyphen, forward slash
        import re
        return bool(re.match(r'^[a-zA-Z0-9_\-/]+$', key))

    def parse_and_handle(self, message: str, actor: str = "telegram") -> Optional[str]:
        """
        Parse a Telegram message and handle if it's a command.
        Returns response message or None if not a command.
        """
        message = message.strip()
        
        if not message.startswith('/'):
            return None
        
        parts = message.split()
        command = parts[0]
        args = parts[1:]
        
        if command == '/prices':
            return self.handle_prices()
        elif command == '/setprice':
            return self.handle_setprice(args, actor)
        else:
            return f"❌ Unknown command: {command}"
