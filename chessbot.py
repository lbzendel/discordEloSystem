import discord
from discord.ext import commands
import sqlite3
import math

# ---------- CONFIGURATION ----------
TOKEN = "MTQwMzE3NjU0Nzg2MjU3NzI3Mg.G4Ws6p.CSLxbgc_0hVTCPS70RZpviN7flMI0GdxF5dLkk"
DATABASE = "elo_bot.db"
prefix = "!"

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 user_id INTEGER PRIMARY KEY,
                 rating REAL DEFAULT 1500)''')
    # games table
    c.execute('''CREATE TABLE IF NOT EXISTS games (
                 game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                 winner_id INTEGER,
                 loser_id INTEGER,
                 winner_rating_before REAL,
                 loser_rating_before REAL,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# ---------- ELO CALCULATION ----------
K = 32

def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_elo(rating_winner, rating_loser):
    exp_win = expected_score(rating_winner, rating_loser)
    exp_loss = expected_score(rating_loser, rating_winner)
    new_win = rating_winner + K * (1 - exp_win)
    new_loss = rating_loser + K * (0 - exp_loss)
    return new_win, new_loss

# ---------- BOT SETUP ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=prefix, intents=intents)

@bot.event
async def on_ready():
    init_db()
    print(f"Logged in as {bot.user}")

# ---------- COMMANDS ----------
@bot.command(name="register")
async def register(ctx, member: discord.Member = None):
    """Register yourself or another member in the rating system"""
    user = member or ctx.author
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user.id,))
    conn.commit()
    conn.close()
    await ctx.send(f"Registered {user.display_name} with starting rating 1500.")

@bot.command(name="game")
async def record_game(ctx, winner: discord.Member, loser: discord.Member):
    """Record a game result and update Elo ratings"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # ensure both registered
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (winner.id,))
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (loser.id,))
    # fetch old ratings
    c.execute("SELECT rating FROM users WHERE user_id = ?", (winner.id,))
    r_w = c.fetchone()[0]
    c.execute("SELECT rating FROM users WHERE user_id = ?", (loser.id,))
    r_l = c.fetchone()[0]
    # update ratings
    new_w, new_l = update_elo(r_w, r_l)
    # store game
    c.execute(
        "INSERT INTO games (winner_id, loser_id, winner_rating_before, loser_rating_before) VALUES (?,?,?,?)",
        (winner.id, loser.id, r_w, r_l)
    )
    # update user ratings
    c.execute("UPDATE users SET rating = ? WHERE user_id = ?", (new_w, winner.id))
    c.execute("UPDATE users SET rating = ? WHERE user_id = ?", (new_l, loser.id))
    conn.commit()
    conn.close()
    await ctx.send(
        f"Game recorded! {winner.display_name} rating: {r_w:.1f} -> {new_w:.1f}, "
        f"{loser.display_name} rating: {r_l:.1f} -> {new_l:.1f}"
    )

@bot.command(name="leaderboard")
async def leaderboard(ctx, top: int = 10):
    """Display top N players by rating"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT user_id, rating FROM users ORDER BY rating DESC LIMIT ?", (top,))
    rows = c.fetchall()
    conn.close()

    embed = discord.Embed(title=f"Top {top} Leaderboard")
    for idx, (uid, rating) in enumerate(rows, start=1):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else str(uid)
        embed.add_field(name=f"{idx}. {name}", value=f"{rating:.1f}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="games")
async def list_games(ctx, member: discord.Member = None):
    """List recorded games for a user"""
    user = member or ctx.author
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "SELECT game_id, winner_id, loser_id, timestamp FROM games WHERE winner_id = ? OR loser_id = ? ORDER BY timestamp DESC",
        (user.id, user.id)
    )
    games = c.fetchall()
    conn.close()

    if not games:
        await ctx.send(f"No games found for {user.display_name}.")
        return

    msg = []
    for gid, win, loss, time in games[:10]:
        w = ctx.guild.get_member(win)
        l = ctx.guild.get_member(loss)
        msg.append(f"ID {gid}: {w.display_name if w else win} beat {l.display_name if l else loss} at {time}")
    await ctx.send("\n".join(msg))

# ---------- RUN BOT ----------
@bot.command(name="ping")
async def ping(ctx):
    """Simple health check"""
    await ctx.send("🏓 Pong!")

if __name__ == "__main__":
    bot.run(TOKEN)
