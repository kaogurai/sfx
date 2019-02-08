from redbot.core import commands, checks, Config
import tempfile
import gtts
import discord
import asyncio
import os
import random
import lavalink
import pydub

class SFX(commands.Cog):
    """Play uploaded sounds or text-to-speech using gTTS"""

    def __init__(self):
        self.tts_languages = list(gtts.lang.tts_langs().keys())
        self.last_track_info = None
        self.current_tts = None
        self.config = Config.get_conf(self, identifier=134621854878007296)
        default_config = {
            'tts': {
                'lang': 'en',
                'padding': 700
            }
        }
        self.config.register_guild(**default_config)
        lavalink.register_event_listener(self.ll_check)


    def __unload(self):
        lavalink.unregister_event_listener(self.ll_check)


    @commands.command(usage='[language code] <text>')
    async def tts(self, ctx, *, text):
        """
        Text-to-speech

        Turns a string of text into audio using the server's default language, if none is specified.
        Use `[p]ttslangs` for a list of valid language codes.
        """

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(f'You must be in a voice channel to use `{ctx.prefix}tts`.')
            return

        tts_config = await self.config.guild(ctx.guild).tts()
        lang = tts_config['lang']
        try:
            lang, text = text.split(' ', maxsplit=1)
            if lang not in self.tts_languages:
                lang = tts_config['lang']
                text = f'{lang} {text}'
        except ValueError:
            pass

        tts_audio = gtts.gTTS(text, lang=lang)
        audio_file = os.path.join(tempfile.gettempdir(), ''.join(random.choice('0123456789ABCDEF') for i in range(12)) + '.mp3')
        tts_audio.save(audio_file)
        audio_data = pydub.AudioSegment.from_mp3(audio_file)
        silence = pydub.AudioSegment.silent(duration=tts_config['padding'])
        padded_audio = silence + audio_data + silence
        padded_audio.export(audio_file, format='mp3')
        player = await lavalink.connect(ctx.author.voice.channel)
        track = (await player.get_tracks(query=audio_file))[0]

        if player.current is None:
            player.queue.append(track)
            self.current_tts = track
            await player.play()
            return

        if self.current_tts is not None:
            player.queue.insert(0, track)
            await player.skip()
            os.remove(self.current_tts.uri)
            self.current_tts = track
            return

        self.last_track_info = (player.current, player.position)
        self.current_tts = track
        player.queue.insert(0, track)
        player.queue.insert(1, player.current)
        await player.skip()

    @commands.group(name='ttsconfig')
    async def ttsconfig(self, ctx):
        """Configure TTS"""
        pass

    @ttsconfig.command(name='lang', usage='[language code]')
    @checks.guildowner()
    async def _tts_lang(self, ctx, *args):
        """
        Configure the default TTS language

        Gets/sets the default language for the `[p]tts` command.
        Use `[p]ttslangs` for a list of language codes.
        """

        tts_config = await self.config.guild(ctx.guild).tts()
        if len(args) == 0:
            await ctx.send(f"Current value of `lang`: {tts_config['lang']}")
            return

        lang = args[0]
        if lang not in self.tts_languages:
            await ctx.send('Invalid langauge. Use [p]ttsconfig langlist for a list of languages.')
            return

        tts_config['lang'] = lang
        await self.config.guild(ctx.guild).tts.set(tts_config)
        await ctx.send(f'`lang` set to {lang}.')


    @ttsconfig.command(name='padding', usage='<duration>')
    @checks.guildowner()
    async def _tts_padding(self, ctx, *args):
        """
        Configure the default TTS padding

        Gets/sets the default duration of padding (in ms) for the `[p]tts` command.
        Adjust if the sound gets cut off at the beginning or the end.
        """

        tts_config = await self.config.guild(ctx.guild).tts()
        if len(args) == 0:
            await ctx.send(f"Current value of `padding`: {tts_config['padding']}")
            return

        padding = 0
        try:
            padding = int(args[0])
        except ValueError:
            await ctx.send_help()
            return

        tts_config['padding'] = padding
        await self.config.guild(ctx.guild).tts.set(tts_config)
        await ctx.send(f'`padding` set to {padding}.')

    @commands.command(name='ttslangs')
    async def _tts_lang_list(self, ctx):
        """
        List of TTS Languages

        Prints the list of valid languages for use with `[p]tts`.
        """

        await ctx.send(f"List of valid languages: {', '.join(self.tts_languages)}")

    async def ll_check(self, player, event, reason):
        if self.current_tts is None and self.last_track_info is None:
            return

        if event == lavalink.LavalinkEvents.TRACK_EXCEPTION and self.current_tts is not None:
            os.remove(self.current_tts.uri)
            self.current_tts = None
            return

        if event == lavalink.LavalinkEvents.TRACK_STUCK and self.current_tts is not None:
            os.remove(self.current_tts.uri)
            self.current_tts = None
            await player.skip()
            return

        if event == lavalink.LavalinkEvents.TRACK_END and player.current is None and self.current_tts is not None:
            os.remove(self.current_tts.uri)
            self.current_tts = None
            return

        if event == lavalink.LavalinkEvents.TRACK_END and player.current.track_identifier == self.last_track_info[0].track_identifier:
            print(str(self.last_track_info[0].uri))
            os.remove(self.current_tts.uri)
            self.current_tts = None
            await player.pause()
            await player.seek(self.last_track_info[1])
            await player.pause(False)
            self.last_track_info = None