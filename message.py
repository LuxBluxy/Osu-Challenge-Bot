import discord
from discord.ext import commands
from discord import app_commands
from osrparse import Replay, Mod
import os
import zipfile
from dotenv import load_dotenv
import json
from collections import defaultdict
import hashlib

load_dotenv()
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Data storage
active_challenges = {}
pending_maps = {}
wins_data = defaultdict(int)  # {user_id: win_count}

# Load wins data from file
def load_wins_data():
    global wins_data
    try:
        with open('wins.json', 'r') as f:
            wins_data = defaultdict(int, json.load(f))
    except FileNotFoundError:
        wins_data = defaultdict(int)

# Save wins data to file
def save_wins_data():
    with open('wins.json', 'w') as f:
        json.dump(dict(wins_data), f)

load_wins_data()

def extract_map_difficulties(osz_path):
    difficulties = []
    with zipfile.ZipFile(osz_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.endswith('.osu'):
                with zip_ref.open(file) as osu_file:
                    title = "Unknown"
                    artist = "Unknown"
                    version = "Unknown"
                    beatmap_hash = ""
                    for line in osu_file:
                        line = line.decode('utf-8').strip()
                        if line.startswith('Title:'):
                            title = line.split(':')[1].strip()
                        elif line.startswith('Artist:'):
                            artist = line.split(':')[1].strip()
                        elif line.startswith('Version:'):
                            version = line.split(':')[1].strip()
                        elif line.startswith('BeatmapHash:'):
                            beatmap_hash = line.split(':')[1].strip()
                    
                    # Calculate hash if not present in file
                    if not beatmap_hash:
                        osu_file.seek(0)
                        beatmap_hash = hashlib.md5(osu_file.read()).hexdigest()
                    
                    difficulties.append({
                        "name": f"{artist} - {title} [{version}]",
                        "hash": beatmap_hash.lower()
                    })
    return difficulties

class DifficultySelect(discord.ui.Select):
    def __init__(self, difficulties):
        options = [
            discord.SelectOption(label=diff["name"][:100], value=str(i), 
            description=f"Difficulty #{i+1}")
            for i, diff in enumerate(difficulties)
        ]
        super().__init__(placeholder="🎚️ Select a difficulty...", options=options)

    async def callback(self, interaction: discord.Interaction):
        challenge_data = pending_maps[interaction.channel.id]
        index = int(self.values[0])
        selected_diff = challenge_data["difficulties"][index]
        
        active_challenges[interaction.channel.id] = {
            "map_name": selected_diff["name"],
            "map_hash": selected_diff["hash"],
            "mode": challenge_data["mode"],
            "players": {interaction.user.id, challenge_data["opponent"].id},
            "scores": {},
            "replays": {}
        }

        embed = discord.Embed(
            title="🔥 Challenge Started! 🔥",
            description=f"⚔️ **Players**: {interaction.user.mention} vs {challenge_data['opponent'].mention}\n"
                       f"🎮 **Mode**: {challenge_data['mode'].upper()}\n"
                       f"🗺️ **Map**: {selected_diff['name']}\n\n"
                       f"⏳ **Now both players should play and upload their .osr replays!**",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)
        del pending_maps[interaction.channel.id]

class DifficultyView(discord.ui.View):
    def __init__(self, difficulties):
        super().__init__()
        self.add_item(DifficultySelect(difficulties))

async def start_challenge(ctx, opponent: discord.Member, mode: str, map_file: discord.Attachment = None):
    mode = mode.lower()
    if mode not in ["std", "taiko", "ctb", "mania"]:
        await ctx.send(embed=discord.Embed(
            title="❌ Invalid Mode",
            description="Please use one of these modes: std, taiko, ctb, mania",
            color=discord.Color.red()
        ))
        return

    if opponent == ctx.author:
        await ctx.send("❌ You can't challenge yourself!")
        return
    if opponent.bot:
        await ctx.send("❌ You can't challenge a bot!")
        return

    if map_file is None:
        embed = discord.Embed(
            title="🎮 New Challenge",
            description=f"{ctx.author.mention} vs {opponent.mention}\n"
                       f"**Mode**: {mode.upper()}\n\n"
                       "Please upload the .osz map file now!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.attachments
        
        try:
            msg = await bot.wait_for('message', check=check, timeout=60)
            if not msg.attachments[0].filename.endswith('.osz'):
                await ctx.send("❌ Please upload a valid .osz file!")
                return
            map_file = msg.attachments[0]
        except TimeoutError:
            await ctx.send("⌛ You took too long to upload the map! Challenge cancelled.")
            return

    await map_file.save("temp.osz")
    difficulties = extract_map_difficulties("temp.osz")
    os.remove("temp.osz")

    if not difficulties:
        await ctx.send("❌ No difficulties found in the map file!")
        return

    pending_maps[ctx.channel.id] = {
        "opponent": opponent,
        "mode": mode,
        "difficulties": difficulties
    }

    view = DifficultyView(difficulties)
    await ctx.send(embed=discord.Embed(
        title="🎚️ Select Difficulty",
        description="Choose the difficulty for your challenge:",
        color=discord.Color.blue()
    ), view=view)

@bot.tree.command(name="challenge", description="Start a new osu! challenge")
@app_commands.describe(
    opponent="The user you want to challenge",
    mode="Game mode (std/taiko/ctb/mania)",
    map_file="The .osz map file"
)
async def slash_challenge(interaction: discord.Interaction, opponent: discord.Member, mode: str, map_file: discord.Attachment):
    await start_challenge(interaction, opponent, mode, map_file)

@bot.command()
async def challenge(ctx, opponent: discord.Member = None, mode: str = None):
    if opponent is None or mode is None:
        await ctx.send(embed=discord.Embed(
            title="❌ Missing Arguments",
            description="Usage: `!challenge @opponent [std/taiko/ctb/mania]`",
            color=discord.Color.red()
        ))
        return
    await start_challenge(ctx, opponent, mode)

async def show_leaderboard(ctx):
    if not wins_data:
        await ctx.send(embed=discord.Embed(
            title="🏆 Leaderboard",
            description="📊 No challenges completed yet!",
            color=discord.Color.blue()
        ))
        return

    sorted_wins = sorted(wins_data.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="🏆 Osu! Challenge Leaderboard", color=discord.Color.gold())
    
    for rank, (user_id, wins) in enumerate(sorted_wins[:10], 1):
        user = await bot.fetch_user(user_id)
        embed.add_field(
            name=f"{get_medal_emoji(rank)} {user.display_name}",
            value=f"🏅 {wins} wins",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.tree.command(name="leaderboard", description="Show osu! challenge leaderboard")
async def slash_leaderboard(interaction: discord.Interaction):
    await show_leaderboard(interaction)

@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx)

async def show_wins(ctx, user: discord.Member):
    win_count = wins_data.get(user.id, 0)
    embed = discord.Embed(
        title=f"🏅 {user.display_name}'s Wins",
        description=f"🎖️ Total wins: {win_count}" if win_count > 0 else "😢 No wins yet!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="wins", description="Show a player's challenge wins")
@app_commands.describe(user="The user to check wins for")
async def slash_wins(interaction: discord.Interaction, user: discord.Member):
    await show_wins(interaction, user)

@bot.command()
async def wins(ctx, user: discord.Member = None):
    await show_wins(ctx, user or ctx.author)

def get_medal_emoji(rank):
    if rank == 1: return "🥇"
    elif rank == 2: return "🥈"
    elif rank == 3: return "🥉"
    return f"{rank}."

@bot.event
async def on_message(message):
    if message.channel.id in active_challenges and message.attachments:
        challenge_data = active_challenges[message.channel.id]
        
        if message.author.id not in challenge_data["players"]:
            return
            
        for attachment in message.attachments:
            if attachment.filename.endswith(".osr"):
                await attachment.save("temp.osr")
                
                try:
                    replay = Replay.from_path("temp.osr")
                    os.remove("temp.osr")
                    
                    # Anti-cheat verification
                    if replay.mode.name.lower() != challenge_data["mode"]:
                        await message.reply(f"❌ Wrong game mode! Expected {challenge_data['mode'].upper()}.")
                        return
                    
                    if replay.beatmap_hash.lower() != challenge_data["map_hash"]:
                        await message.reply("❌ Replay doesn't match the selected map!")
                        return
                    
                    if message.author.id in challenge_data["replays"]:
                        await message.reply("❌ You've already submitted a replay!")
                        return
                    
                    # Calculate accuracy
                    total_hits = replay.count_300 + replay.count_100 + replay.count_50 + replay.count_miss
                    accuracy = (replay.count_300 * 300 + replay.count_100 * 100 + replay.count_50 * 50) / (total_hits * 300) * 100 if total_hits > 0 else 0
                    
                    # Store results
                    challenge_data["scores"][message.author.id] = {
                        "score": replay.score,
                        "accuracy": accuracy,
                        "mods": replay.mods
                    }
                    challenge_data["replays"][message.author.id] = True
                    
                    # Send confirmation
                    embed = discord.Embed(
                        title="✅ Score Registered!",
                        description=f"👤 Player: {message.author.mention}",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="⭐ Score", value=f"{replay.score:,}", inline=True)
                    embed.add_field(name="🎯 Accuracy", value=f"{accuracy:.2f}%", inline=True)
                    embed.add_field(name="🌀 Mods", value=f"{replay.mods or 'None'}", inline=True)
                    await message.reply(embed=embed)
                    
                    # Check if both players submitted
                    if len(challenge_data["scores"]) == 2:
                        players = list(challenge_data["scores"].items())
                        winner = max(players, key=lambda x: x[1]["score"])
                        
                        # Update leaderboard
                        wins_data[winner[0]] += 1
                        save_wins_data()
                        
                        # Send results
                        winner_user = await bot.fetch_user(winner[0])
                        loser_user = await bot.fetch_user(min(players, key=lambda x: x[1]["score"])[0])
                        
                        embed = discord.Embed(
                            title="🏆 Challenge Complete!",
                            description=f"⚔️ Map: {challenge_data['map_name']}\n"
                                      f"🎮 Mode: {challenge_data['mode'].upper()}",
                            color=discord.Color.gold()
                        )
                        embed.add_field(
                            name=f"🎉 Winner: {winner_user.display_name}",
                            value=f"⭐ Score: {winner[1]['score']:,}\n"
                                 f"🎯 Accuracy: {winner[1]['accuracy']:.2f}%\n"
                                 f"🌀 Mods: {winner[1]['mods'] or 'None'}",
                            inline=True
                        )
                        embed.add_field(
                            name=f"😢 Loser: {loser_user.display_name}",
                            value=f"⭐ Score: {min(p[1]['score'] for p in players):,}\n"
                                 f"🎯 Accuracy: {min(p[1]['accuracy'] for p in players):.2f}%\n"
                                 f"🌀 Mods: {min(p[1]['mods'] for p in players) or 'None'}",
                            inline=True
                        )
                        await message.channel.send(embed=embed)
                        del active_challenges[message.channel.id]
                        
                except Exception as e:
                    await message.reply(f"❌ Error processing replay: {str(e)}")
    
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        await bot.tree.sync()
        print("Commands synced successfully!")
    except Exception as e:
        print(f"Error syncing commands: {e}")

bot.run(os.getenv("DISCORD_TOKEN"))