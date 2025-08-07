#!/usr/bin/env python3
import asyncio
import signal
import sys
from typing import Optional

from application.bot.discord_client import DiscordMinutesBot
from infrastructure.config.settings import EnvironmentConfig
from framework.error_code.errors import DetailedError, ErrorCode


async def main() -> None:
    """Main entry point for Discord Minutes Bot"""
    bot: Optional[DiscordMinutesBot] = None
    
    try:
        # Initialize configuration
        config = EnvironmentConfig()
        
        # Validate required environment variables
        required_vars = ['DISCORD_BOT_TOKEN', 'REDIS_URL', 'OPENAI_API_KEY', 'VIBE_URL']
        missing_vars = []
        
        for var in required_vars:
            if not config.get_config(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set the following environment variables:")
            for var in missing_vars:
                print(f"  export {var}=your_value_here")
            sys.exit(1)
        
        # Initialize and start bot
        print("🤖 Starting Discord Minutes Bot...")
        bot = DiscordMinutesBot(config)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}, shutting down gracefully...")
            asyncio.create_task(shutdown(bot))
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the bot
        await bot.start_bot()
        
    except DetailedError as e:
        print(f"❌ Configuration error: {e.message}")
        if e.context:
            print(f"   Context: {e.context}")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Unexpected error starting bot: {str(e)}")
        sys.exit(1)
    
    finally:
        if bot:
            await shutdown(bot)


async def shutdown(bot: Optional[DiscordMinutesBot]) -> None:
    """Graceful shutdown procedure"""
    if not bot:
        return
    
    try:
        print("🔄 Shutting down bot...")
        
        # Stop all active recordings
        for channel_id, recorder in list(bot.recorders.items()):
            print(f"  📱 Stopping recording for channel {channel_id}")
            await recorder.stop()
            if recorder.voice_client and recorder.voice_client.is_connected():
                await recorder.voice_client.disconnect()
        
        # Close bot connection
        if not bot.is_closed():
            await bot.close()
        
        print("✅ Bot shutdown complete")
        
    except Exception as e:
        print(f"⚠️  Error during shutdown: {str(e)}")
    
    # Force exit
    sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)