import os
from os.path import exists
import discord
import json
from discord.ext import commands
from dotenv import load_dotenv
import datetime
from colorama import init, Fore
from typing import Dict, Any

# ---------------- Logging ---------------- # 
# SHOUTOUT EIGHTBY8
def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    colors = {
        "INFO": Fore.CYAN,
        "SUCCESS": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "INIT": Fore.MAGENTA,
        "PIN": Fore.BLUE
    }
    color = colors.get(level, "")
    print(color + f"[{timestamp}] [{level}] {message}")

# Initalize colorama
init(autoreset=True)

load_dotenv()

# ---------------- Globals ---------------- #
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = os.getenv("OWNER_ID")
CONFIG_FILE = "config.json"
PIN_FILE = "pins.json"
PINCOUNT_FILE = "pinCount.json"


if not TOKEN:
    log("'DISCORD_TOKEN' is not set in the environment", "ERROR")
else: 
    log("'DISCORD_TOKEN' Loaded", "SUCCESS")

# ---------------- In-Memory States ---------------- #
pinCount: Dict[int, list[str]] = {}
pins: Dict[int, list[str]] = {}



# ---------------- Bot Setup ---------------- #
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------- Save/Load Config ---------------- #
def saveJson(filename: str, data: dict):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            log(f"Data saved to '{filename}'", "SUCCESS")
    except Exception as e:
        log(f"Failed to save '{filename}': {e}","ERROR")

def loadJson(filename: str, data: dict):
    if not os.path.exists(filename):
        log(f"'{filename}' not found creating a new one with defaults...", "WARNING")
        initalData = data if data is not None else {}
        saveJson(filename, initalData)
        return initalData

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            log(f"JSON Loaded: '{filename}'", "SUCCESS")
            return data
    except Exception as e:
        log(f"Failed to load config: {e}", "ERROR")
        return data if data is not None else {}

def loadConfig():
    """Load configuration from JSON; create it with defaults if missing."""
    global CHANNEL_ID, OWNER_ID
    
    #  Check if file exists. If not, create it with current global values.
    if not os.path.exists(CONFIG_FILE):
        log(f"{CONFIG_FILE} not found. Creating a new one with defaults...", "WARNING")

        configData = {
                "channel_id": CHANNEL_ID,
                "owner_id": OWNER_ID
            }
        saveJson("config.json", configData) 
        return
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

            CHANNEL_ID = data.get("channel_id", CHANNEL_ID)
            OWNER_ID = data.get("owner_id", OWNER_ID)
            
            log(f"Config file found: {CONFIG_FILE}", "INFO")
    except Exception as e:
        log(f"Failed to load config: {e}", "ERROR")


# ---------------- Bot Setup ---------------- #
@bot.event
async def on_ready():
    global OWNER_ID
    
    try:
        synced = await bot.tree.sync()
        log(f"Synced {len(synced)} slash commands", "INFO")
    except Exception as e:
        log(f"Failed to sync commands: {e}", "ERROR")

    versionNumber = "v0.3.0"
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name=versionNumber)
    )

    log(f"Logged in as {bot.user} | {versionNumber}", "SUCCESS")

    if OWNER_ID is None:
        if GUILD_ID:
            try:
                guild_id = int(GUILD_ID)
                guild = bot.get_guild(guild_id)
                
                if not guild:
                    guild = await bot.fetch_guild(guild_id)
                
                if guild:
                    OWNER_ID = guild.owner_id
                    ownerName = guild.get_member(OWNER_ID) or await guild.fetch_member(OWNER_ID)
                    log(f"Auto-configured Owner: {ownerName} ({OWNER_ID})", "INIT")
                    updatedData = {
                        "channel_id": CHANNEL_ID,
                        "owner_id": OWNER_ID
                    }
                    saveJson(CONFIG_FILE, updatedData)
                else:
                    log(f"Could not find guild with ID {guild_id}", "ERROR")
            except ValueError:
                log("GUILD_ID in .env is not a valid number!", "ERROR")
        else:
            log("GUILD_ID is missing from your .env file!", "ERROR")

# ---------------- Bot Events ---------------- #
@bot.event
async def on_raw_reaction_add(payload) -> None:
    global pinCount, pins, CHANNEL_ID
    foundImage = None
    
    # If the message is from the bot
    if payload.user_id == bot.user.id:
        return

    if payload.emoji.name == "📌":
        try:
            user = bot.get_user(payload.user_id) or await bot.fetch_user(payload.user_id)
            channel = bot.get_channel(payload.channel_id) or await bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            if message.author.bot:
                return

            if CHANNEL_ID:
                if str(payload.channel_id) == str(CHANNEL_ID):
                    return

                reactorID = str(user.id)
                messageID = str(message.id)
                reactorName = user.name.capitalize()
                target_id = int(CHANNEL_ID)
                target_channel = bot.get_channel(target_id) or await bot.fetch_channel(target_id)

                # If the message has already been pinned
                if messageID in pins:
                    await channel.send(f"{user.mention} > This message has already been pinned..")
                    log(f"Message: [{messageID}] already pinned. Skipping..", "WARNING")
                    return

                # Handle pin tracking counts
                if reactorID not in pinCount:
                    pinCount[reactorID] = 0
                pinCount[reactorID] += 1

                # If the message has a picture or GIF
                if message.attachments:
                    if any(message.attachments[0].filename.lower().endswith(ext) for ext in ["png", "jpg", "jpeg", "gif", "webp"]):
                        foundImage = message.attachments[0].url
                        log("Image found.", "PIN")
                        
                # Send Embed
                embedContent = f"{message.author.name.capitalize()}: {message.content}"
                view = CreateEmbed(data=embedContent, title=f"📌 {reactorName} | Pin #{pinCount[reactorID]}", image_url=foundImage)
                
                await channel.send(f"{user.mention} > Message pinned to {target_channel.mention}.", delete_after=5)
                
                # FIX 1: Capture the message object into embed_msg variable
                embed_msg = await target_channel.send(embed=view.pinEmbed())

                # Save the bot's embed message ID into tracking dict
                pins[messageID] = str(embed_msg.id)
                
                # Save jsons
                saveJson(PINCOUNT_FILE, pinCount) 
                saveJson(PIN_FILE, pins)
                
                log(f"Pin Count for {reactorName}: {pinCount[reactorID]}", "INFO")
                log(f"Author: {message.author.name.capitalize()} | Message: '{message.content[:15]}...' | Pin User: {reactorName}", "PIN")
            else:
                await channel.send(f"{user.mention} > The pin channel has not been set...")
                log("Pin detected, but 'CHANNEL_ID' is not configured.", "WARNING")

        except Exception as e:
            log(f"Failed to process pin: {e}", "ERROR")


