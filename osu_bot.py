import discord
from discord.ext import commands
import os
from osu_replay_parser import OsuReplayAnalyzer

class OsuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        print(f'Bot conectado como {self.user.name}')

    async def analyze_replay(self, file_path):
        analyzer = OsuReplayAnalyzer(file_path)
        return analyzer.parse(), analyzer.get_mods()

bot = OsuBot()

@bot.command()
async def analyze(ctx):
    if not ctx.message.attachments:
        return await ctx.send("⚠️ Por favor adjunta un archivo .osr")

    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith('.osr'):
        return await ctx.send("❌ El archivo debe ser un replay de osu! (.osr)")

    try:
        await attachment.save('temp.osr')
        data, mods = await bot.analyze_replay('temp.osr')
        os.remove('temp.osr')
        
        embed = create_analysis_embed(data, mods)
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"🔥 Error procesando el replay: {str(e)}")
        if os.path.exists('temp.osr'):
            os.remove('temp.osr')

def create_analysis_embed(data, mods):
    embed = discord.Embed(
        title="🎮 Análisis de Replay de osu!",
        color=0xFF69B4,
        description=f"**Jugador:** {data['player_name']}"
    )
    
    accuracy = calculate_accuracy(data)
    duration = data['replay_data'][-1]['time_offset']/1000 if data['replay_data'] else 0
    
    embed.add_field(name="📊 Estadísticas Principales", value=(
        f"» **Score:** {data['score']:,}\n"
        f"» **Combo máximo:** {data['max_combo']}\n"
        f"» **Precisión:** {accuracy:.2f}%\n"
        f"» **Mods:** {mods}"
    ), inline=False)

    embed.add_field(name="🎯 Desempeño", value=(
        f"» **300:** {data['count_300']}\n"
        f"» **100:** {data['count_100']}\n"
        f"» **50:** {data['count_50']}\n"
        f"» **❌ Misses:** {data['misses']}"
    ), inline=True)

    embed.add_field(name="📅 Información", value=(
        f"» **Duración:** {duration:.2f}s\n"
        f"» **Fecha:** {data['timestamp'].strftime('%d/%m/%Y %H:%M')}\n"
        f"» **Frames:** {len(data['replay_data']):,}"
    ), inline=True)

    embed.set_footer(text="Análisis proporcionado por osu! Replay Analyzer")
    return embed

def calculate_accuracy(data):
    total = sum([data['count_300'], data['count_100'], data['count_50'], data['misses']])
    if total == 0:
        return 0.0
    return (data['count_300']*300 + data['count_100']*100 + data['count_50']*50) / (total * 300) * 100

if __name__ == "__main__":
    bot.run('MTM1NTkyNTg2ODU2MzY2MDkxMQ.GZf1FL.MGL7XdTnkHqqMP9madW_AQzRmXjpOmJba5sfpQ') 