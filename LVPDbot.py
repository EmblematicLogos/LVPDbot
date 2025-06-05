import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
from datetime import timedelta

TOKEN = 'MTM3OTg5ODUzMDQ5MTAxMTE5Mw.G1qu-t.sBi5w_gEPLfCHipcv49X7ZEoy0bn5Qsm_cFBM4'
TEST_GUILD_ID = 1379124902539558965

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === Database Setup ===
def create_user_table():
    connection = sqlite3.connect(f"{BASE_DIR}/user_warnings.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users_per_guild (
            user_id INTEGER,
            warning_count INTEGER,
            guild_id INTEGER,
            PRIMARY KEY(user_id, guild_id)
        )
    """)
    connection.commit()
    connection.close()

def increase_and_get_warnings(user_id: int, guild_id: int):
    connection = sqlite3.connect(f"{BASE_DIR}/user_warnings.db")
    cursor = connection.cursor()
    cursor.execute("SELECT warning_count FROM users_per_guild WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    result = cursor.fetchone()
    if result is None:
        cursor.execute("INSERT INTO users_per_guild (user_id, warning_count, guild_id) VALUES (?, 1, ?)", (user_id, guild_id))
        connection.commit()
        connection.close()
        return 1
    else:
        new_count = result[0] + 1
        cursor.execute("UPDATE users_per_guild SET warning_count = ? WHERE user_id = ? AND guild_id = ?", (new_count, user_id, guild_id))
        connection.commit()
        connection.close()
        return new_count

def get_warnings(user_id: int, guild_id: int):
    connection = sqlite3.connect(f"{BASE_DIR}/user_warnings.db")
    cursor = connection.cursor()
    cursor.execute("SELECT warning_count FROM users_per_guild WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    result = cursor.fetchone()
    connection.close()
    return result[0] if result else 0

def reset_warnings(user_id: int, guild_id: int):
    connection = sqlite3.connect(f"{BASE_DIR}/user_warnings.db")
    cursor = connection.cursor()
    cursor.execute("DELETE FROM users_per_guild WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    connection.commit()
    connection.close()

# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

profanity = [
    "fuck", "shit", "bitch", "asshole", "bastard", "dick", "pussy", "cunt",
    "fag", "slut", "whore", "damn", "crap", "cock", "douche", "motherfucker",
    "nigger", "nigga", "retard", "twat", "wanker", "arsehole", "bollocks",
]

# === Events ===
@bot.event
async def on_ready():
    test_guild = discord.Object(id=TEST_GUILD_ID)
    await tree.sync(guild=test_guild)
    print(f"✅ {bot.user} is online and synced to test guild {TEST_GUILD_ID}")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    content = msg.content.lower()
    if any(word in content for word in profanity):
        warnings = increase_and_get_warnings(msg.author.id, msg.guild.id)
        mute_duration = timedelta(minutes=15 * warnings)

        try:
            await msg.author.timeout(mute_duration, reason="Profanity warning.")
            await msg.channel.send(
                f"⚠️ {msg.author.mention} used profanity. Warning {warnings}. Muted for {15 * warnings} minutes."
            )
        except discord.Forbidden:
            await msg.channel.send("I don't have permission to timeout this user.")
        except Exception as e:
            await msg.channel.send(f"Error muting user: {e}")

        await msg.delete()

    await bot.process_commands(msg)

# === Slash Commands ===
@tree.command(name="warn", description="Warn a member and mute them for 15 minutes per warning", guild=discord.Object(id=TEST_GUILD_ID))
@app_commands.describe(user="The user to warn")
async def warn(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission to warn users.", ephemeral=True)
        return

    warnings = increase_and_get_warnings(user.id, interaction.guild.id)
    mute_duration = timedelta(minutes=15 * warnings)

    try:
        await user.timeout(mute_duration, reason="Manual warning by mod.")
        await interaction.response.send_message(
            f"⚠️ {user.mention} has been warned. Total warnings: {warnings}. Muted for {15 * warnings} minutes."
        )
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout that user.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@tree.command(name="checkwarnings", description="Check how many warnings a user has", guild=discord.Object(id=TEST_GUILD_ID))
@app_commands.describe(user="The user to check")
async def checkwarnings(interaction: discord.Interaction, user: discord.Member):
    warnings = get_warnings(user.id, interaction.guild.id)
    embed = discord.Embed(title="⚠️ Warning Info", color=discord.Color.orange())
    embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else discord.Embed.Empty)
    embed.add_field(name="User", value=f"{user.mention}", inline=True)
    embed.add_field(name="Warnings", value=f"{warnings}", inline=True)
    embed.set_footer(text=f"Requested by {interaction.user}")
    await interaction.response.send_message(embed=embed)

@tree.command(name="resetwarnings", description="Reset a user's warning count", guild=discord.Object(id=TEST_GUILD_ID))
@app_commands.describe(user="The user to reset warnings for")
async def resetwarnings(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission to reset warnings.", ephemeral=True)
        return

    reset_warnings(user.id, interaction.guild.id)
    await interaction.response.send_message(f"✅ {user.mention}'s warnings have been reset.")

@tree.command(name="unmute", description="Unmute a user early", guild=discord.Object(id=TEST_GUILD_ID))
@app_commands.describe(user="The user to unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission to unmute users.", ephemeral=True)
        return

    try:
        await user.timeout(None)
        await interaction.response.send_message(f"🔈 {user.mention} has been unmuted.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to unmute that user.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# === Start Bot ===
create_user_table()
bot.run(TOKEN)