@bot.event
async def on_raw_reaction_remove(content) -> None:
    global pins, CHANNEL_ID

    if content.emoji.name == "📌":
        try:
            messageID = str(content.message_id)
            
            if messageID in pins:
                embedMessageID = int(pins[messageID])

                if not CHANNEL_ID:
                    log("Unpin detected but 'CHANNEL_ID' not set", "WARNING")
                    return

                target_channel = bot.get_channel(int(CHANNEL_ID)) or await bot.fetch_channel(int(CHANNEL_ID))

                try:
                    embed_msg = await target_channel.fetch_message(embedMessageID)
                    await embed_msg.delete()
                    log(f"Deleted Pin: [{embedMessageID}]", "PIN")
                except discord.NotFound:
                    log(f"Tried to delete [{embedMessageID}] but it was already missing", "WARNING")

                # Clean up memory and file cache
                del pins[messageID]
                saveJson(PIN_FILE, pins)

                origChannel = bot.get_channel(content.channel_id) or await bot.fetch_channel(content.channel_id)
                await origChannel.send("Message unpinned from the board.", delete_after=5)
            else:
                origChannel = bot.get_channel(content.channel_id) or await bot.fetch_channel(content.channel_id)
                log(f"Reaction removed in [#{origChannel.name}], but no tracking ID was found in pins.json.", "INFO")

        except Exception as e:
            log(f"Failed to handle reaction removal: {e}", "ERROR")
# ---------------- Commands ---------------- #
@tree.command(name="setchannel", description="Set the channel where all pins will be sent")
async def set_channel(interaction: discord.Interaction) -> None:
    global CHANNEL_ID
   
   # If no 'OWNER_ID' is set
    if OWNER_ID is None:
        log("Permission check failed: OWNER_ID is not set in .env or config.", "ERROR")
        return await interaction.response.send_message("Bot configuration error: Owner ID not found.", ephemeral=True)
    
    # If user is not owner
    if interaction.user.id != int(OWNER_ID):
        return await interaction.response.send_message("You do not have permission to set channels.", ephemeral=True)

    # Update and save json
    CHANNEL_ID = interaction.channel.id
    updatedData = {
            "channel_id": CHANNEL_ID,
            "owner_id": OWNER_ID
        }
    saveJson(CONFIG_FILE, updatedData)
    
    await interaction.response.send_message(f"Pinboard channel set to: {interaction.channel.mention}")
    log(f"Pinboard channel set to {interaction.channel.id} by {interaction.user.name.capitalize()}", "INFO")

@tree.command(name="testembed", description="Spawn a test embed")
async def testEmbed(interaction: discord.Interaction):
    await interaction.response.defer() 

    try:
        view = CreateEmbed(data="Test Data", title="Test Pin") 
        embed = view.pinEmbed()

        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        log(f"Error in testEmbed: {e}", "ERROR")
        await interaction.followup.send("An error occurred while generating the embed.")


# ---------------- UI / Embeds ---------------- #
class CreateEmbed(discord.ui.View):
    def __init__(self, data, timeout=180, title="", description="", color=0xffffff, image_url=None):
        super().__init__(timeout=timeout)
        self.data = data 
        self.titleText = title
        self.descText = description  
        self.color = color
        self.imageURL = image_url



    def pinEmbed(self):
        embed = discord.Embed(
            title=f"{self.titleText}",
            description = str(self.data),
            color=self.color,
        )
        
        if self.imageURL:
            embed.set_image(url=self.imageURL)
           
        dateString = datetime.datetime.now().strftime("%b %d, %Y | %I:%M %p")
        embed.set_footer(text=f"Pinned on {dateString}")
        return embed

# ---------------- Run ---------------- #
def main():
    global CHANNEL_ID, OWNER_ID, pinCount, pins

    # Load config.json
    config = loadJson(CONFIG_FILE, data={"channel_id": None, "owner_id": None})
    CHANNEL_ID = config.get("channel_id")
    OWNER_ID = config.get("owner_id")
    log(f"'config.json' Loaded | Channel: {CHANNEL_ID} | Owner: {OWNER_ID}", "INFO")

    #Load pinCount.json
    pinCount = loadJson(PINCOUNT_FILE, data={})

    #Load pins.json
    pins = loadJson(PIN_FILE, data={})

    try:
        bot.run(TOKEN)
    except Exception as e:
        log(f"Failed to start bot: {e}", "ERROR")

if __name__ == "__main__":
    main()
