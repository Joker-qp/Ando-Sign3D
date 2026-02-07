import discord
from discord.ext import commands
import asyncio
import websockets
import socket
import subprocess
import platform
import re
from typing import Dict, List, Optional, Any
import logging
import os
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# ===== LOGGİNG AYARLARI =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== AYARLAR =====
# .env dosyasından DISCORD_TOKEN anahtarını oku
TOKEN = os.getenv('DISCORD_TOKEN')

# Hologram cihazlarının bilgileri
HOLOGRAM_DEVICES: Dict[str, Dict[str, str]] = {}

# Kelime-Model eşleştirmeleri
MODEL_SHORTCUTS: Dict[str, Dict[str, Any]] = {}

# ===== BOT AYARLARI =====
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global WebSocket bağlantıları
websockets_dict: Dict[str, websockets.WebSocketClientProtocol] = {}
websocket_connected_dict: Dict[str, bool] = {}

# ===== AĞ TARAMA FONKSİYONLARI =====
async def check_hologram_device(ip: str) -> Dict[str, Any]:
    try:
        ws_url = f"ws://{ip}/ws"
        async with asyncio.timeout(2):
            ws = await websockets.connect(ws_url)
            try:
                await ws.send("PING")
                async with asyncio.timeout(2):
                    response = await ws.recv()
                await ws.send("GET_ID")
                try:
                    async with asyncio.timeout(1):
                        id_response = await ws.recv()
                        device_id = id_response.strip()
                except asyncio.TimeoutError:
                    device_id = f"DEVICE_{ip.replace('.', '_')}"
                await ws.close()
                return {"ip": ip, "device_id": device_id, "found": True}
            except Exception as e:
                logger.debug(f"Device check failed for {ip}: {e}")
                await ws.close()
                return {"ip": ip, "found": False}
    except Exception as e:
        logger.debug(f"Connection failed for {ip}: {e}")
        return {"ip": ip, "found": False}

async def scan_network(ip_range: str = "192.168.1") -> List[Dict[str, Any]]:
    logger.info(f"Network scan started: {ip_range}.x")
    async def ping_ip(i: int) -> Optional[str]:
        ip = f"{ip_range}.{i}"
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', '-w', '100', ip]
            result = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(result.wait(), timeout=1.0)
            if result.returncode == 0:
                return ip
        except (asyncio.TimeoutError, Exception):
            pass
        return None
    
    ping_tasks = [ping_ip(i) for i in range(1, 255)]
    ping_results = await asyncio.gather(*ping_tasks)
    active_ips = [ip for ip in ping_results if ip is not None]
    ws_tasks = [check_hologram_device(ip) for ip in active_ips]
    ws_results = await asyncio.gather(*ws_tasks)
    found_devices = [device for device in ws_results if device["found"]]
    return found_devices

# ===== WEBSOCKET BAĞLANTISI =====
async def connect_websocket(nickname: str) -> None:
    device_info = HOLOGRAM_DEVICES.get(nickname)
    if not device_info: return
    
    device_id = device_info["device_id"]
    websocket_url = f"ws://{device_info['ip']}/ws"
    
    while nickname in HOLOGRAM_DEVICES:
        try:
            async with websockets.connect(websocket_url) as ws:
                websockets_dict[nickname] = ws
                websocket_connected_dict[nickname] = True
                logger.info(f"✅ [{nickname}] Connected to {device_info['ip']}")
                try:
                    while websocket_connected_dict.get(nickname, False):
                        await ws.send(f"PING {device_id}")
                        await asyncio.sleep(5)
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"[{nickname}] Connection closed")
                except Exception as e:
                    logger.error(f"[{nickname}] Heartbeat error: {e}")
        except Exception as e:
            logger.error(f"❌ [{nickname}] Connection failed: {e}")
            websocket_connected_dict[nickname] = False
            await asyncio.sleep(3)
    
    websocket_connected_dict[nickname] = False
    if nickname in websockets_dict: del websockets_dict[nickname]

async def send_command_to_all(command: str) -> bool:
    if not HOLOGRAM_DEVICES: return False
    sent = False
    for nickname, device_info in HOLOGRAM_DEVICES.items():
        ws = websockets_dict.get(nickname)
        if not ws or not websocket_connected_dict.get(nickname, False): continue
        try:
            await ws.send(f"{device_info['device_id']} {command}")
            sent = True
        except Exception as e:
            logger.error(f"❌ [{nickname}] Send error: {e}")
            websocket_connected_dict[nickname] = False
    return sent

# ===== DISCORD BOT OLAYLARI =====
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")
    for nickname in HOLOGRAM_DEVICES.keys():
        bot.loop.create_task(connect_websocket(nickname))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        message_parts = ctx.message.content[1:].strip().split()
        if not message_parts: return
        keyword = message_parts[0].lower()
        
        repeat_count = 1
        for part in message_parts[1:]:
            if part.startswith("tekrar="):
                val = part.split("=")[1]
                repeat_count = -1 if val in ("∞", "inf") else int(val)
        
        if keyword in MODEL_SHORTCUTS:
            url = MODEL_SHORTCUTS[keyword]["url"]
            cmd = f"model {url} loop" if repeat_count == -1 else (f"model {url} repeat={repeat_count}" if repeat_count > 1 else f"model {url}")
            if await send_command_to_all(cmd):
                await ctx.send(f"🎬 **{keyword}** yükleniyor (Tekrar: {repeat_count if repeat_count != -1 else '∞'})")
        else:
            await ctx.send(f"❌ Komut bulunamadı. Yardım için: `!yardım` ")
    else:
        logger.error(f"Hata: {error}")

# ===== KOMUTLAR =====
@bot.command(name="keşfet")
async def discover(ctx, ip_range="192.168.1"):
    msg = await ctx.send(f"🔍 `{ip_range}.x` taranıyor...")
    found = await scan_network(ip_range)
    if not found:
        await msg.edit(content="❌ Cihaz bulunamadı.")
        return
    embed = discord.Embed(title="Bulunan Cihazlar", color=discord.Color.green())
    for i, d in enumerate(found, 1):
        embed.add_field(name=f"Cihaz {i}", value=f"ID: `{d['device_id']}`\nIP: `{d['ip']}`", inline=False)
    await msg.edit(content=None, embed=embed)

@bot.command(name="ekle")
async def add(ctx, nickname, device_id, ip):
    HOLOGRAM_DEVICES[nickname] = {"device_id": device_id, "ip": ip}
    bot.loop.create_task(connect_websocket(nickname))
    await ctx.send(f"✅ `{nickname}` eklendi.")

@bot.command(name="model")
async def model(ctx, *, url):
    if await send_command_to_all(f"model {url}"):
        await ctx.send(f"🎬 Model yükleniyor: {url}")

@bot.command(name="durum")
async def status(ctx):
    embed = discord.Embed(title="Bot Durumu", color=discord.Color.blue())
    for nick, info in HOLOGRAM_DEVICES.items():
        st = "🟢 Bağlı" if websocket_connected_dict.get(nick) else "🔴 Bağlı Değil"
        embed.add_field(name=nick, value=f"IP: {info['ip']}\nDurum: {st}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="yardım")
async def help_cmd(ctx):
    await ctx.send("**Komutlar:**\n`!keşfet`, `!ekle`, `!model`, `!durum`, `!yardım` \nKısayollar için: `!kelime_ekle` ")

# ===== BOT BAŞLAT =====
if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN bulunamadı! .env dosyasını kontrol et.")
        exit(1)
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"❌ Başlatma hatası: {e}")