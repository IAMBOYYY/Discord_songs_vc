import asyncio
import os
import random

import discord
import wavelink
from aiohttp import web
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ["DISCORD_TOKEN"]
# Public Lavalink node (free, community-run). Change these in Render env vars if it goes down.
LAVALINK_URI = os.getenv("LAVALINK_URI", "https://lavalink.nazha.online:443")
LAVALINK_PASS = os.getenv("LAVALINK_PASS", "nazhafreelava")
LAVALINK_URI2 = os.getenv("LAVALINK_URI2")  # optional backup node
LAVALINK_PASS2 = os.getenv("LAVALINK_PASS2", "")
HOME_VC = int(os.getenv("HOME_VC_ID", "0"))  # voice channel the bot stays in 24/7

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
state = {"radio": True}   # random 24/7 mode on/off
radio_now = {}            # guild_id -> identifier of the random track playing


def fmt(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


async def search(query: str):
    """YouTube first; fall back to SoundCloud if YouTube is blocked or broken."""
    if query.startswith("http"):
        return await wavelink.Playable.search(query)
    for source in (wavelink.TrackSource.YouTube, wavelink.TrackSource.SoundCloud):
        try:
            found = await wavelink.Playable.search(query, source=source)
            if found:
                return found
        except Exception:
            pass
    return []


def setup_player(vc: wavelink.Player):
    vc.inactive_timeout = None                      # never leave when idle
    vc.autoplay = wavelink.AutoPlayMode.partial     # auto-advance the queue


def is_radio(vc: wavelink.Player) -> bool:
    return bool(vc.current) and radio_now.get(vc.guild.id) == vc.current.identifier


async def play_random(vc: wavelink.Player):
    if not state["radio"] or not os.path.exists("songs.txt"):
        return
    with open("songs.txt", encoding="utf-8") as f:
        pool = [l.strip() for l in f if l.strip()]
    for _ in range(5):
        try:
            found = await search(random.choice(pool))
        except Exception:
            continue
        tracks = found.tracks if isinstance(found, wavelink.Playlist) else found
        if tracks:
            radio_now[vc.guild.id] = tracks[0].identifier
            await vc.play(tracks[0])
            return


async def join_home():
    await bot.wait_until_ready()
    ch = bot.get_channel(HOME_VC)
    if not ch:
        return
    vc = ch.guild.voice_client or await ch.connect(cls=wavelink.Player, self_deaf=True)
    setup_player(vc)
    if not vc.playing:
        await play_random(vc)


async def enqueue(vc: wavelink.Player, track: wavelink.Playable):
    if vc.playing and not is_radio(vc):
        await vc.queue.put_wait(track)
    else:
        await vc.play(track)  # replaces a random song right away


# ---------- events ----------
async def keep_alive():
    """Tiny web page so Render (and UptimeRobot) see a live web service."""
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000"))).start()


async def connect_lavalink():
    await bot.wait_until_ready()
    for attempt in range(20):
        nodes = [wavelink.Node(identifier=f"main{attempt}", uri=LAVALINK_URI, password=LAVALINK_PASS)]
        if LAVALINK_URI2:
            nodes.append(wavelink.Node(identifier=f"backup{attempt}", uri=LAVALINK_URI2, password=LAVALINK_PASS2))
        try:
            await wavelink.Pool.connect(nodes=nodes, client=bot)
            return
        except Exception as e:
            print("Lavalink connect failed, retrying in 20s:", e)
            await asyncio.sleep(20)


@bot.event
async def setup_hook():
    await keep_alive()
    await bot.tree.sync()
    asyncio.create_task(connect_lavalink())


@bot.event
async def on_wavelink_node_ready(payload):
    print("Lavalink connected")
    await join_home()


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    vc = payload.player
    if (vc and payload.reason != "replaced"
            and vc.queue.mode == wavelink.QueueMode.normal and vc.queue.is_empty):
        await asyncio.sleep(1)
        if not vc.playing:
            await play_random(vc)


@bot.event
async def on_voice_state_update(member, before, after):
    # if the bot gets kicked/disconnected from the home channel, rejoin
    if HOME_VC and member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(3)
        await join_home()


# ---------- /play with search menu ----------
class PickSelect(discord.ui.Select):
    def __init__(self, tracks):
        opts = [
            discord.SelectOption(
                label=t.title[:100],
                description=f"{t.author[:60]} • {fmt(t.length)}",
                value=str(i),
            )
            for i, t in enumerate(tracks)
        ]
        super().__init__(placeholder="Choose a song", options=opts)

    async def callback(self, inter: discord.Interaction):
        v = self.view
        if inter.user != v.user:
            return await inter.response.send_message("This menu isn't yours.", ephemeral=True)
        track = v.tracks[int(self.values[0])]
        await enqueue(v.vc, track)
        await inter.response.edit_message(content=f"✅ Added **{track.title}**", view=None)


class PickView(discord.ui.View):
    def __init__(self, tracks, user, vc):
        super().__init__(timeout=30)
        self.tracks, self.user, self.vc = tracks, user, vc
        self.add_item(PickSelect(tracks))


@bot.tree.command(description="Search and play a song")
@app_commands.describe(song="Song name or YouTube link", author="Artist (optional)")
async def play(inter: discord.Interaction, song: str, author: str = ""):
    if not inter.user.voice:
        return await inter.response.send_message("Join a voice channel first.", ephemeral=True)
    await inter.response.defer()

    vc = inter.guild.voice_client
    if vc is None:
        vc = await inter.user.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
        setup_player(vc)
    elif vc.channel != inter.user.voice.channel:
        return await inter.followup.send(f"Join {vc.channel.mention} to use me.")

    try:
        found = await search(f"{song} {author}".strip())
    except Exception:
        return await inter.followup.send("Search failed, try again.")
    if not found:
        return await inter.followup.send("No results.")

    if isinstance(found, wavelink.Playlist):  # playlist link: add everything
        for t in found.tracks:
            await enqueue(vc, t)
        return await inter.followup.send(f"✅ Added playlist **{found.name}**")

    tracks = list(found)[:5]
    await inter.followup.send("Pick a song:", view=PickView(tracks, inter.user, vc))


# ---------- controls ----------
async def vc_or_fail(inter: discord.Interaction):
    vc = inter.guild.voice_client
    if not vc:
        await inter.response.send_message("I'm not in a voice channel.", ephemeral=True)
    return vc


@bot.tree.command(description="Skip the current song")
async def skip(inter: discord.Interaction):
    if vc := await vc_or_fail(inter):
        await vc.skip(force=True)
        await inter.response.send_message("⏭ Skipped")


@bot.tree.command(description="Pause / resume")
async def pause(inter: discord.Interaction):
    if vc := await vc_or_fail(inter):
        await vc.pause(not vc.paused)
        await inter.response.send_message("⏸ Paused" if vc.paused else "▶️ Resumed")


@bot.tree.command(description="Shuffle the queue")
async def shuffle(inter: discord.Interaction):
    if vc := await vc_or_fail(inter):
        vc.queue.shuffle()
        await inter.response.send_message("🔀 Queue shuffled")


@bot.tree.command(description="Loop mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="off", value="off"),
    app_commands.Choice(name="current song", value="track"),
    app_commands.Choice(name="whole queue", value="queue"),
])
async def loop(inter: discord.Interaction, mode: app_commands.Choice[str]):
    if vc := await vc_or_fail(inter):
        vc.queue.mode = {
            "off": wavelink.QueueMode.normal,
            "track": wavelink.QueueMode.loop,
            "queue": wavelink.QueueMode.loop_all,
        }[mode.value]
        await inter.response.send_message(f"🔁 Loop: **{mode.name}**")


