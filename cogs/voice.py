import discord
from discord.ext import commands
import asyncio
from audio.capture import ProcessAudioCaptureService
from audio.source import ProcessAudioSource

class VoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Using hardcoded Firefox exact path as requested
        self.capture_service = ProcessAudioCaptureService(process_identifier=r"C:\Program Files\Mozilla Firefox\firefox.exe")

    @commands.command(name="join")
    async def join(self, ctx):
        """Joins the user's voice channel and starts streaming application audio."""
        if not ctx.author.voice:
            await ctx.send("You are not connected to a voice channel.")
            return

        channel = ctx.author.voice.channel

        # Connect or move to the channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        await ctx.send(f"Joined {channel.name}. Starting continuous audio broadcast from Firefox...")

        # Start background capture process
        self.capture_service.start()

        # Small delay to allow the capture process to start and fill the buffer
        await asyncio.sleep(1)

        # Create AudioSource and play
        audio_source = ProcessAudioSource(self.capture_service.get_audio_queue())
        
        # Stop any existing playback
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

        # Continuously broadcast using event-driven architecture
        ctx.voice_client.play(audio_source, after=lambda e: print(f'Player error: {e}') if e else None)


    @commands.command(name="leave")
    async def leave(self, ctx):
        """Stops the audio and leaves the voice channel."""
        if ctx.voice_client:
            await ctx.send("Stopping broadcast and leaving...")
            
            # Stop playback
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                
            # Stop capture service
            self.capture_service.stop()
            
            # Disconnect
            await ctx.voice_client.disconnect()
        else:
            await ctx.send("I'm not in a voice channel.")

async def setup(bot):
    await bot.add_cog(VoiceCog(bot))
