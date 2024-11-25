import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
import json
import requests
import random
from datetime import datetime, timedelta, timezone
import shutil
from discord import app_commands
import aiohttp



# Load environment variables from the .env file
load_dotenv()

# Bot Token and Admin ID
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Set up bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True  # Ensure bot has permission to handle reactions
bot = commands.Bot(command_prefix="!", intents=intents)

#---------------------- IMPORTANT FOLDER PATHS----------------------#
CHARACTERS_FILE = "characters.json"
IMAGE_FOLDER = "images/"
COMMAND_LOCKS_FILE = "command_locks.json"
GOLD_FILE = "gold.json"
CHANNEL_SETTINGS_FILE = "channel_settings.json"

#---------------------------------INITIALIZING ALL THE PATHS AND STUFF----------------------#
if os.path.exists(CHANNEL_SETTINGS_FILE):
    try:
        with open(CHANNEL_SETTINGS_FILE, "r") as f:
            raw_settings = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print(f"Corrupted or empty {CHANNEL_SETTINGS_FILE}. Reinitializing...")
        raw_settings = {}
else:
    raw_settings = {}

# Deserialize datetime strings back to datetime objects
for guild_id, settings in raw_settings.items():
    hunting_ground = settings.get("hunting_ground")
    if hunting_ground and "last_spawn" in hunting_ground:
        hunting_ground["last_spawn"] = datetime.fromisoformat(hunting_ground["last_spawn"])

channel_settings = raw_settings

shutil.copy(CHANNEL_SETTINGS_FILE, CHANNEL_SETTINGS_FILE + ".backup")

def save_channel_settings():
    """Save the channel settings to the file, creating it if necessary."""
    def serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    with open(CHANNEL_SETTINGS_FILE, "w") as f:
        json.dump(channel_settings, f, indent=4, default=serialize)



# Load gold data or initialize if file does not exist
if os.path.exists(GOLD_FILE):
    with open(GOLD_FILE, "r") as f:
        gold_data = json.load(f)
else:
    gold_data = {}

def save_gold_data():
    """Save the current gold data to the JSON file."""
    with open(GOLD_FILE, "w") as f:
        json.dump(gold_data, f, indent=4)

# Load or initialize command locks
if os.path.exists(COMMAND_LOCKS_FILE):
    with open(COMMAND_LOCKS_FILE, "r") as f:
        command_locks = json.load(f)
else:
    command_locks = {}

# admin id check thingy
def is_admin(user_id):
    return user_id in ADMIN_IDS

#more admin check thingies
# Function to add an admin (if needed later)
def add_admin(user_id):
    ADMIN_IDS.add(user_id)
    os.environ["ADMIN_IDS"] = ",".join(map(str, ADMIN_IDS))  # Update .env if necessary

# Function to remove an admin (if needed later)
def remove_admin(user_id):
    ADMIN_IDS.discard(user_id)
    os.environ["ADMIN_IDS"] = ",".join(map(str, ADMIN_IDS))  # Update .env if necessary

# Save command locks function
def save_command_locks():
    with open(COMMAND_LOCKS_FILE, "w") as f:
        json.dump(command_locks, f, indent=4)

# Ensure image folder exists
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# Load characters from file if it exists
if os.path.exists(CHARACTERS_FILE):
    with open(CHARACTERS_FILE, 'r') as f:
        characters = json.load(f)
else:
    characters = {}

# Sync the slash commands with Discord
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')

# Update the save_characters function
def save_characters():
    with open(CHARACTERS_FILE, 'w') as f:
        json.dump(characters, f, indent=4)

# Ensure default attributes are set when loading characters
if os.path.exists(CHARACTERS_FILE):
    with open(CHARACTERS_FILE, 'r') as f:
        characters = json.load(f)
        # Add missing attributes to existing characters
        for char_data in characters.values():
            if "status" not in char_data:
                char_data["status"] = "Alive"
else:
    characters = {}
 
# Check if a command is locked
def is_command_locked(command_name):
    return command_locks.get(command_name, False)

def validate_image_urls():
    invalid_characters = []
    for name, char in characters.items():
        for url in char.get("images", []):
            if not url or not url.startswith("http"):
                invalid_characters.append(name)
                break  # Stop checking further URLs for this character
    return invalid_characters

# Example usage:
invalid_characters = validate_image_urls()
if invalid_characters:
    print(f"Characters with invalid image URLs: {', '.join(invalid_characters)}")
else:
    print("All characters have valid image URLs.")

# Decorator to enforce command lock
def check_admin_lock(command_name):
    async def predicate(interaction: discord.Interaction):
        if is_command_locked(command_name) and not is_admin(interaction.user.id):
            await interaction.response.send_message("This command is locked for admins only.", ephemeral=True)
            return False
        return True
    return commands.check(predicate)

#-------%%%%%%%%%%%%%%% THE START OF ALL COMMANDS/ COMMAND LIST/ COMMANDS %%%%%%%%-------------##############

#=-----------------------KILL AND RESSURECT COMMAND-------------------------#
@bot.tree.command(name="kill", description="Change a character's status to deceased and specify the cause of death.")
@check_admin_lock("kill")
async def kill_character(interaction: discord.Interaction, character_name: str, how: str):
    """
    Mark a character as deceased and save the cause of death.
    
    Args:
        interaction: The interaction object from Discord.
        character_name: The name of the character to mark as deceased.
        how: A description of how the character died (cause of death).
    """
    # Check if the character exists
    character = characters.get(character_name)
    if not character:
        await interaction.response.send_message(f"Character '{character_name}' not found.", ephemeral=True)
        return

    # Update the character's status and cause of death
    character["status"] = "Deceased 💀"
    character["cause_of_death"] = how  # Add the cause of death
    save_characters()

    await interaction.response.send_message(f"💀 The character '{character_name}' has been marked as deceased. Cause of death: {how}")


@bot.tree.command(name="revive", description="Change a character's status to alive.")
@check_admin_lock("revive")
async def resurrect_character(interaction: discord.Interaction, character_name: str):
    # Check if the character exists
    character = characters.get(character_name)
    if not character:
        await interaction.response.send_message(f"Character '{character_name}' not found.", ephemeral=True)
        return

    # Update the character's status
    character["status"] = "Alive"
    save_characters()

    await interaction.response.send_message(f"The character '{character_name}' has been resurrected and is now alive.")

#------------------ADMIN RELATED COMMANDS-------------------------#

