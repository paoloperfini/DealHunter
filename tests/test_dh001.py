"""Unit tests for DH-001: Telegram price management feature."""
import sys
import tempfile
from pathlib import Path
import sqlite3
from datetime import datetime

# Setup path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src import storage
from src.control.telegram_commands import TelegramCommandHandler


class TestStorageSettings:
    """Test settings table functionality in storage."""
    
    def test_settings_table_created(self):
        """Verify settings table is created during database connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            # Check if settings table exists
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
            )
            assert cursor.fetchone() is not None, "settings table not created"
            conn.close()
    
    def test_set_and_get_setting(self):
        """Test setting and retrieving a value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            # Set a value
            storage.set_setting(conn, key="test_key", value="100.50", actor="test_user")
            
            # Get the value back
            value = storage.get_setting(conn, "test_key")
            assert value == "100.50"
            conn.close()
    
    def test_set_setting_overwrites_existing(self):
        """Test that setting a key overwrites the previous value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            storage.set_setting(conn, key="key1", value="old_value", actor="actor1")
            storage.set_setting(conn, key="key1", value="new_value", actor="actor2")
            
            value = storage.get_setting(conn, "key1")
            assert value == "new_value"
            conn.close()
    
    def test_get_nonexistent_setting(self):
        """Test that getting a non-existent setting returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            value = storage.get_setting(conn, "nonexistent")
            assert value is None
            conn.close()
    
    def test_list_all_settings(self):
        """Test listing all settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            storage.set_setting(conn, key="key1", value="value1", actor="actor1")
            storage.set_setting(conn, key="key2", value="value2", actor="actor2")
            
            settings = storage.list_all_settings(conn)
            
            assert len(settings) == 2
            assert settings["key1"][0] == "value1"
            assert settings["key2"][0] == "value2"
            assert settings["key1"][2] == "actor1"
            assert settings["key2"][2] == "actor2"
            conn.close()
    
    def test_setting_includes_timestamp_and_actor(self):
        """Test that settings include timestamp and actor information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            before = datetime.utcnow().isoformat()
            storage.set_setting(conn, key="audit_test", value="123", actor="test_actor")
            after = datetime.utcnow().isoformat()
            
            settings = storage.list_all_settings(conn)
            value, ts_utc, actor = settings["audit_test"]
            
            assert value == "123"
            assert actor == "test_actor"
            assert before <= ts_utc <= after
            conn.close()


class TestTelegramCommandHandler:
    """Test Telegram command handling."""
    
    def test_prices_empty_database(self):
        """Test /prices command when no settings exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.handle_prices()
            
            assert "📊 No prices configured yet" in response
            conn.close()
    
    def test_prices_lists_settings(self):
        """Test /prices command lists all settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            storage.set_setting(conn, key="rtx_5090/good", value="3500", actor="admin")
            storage.set_setting(conn, key="cpu_9800x3d/good", value="400", actor="admin")
            
            handler = TelegramCommandHandler(conn)
            response = handler.handle_prices()
            
            assert "cpu_9800x3d/good: 400€" in response
            assert "rtx_5090/good: 3500€" in response
            assert "by admin" in response
            conn.close()
    
    def test_setprice_valid_input(self):
        """Test /setprice command with valid input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.handle_setprice(["test_key", "250"], actor="user1")
            
            assert "✅ Updated" in response
            assert "test_key = 250€" in response
            
            # Verify it was actually set
            value = storage.get_setting(conn, "test_key")
            assert value is not None
            conn.close()
    
    def test_setprice_insufficient_args(self):
        """Test /setprice command with insufficient arguments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.handle_setprice([], actor="user1")
            
            assert "❌ Usage" in response
            conn.close()
    
    def test_setprice_float_values(self):
        """Test /setprice command with float values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.handle_setprice(["price_key", "199.99"], actor="user1")
            
            assert "✅ Updated" in response
            value = storage.get_setting(conn, "price_key")
            assert value == "199.99"
            conn.close()
    
    def test_setprice_invalid_key(self):
        """Test /setprice command with invalid key format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.handle_setprice(["invalid@key!", "100"], actor="user1")
            
            assert "❌ Invalid key format" in response
            conn.close()
    
    def test_setprice_valid_key_patterns(self):
        """Test /setprice accepts valid key patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            
            # Test allowed patterns: alphanumeric, underscore, hyphen, forward slash
            valid_keys = [
                "product_name/good_price",
                "RTX-5090",
                "price_eur_123",
                "item/subitem/price"
            ]
            
            for key in valid_keys:
                response = handler.handle_setprice([key, "100"], actor="user1")
                assert "✅ Updated" in response, f"Should accept key: {key}"
            
            conn.close()
    
    def test_parse_and_handle_prices_command(self):
        """Test parsing and handling /prices command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.parse_and_handle("/prices", actor="user1")
            
            assert response is not None
            assert "📊" in response
            conn.close()
    
    def test_parse_and_handle_setprice_command(self):
        """Test parsing and handling /setprice command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.parse_and_handle("/setprice mykey 500", actor="user1")
            
            assert response is not None
            assert "✅ Updated" in response
            conn.close()
    
    def test_parse_and_handle_non_command(self):
        """Test that non-command messages return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.parse_and_handle("This is just a message", actor="user1")
            
            assert response is None
            conn.close()
    
    def test_parse_and_handle_unknown_command(self):
        """Test handling of unknown commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            conn = storage.connect(db_path)
            
            handler = TelegramCommandHandler(conn)
            response = handler.parse_and_handle("/unknown_command", actor="user1")
            
            assert response is not None
            assert "❌ Unknown command" in response
            conn.close()


if __name__ == "__main__":
    # Run tests manually
    test_storage = TestStorageSettings()
    test_storage.test_settings_table_created()
    test_storage.test_set_and_get_setting()
    test_storage.test_set_setting_overwrites_existing()
    test_storage.test_get_nonexistent_setting()
    test_storage.test_list_all_settings()
    test_storage.test_setting_includes_timestamp_and_actor()
    print("✅ All storage tests passed!")
    
    test_commands = TestTelegramCommandHandler()
    test_commands.test_prices_empty_database()
    test_commands.test_prices_lists_settings()
    test_commands.test_setprice_valid_input()
    test_commands.test_setprice_insufficient_args()
    test_commands.test_setprice_float_values()
    test_commands.test_setprice_invalid_key()
    test_commands.test_setprice_valid_key_patterns()
    test_commands.test_parse_and_handle_prices_command()
    test_commands.test_parse_and_handle_setprice_command()
    test_commands.test_parse_and_handle_non_command()
    test_commands.test_parse_and_handle_unknown_command()
    print("✅ All command handler tests passed!")
    
    print("\n✅✅✅ All DH-001 tests passed! ✅✅✅")
