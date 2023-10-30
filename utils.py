import os
import sys
import time
import urllib.parse
import urllib.request
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

CLIENT_ID = config('SPOTIFY_ID')
CLIENT_SECRET = config('SPOTIFY_SECRET')


def clearCacheFiles(currentServers):
    if not currentServers:
        for file in os.listdir():
            if os.path.splitext(file)[1] in ['.webm', '.mp4', '.m4a', '.mp3', '.ogg'] and time.time() - os.path.getmtime(file) > 7200:
                os.remove(file)


def get_res_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    if os.path.isfile(os.path.join(base_path, relative_path)):
        return os.path.join(base_path, relative_path)
    else:
        raise FileNotFoundError(
            f'Embedded file {os.path.join(base_path, relative_path)} is not found!')


async def JoinVoiceChannel(ctx, channel, currentServers, ServerSession):
    voice_client = await channel.connect()
    if voice_client.is_connected():
        currentServers[ctx.guild.id] = ServerSession(
            ctx.guild.id, voice_client)
        await ctx.send(f'Connected to {voice_client.channel.name}.')
        return currentServers[ctx.guild.id]
    else:
        await ctx.send(f'Failed to connect to voice channel {ctx.author.voice.channel.name}.')


async def findingYTBFromQuery(query):
    query_string = urllib.parse.urlencode({"search_query": query})
    formatUrl = urllib.request.urlopen(
        "https://www.youtube.com/results?" + query_string)
    search_results = re.findall(
        r"watch\?v=(\S{11})", formatUrl.read().decode())
    url = f'https://www.youtube.com/watch?v={search_results[0]}'
    return url


async def findYTBFromSpotify(ctx, spotify_link):
    # Spotify API credentials
    # moved

    # Initialize Spotipy client
    client_credentials_manager = SpotifyClientCredentials(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    try:
        # Get track information from Spotify API
        track_id = spotify_link.split('/')[-1]
        track_id = spotify_link.split('?')[0]

        # Get track information
        track_info = sp.track(track_id)

        # Get track name and artists
        track_name = track_info['name']
        track_artists = [artist['name'] for artist in track_info['artists']]
        query = f"{track_name} {', '.join(track_artists)}"

        return query
    except spotipy.exceptions.SpotifyException:
        await ctx.send("Invalid Spotify link or unable to fetch track information.")
