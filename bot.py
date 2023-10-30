import sys
import re
import atexit
import logging
import requests
import urllib.parse
import urllib.request
import nextcord
from nextcord.ext import commands
import yt_dlp
from decouple import config
from typing import Dict

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

import spotipy.util as util
import tempfile
import os
from nextcord import FFmpegPCMAudio


from classes import ServerSession
from utils import clearCacheFiles, JoinVoiceChannel, findingYTBFromQuery, findYTBFromSpotify


sys.path.append('.')

logging.basicConfig(level=logging.WARNING)

yt_dlp.utils.bug_reports_message = lambda: ''

intents = nextcord.Intents.default()
intents.message_content = True

help_command = commands.DefaultHelpCommand(no_category='Commands')

bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), intents=intents,
                   help_command=help_command, strip_after_prefix=True)

token = config('TOKEN')
CLIENT_ID = config('SPOTIFY_ID')
CLIENT_SECRET = config('SPOTIFY_SECRET')
REDIRECT_URI = "http://localhost:8000/callback"
JOKE_YTB = "https://youtu.be/EMldOiiG1Ko"


ytdl_format_options = {'format': 'bestaudio',
                       'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
                       'restrictfilenames': True,
                       'no-playlist': True,
                       'nocheckcertificate': True,
                       'ignoreerrors': False,
                       'logtostderr': False,
                       'geo-bypass': True,
                       'quiet': True,
                       'no_warnings': True,
                       'default_search': 'auto',
                       'source_address': '0.0.0.0'}
ffmpeg_options = {'options': '-vn -sn'}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


currentServers: Dict[int, ServerSession] = {}


@atexit.register
def cleanup():
    global currentServers
    for vc in currentServers.values():
        vc.disconnect()
        vc.cleanup()
    currentServers = {}
    clearCacheFiles(currentServers)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f'{ctx.author}\'s message "{ctx.message.content}" triggered error:\n{error}')


@bot.command()
async def disconnect(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        session = currentServers[guild_id]
        voice_client = session.voice_client
        await voice_client.disconnect()
        voice_client.cleanup()
        del currentServers[guild_id]
        await ctx.send(f'Disconnected from {voice_client.channel.name}.')


@bot.command()
async def pause(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        voice_client = currentServers[guild_id].voice_client
        if voice_client.is_playing():
            voice_client.pause()
            await ctx.send('Paused')


@bot.command()
async def resume(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        voice_client = currentServers[guild_id].voice_client
        if voice_client.is_paused():
            voice_client.resume()
            await ctx.send('Resumed')


@bot.command()
async def skip(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        session = currentServers[guild_id]
        voice_client = session.voice_client
        if voice_client.is_playing():
            if len(session.queue) > 1:
                await ctx.send(f'Skipping current song, will now play: {currentServers[guild_id].queue[1].title}')
                voice_client.stop()
            else:
                await ctx.send('This is already the last item in the queue!')


@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        await ctx.send(f'{currentServers[guild_id].displayQueue()}')


@bot.command()
async def remove(ctx, i: int):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        if i == 0:
            await ctx.send('Cannot remove the currently playing song. Please use !skip instead.')
        elif i >= len(currentServers[guild_id].queue):
            await ctx.send(f'The queue is not that long. There are only {len(currentServers[guild_id].queue)-1} items in the queue.')
        else:
            removed = currentServers[guild_id].queue.pop(i)
            removed.audio_source.cleanup()
            await ctx.send(f'Removed {removed} from the queue.')


@bot.command()
async def clear(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        session = currentServers[guild_id]
        voice_client = session.voice_client
        session.queue = []
        if voice_client.is_playing():
            voice_client.stop()
        await ctx.send('Queue cleared.')


@bot.command()
async def song(ctx):
    guild_id = ctx.guild.id
    if guild_id in currentServers:
        await ctx.send(f'Now playing: {currentServers[guild_id].queue[0].title}')


@bot.command()
async def play(ctx, *, query: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if guild_id not in currentServers:
            if ctx.author.voice is None:
                await ctx.send(f'You are not connected to any voice channel!')
                return
            else:
                session = await JoinVoiceChannel(ctx, ctx.author.voice.channel, currentServers, ServerSession)
        else:
            session = currentServers[guild_id]
            if session.voice_client.channel != ctx.author.voice.channel:
                await session.voice_client.move_to(ctx.author.voice.channel)
                await ctx.send(f'Connected to {ctx.author.voice.channel}.')

        url = query

        # check if it's spotify, youtube etc
        if ".spotify." in query:
            url = await findYTBFromSpotify(ctx, url)
        elif "soundcloud." in query:
            await ctx.send('Soundcloud not currently supported.')
            url = JOKE_YTB

    await session.addToQueue(ctx, url, bot)
    if not session.voice_client.is_playing() and len(session.queue) <= 1:
        await session.startPlaying(ctx)

clearCacheFiles(currentServers)
bot.run(token)