# Admin lock and unlock slash command
@bot.tree.command(name="adminlock", description="Lock a command for admins only.")
async def admin_lock(interaction: discord.Interaction, command_name: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to lock commands.", ephemeral=True)
        return

    command_locks[command_name] = True
    save_command_locks()
    await interaction.response.send_message(f"The command '{command_name}' has been locked for admins only.", ephemeral=True)

@bot.tree.command(name="adminunlock", description="Unlock a command for everyone.")
async def admin_unlock(interaction: discord.Interaction, command_name: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to unlock commands.", ephemeral=True)
        return

    command_locks[command_name] = False
    save_command_locks()
    await interaction.response.send_message(f"The command '{command_name}' has been unlocked for everyone.", ephemeral=True)

# Slash Command to upload a new character
@bot.tree.command(name="upload", description="Upload a new character (name, description, side note, and optional image).")
@check_admin_lock("upload")
async def upload_character(interaction: discord.Interaction, name: str, description: str, 
                           side_note: str = "No side note provided.", imageurl: str = None, 
                           imagefile: discord.Attachment = None):
    """Upload a character with name, description, side note, and optional image (URL or file)."""
    
    # Ensure the character doesn't already exist
    if name.lower() in [char.lower() for char in characters]:
        await interaction.response.send_message(f"A character named '{name}' already exists!")
        return
    
    # Handle image URL if provided
    character_images = []
    
    if imageurl:
        if imageurl.startswith("http"):  # Validate that it's a URL
            character_images.append(imageurl)
        else:
            await interaction.response.send_message("Please provide a valid image URL.", ephemeral=True)
            return

    # Handle image file attachment if provided
    if imagefile:
        # Get the image file URL (attachment provided by Discord)
        image_url = imagefile.url  # The bot can access the URL of the uploaded image
        character_images.append(image_url)
    
    # Create the character data and add it
    characters[name] = {
        "description": description,
        "side_note": side_note,  # Add the side note
        "images": character_images,
        "status": "Alive",
        "owner": None
    }
    
    save_characters()  # Save to the file

    # Send confirmation message
    await interaction.response.send_message(f"Character '{name}' uploaded successfully!")



    
#Change info for a character
@bot.tree.command(name="changeinfo", description="Change info for an existing character.")
@check_admin_lock("changeinfo")
async def changeinfo(interaction: discord.Interaction, character_name: str, new_name: str = None, new_info: str = None, new_side_note: str = None, new_images: str = None):
    """Change a character's name, description, side note, or images."""
    
    # Check if the character exists
    if character_name not in characters:
        await interaction.response.send_message(f"Character '{character_name}' not found.", ephemeral=True)
        return

    # Get the character's data
    character_data = characters.pop(character_name)  # Remove the old entry

    # Update the character's name if provided
    if new_name:
        character_data['name'] = new_name  # Update the 'name' field
        # Add the character back with the new name as the key
        characters[new_name] = character_data
    else:
        # If no new name is provided, keep the original character_name
        characters[character_name] = character_data

    # Update the character's description (info)
    if new_info:
        characters[new_name if new_name else character_name]['description'] = new_info

    # Update the character's side note if provided
    if new_side_note:
        characters[new_name if new_name else character_name]['side_note'] = new_side_note

    # Update the character's images if provided
    if new_images:
        character_images = []
        image_urls = new_images.split()  # Split images by spaces for multiple URLs
        
        for url in image_urls:
            if url.startswith("http"):  # If it's a URL
                character_images.append(url)
            else:
                # Assume it's a local file (uploaded via Discord)
                try:
                    attachment = await interaction.message.attachments[0].read()
                    file_path = os.path.join(IMAGE_FOLDER, f"{new_name if new_name else character_name}_{len(character_images)}.png")
                    with open(file_path, 'wb') as f:
                        f.write(attachment)
                    character_images.append(file_path)  # Store the file path
                except Exception as e:
                    await interaction.response.send_message(f"Error saving image file: {e}", ephemeral=True)
                    return
        
        # Set the new images for the character
        characters[new_name if new_name else character_name]['images'] = character_images

    # Save the updated character data to the file
    save_characters()

    # Send confirmation message
    updated_name = new_name if new_name else character_name  # Use character_name directly if no new_name is provided
    update_message = f"Character '{updated_name}' has been updated."

    if new_info:
        update_message += f"\nNew Description: {new_info}"
    if new_side_note:
        update_message += f"\nNew Side Note: {new_side_note}"
    if new_images:
        update_message += f"\nNew Images: {', '.join(new_images.split())}"

    await interaction.response.send_message(update_message)



# Slash Command to list all characters
@bot.tree.command(name="list", description="List all uploaded characters with their statuses.")
@check_admin_lock("list")
async def list_characters(interaction: discord.Interaction):
    """
    List all characters in chunks, ensuring message length does not exceed 2000 characters.
    """
    if not characters:
        await interaction.response.send_message("No characters uploaded yet.")
        return

    # Sort characters alphabetically
    sorted_characters = sorted(characters.items(), key=lambda x: x[0].lower())

    # Prepare character details
    character_list = [
        f"{i+1}. {name} {'💀' if char.get('status', 'Alive') == 'Deceased 💀' else ''}"
        for i, (name, char) in enumerate(sorted_characters)
    ]

    # Chunk the character list to fit within Discord's 2000 character limit
    chunk_size = 50  # Adjust as needed based on average character size
    chunks = [
        "\n".join(character_list[i:i + chunk_size])
        for i in range(0, len(character_list), chunk_size)
    ]

    # Send the chunks as multiple messages
    for i, chunk in enumerate(chunks):
        embed = discord.Embed(
            title=f"Character List (Part {i+1}/{len(chunks)})",
            description=chunk,
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed)

    # Confirm completion of the list command
    await interaction.response.send_message(
        f"Character list has been posted in {len(chunks)} parts.", ephemeral=True
    )


    

# Slash Command to delete a character
@bot.tree.command(name="delete", description="Delete a character.")
@check_admin_lock("delete")
async def delete_character(interaction: discord.Interaction, name: str):
    """Delete an existing character."""
    
    # Find the character (case-insensitive lookup)
    character = None
    for char_name in characters:
        if char_name.lower() == name.lower():
            character = characters[char_name]
            break
    
    if not character:
        await interaction.response.send_message(f"Character '{name}' not found.")
        return

    # Delete the character and save
    del characters[char_name]
    save_characters()
    
    await interaction.response.send_message(f"Character '{name}' has been deleted.")

# Slash command for dice rolling and picking

@bot.tree.command(name="roll", description="Roll a dice with a specified number of sides.")
@check_admin_lock("roll")
async def roll_dice(interaction: discord.Interaction, sides: int = 6):
    """Roll a die with a given number of sides (default is 6)."""
    if sides < 1:
        await interaction.response.send_message("The number of sides must be at least 1.")
        return
    
    result = random.randint(1, sides)  # Roll the die
    await interaction.response.send_message(f"You rolled a {result} on a {sides}-sided die.")
    
@bot.tree.command(name="pick", description="Pick a random option from a list of options with a prompt.")
@check_admin_lock("pick")
async def pick_option(interaction: discord.Interaction, prompt: str, option1: str, option2: str, option3: str = None, 
                      option4: str = None, option5: str = None, option6: str = None, 
                      option7: str = None, option8: str = None, option9: str = None, option10: str = None):
    """Choose randomly between the given options (up to 10) with a prompt."""
    
    # Collect all provided options (filter out None values)
    options = [option for option in [option1, option2, option3, option4, option5, 
                                     option6, option7, option8, option9, option10] if option]
    
    # Ensure that at least one option is provided and no more than 10
    if len(options) < 1 or len(options) > 10:
        await interaction.response.send_message("Please provide between 1 and 10 options.")
        return
    
    # Randomly choose one option
    chosen_option = random.choice(options)

    # Format the options list for display
    options_list = "\n".join([f"{i+1}. {option}" for i, option in enumerate(options)])

    # Send the response showing the prompt, available options, and the randomly picked one
    await interaction.response.send_message(
        f"**Question:** {prompt}\n\n**Options:**\n{options_list}\n\n**Fate has chosen:** {chosen_option}")

    
# Slash command to view which commands are admin locked or not

@bot.tree.command(name="adminlist", description="View bot admins and command lock statuses.")
async def admin_list(interaction: discord.Interaction):
    # Check if the user is an admin
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to view admin details.", ephemeral=True)
        return

    # Get list of admins
    admin_list = "\n".join([f"- <@{admin_id}>" for admin_id in ADMIN_IDS]) or "No admins configured."

    # Get command lock statuses
    if command_locks:
        lock_status = "\n".join(
            [f"- {command}: {'🔒 Locked' if status else '🔓 Unlocked'}" for command, status in command_locks.items()]
        )
    else:
        lock_status = "No commands have been locked yet."

    # Prepare response
    response = (
        "**🔧 Bot Admins:**\n"
        f"{admin_list}\n\n"
        "**🔒 Command Lock Statuses:**\n"
        f"{lock_status}"
    )

    await interaction.response.send_message(response, ephemeral=True)

#------------------SPAWN CHARACTER COMMAND---------------------#

# Spawn a random character with image navigation
# Spawn a random character with image navigation
@bot.tree.command(name="spawn", description="Spawn a random unclaimed character.")
@check_admin_lock("spawn")
async def spawn_character(interaction: discord.Interaction):
    """Spawn a random character for claiming with image navigation."""
    import random

    # Defer the interaction to avoid timeout issues
    await interaction.response.defer(thinking=True)

    # Filter characters that are unclaimed and alive
    unclaimed_characters = {
        name: char for name, char in characters.items()
        if ("owner" not in char or char["owner"] is None) and char.get("status") == "Alive"
    }

    if not unclaimed_characters:
        await interaction.followup.send("No unclaimed alive characters are available!", ephemeral=True)
        return

    # Choose a random unclaimed character
    name, character = random.choice(list(unclaimed_characters.items()))
    description = character.get("description", "No description available.")
    images = character.get("images", [])
    images = ' '.join(images).split() 
    side_note = character.get("side_note", "No side note provided.")

    # Double-check the character is unclaimed before continuing
    if character.get("owner"):
        await interaction.followup.send(
            f"An error occurred: {name} is already claimed. Please try again.",
            ephemeral=True
        )
        return

    # Send an initial spawning message
    spawning_message = await interaction.followup.send(
        "Spawning a character...", ephemeral=True  # Temporary message
    )

    # Initialize image navigation variables
    current_index = 0
    total_images = len(images)

    # Create an embed with character details
    embed = discord.Embed(
        title=name,
        description=f"{description}\n\n"
        f"Side Note: {side_note}\n\n"
        f"Unclaimed",
        color=discord.Color.green()
    )

    # Check if there are valid image URLs
    if images:
        try:
            # Get the first valid image URL
            character_image = None
            for image_url in images:
                # Log the current URL for debugging purposes
                print(f"Checking image URL for {name}: {image_url}")

                # Ensure the URL is a valid HTTP URL
                
                character_image = image_url
                break
 # Replace with an actual default image

            embed.set_image(url=character_image)
            embed.set_footer(text=f"Image {current_index + 1}/{total_images}")
        except Exception as e:
            # Log the error for debugging with character name and problematic URL
            print(f"Error while setting image for character '{name}': {str(e)}")
            await interaction.followup.send(
                f"An error occurred with the image URL for '{name}'. Please check the logs.",
                ephemeral=True
            )
            return

    # Send the main message (non-ephemeral, so others can interact)
    message = await interaction.followup.send(embed=embed)

    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")
    await message.add_reaction("✨")  # Reaction for claiming the character

    # Delete the "Spawning a character..." message
    await spawning_message.delete()

    def check(reaction, user):
        return (
            user != bot.user
            and str(reaction.emoji) in ["⬅️", "➡️", "✨"]
            and reaction.message.id == message.id
        )

    try:
        while True:
            # Wait for a reaction (navigation or claim)
            reaction, user = await bot.wait_for("reaction_add", check=check, timeout=600.0)

            if str(reaction.emoji) == "⬅️" and images:
                # Navigate to the previous image
                current_index = (current_index - 1) % total_images
            elif str(reaction.emoji) == "➡️" and images:
                # Navigate to the next image
                current_index = (current_index + 1) % total_images
            elif str(reaction.emoji) == "✨":
                # Handle character claiming
                if character.get("owner"):
                    await interaction.followup.send(
                        f"{name} is already claimed by <@{character['owner']}>.",
                        ephemeral=True
                    )
                    continue

                # Mark the character as claimed
                character["owner"] = user.id
                save_characters()  # Save ownership changes to file
                await interaction.followup.send(
                    f"{name} is now claimed by <@{user.id}>!",
                    ephemeral=False
                )
                break  # Exit the loop after claiming the character

            # Update the embed with the new image and footer
            if images:
                embed.set_image(url=images[current_index])
                embed.set_footer(text=f"Image {current_index + 1}/{total_images}")
            await message.edit(embed=embed)

            # Remove the user's reaction
            await message.remove_reaction(reaction.emoji, user)

    except asyncio.TimeoutError:
        await message.clear_reactions()




#----------------------VIEW CHARACTER COMMAND------------------------------------------------------#


@bot.tree.command(name="view", description="View a character's details and images.")
@check_admin_lock("view")
async def view_character(interaction: discord.Interaction, name: str):
    """
    View a character's details and navigate through images.
    """
    # Retrieve the character from the data
    character = characters.get(name)
    if not character:
        await interaction.response.send_message(f"Character '{name}' not found.", ephemeral=True)
        return

    # Extract character details
    owner = character.get("owner", None)
    description = character.get("description", "No description available.")
    side_note = character.get("side_note", "No side note provided.")
    images = character.get("images", [])
    status = character.get("status", "Alive")
    cause_of_death = character.get("cause_of_death", None)

    # Validate and clean image paths
    validated_images = []
    local_files = {}  # For storing local files that need to be attached
    for img_entry in images:
        for img in img_entry.split():  # Split multiple URLs separated by spaces or newlines
            if img.startswith("http"):  # Public URL
                validated_images.append(img)
            elif os.path.isfile(img):  # Local file
                file_name = os.path.basename(img)
                validated_images.append(f"attachment://{file_name}")  # For inline image in embed
                local_files[file_name] = img  # Store file path for later attachment

    if not validated_images:
        await interaction.response.send_message(f"Character '{name}' has no valid images to display.", ephemeral=True)
        return

    # Prepare embed details
    owner_text = f"Owned by: <@{owner}>" if owner else "Available"
    death_text = f"**Cause of Death:** {cause_of_death}" if status == "Deceased 💀" and cause_of_death else ""
    current_index = 0
    total_images = len(validated_images)

    # Create an embed with the first image
    embed = discord.Embed(
        title=name,
        description=(f"{owner_text}\n\n{description}\n\nSide Note: {side_note}\n\nStatus: {status}\n{death_text}"),
        color=discord.Color.blue()
    )
    embed.set_image(url=validated_images[current_index])
    embed.set_footer(text=f"Image {current_index + 1}/{total_images}")

    # Prepare local files to be sent as attachments (used for embed)
    files = [discord.File(path, filename=file_name) for file_name, path in local_files.items()]

    # Send the embed with attachments only if there are local files; otherwise, just the embed
    if files:
        await interaction.response.send_message(embed=embed, files=files)  # Send both embed and files
    else:
        await interaction.response.send_message(embed=embed)  # Send only embed

    message = await interaction.original_response()

    # Add reactions for navigation if there are multiple images
    if total_images > 1:
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")

        def check(reaction, user):
            # Allow anyone to react (not just the user who invoked /view)
            return (
                user != bot.user and
                str(reaction.emoji) in ["⬅️", "➡️"] and
                reaction.message.id == message.id
            )

        try:
            while True:
                reaction, user = await bot.wait_for("reaction_add", check=check, timeout=60.0)

                if str(reaction.emoji) == "⬅️":
                    current_index = (current_index - 1) % total_images
                elif str(reaction.emoji) == "➡️":
                    current_index = (current_index + 1) % total_images

                # Update the embed with the new image
                embed.set_image(url=validated_images[current_index])
                embed.set_footer(text=f"Image {current_index + 1}/{total_images}")
                await message.edit(embed=embed)

                # Remove the user's reaction to allow further input
                await message.remove_reaction(reaction.emoji, user)
        except asyncio.TimeoutError:
            await message.clear_reactions()


@view_character.autocomplete("name")
async def view_character_autocomplete(interaction: discord.Interaction, current: str):
    """
    Autocomplete function to suggest character names based on user input.
    """
    # List all character names that start with the current input (case-insensitive)
    suggestions = [name for name in characters if name.lower().startswith(current.lower())]
    # Send the suggestions to the autocomplete menu
    return [app_commands.Choice(name=char_name, value=char_name) for char_name in suggestions]



#--------------------Release Command------------------------------#



@bot.tree.command(name="release", description="Release ownership of a claimed character.")
@check_admin_lock("release")
async def release_character(interaction: discord.Interaction, character_name: str):
    """Release ownership of a claimed character."""
    # Defer the response to avoid timeout
    await interaction.response.defer(thinking=True)

    # Check if the character exists
    character = characters.get(character_name)
    if not character:
        await interaction.followup.send(
            f"The character '{character_name}' does not exist in the system.",
            ephemeral=True
        )
        return

    # Check if the character is claimed
    if not character.get("owner"):
        await interaction.followup.send(
            f"The character '{character_name}' is not currently claimed by anyone.",
            ephemeral=True
        )
        return

    # Check if the user is the owner
    if character["owner"] != interaction.user.id:
        await interaction.followup.send(
            f"You do not own '{character_name}', so you cannot release it.",
            ephemeral=True
        )
        return

    # Release ownership
    character["owner"] = None
    save_characters()  # Save changes to file
    await interaction.followup.send(
        f"You have successfully released ownership of '{character_name}'.",
        ephemeral=False
    )



#------------------------LIST ALL COMMANDS-----------------#
# List all commands
@bot.tree.command(name="list_commands", description="List all commands.")
async def list_commands(interaction: discord.Interaction):
    commands = [cmd.name for cmd in bot.tree.get_commands()]
    await interaction.response.send_message(f"Registered commands: {', '.join(commands)}")
    
#----GUIDE TO USE BOT LATEST 19/11/2024------------#
@bot.tree.command(name="guide", description="Get a guide on how to use the bot.")
async def guide(interaction: discord.Interaction):
    guide_text = """
    **Guide to Using the Bot**

    **Character Management:**
    - `/upload`: Upload a new character (name, description, and optional images).
    - `/view`: View details of a character.
    - `/changeinfo`: Update a character's name or description.
    - `/list`: List all characters and their statuses.
    - `/delete`: Delete a character (admins only).

    **Character Status:**
    - `/kill`: Mark a character as deceased.
    - `/revive`: Revive a character back to alive.
    - `/spawn`: Spawn a random unclaimed character (alive only).

    **Ownership Commands:**
    - `/release`: Release ownership of a claimed character.

    **Utility Commands:**
    - `/roll`: Roll a dice (default 6 sides).
    - `/pick`: Randomly pick an option from a list.
    - `/list_commands`: List all available commands.

    **Admin Commands:**
    - `/adminlock`: Lock a command for admin use only.
    - `/adminunlock`: Unlock a command for everyone.
    - `/adminlist`: View admins and lock statuses.

    **Last Updated on 19 November 2024**
    """
    await interaction.response.send_message(guide_text, ephemeral=True)
    
#-----------------------GOLD RELATED COMMANDS--------------------------#
@bot.tree.command(name="addgold", description="Add gold to your balance.")
@check_admin_lock("addgold")
async def add_gold(interaction: discord.Interaction, amount: int):
    """Add a specified amount of gold to the user's balance."""
    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    gold_data[user_id] = gold_data.get(user_id, 0) + amount
    save_gold_data()

    await interaction.response.send_message(f"💰 {amount} gold has been added to your balance. Total: {gold_data[user_id]} gold.")

@bot.tree.command(name="deletegold", description="Delete gold from your balance.")
@check_admin_lock("deletegold")
async def delete_gold(interaction: discord.Interaction, amount: int):
    """Remove a specified amount of gold from the user's balance."""
    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    current_balance = gold_data.get(user_id, 0)

    if current_balance < amount:
        await interaction.response.send_message(f"You don't have enough gold! Current balance: {current_balance} gold.", ephemeral=True)
        return

    gold_data[user_id] -= amount
    save_gold_data()

    await interaction.response.send_message(f"❌ {amount} gold has been removed from your balance. Remaining: {gold_data[user_id]} gold.")

@bot.tree.command(name="balance", description="Check your gold balance.")
async def check_balance(interaction: discord.Interaction):
    """Check the user's gold balance."""
    user_id = str(interaction.user.id)
    balance = gold_data.get(user_id, 0)

    await interaction.response.send_message(f"💰 You currently have {balance} gold.")
@bot.tree.command(name="givegold", description="Give gold to another user.")
@check_admin_lock("givegold")
async def give_gold(interaction: discord.Interaction, recipient: discord.Member, amount: int):
    """Transfer a specified amount of gold to another user."""
    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    sender_id = str(interaction.user.id)
    recipient_id = str(recipient.id)

    if sender_id == recipient_id:
        await interaction.response.send_message("You cannot give gold to yourself.", ephemeral=True)
        return

    sender_balance = gold_data.get(sender_id, 0)

    if sender_balance < amount:
        await interaction.response.send_message(f"You don't have enough gold to give! Current balance: {sender_balance} gold.", ephemeral=True)
        return

    # Transfer gold
    gold_data[sender_id] = sender_balance - amount
    gold_data[recipient_id] = gold_data.get(recipient_id, 0) + amount
    save_gold_data()

    await interaction.response.send_message(f"✅ You have given {amount} gold to {recipient.mention}. Remaining balance: {gold_data[sender_id]} gold.")
    
#--------Graveyard command and Graveyard Related ---------#

@bot.tree.command(name="setgraveyard", description="Set a channel to display deceased characters.")
@commands.has_permissions(administrator=True)
async def set_graveyard(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the graveyard channel for the guild."""
    guild_id = str(interaction.guild_id)

    if guild_id not in channel_settings:
        channel_settings[guild_id] = {}

    # Save the graveyard channel ID
    channel_settings[guild_id]["graveyard_channel"] = channel.id
    save_channel_settings()

    await interaction.response.send_message(f"✅ The graveyard channel has been set to {channel.mention}.", ephemeral=True)

    
async def update_graveyard():
    """Periodic task to update the graveyard channel."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        for guild_id, channels in channel_settings.items():
            graveyard_channel_id = channels.get("graveyard_channel")
            if graveyard_channel_id:
                channel = bot.get_channel(graveyard_channel_id)

                if channel:
                    # Collect all deceased characters
                    deceased_characters = sorted(
                        [name for name, char in characters.items() if char.get("status") == "Deceased 💀"]
                    )
                    if deceased_characters:
                        character_list = "\n".join([f"💀 {name}" for name in deceased_characters])
                        content = f"**Graveyard of Deceased Characters:**\n{character_list}"
                    else:
                        content = "**Graveyard of Deceased Characters:**\nNo deceased characters yet."

                    # Find the latest bot message in the channel to edit
                    async for message in channel.history(limit=10):
                        if message.author == bot.user and message.content.startswith("**Graveyard"):
                            await message.edit(content=content)
                            break
                    else:
                        # No message found; send a new one
                        await channel.send(content)

        await asyncio.sleep(7)  # Update every 2 seconds





#-----------------------Character List Settings Command-------------#

# Global variable to track message IDs for live updates
character_list_messages = {}  # Format: {guild_id: [message_id_1, message_id_2, ...]}

@bot.tree.command(name="setcharacterlist", description="Set a channel to display all characters with their statuses.")
@commands.has_permissions(administrator=True)
async def set_characterlist(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Set the character list channel for the guild.
    """
    guild_id = str(interaction.guild_id)

    if guild_id not in channel_settings:
        channel_settings[guild_id] = {}

    # Save the character list channel ID
    channel_settings[guild_id]["characterlist_channel"] = channel.id
    save_channel_settings()

    # Reset tracked messages for this guild (new channel means new posts)
    character_list_messages[guild_id] = []

    await interaction.response.send_message(f"✅ The character list channel has been set to {channel.mention}.", ephemeral=True)


async def update_character_list():
    """
    Periodic task to update the character list channel with messages split into chunks of 50 characters.
    """
    await bot.wait_until_ready()

    while not bot.is_closed():
        for guild_id, channels in channel_settings.items():
            characterlist_channel_id = channels.get("characterlist_channel")
            if characterlist_channel_id:
                channel = bot.get_channel(characterlist_channel_id)

                if channel:
                    # Build the character list in chunks of 50
                    sorted_characters = sorted(characters.items(), key=lambda x: x[0].lower())
                    chunks = []
                    chunk = []
                    for i, (name, char) in enumerate(sorted_characters, start=1):
                        status = char.get("status", "Alive")
                        owner_id = char.get("owner")
                        owner_text = f" (Owned by <@{owner_id}>)" if owner_id else ""
                        if status == "Deceased 💀":
                            chunk.append(f"{i}. 💀 {name}")
                        elif owner_id:
                            chunk.append(f"{i}. 🔒 {name}{owner_text}")
                        else:
                            chunk.append(f"{i}. 🌿 {name}")

                        # Split into a new chunk every 50 characters
                        if len(chunk) >= 50:
                            chunks.append("\n".join(chunk))
                            chunk = []

                    # Add any remaining characters in the last chunk
                    if chunk:
                        chunks.append("\n".join(chunk))

                    # Retrieve or initialize message tracking for the guild
                    if guild_id not in character_list_messages:
                        character_list_messages[guild_id] = []

                    # Update or create messages for each chunk
                    for i, chunk_content in enumerate(chunks):
                        if i < len(character_list_messages[guild_id]):
                            # Edit existing messages
                            message_id = character_list_messages[guild_id][i]
                            try:
                                message = await channel.fetch_message(message_id)
                                await message.edit(content=f"**All Characters (Part {i+1}):**\n{chunk_content}")
                            except discord.NotFound:
                                # If the message was deleted, create a new one
                                message = await channel.send(f"**All Characters (Part {i+1}):**\n{chunk_content}")
                                character_list_messages[guild_id][i] = message.id
                        else:
                            # Create new messages if needed
                            message = await channel.send(f"**All Characters (Part {i+1}):**\n{chunk_content}")
                            character_list_messages[guild_id].append(message.id)

                    # Remove extra messages if chunks decreased
                    while len(character_list_messages[guild_id]) > len(chunks):
                        message_id = character_list_messages[guild_id].pop()
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.delete()
                        except discord.NotFound:
                            # Message was already deleted; ignore
                            pass

        await asyncio.sleep(10)  # Update every 10 seconds


@bot.event
async def on_ready():
    """
    Start all periodic tasks when the bot is ready.
    """
    bot.loop.create_task(update_character_list())
    print(f"Logged in as {bot.user}")



#------------------Setting a Hunting Ground-------------------------#

@bot.tree.command(
    name="sethuntingground",
    description=
    "Set a hunting ground in a channel with a spawn interval (in seconds).")
@commands.has_permissions(administrator=True)
async def set_hunting_ground(interaction: discord.Interaction,
                             channel: discord.TextChannel, interval: int):
    """
    Set a hunting ground in the specified channel with the given interval in seconds.
    """
    guild_id = str(interaction.guild_id)

    # Ensure the guild has an entry in channel_settings
    if guild_id not in channel_settings:
        channel_settings[guild_id] = {}

    # Save the hunting ground details
    channel_settings[guild_id]["hunting_ground"] = {
        "channel_id": channel.id,
        "interval": interval
    }
    save_channel_settings()  # Save to the file

    await interaction.response.send_message(
        f"✅ Hunting ground set in {channel.mention} with an interval of {interval} seconds.",
        ephemeral=True)


async def update_hunting_grounds():
    """Continuously post characters to hunting ground channels at their specified intervals."""
    await bot.wait_until_ready()

    while not bot.is_closed():
        now = datetime.now(timezone.utc)  # Current time

        for guild_id, settings in channel_settings.items():
            hunting_ground = settings.get("hunting_ground")
            if not hunting_ground:
                continue

            # Extract details
            channel_id = hunting_ground["channel_id"]
            interval = hunting_ground["interval"]
            last_spawn = hunting_ground.get("last_spawn",
                                            now - timedelta(seconds=interval))

            # Check if it's time to post
            if (now - last_spawn).total_seconds() >= interval:
                await post_character_to_channel(channel_id)

                # Update the last_spawn time in memory and save
                hunting_ground["last_spawn"] = now
                save_channel_settings()  # Persist this update to the file

        await asyncio.sleep(1)  # Check every second


async def post_character_to_channel(channel_id):
    """Spawn a random unclaimed character in the specified channel."""
    channel = bot.get_channel(channel_id)
    if not channel:
        return  # Channel no longer exists, skip it

    # Filter unclaimed, alive characters
    unclaimed_characters = {
        name: char
        for name, char in characters.items()
        if ("owner" not in char or char["owner"] is None)
        and char.get("status") == "Alive"
    }

    if not unclaimed_characters:
        await channel.send("No unclaimed alive characters are available!")
        return

    # Choose a random unclaimed character
    name, character = random.choice(list(unclaimed_characters.items()))
    description = character.get("description", "No description available.")
    images = character.get("images", [])
    images = ' '.join(images).split() 
    side_note = character.get("side_note", "No side note provided.")

    # Create an embed for the character
    embed = discord.Embed(title=name,
                          description=f"{description}\n\n{side_note}",
                          color=discord.Color.green())
    if images:
        embed.set_image(url=images[0])  # Show the first image if available
        embed.set_footer(text=f"Image 1/{len(images)}")

    # Send the embed to the channel
    message = await channel.send(embed=embed)

    # Add reactions for interaction
    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")
    await message.add_reaction("✨")  # Reaction for claiming

    # Handle reactions in a separate task
    bot.loop.create_task(handle_reactions(message, name, character, images))


async def handle_reactions(message, name, character, images):
    """Handle reactions for navigating images or claiming the character."""
    current_index = 0
    total_images = len(images)

    def check(reaction, user):
        return (user != bot.user and str(reaction.emoji) in ["⬅️", "➡️", "✨"]
                and reaction.message.id == message.id)

    try:
        while True:
            reaction, user = await bot.wait_for("reaction_add",
                                                check=check,
                                                timeout=60000.0)

            if str(reaction.emoji) == "⬅️" and images:
                current_index = (current_index - 1) % total_images
            elif str(reaction.emoji) == "➡️" and images:
                current_index = (current_index + 1) % total_images
            elif str(reaction.emoji) == "✨" and ("owner" not in character or
                                                 character["owner"] is None):
                # Mark as claimed and save
                character["owner"] = user.id
                save_characters()
                await message.channel.send(
                    f"{name} is now claimed by <@{user.id}>!")
                break  # Exit after claiming

            # Update embed with new image
            if images:
                embed = message.embeds[0]
                embed.set_image(url=images[current_index])
                embed.set_footer(
                    text=f"Image {current_index + 1}/{total_images}")
                await message.edit(embed=embed)

            # Remove user's reaction
            await message.remove_reaction(reaction.emoji, user)

    except asyncio.TimeoutError:
        await message.clear_reactions()
        
#--------------------Quick Upload0-----------------#


#Removed#


#----------------------------------# IMAGE SEARCHING COMMAND GIMAGE #-----------------------------#

#No longer required

#-------------------------ADD PIC COMMAND FOR CONVINENICEN ADDPIC--------------------#

@bot.tree.command(name="addpic", description="Add specific images to a character using a search query.")
async def add_pic(interaction: discord.Interaction, character: str, query: str, number: int = 1):
    """
    Add specific images to a character using SerpAPI image search.

    Args:
        interaction: The Discord interaction object.
        character (str): The name of the character to add images to.
        query (str): Search query for the images.
        number (int): The number of images to add (default is 1).
    """
    # Validate number of images
    if number < 1 or number > 10:
        await interaction.response.send_message(
            "Please specify a number between 1 and 10.", ephemeral=True
        )
        return

    # Check if the character exists
    char_data = characters.get(character)
    if not char_data:
        await interaction.response.send_message(
            f"Character '{character}' not found.", ephemeral=True
        )
        return

    # Use SerpAPI to fetch images
    search_url = "https://google.serper.dev/images"
    payload = {"q": query}
    headers = {
        "X-API-KEY": os.getenv("SERPAPI_API_KEY"),
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(search_url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            images = data.get("images", [])
            image_urls = [
                img["imageUrl"]
                for img in images
                if img["imageUrl"].endswith((".png", ".jpg", ".jpeg"))
            ]

            if image_urls:
                # Add the images to the character
                selected_urls = random.sample(image_urls, min(number, len(image_urls)))
                char_data.setdefault("images", []).extend(selected_urls)
                save_characters()  # Save the updated character data

                await interaction.response.send_message(
                    f"Added {len(selected_urls)} image(s) to '{character}' from query '{query}'.\n" +
                    "\n".join(selected_urls)
                )
            else:
                await interaction.response.send_message("No valid image URLs found.")
        else:
            await interaction.response.send_message(
                f"Failed to fetch images. Status code: {response.status_code}.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred while fetching images: {e}", ephemeral=True
        )

#-------------------WIKIPEDIA COMMAND-----------------------------------#
import aiohttp

@bot.tree.command(name="wikipedia", description="Fetch a brief description from Wikipedia.")
async def wikipedia_description(interaction: discord.Interaction, name: str):
    """
    Fetch a brief description of a topic from Wikipedia.
    
    Args:
        interaction: The interaction object from Discord.
        name: The name of the topic to search for.
    """
    await interaction.response.defer()  # Defer response to avoid timeout

    async def get_description(name: str):
        try:
            async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0'}) as session:
                async with session.get('https://en.wikipedia.org/wiki/' + name.replace(' ', '_')) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.text()
                    data = data[data.find('<p>'):]
                    data = data[:data.find('</p>')]
                    data = data.replace('&#91;', '[').replace('&#93;', ']')
                    text = ''
                    waiting_on = None
                    for c in data:
                        if not waiting_on:
                            if c == '<':
                                waiting_on = '>'
                            elif c == '&':
                                waiting_on = ';'
                            elif c == '(':
                                text = text.strip()
                                waiting_on = ')'
                            elif c == '[':
                                waiting_on = ']'
                            else:
                                text += c
                        elif c == waiting_on:
                            waiting_on = None
                    text = ' '.join(text.split())
                    if text.endswith(' may refer to:'):
                        return None
                    return text
        except Exception:
            return None

    description = await get_description(name)
    if description:
        await interaction.followup.send(f"**Wikipedia Summary for {name}:**\n{description}")
    else:
        await interaction.followup.send(f"Could not find a description for '{name}' on Wikipedia.")
        
#--------------------AUTOADD A CHARACTER AUTO ADD VERY EASY PRECIOUS----------------#

@bot.tree.command(name="autoadd", description="Automatically add a new character with wiki info and images.")
async def autoadd_character(interaction: discord.Interaction, 
                            name: str, 
                            imagequery: str, 
                            sidenote: str = "No side note provided.", 
                            number: int = 1):
    """
    Automatically add a new character with data fetched from a wiki and image search.

    Args:
        interaction: The interaction object from Discord.
        name: Name of the character and the Wikipedia search term.
        imagequery: The search query for images.
        sidenote: A side note to add to the character.
        number: The number of images to add (default is 1).
    """
    await interaction.response.defer(thinking=True)  # Defer response to avoid timeout

    # Validate the number of images
    if number < 1 or number > 10:
        await interaction.followup.send("Please specify a number between 1 and 10 for the number of images.", ephemeral=True)
        return

    # Ensure the character doesn't already exist
    if name.lower() in [char.lower() for char in characters]:
        await interaction.followup.send(f"A character named '{name}' already exists!", ephemeral=True)
        return

    # Function to fetch description from Wikipedia
    async def fetch_description(wiki_name: str):
        try:
            async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
                async with session.get(f'https://en.wikipedia.org/wiki/{wiki_name.replace(" ", "_")}') as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.text()
                    data = data[data.find('<p>'):]
                    data = data[:data.find('</p>')]
                    data = data.replace('&#91;', '[').replace('&#93;', ']')
                    text = ''
                    waiting_on = None
                    for c in data:
                        if not waiting_on:
                            if c == '<':
                                waiting_on = '>'
                            elif c == '&':
                                waiting_on = ';'
                            elif c == '(':
                                text = text.strip()
                                waiting_on = ')'
                            elif c == '[':
                                waiting_on = ']'
                            else:
                                text += c
                        elif c == waiting_on:
                            waiting_on = None
                    text = ' '.join(text.split())
                    if text.endswith(' may refer to:'):
                        return None
                    return text
        except Exception:
            return None

    # Fetch description from Wikipedia
    description = await fetch_description(name)
    if not description:
        await interaction.followup.send(f"Could not fetch a description for '{name}' from Wikipedia.", ephemeral=True)
        return

    # Fetch images using SerpAPI
    async def fetch_images(query: str, max_images: int):
        search_url = "https://google.serper.dev/images"
        payload = {"q": query}
        headers = {
            "X-API-KEY": os.getenv("SERPAPI_API_KEY"),
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(search_url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                images = data.get("images", [])
                image_urls = [img["imageUrl"] for img in images if img["imageUrl"].endswith((".png", ".jpg", ".jpeg"))]
                return random.sample(image_urls, min(max_images, len(image_urls)))
        except Exception:
            return []
        return []

    # Fetch images
    images = await fetch_images(imagequery, number)
    if not images:
        await interaction.followup.send(f"No images found for query '{imagequery}'.", ephemeral=True)
        return

    # Add the character to the data
    characters[name] = {
        "description": description,
        "side_note": sidenote,
        "images": images,
        "status": "Alive",
        "owner": None
    }
    save_characters()  # Save to the JSON file

    # Build confirmation message
    embed = discord.Embed(
        title=f"Character '{name}' Created!",
        description=f"**Description:** {description}\n\n**Side Note:** {sidenote}\n\n**Images:** {len(images)} image(s) added.",
        color=discord.Color.green()
    )
    if images:
        embed.set_image(url=images[0])

    await interaction.followup.send(embed=embed)
    
#--------------OWN LIST COMMAND------------#

@bot.tree.command(name="ownlist", description="List all characters you own.")
async def ownlist(interaction: discord.Interaction):
    """List all characters owned by the user."""
    user_id = str(interaction.user.id)
    owned_characters = [
        name for name, char in characters.items() if char.get("owner") == interaction.user.id
    ]
    
    if not owned_characters:
        await interaction.response.send_message("You do not own any characters.", ephemeral=True)
        return

    # Format the list for display
    character_list = "\n".join([f"{i + 1}. {name}" for i, name in enumerate(owned_characters)])
    await interaction.response.send_message(f"**Your Owned Characters:**\n{character_list}")

#------------------COCK SUCKING CHALLENGE-----------------------#

@bot.tree.command(name="bjchallenge", description="Challenge another users roster to a cock sucking contest!")
async def bjchallenge(interaction: discord.Interaction, target_user: discord.Member):
    """Initiate a cock sucking contest."""
    if target_user == interaction.user:
        await interaction.response.send_message("You cannot challenge yourself.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"{target_user.mention}, your roster has been challenged to a cock sucking contest by {interaction.user.mention}!\n"
        "Do you accept?", 
        view=ChallengeView(interaction.user, target_user)
    )
    
def create_progress_bar(percentage, total_blocks=20):
    """
    Generate a progress bar string with blocks based on percentage.
    """
    filled_blocks = int((percentage / 100) * total_blocks)
    empty_blocks = total_blocks - filled_blocks
    return f"[{'█' * filled_blocks}{'░' * empty_blocks}] {percentage}%"

class ChallengeView(discord.ui.View):
    def __init__(self, challenger, target_user):
        super().__init__()
        self.challenger = challenger
        self.target_user = target_user
        self.chosen_characters = {challenger: None, target_user: None}
        self.character_images = {}

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target_user:
            await interaction.response.send_message("Only the challenged user can accept!", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"Challenge accepted! {self.challenger.mention} and {self.target_user.mention}, please choose your characters.",
            ephemeral=False
        )
        await self.prompt_character_choice(interaction.channel)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target_user:
            await interaction.response.send_message("Only the challenged user can decline!", ephemeral=True)
            return
        
        await interaction.response.send_message(f"{self.target_user.mention} has declined the challenge.", ephemeral=False)
        self.stop()

    async def prompt_character_choice(self, channel):
        for user in [self.challenger, self.target_user]:
            await channel.send(f"{user.mention}, please type the name of the character you want to use.")

        def check(msg):
            return msg.author in [self.challenger, self.target_user] and msg.channel == channel

        for _ in range(2):
            msg = await bot.wait_for("message", check=check)
            character_name = msg.content.strip()
            character = characters.get(character_name)

            # Check if the character exists
            if not character:
                await channel.send(f"Character '{character_name}' not found. Please choose again.")
                return await self.prompt_character_choice(channel)

            # Check if the character is owned by the user
            owner_id = character.get("owner")
            if owner_id != msg.author.id:
                await channel.send(
                    f"{character_name} is not owned by you! Please select a character you own."
                )
                return await self.prompt_character_choice(channel)

            # If all checks pass, assign the character
            self.chosen_characters[msg.author] = character_name
            self.character_images[msg.author] = character["images"][0].split()[0] if character["images"] else None

        await self.start_challenge(channel)

    async def start_challenge(self, channel):
        random_texts = [
            "sucking like a pro 🤤",
            "taking it slow and steady 🍑",
            "panting heavily 😤",
            "getting enthusiastic 👅",
            "working the shaft vigorously 💦",
            "trying to outdo the competition 🤔",
            "slurping loudly 😳",
            "showing some serious skill 🔥",
        ]

        # Get the characters
        char1 = self.chosen_characters[self.challenger]
        char2 = self.chosen_characters[self.target_user]

        img1 = self.character_images[self.challenger]
        img2 = self.character_images[self.target_user]

        # Send initial "versus" message with character images
        embed1 = discord.Embed(
            title=f"{char1} (owned by {self.challenger.display_name})",
            color=discord.Color.blue()
        ).set_image(url=img1)

        embed2 = discord.Embed(
            title=f"{char2} (owned by {self.target_user.display_name})",
            color=discord.Color.red()
        ).set_image(url=img2)

        # Send both character embeds side-by-side
        message1 = await channel.send(embed=embed1)
        message2 = await channel.send(embed=embed2)

        # Track progress
        progress = {self.challenger: 0, self.target_user: 0}

        # Simulate the challenge
        while progress[self.challenger] < 100 and progress[self.target_user] < 100:
            await asyncio.sleep(1)

            # Update progress
            progress[self.challenger] += random.randint(5, 15)
            progress[self.target_user] += random.randint(5, 15)

            # Cap progress at 100
            progress[self.challenger] = min(progress[self.challenger], 100)
            progress[self.target_user] = min(progress[self.target_user], 100)

            # Get random updates for each character
            status_challenger = random.choice(random_texts)
            status_target = random.choice(random_texts)

            # Create progress bars
            progress_bar_challenger = create_progress_bar(progress[self.challenger])
            progress_bar_target = create_progress_bar(progress[self.target_user])

            # Update the progress message
            embed1.description = (
                f"**{char1}'s Progress:** {progress_bar_challenger} - {status_challenger}"
            )
            embed2.description = (
                f"**{char2}'s Progress:** {progress_bar_target} - {status_target}"
            )
            await message1.edit(embed=embed1)
            await message2.edit(embed=embed2)

        # Determine the winner
        if progress[self.challenger] >= 100:
            winner = self.challenger
        else:
            winner = self.target_user
        winning_character = char1 if winner == self.challenger else char2

        # Update final message with the winner
        embed1.title = f"🎉 {winning_character} Wins! 🎉"
        embed1.description = (
            f"The Panelist moans and releases a large load in {winning_character}'s mouth! 🥒 💦 The Winner is **{winning_character}**!\n"
            f"Better luck next time, {char1 if winner == self.target_user else char2}!"
        )
        embed2.title = f"🎉 {winning_character} Wins! 🎉"
        embed2.description = (
            f"The Panelist moans and releases a large load in {winning_character}'s mouth! 🥒 💦 The Winner is **{winning_character}**!\n"
            f"Better luck next time, {char1 if winner == self.target_user else char2}!"
        )

        # Send final winner embed
        await message1.edit(embed=embed1)
        await message2.edit(embed=embed2)
        
        
        
###############################################################################
#----------------------------Trading Commands----------------------------------#
###############################################################################



#------------------------Give Character--------------------#
@bot.tree.command(name="givechar", description="Transfer ownership of a character to another user.")
async def give_character(interaction: discord.Interaction, character_name: str):
    """Transfer ownership of a character."""
    character = characters.get(character_name)
    
    # Check if the character exists
    if not character:
        await interaction.response.send_message(f"Character '{character_name}' not found.", ephemeral=True)
        return
    
    # Check if the user owns the character
    if character.get("owner") != interaction.user.id:
        await interaction.response.send_message(f"You do not own the character '{character_name}'.", ephemeral=True)
        return

    await interaction.response.send_message("Who do you want to give this character to? Mention the user.")

    def check(msg):
        return msg.author == interaction.user and msg.mentions

    try:
        msg = await bot.wait_for("message", check=check, timeout=30)
        recipient = msg.mentions[0]
        
        # Update ownership
        character["owner"] = recipient.id
        save_characters()

        await interaction.followup.send(f"Character '{character_name}' has been given to {recipient.mention}.")
    except asyncio.TimeoutError:
        await interaction.followup.send("No response received. Transfer cancelled.", ephemeral=True)

#---------------------------------SELL CHARACTER--------------------------#

@bot.tree.command(name="sell", description="Put a character up for sale.")
async def sell_character(interaction: discord.Interaction, character_name: str, amount: int):
    """Put a character for sale."""
    if amount <= 0:
        await interaction.response.send_message("Sale amount must be greater than 0.", ephemeral=True)
        return

    character = characters.get(character_name)
    
    # Check if the character exists
    if not character:
        await interaction.response.send_message(f"Character '{character_name}' not found.", ephemeral=True)
        return
    
    # Check if the user owns the character
    if character.get("owner") != interaction.user.id:
        await interaction.response.send_message(f"You do not own the character '{character_name}'.", ephemeral=True)
        return

    # Store sale information
    character["sale_price"] = amount
    save_characters()

    embed = discord.Embed(
        title=f"{character_name} is for sale!",
        description=f"Price: {amount} gold\n\nClick the button below to purchase.",
        color=discord.Color.gold()
    )
    message = await interaction.response.send_message(embed=embed, view=BuyView(character_name))

class BuyView(discord.ui.View):
    def __init__(self, character_name):
        super().__init__()
        self.character_name = character_name

    @discord.ui.button(label="Buy", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        character = characters.get(self.character_name)

        # Check if the character is still for sale
        if not character or "sale_price" not in character:
            await interaction.response.send_message("This character is no longer for sale.", ephemeral=True)
            return

        # Check if the user has enough gold
        sale_price = character["sale_price"]
        if gold_data.get(user_id, 0) < sale_price:
            await interaction.response.send_message("You do not have enough gold to buy this character.", ephemeral=True)
            return

        # Deduct gold from buyer and transfer ownership
        seller_id = character["owner"]
        gold_data[user_id] -= sale_price
        gold_data[seller_id] = gold_data.get(seller_id, 0) + sale_price

        character["owner"] = interaction.user.id
        del character["sale_price"]  # Remove sale status
        save_characters()
        save_gold_data()

        await interaction.response.send_message(f"Congratulations! You have purchased '{self.character_name}'.")





###########################################################
###########################################################
#----------------- END OF COMMAND LIST--------------------#
###########################################################
###########################################################



# Some syncing stuft idk what its for tbh
async def setup_hook():
    await bot.tree.sync()
    print("Command tree synced.")

bot.setup_hook = setup_hook


# Start the bot with your token from the environment variable
bot.run(DISCORD_TOKEN)
