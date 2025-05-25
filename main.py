import random
import discord
import os
import asyncio
import yt_dlp
from playlist import PlaylistManager
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

    yt_dl_options = {
        "format": "bestaudio/best",
        "noplaylist": True
    }
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'options': '-vn'}

    queues = {}
    playlist_states = {}
    bot.playlist_manager = None


    @bot.event
    async def on_ready():
        print(f'{bot.user} is now online')
        bot.playlist_manager = await PlaylistManager().initialize()


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
            guild_id = ctx.guild.id

            if len(queues.get(guild_id, [])) <= 1:
                asyncio.run_coroutine_threadsafe(
                    load_more_songs(ctx, count=2),
                    bot.loop
                )

            if len(queues[ctx.guild.id]) > 0:
                voice_client = ctx.voice_client

                song = queues[ctx.guild.id].pop(0)
                source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)

                def after(error):
                    if error:
                        print(f"Player error: {error}")
                    else:
                        # Schedule play_next to run again
                        bot.loop.call_soon_threadsafe(lambda: play_next(ctx))
                
                voice_client.play(source, after=after)
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
            
            guild_id = ctx.guild.id
            if guild_id in queues:
                queues[guild_id] = []
            if guild_id in playlist_states:  # NEW: Clean up playlist state
                del playlist_states[guild_id]


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


    @bot.command(name='skip')
    async def skip(ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Skipped to the next song", silent=True)
        else:
            await ctx.send("Nothing is playing to skip", silent=True)


    @bot.group(name='playlist', invoke_without_command=True)
    async def playlist(ctx):
        await ctx.send(
            "Please use a subcommand:\n"
            "?playlist create [name] - Create a new playlist\n"
            "?playlist delete [name] - Delete a playlist\n"
            "?playlist list - Show all playlists\n"
            "?playlist show [name] - Show songs in a playlist\n"
            "?playlist add [name] [url] - Add a song to a playlist\n"
            "?playlist remove [name] [index] - Remove a song from a playlist\n"
            "?playlist play [name] - Play all songs in order\n"
            "?playlist play [name] --random - Play one random song\n"
            "?playlist play [name] --shuffle - Play all songs in random order",
            silent=True
        )


    @playlist.command(name='create')
    async def playlist_create(ctx, *, name):
        """Create a new playlist"""
        # Validate playlist name
        if not name or len(name) > 50 or any(c in name for c in '\\/:*?"<>|'):
            await ctx.send("Invalid playlist name. Please use a name without special characters and less than 50 characters.")
            return

        success = await bot.playlist_manager.create_playlist(name)
        if success:
            await ctx.send(f"Playlist '{name}' created successfully!", silent=True)
        else:
            await ctx.send(f"A playlist named '{name}' already exists!", silent=True)
    

    @playlist.command(name='delete')
    async def playlist_delete(ctx, *, name):
        success = await bot.playlist_manager.delete_playlist(name)
        if success:
            await ctx.send(f"Playlist '{name}' eliminated", silent=True)
        else:
            await ctx.send(f"No playlist named that man...")


    @playlist.command(name='list')
    async def playlist_list(ctx):
        """List all available playlists"""
        playlists = bot.playlist_manager.list_playlists()
        
        if not playlists:
            await ctx.send("No playlists have been created yet.", silent=True)
            return
            
        response = "**Available Playlists:**\n"
        for i, name in enumerate(playlists, 1):
            response += f"{i}. {name}\n"
            
        await ctx.send(response, silent=True)


    @playlist.command(name='show')
    async def playlist_show(ctx, *, name):
        """Show songs in a specific playlist"""
        playlist = bot.playlist_manager.get_playlist(name)
        
        if playlist is None:
            await ctx.send(f"No playlist named '{name}' found!", silent=True)
            return
            
        if not playlist:
            await ctx.send(f"Playlist '{name}' is empty.", silent=True)
            return
            
        response = f"**Songs in Playlist '{name}':**\n"
        for i, song in enumerate(playlist, 1):
            response += f"{i}. {song['title']}\n"
            
        await ctx.send(response, silent=True)


    @playlist.command(name='add')
    async def playlist_add(ctx, playlist_name, url):
        """Add a song to a playlist"""
        # Get minimal song info and add to playlist (no download)
        try:
            
            minimal_options = {
                'quiet': True,
                'extract_flat': True,
                'skip_download': True,
                'noplaylist': True,
                'format': 'none'
            }

            with yt_dlp.YoutubeDL(minimal_options) as minimal_ytdl:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: minimal_ytdl.extract_info(url, download=False, process=False))
            
            song = {
                'title': data.get('title', 'Unknown'),
                'url': url
            }
            
            success = await bot.playlist_manager.add_song_to_playlist(playlist_name, song)
            if success:
                await ctx.send(f"Added '{song['title']}' to playlist '{playlist_name}'", silent=True)
            else:
                await ctx.send(f"Failed to add song. Either the playlist '{playlist_name}' doesn't exist or the song is already in the playlist.", silent=True)
                
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            print(e)


    @playlist.command(name='remove')
    async def playlist_remove(ctx, playlist_name, index: int):
        """Remove a song from a playlist by index (starting from 1)"""
        # Convert from user-friendly index (1-based) to 0-based index
        index = index - 1
        
        success = await bot.playlist_manager.remove_song_from_playlist(playlist_name, index)
        if success:
            await ctx.send(f"Song removed from playlist '{playlist_name}'", silent=True)
        else:
            await ctx.send(f"Failed to remove song. Check that the playlist exists and the index is valid.", silent=True)


    @playlist.command(name='play')
    async def playlist_play(ctx, name, *flags):
        """Play songs from a playlist

        Usage:
        ?playlist play [name]            - Play the entire playlist in order
        ?playlist play [name] --random   - Play one random song from the playlist
        ?playlist play [name] --shuffle  - Play all songs in random order
        """

        random_mode = '--random' in flags
        shuffle_mode = '--shuffle' in flags

        added_count = 0
        
        playlist = bot.playlist_manager.get_playlist(name)

        if playlist is None:
            await ctx.send(f"No playlist named '{name}' found!", silent=True)
            return

        if not playlist:
            await ctx.send(f"Playlist '{name}' is empty.", silent=True)
            return

        # Check if user is in a voice channel
        if ctx.author.voice is None:
            await ctx.send("You must be in a voice channel to use this command.")
            return
            
        voice_channel = ctx.author.voice.channel
        
        # Connect to voice channel if not already connected
        if ctx.voice_client is None:
            await voice_channel.connect()
        elif ctx.voice_client.channel != voice_channel:
            await ctx.voice_client.move_to(voice_channel)
        
        # Initialize queue for this server if it doesn't exist
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []


        songs_to_add = playlist.copy()
        if shuffle_mode:
            random.shuffle(songs_to_add)

        playlist_states[ctx.guild.id] = {
            'remaining_songs': songs_to_add,
            'is_random': random_mode
        }

        songs_to_process = 3 if not random_mode else 1

        for i in range(min(songs_to_process, len(songs_to_add))):
            song = songs_to_add.pop(0)

            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song['url'], download=False))

                queue_entry = {
                    'title': song['title'],
                    'url': data.get('url')
                }
                queues[ctx.guild.id].append(queue_entry)


            except Exception as e:
                print(e)

        playlist_states[ctx.guild.id]['remaining_songs'] = songs_to_add

        if not ctx.voice_client.is_playing():
            play_next(ctx)


    async def load_more_songs(ctx, count=2):
        guild_id = ctx.guild.id

        if guild_id not in playlist_states:
            return 0
        
        state = playlist_states[guild_id]
        loaded_count = 0

        for _ in range(count):
            if state['is_random']:
                remaing = state['remaining_songs']
                if not remaing:
                    break
                song = random.choice(remaing)

            else:
                if not state['remaining_songs']:
                    break # no more songs
                song = state['remaining_songs'].pop(0)

            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song['url'], download=False))

                queue_entry = {
                    'title': song['title'],
                    'url': data.get('url')
                }
                queues[guild_id].append(queue_entry)
                loaded_count += 1

            except Exception as e:
                print(e)
                break

        return loaded_count


    @playlist.command(name='create-from-url')
    async def playlist_create_from_url(ctx, name, url):
        """Create a new playlist from a Youtube playlist URL"""

        if not name or len(name) > 50 or any(c in name for c in '\\/:*?"<>|'):
            print()
            return

        if 'list=' not in url:
            print("not a playlist url")
            return

        success = await bot.playlist_manager.create_playlist(name)
        if not success:
            await ctx.send(f"A playlist named '{name}' already exists!", silent=True)
            return
        
        # Notify user that extraction is starting
        message = await ctx.send(f"Creating playlist '{name}' from YouTube playlist. This may take a while depending on the size of the playlist...", silent=True)

        playlist_options = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'noplaylist': False,
            'format': 'none'
        }

        try:
            with yt_dlp.YoutubeDL(playlist_options) as playlist_ytdl:
                loop = asyncio.get_event_loop()
                playlist_data = await loop.run_in_executor(None, lambda: playlist_ytdl.extract_info(url, download=False))

                if 'entries' not in playlist_data:
                    await message.edit(content=f"Failed to extract playlist data. Please verify the URL")
                    await bot.playlist_manager.delete_playlist(name)
                    return
                
                songs_added = 0
                failed_songs = 0
                entries = list(filter(None, playlist_data['entries']))
                total_songs = len(entries)

                if total_songs == 0:
                    await message.edit(content=f"The YouTube playlist appears to be empty or private. No songs were added.")
                    await bot.playlist_manager.delete_playlist(name)
                    return
                
                await message.edit(content=f"Found {total_songs} songs in the YouTube playlist. Adding to '{name}'...")

                for entry in entries:
                    try:
                        video_id = entry.get('id')
                        if not video_id:
                            failed_songs += 1
                            continue

                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        title = entry.get('title', f"Video {video_id}")

                        song = {
                            'title': title,
                            'url': video_url
                        }

                        success = await bot.playlist_manager.add_song_to_playlist(name, song)
                        if success:
                            songs_added += 1
                        else:
                            failed_songs += 1

                    except Exception as song_error:
                        print(f"Error adding song: {song_error}")
                        failed_songs += 1

                # Final update
                if songs_added > 0:
                    if failed_songs > 0:
                        await message.edit(content=f"Added {songs_added} songs to playlist '{name}'. {failed_songs} songs could not be added (possibly duplicates or errors).")
                    else:
                        await message.edit(content=f"Successfully added all {songs_added} songs to playlist '{name}'!")
                else:
                    await message.edit(content=f"Failed to add any songs to playlist '{name}'. Please check the YouTube playlist.")
                    await bot.playlist_manager.delete_playlist(name)
            

        except Exception as e:
            print(e)
            # Delete the created playlist if an error occurs
            await bot.playlist_manager.delete_playlist(name)  

    bot.run(TOKEN)


if __name__ == "__main__":
    run_bot()