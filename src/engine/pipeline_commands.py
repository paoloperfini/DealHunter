"""Pipeline for handling Telegram bot commands and updating settings dynamically."""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

from ..control.telegram_commands import TelegramCommandHandler
from ..notifiers.notifiers import get_telegram_updates, send_telegram_message
from ..storage import connect


def run_once(cfg: Dict[str, Any]) -> None:
    """
    Poll Telegram for updates (commands) and process them.
    Store the update offset in a state file so we don't re-process old updates.
    """
    tg_cfg = cfg.get("notifiers", {}).get("telegram", {})
    
    if not tg_cfg.get("enabled"):
        return
    
    # Get bot token and chat ID from environment
    bot_token = os.environ.get(tg_cfg.get("bot_token_env", ""), "")
    chat_id = os.environ.get(tg_cfg.get("chat_id_env", ""), "")
    
    if not bot_token or not chat_id:
        return
    
    # Load the state file to get the last processed update_id (offset)
    state_file = cfg["settings"].get("telegram_state_file", "data/.telegram_state.json")
    offset = _load_offset(state_file)
    
    # Connect to database
    db_path = cfg["settings"].get("history_db", "data/history.sqlite")
    conn = connect(db_path)
    
    try:
        # Fetch updates from Telegram
        updates, new_offset = get_telegram_updates(bot_token, offset=offset, timeout=5)
        
        if updates:
            # Save new offset first (so we don't re-process if we crash)
            _save_offset(state_file, new_offset)
        
        # Process each update
        handler = TelegramCommandHandler(conn)
        for update in updates:
            _process_update(update, handler, bot_token, chat_id)
    finally:
        conn.close()


def _load_offset(state_file: str) -> int:
    """Load the last processed update_id from state file."""
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                data = json.load(f)
                return data.get("offset", 0)
    except Exception:
        pass
    return 0


def _save_offset(state_file: str, offset: int) -> None:
    """Save the current offset to state file."""
    try:
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        with open(state_file, "w") as f:
            json.dump({"offset": offset}, f)
    except Exception as e:
        print(f"⚠️ Error saving Telegram state: {e}")


def _process_update(update: Dict[str, Any], handler: TelegramCommandHandler, 
                    bot_token: str, chat_id: str) -> None:
    """Process a single Telegram update (message with command)."""
    try:
        # Extract message
        message = update.get("message", {})
        if not message:
            return
        
        # Extract text from message
        text = (message.get("text") or "").strip()
        if not text:
            return
        
        # Try to handle as command
        response = handler.parse_and_handle(text, actor="telegram_user")
        if response:
            # Send response back to Telegram
            send_telegram_message(bot_token, chat_id, response)
    except Exception as e:
        print(f"⚠️ Error processing Telegram update: {e}")
