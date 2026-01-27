#!/usr/bin/env python3
"""
Test script to verify Telegram notifications are working.
"""

import os
import sys
from pathlib import Path

# Add root directory to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from notifiers import TelegramNotifier
from utils import load_config


def main():
    """Test Telegram notification."""
    print("🧪 Testing Telegram Notification")
    print("=" * 60)

    # Load config
    config = load_config('config/config.yaml')
    telegram_config = config.get('telegram', {})

    print(f"Telegram enabled: {telegram_config.get('enabled')}")
    print(f"Bot token set: {'Yes' if telegram_config.get('bot_token') else 'No'}")
    print(f"Chat IDs: {telegram_config.get('chat_ids')}")
    print()

    # Initialize notifier
    notifier = TelegramNotifier(telegram_config)

    if not notifier.enabled:
        print("❌ Telegram notifier is disabled!")
        return

    # Send test message
    print("📤 Sending test message...")
    try:
        success = notifier.send_test_message()

        if success:
            print("✅ Test notification sent successfully!")
            print("📱 Check your Telegram app")
        else:
            print("❌ Failed to send test notification")
            print("Check your bot token and chat IDs in Render environment variables")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nPlease verify:")
        print("1. TELEGRAM_BOT_TOKEN is correct in Render environment")
        print("2. TELEGRAM_CHAT_IDS contains your chat ID")
        print("3. You've sent /start to your bot in Telegram")


if __name__ == "__main__":
    main()
