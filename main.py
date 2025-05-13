import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
from discord.ext import commands


def run_bot():
    # loads .env into memory 
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    # setup bot with command prefix
    intents = discord.Intents.default()
    intents.message_content = True
    # client = discord.Client(intents=intents)
    bot = commands.Bot(command_prefix='?', intents=intents)

    voice_clients = {}
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'options': '-vn'}

    queues = {}


    @bot.event
    async def on_ready():
        print(f'{bot.user} is now online')


    @bot.command(name='play')
    async def on_message(ctx, url):
        if ctx.author.voice is None:
            await ctx.send("You must be in a voice channel to use this command", silent=True)
            return
        
        # context = ctx
        voice_channel = ctx.author.voice.channel

        # connect to voice channel if not connected 
        # moves bot to current channel if it's not in one or 
        # moves bot from current channel to users channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        elif ctx.voice_client.channel != voice_channel:
            await ctx.voice_client.move_to(voice_channel)

        # Add song to queue
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            song = {
                'title': data.get('title', 'Unknown'),
                'url':data.get('url')
            }

            queues[ctx.guild.id].append(song)
            # await ctx.send(f"Added to queue: {song['title']}", silent=True)

            if not ctx.voice_client.is_playing():
                play_next(ctx)
            
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", silent=True)
            print(e)


    def play_next(ctx):
            if len(queues[ctx.guild.id]) > 0:
                voice_client = ctx.voice_client

                song = queues[ctx.guild.id].pop(0)
                source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)

                def song_end(error):
                    if error:
                        print(f"Player error: {error}")
                    else:
                        asyncio.run_coroutine_threadsafe(
                            bot.loop
                        )
                        play_next(ctx)
                
                voice_client.play(source, after=song_end)
                asyncio.run_coroutine_threadsafe(
                    ctx.send(f"Now playing: {song['title']}", silent=True),
                    bot.loop
                )


    @bot.command(name='pause')
    async def pause(ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            # await ctx.send("Playback paused.", silent=True)
        else:
            await ctx.send("Nothing is playing right now... dumbass", silent=True)


    @bot.command(name='leave')
    async def leave(ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            
            if ctx.guild.id in queues:
                queues[ctx.guild.id] = []


    @bot.command(name='resume')
    async def resume(ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            # await ctx.send("Playback resumed.")
        else:
            await ctx.send("Nothing is paused right now.", silent=True)
            

    @bot.command(name='queue')
    async def queue(ctx):
        pass

    @bot.command(name='skip ')
    async def skip(ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Skipped to the next song", silent=True)
        else:
            await ctx.send("Nothing is playing to skip", silent=True)

    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot()