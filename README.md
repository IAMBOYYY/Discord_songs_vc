# 24/7 Discord Music Bot

A Discord music bot that sits in one voice channel 24/7, plays random songs when nobody has queued anything, and lets people search and queue songs with slash commands.

- Built with **discord.py** and **Wavelink** (it talks to a **Lavalink** audio server).
- Runs for free on **Render** using a public Lavalink node. No VPS needed.
- Songs come from YouTube (with a SoundCloud fallback).

> **Heads up:** Streaming from YouTube with bots goes against YouTube's terms and can break at any time. Use it for your own small, private server at your own risk. Free public Lavalink nodes are run by strangers and can go offline without warning.

---

## Commands

| Command | What it does |
|---|---|
| `/play song [author]` | Searches and shows 5 results to pick from. Links and playlists work too |
| `/skip` | Skip the current song |
| `/pause` | Pause or resume |
| `/queue` | Show what is playing and what is next |
| `/clear` | Clear the queue |
| `/shuffle` | Shuffle the queue |
| `/loop off / current song / whole queue` | Loop mode |
| `/volume 1-100` | Player volume (leave at 100, use Discord's User Volume instead) |
| `/radio on/off` | Turn the random 24/7 songs on or off |
| `/nowplaying` | Show the current song |
| `/nodeinfo` | Audio health: node load, dropped frames, ping, plugins |
| `/normalize on/off` | Even out loud/quiet songs (only works if the node has the LavaDSPX plugin) |

Random songs come from `songs.txt` (one search per line). Edit it to your taste.

---

## Setup (step by step)

### 1. Fork this repo
Click **Fork** on GitHub. Keep your fork **private** if you like. Never put your bot token in any file.

### 2. Create the Discord bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Open the **Bot** tab, click **Reset Token**, and copy the token. Keep it secret.
3. On the same tab you do **not** need any privileged intents. A "message content intent is missing" warning in the logs is harmless.
4. Open the **General Information** tab and copy the **Application ID**.
5. Invite the bot to your server using this link (replace `YOUR_APP_ID`):

```
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot%20applications.commands&permissions=3148800
```

The permissions are: View Channel, Send Messages, Connect, Speak.

### 3. Get your voice channel ID
1. In Discord, go to **Settings → Advanced** and turn on **Developer Mode**.
2. Long-press (mobile) or right-click (desktop) the voice channel you want the bot to live in, and choose **Copy Channel ID**.
3. Make sure the bot's role can **View**, **Connect** and **Speak** in that channel.

### 4. Deploy on Render (free)
1. Create an account at [render.com](https://render.com) and connect your GitHub.
2. Click **New → Web Service** and pick your fork.
3. Use these settings:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python bot.py`
   - **Instance type:** Free
4. Under **Environment**, add:

| Variable | Value |
|---|---|
| `DISCORD_TOKEN` | your bot token |
| `HOME_VC_ID` | the voice channel ID from step 3 |
| `PYTHON_VERSION` | `3.11.9` (optional, Python 3.11 or newer works) |

5. Click **Deploy**. When it is live, open the **Logs** tab and look for:
   - `Using Lavalink node: ...`
   - `Joining home voice channel...`

The bot should now appear in your voice channel and start playing random songs.

### 5. Keep it awake
Render's free tier goes to sleep after 15 minutes without web traffic. The bot runs a tiny web page for this.

1. Copy your Render URL (like `https://your-bot.onrender.com`).
2. In a free monitoring service (UptimeRobot, Pulsetic, cron-job.org, etc.) create an **HTTP(s) / website monitor** for that URL with a **5 minute** interval.

Do **not** use a "heartbeat" monitor. A heartbeat waits for your app to ping *it*, and does nothing to wake Render.

---

## Lavalink nodes

The bot needs a Lavalink v4 server for audio. By default it tries these in order and uses the first one that works:

1. `LAVALINK_URI` / `LAVALINK_PASS` (your env vars, if set)
2. `LAVALINK_URI2` / `LAVALINK_PASS2` (optional backup)
3. The built-in `FALLBACK_NODES` list in `bot.py`

Example env vars (use `https://host:443` for secure nodes):

```
LAVALINK_URI=https://your-node.example.com:443
LAVALINK_PASS=the-node-password
```

Public nodes come and go. Find current ones in public lists on GitHub (search for "free lavalink list" or "lavalink-list"), then put a working one in the env vars. Pick one close to you for better quality. If you see `Cannot connect to host ... Name or service not known` in the logs, that node is dead.

### Want better quality? Run your own Lavalink
A free public node is shared with many other bots, so some stutter or uneven loudness is normal. For the best result, run your own on a spare PC, a Raspberry Pi, or a free cloud VM (for example Oracle Cloud Always Free):

1. Install Java 17 or newer.
2. Download `Lavalink.jar` from the [Lavalink releases](https://github.com/lavalink-devs/Lavalink/releases).
3. Put it next to the included `application.yml` (it has the YouTube plugin set up; check the [youtube-source repo](https://github.com/lavalink-devs/youtube-source) for the newest plugin version).
4. Run `java -jar Lavalink.jar`.
5. Set `LAVALINK_URI` to your server's address and `LAVALINK_PASS` to the password in `application.yml`.

For `/normalize`, install the LavaDSPX plugin on your own Lavalink (see its README).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot doesn't join the voice channel | Check `HOME_VC_ID`, and that the bot can Connect and Speak. Read the logs for `Using Lavalink node` |
| `Name or service not known` / `Cannot connect to host` | That Lavalink node is dead. Use another one |
| Slash commands don't show up | Re-invite with the link above (it needs `applications.commands`) and wait a few minutes |
| Bot leaves after a while on Render | Your monitor must be an HTTP monitor on the Render URL, not a heartbeat |
| Audio stutters | Run `/nodeinfo`. If `nulled`/`deficit` are above 0 or the ping is high, switch to a closer node. Also set the voice channel's **Region Override** near the node |
| Songs are sometimes loud, sometimes quiet | Songs are uploaded at different loudness and the bot streams them raw. Keep `/volume` at 100, set the bot's **User Volume** in Discord, and prefer "official audio" uploads. `/normalize` needs a node with LavaDSPX |
| YouTube songs fail but SoundCloud works | YouTube changes often break the node's YouTube plugin. Try another node |

---

## Files

- `bot.py`: the bot
- `requirements.txt`: Python packages
- `songs.txt`: pool of searches for random 24/7 mode
- `application.yml`: optional config if you run your own Lavalink

## License

Add a license of your choice. Music is streamed from third-party services; you are responsible for how you use this bot.