@bot.tree.command(description="Show the queue")
async def queue(inter: discord.Interaction):
    if vc := await vc_or_fail(inter):
        now = f"**Now:** {vc.current.title}\n" if vc.current else ""
        lines = [f"{i + 1}. {t.title}" for i, t in enumerate(list(vc.queue)[:10])]
        await inter.response.send_message(now + ("\n".join(lines) or "Queue is empty."))


@bot.tree.command(description="Clear the queue")
async def clear(inter: discord.Interaction):
    if vc := await vc_or_fail(inter):
        vc.queue.clear()
        await inter.response.send_message("🧹 Queue cleared")


@bot.tree.command(description="Set volume 1-100")
async def volume(inter: discord.Interaction, level: app_commands.Range[int, 1, 100]):
    if vc := await vc_or_fail(inter):
        await vc.set_volume(level)
        await inter.response.send_message(f"🔊 Volume {level}")


@bot.tree.command(description="Turn random 24/7 songs on or off")
async def radio(inter: discord.Interaction, on: bool):
    state["radio"] = on
    vc = inter.guild.voice_client
    if on and vc and not vc.playing:
        await play_random(vc)
    await inter.response.send_message(f"📻 Random radio: **{'on' if on else 'off'}**")


@bot.tree.command(description="What's playing")
async def nowplaying(inter: discord.Interaction):
    if vc := await vc_or_fail(inter):
        t = vc.current
        await inter.response.send_message(
            f"🎵 **{t.title}** — {t.author} ({fmt(t.length)})" if t else "Nothing playing."
        )


bot.run(TOKEN)
