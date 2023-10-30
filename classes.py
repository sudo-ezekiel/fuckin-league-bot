from typing import List
import urllib.parse
import urllib.request
import asyncio
import nextcord
import yt_dlp

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


class Source:
    def __init__(self, audio_source: nextcord.AudioSource, metadata):
        self.audio_source: nextcord.AudioSource = audio_source
        self.metadata = metadata
        self.title: str = metadata.get('title', 'Unknown title')
        self.url: str = metadata.get('url', 'Unknown URL')

    def __str__(self):
        return f'{self.title} ({self.url})'


class YTDLSource(Source):
    def __init__(self, audio_source: nextcord.AudioSource, metadata):
        super().__init__(audio_source, metadata)
        # yt-dlp specific key name for original URL
        self.url: str = metadata.get('webpage_url', 'Unknown URL')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in metadata:
            metadata = metadata['entries'][0]
        filename = metadata['url'] if stream else ytdl.prepare_filename(
            metadata)
        return cls(await nextcord.FFmpegOpusAudio.from_probe(filename, **ffmpeg_options), metadata)


class ServerSession:
    def __init__(self, guild_id, voice_client):
        self.guild_id: int = guild_id
        self.voice_client: nextcord.VoiceClient = voice_client
        self.queue: List[Source] = []

    def displayQueue(self) -> str:
        currently_playing = f'Currently playing: 0. {self.queue[0]}'
        return currently_playing + '\n' + '\n'.join([f'{i + 1}. {s}' for i, s in enumerate(self.queue[1:])])

    async def addToQueue(self, ctx, url, bot):
        yt_source = await YTDLSource.from_url(url, loop=bot.loop, stream=False)
        self.queue.append(yt_source)
        if self.voice_client.is_playing():
            async with ctx.typing():
                await ctx.send(f'Added to queue: {yt_source.title}')
            pass

    async def startPlaying(self, ctx):
        async with ctx.typing():
            self.voice_client.play(
                self.queue[0].audio_source, after=lambda e=None: self.afterPlaying(ctx, e))
        await ctx.send(f'Now playing: {self.queue[0].title}')

    async def afterPlaying(self, ctx, error):
        if error:
            raise error
        else:
            if self.queue:
                await self.playNext(ctx)

    async def playNext(self, ctx):
        self.queue.pop(0)
        if self.queue:
            async with ctx.typing():
                await self.voice_client.play(self.queue[0].audio_source, after=lambda e=None: self.afterPlaying(ctx, e))
            await ctx.send(f'Now playing: {self.queue[0].title}')
