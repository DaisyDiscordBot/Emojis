"""
Daisy Emojis - Discord Application Emoji Manager

Copyright (c) 2025 neoarz (DaisyDiscordBot)
All Rights Reserved. See LICENSE file for details.
"""

import os
import requests
import sys
from pathlib import Path
import base64
import hashlib
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import tempfile

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import cairosvg
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
EMOJI_FOLDER = os.getenv('EMOJI_FOLDER', 'emojis')
EMOJI_CODES_FILE = os.getenv('EMOJI_CODES_FILE', 'emojis.txt')

SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}

def get_image_hash(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def convert_svg_to_png(svg_path):
    if not SVG_SUPPORT:
        return None
    
    try:
        temp_png = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_png.close()
        
        cairosvg.svg2png(url=str(svg_path), write_to=temp_png.name, output_width=512, output_height=512)
        return temp_png.name
    except Exception as e:
        print(f"Error converting SVG: {e}")
        return None

def get_existing_emojis():
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/emojis"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        emojis = {}
        for emoji in response.json()['items']:
            emojis[emoji['name']] = {
                'id': emoji['id'],
                'animated': emoji.get('animated', False)
            }
        return emojis
    else:
        print(f"Error fetching emojis: {response.status_code} - {response.text}")
        return {}

def delete_emoji(emoji_id, emoji_name):
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/emojis/{emoji_id}"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    response = requests.delete(url, headers=headers)
    
    if response.status_code == 204:
        return True, "Success"
    else:
        return False, f"{response.status_code} - {response.text}"

def upload_emoji(file_path, emoji_name):
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/emojis"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    file_ext = Path(file_path).suffix.lower()
    temp_png_path = None
    
    if file_ext == '.svg':
        if not SVG_SUPPORT:
            return False, "SVG support not available (cairosvg not installed)", None
        
        temp_png_path = convert_svg_to_png(file_path)
        if not temp_png_path:
            return False, "Failed to convert SVG to PNG", None
        
        file_path = temp_png_path
        file_ext = '.png'
    
    with open(file_path, 'rb') as f:
        image_data = f.read()
    
    if temp_png_path:
        try:
            os.unlink(temp_png_path)
        except:
            pass
    
    if file_ext == '.png':
        image_type = 'image/png'
    elif file_ext in ['.jpg', '.jpeg']:
        image_type = 'image/jpeg'
    elif file_ext == '.gif':
        image_type = 'image/gif'
    elif file_ext == '.webp':
        image_type = 'image/webp'
    else:
        return False, "Unsupported format", None
    
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    data_uri = f"data:{image_type};base64,{image_base64}"
    
    payload = {
        "name": emoji_name,
        "image": data_uri
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 201:
        emoji_data = response.json()
        return True, "Success", emoji_data
    else:
        return False, f"{response.status_code} - {response.text}", None

def format_emoji_code(emoji_name, emoji_id, animated=False):
    prefix = "a" if animated else ""
    return f"<{prefix}:{emoji_name}:{emoji_id}>"

def find_all_emoji_files(emoji_folder):
    emoji_path = Path(emoji_folder)
    emoji_files = {}
    
    for file_path in emoji_path.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_FORMATS:
            emoji_name = file_path.stem
            
            relative_path = file_path.relative_to(emoji_path)
            
            emoji_files[emoji_name] = {
                'path': file_path,
                'relative_path': str(relative_path)
            }
    
    return emoji_files

def write_emoji_codes(emojis_dict, local_files):
    with open(EMOJI_CODES_FILE, 'w', encoding='utf-8') as f:
        f.write("Discord Application Emoji Codes\n")
        f.write(f"Total emojis: {len(emojis_dict)}\n")
        f.write("="*60 + "\n\n")
        
        for emoji_name in sorted(emojis_dict.keys()):
            emoji_info = emojis_dict[emoji_name]
            emoji_code = format_emoji_code(
                emoji_name, 
                emoji_info['id'], 
                emoji_info.get('animated', False)
            )
            
            f.write(f"{emoji_name:30} {emoji_code}\n")
        
        ny_time = datetime.now(ZoneInfo("America/New_York"))
        f.write(f"\nLast updated on: {ny_time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n")

def main():
    if not BOT_TOKEN or not APPLICATION_ID:
        print("Error: DISCORD_BOT_TOKEN and DISCORD_APPLICATION_ID must be set")
        sys.exit(1)
    
    emoji_path = Path(EMOJI_FOLDER)
    if not emoji_path.exists():
        print(f"Emoji folder '{EMOJI_FOLDER}' not found, creating it...")
        emoji_path.mkdir(parents=True, exist_ok=True)
    
    print("Fetching existing emojis from Discord...")
    existing_emojis = get_existing_emojis()
    print(f"Found {len(existing_emojis)} existing emojis on Discord")
    
    print(f"Scanning '{EMOJI_FOLDER}' folder recursively...")
    local_files = find_all_emoji_files(EMOJI_FOLDER)
    
    print(f"Found {len(local_files)} emoji files in local folder (including subfolders)")
    
    uploaded_count = 0
    updated_count = 0
    deleted_count = 0
    skipped_count = 0
    error_count = 0
    
    print("\n--- Processing Local Emojis ---")
    for emoji_name, file_info in local_files.items():
        file_path = file_info['path']
        relative_path = file_info['relative_path']
        
        if emoji_name in existing_emojis:
            print(f"Skipping '{emoji_name}' ({relative_path}) - already exists")
            skipped_count += 1
        else:
            print(f"Uploading '{emoji_name}' ({relative_path})...", end=" ")
            success, message, emoji_data = upload_emoji(file_path, emoji_name)
            
            if success:
                print("Success")
                existing_emojis[emoji_name] = {
                    'id': emoji_data['id'],
                    'animated': emoji_data.get('animated', False)
                }
                uploaded_count += 1
                time.sleep(1.5)
            else:
                print(f"Failed: {message}")
                error_count += 1
                if "429" in str(message):
                    print("Rate limited, waiting 5 seconds...")
                    time.sleep(5)
    
    print("\n--- Checking for Emojis to Delete ---")
    emojis_to_delete = set(existing_emojis.keys()) - set(local_files.keys())
    
    if emojis_to_delete:
        print(f"Found {len(emojis_to_delete)} emojis to delete from Discord")
        for emoji_name in emojis_to_delete:
            emoji_id = existing_emojis[emoji_name]['id']
            print(f"Deleting '{emoji_name}'...", end=" ")
            success, message = delete_emoji(emoji_id, emoji_name)
            
            if success:
                print("Deleted")
                del existing_emojis[emoji_name]
                deleted_count += 1
                time.sleep(1.5)
            else:
                print(f"Failed: {message}")
                error_count += 1
                if "429" in str(message):
                    print("Rate limited, waiting 5 seconds...")
                    time.sleep(5)
    else:
        print("No emojis to delete")
    
    print(f"\n--- Writing Emoji Codes to {EMOJI_CODES_FILE} ---")
    write_emoji_codes(existing_emojis, local_files)
    print(f"Emoji codes written to {EMOJI_CODES_FILE}")
    
    print("\n--- Summary ---")
    print(f"Uploaded: {uploaded_count}")
    print(f"Updated: {updated_count}")
    print(f"Deleted: {deleted_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {error_count}")
    print(f"Total emojis in file: {len(existing_emojis)}")
    
    if error_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()