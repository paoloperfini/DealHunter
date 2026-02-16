"""Pipeline for handling Telegram bot commands and updating settings dynamically."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from ..control.telegram_commands import TelegramCommandHandler
from ..notifiers.notifiers import get_telegram_updates, send_telegram_message
from ..storage import connect

logger = logging.getLogger(__name__)


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

    logger.debug("tg_cfg=%s", tg_cfg)
    logger.debug("bot_token_len=%s", len(bot_token))
    logger.debug("allowed_chat_id=%s", repr(chat_id))

    if not bot_token or not chat_id:
        logger.warning("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars; commands disabled")
        return

    # Load the state file to get the last processed update_id (offset)
    state_file = cfg["settings"].get("telegram_state_file", "data/.telegram_state.json")
    offset = _load_offset(state_file)
    logger.debug("offset_loaded=%s state_file=%s", offset, state_file)

    # Connect to database
    db_path = cfg["settings"].get("history_db", "data/history.sqlite")
    conn = connect(db_path)

    try:
        # Fetch updates from Telegram
        updates, new_offset = get_telegram_updates(bot_token, offset=offset, timeout=5)
        logger.debug("updates_count=%s new_offset=%s", len(updates), new_offset)

        if updates:
            # Save new offset first (so we don't re-process if we crash)
            _save_offset(state_file, new_offset)
            try:
                logger.debug("first_update=%s", json.dumps(updates[0])[:500])
            except Exception:
                pass

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
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("offset", 0) or 0)
    except Exception:
        pass
    return 0


def _save_offset(state_file: str, offset: int) -> None:
    """Save the current offset to state file."""
    try:
        folder = os.path.dirname(state_file)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"offset": int(offset)}, f)
    except Exception as e:
        logger.warning("Error saving Telegram state: %s", e)


def _process_update(
    update: Dict[str, Any],
    handler: TelegramCommandHandler,
    bot_token: str,
    allowed_chat_id: str,
) -> None:
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

        response = handler.parse_and_handle(text, actor="telegram_user")
        logger.debug("response=%s", repr(response))

        if not response:
            return

        # Reply only to the chat we received the message from,
        # but enforce that it matches the configured allowed chat ID.
        incoming_chat_id = str(message.get("chat", {}).get("id", "") or "")
        if not incoming_chat_id:
            return

        if str(allowed_chat_id) != incoming_chat_id:
            logger.debug("Ignoring command from unauthorized chat_id=%s", incoming_chat_id)
            return

        send_telegram_message(bot_token, incoming_chat_id, response)
        logger.debug("send ok")

    except Exception:
        logger.exception("Error processing Telegram update")
