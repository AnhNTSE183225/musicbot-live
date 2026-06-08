import os
import asyncio
from dotenv import load_dotenv
from core.bot import MusicBot

def main():
    # Load environment variables
    load_dotenv()
    
    token = os.getenv("DISCORD_TOKEN")
    if not token or token == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file.")
        return

    # Initialize bot
    bot = MusicBot()
    
    # Run the bot
    bot.run(token)

if __name__ == "__main__":
    # Ensure Windows multiprocessing compatibility
    import multiprocessing
    multiprocessing.freeze_support()
    main()
