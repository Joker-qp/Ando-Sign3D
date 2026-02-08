# bot.py - Geliştirilmiş Discord Bot (Sadece Port 8080 Güncellemesi)

import discord
from discord.ext import commands, tasks
import asyncio
import websockets
import socket
import subprocess
import platform
import re
import json
from typing import Dict, List, Optional, Any, Tuple
import logging
import os
from dotenv import load_dotenv
from datetime import datetime
import aiohttp

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# ===== LOGGİNG AYARLARI =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== AYARLAR =====
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logger.error("❌ DISCORD_TOKEN bulunamadı! .env dosyasını kontrol et.")
    exit(1)

# Hologram cihazlarının bilgileri
HOLOGRAM_DEVICES: Dict[str, Dict[str, Any]] = {}

# Kelime-Model eşleştirmeleri (kısayollar)
MODEL_SHORTCUTS: Dict[str, Dict[str, Any]] = {}

# Config dosya yolu
CONFIG_FILE = "bot_config.json"

# ===== BOT AYARLARI =====
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Global WebSocket bağlantıları
websockets_dict: Dict[str, websockets.WebSocketClientProtocol] = {}
websocket_connected_dict: Dict[str, bool] = {}
websocket_tasks: Dict[str, asyncio.Task] = {}

# İstatistikler
stats = {
    "commands_executed": 0,
    "messages_sent": 0,
    "devices_discovered": 0,
    "uptime_start": None
}

# ===== KONFİGÜRASYON YÖNETİMİ =====
def load_config():
    """Kaydedilmiş cihazları ve kısayolları yükle"""
    global HOLOGRAM_DEVICES, MODEL_SHORTCUTS
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                HOLOGRAM_DEVICES = data.get('devices', {})
                MODEL_SHORTCUTS = data.get('shortcuts', {})
                logger.info(f"✅ Config yüklendi: {len(HOLOGRAM_DEVICES)} cihaz, {len(MODEL_SHORTCUTS)} kısayol")
    except Exception as e:
        logger.error(f"Config yükleme hatası: {e}")

def save_config():
    """Cihazları ve kısayolları kaydet"""
    try:
        data = {
            'devices': HOLOGRAM_DEVICES,
            'shortcuts': MODEL_SHORTCUTS
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("✅ Config kaydedildi")
    except Exception as e:
        logger.error(f"Config kaydetme hatası: {e}")

# ===== AĞ TARAMA FONKSİYONLARI =====
async def check_hologram_device(ip: str) -> Dict[str, Any]:
    """Bir IP'de hologram cihazı olup olmadığını kontrol et"""
    try:
        # PORT 8080 OLARAK DEĞİŞTİRİLDİ
        ws_url = f"ws://{ip}:8080/ws"
        async with asyncio.timeout(2):
            ws = await websockets.connect(ws_url)
            try:
                # PING gönder
                await ws.send("PING")
                async with asyncio.timeout(2):
                    response = await ws.recv()
                
                # ID iste
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
    """Ağdaki tüm hologram cihazlarını bul"""
    logger.info(f"🔍 Network scan started: {ip_range}.x")
    
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
    
    # Tüm IP'leri ping'le
    ping_tasks = [ping_ip(i) for i in range(1, 255)]
    ping_results = await asyncio.gather(*ping_tasks)
    active_ips = [ip for ip in ping_results if ip is not None]
    
    logger.info(f"📡 {len(active_ips)} aktif IP bulundu")
    
    # Aktif IP'lerde WebSocket kontrolü yap
    ws_tasks = [check_hologram_device(ip) for ip in active_ips]
    ws_results = await asyncio.gather(*ws_tasks)
    found_devices = [device for device in ws_results if device["found"]]
    
    logger.info(f"✅ {len(found_devices)} hologram cihazı bulundu")
    stats["devices_discovered"] += len(found_devices)
    
    return found_devices

# ===== WEBSOCKET BAĞLANTISI VE YÖNETİMİ =====
async def connect_websocket(nickname: str) -> None:
    """Bir cihaza WebSocket bağlantısı kur ve heartbeat gönder"""
    device_info = HOLOGRAM_DEVICES.get(nickname)
    if not device_info:
        return
    
    device_id = device_info["device_id"]
    # PORT 8080 OLARAK DEĞİŞTİRİLDİ
    websocket_url = f"ws://{device_info['ip']}:8080/ws"
    reconnect_delay = 3
    max_reconnect_delay = 30
    
    while nickname in HOLOGRAM_DEVICES:
        try:
            async with websockets.connect(websocket_url, ping_interval=None) as ws:
                websockets_dict[nickname] = ws
                websocket_connected_dict[nickname] = True
                reconnect_delay = 3  # Reset delay on successful connection
                
                logger.info(f"✅ [{nickname}] Bağlandı: {device_info['ip']}")
                
                try:
                    # Heartbeat döngüsü
                    while websocket_connected_dict.get(nickname, False):
                        await ws.send(f"PING {device_id}")
                        logger.debug(f"[{nickname}] PING gönderildi")
                        await asyncio.sleep(5)
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"⚠️ [{nickname}] Bağlantı kapandı")
                except Exception as e:
                    logger.error(f"❌ [{nickname}] Heartbeat hatası: {e}")
                    
        except Exception as e:
            logger.error(f"❌ [{nickname}] Bağlantı hatası: {e}")
            websocket_connected_dict[nickname] = False
            
            # Exponential backoff
            logger.info(f"🔄 [{nickname}] {reconnect_delay}s sonra yeniden bağlanılacak...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    # Cleanup
    websocket_connected_dict[nickname] = False
    if nickname in websockets_dict:
        del websockets_dict[nickname]
    logger.info(f"🔌 [{nickname}] Bağlantı sonlandırıldı")

async def send_command_to_device(nickname: str, command: str) -> bool:
    """Belirli bir cihaza komut gönder"""
    device_info = HOLOGRAM_DEVICES.get(nickname)
    if not device_info:
        return False
    
    ws = websockets_dict.get(nickname)
    if not ws or not websocket_connected_dict.get(nickname, False):
        logger.warning(f"⚠️ [{nickname}] Bağlı değil")
        return False
    
    try:
        message = f"{device_info['device_id']} {command}"
        await ws.send(message)
        logger.info(f"📤 [{nickname}] Komut gönderildi: {command}")
        stats["messages_sent"] += 1
        return True
    except Exception as e:
        logger.error(f"❌ [{nickname}] Gönderme hatası: {e}")
        websocket_connected_dict[nickname] = False
        return False

async def send_command_to_all(command: str) -> Tuple[int, int]:
    """Tüm cihazlara komut gönder"""
    if not HOLOGRAM_DEVICES:
        return 0, 0
    
    success_count = 0
    total_count = len(HOLOGRAM_DEVICES)
    
    tasks = []
    for nickname in HOLOGRAM_DEVICES.keys():
        tasks.append(send_command_to_device(nickname, command))
    
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r)
    
    return success_count, total_count

# ===== DISCORD BOT OLAYLARI =====
@bot.event
async def on_ready():
    """Bot hazır olduğunda çalışır"""
    logger.info(f"✅ Bot giriş yaptı: {bot.user}")
    logger.info(f"📊 Sunucu sayısı: {len(bot.guilds)}")
    
    stats["uptime_start"] = datetime.now()
    
    # Kaydedilmiş config'i yükle
    load_config()
    
    # Kaydedilmiş cihazlara bağlan
    for nickname in HOLOGRAM_DEVICES.keys():
        task = bot.loop.create_task(connect_websocket(nickname))
        websocket_tasks[nickname] = task
    
    # Status güncelleme task'ını başlat
    update_status.start()
    
    # Bot durumunu ayarla
    await bot.change_presence(
        activity=discord.Game(name="🎮 Hologram Kontrol | !yardım")
    )

@bot.event
async def on_command_error(ctx, error):
    """Komut hatalarını yönet"""
    if isinstance(error, commands.CommandNotFound):
        # Kısayol kontrolü
        message_parts = ctx.message.content[1:].strip().split()
        if not message_parts:
            return
        
        keyword = message_parts[0].lower()
        
        # Parametreleri parse et
        repeat_count = 1
        loop = False
        
        for part in message_parts[1:]:
            if part.startswith("tekrar="):
                val = part.split("=")[1]
                if val in ("∞", "inf", "loop"):
                    loop = True
                else:
                    try:
                        repeat_count = int(val)
                    except ValueError:
                        pass
        
        # Kısayol varsa çalıştır
        if keyword in MODEL_SHORTCUTS:
            url = MODEL_SHORTCUTS[keyword]["url"]
            
            if loop:
                cmd = f"model {url} loop"
            elif repeat_count > 1:
                cmd = f"model {url} repeat={repeat_count}"
            else:
                cmd = f"model {url}"
            
            success, total = await send_command_to_all(cmd)
            
            if success > 0:
                repeat_text = "∞" if loop else str(repeat_count)
                await ctx.send(
                    f"🎬 **{keyword}** modeli yükleniyor\n"
                    f"📡 Gönderildi: {success}/{total} cihaz\n"
                    f"🔄 Tekrar: {repeat_text}"
                )
            else:
                await ctx.send("❌ Hiçbir cihaz bağlı değil!")
        else:
            await ctx.send(
                f"❌ `{keyword}` komutu veya kısayolu bulunamadı.\n"
                f"💡 Yardım için: `!yardım`"
            )
    
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik parametre! Kullanım için `!yardım {ctx.command.name}` yazın.")
    
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Geçersiz parametre! Kullanım için `!yardım {ctx.command.name}` yazın.")
    
    else:
        logger.error(f"Komut hatası: {error}", exc_info=True)
        await ctx.send(f"❌ Bir hata oluştu: {str(error)}")

@bot.event
async def on_message(message):
    """Mesajları logla"""
    if message.author == bot.user:
        return
    
    logger.debug(f"💬 [{message.guild.name if message.guild else 'DM'}] {message.author}: {message.content}")
    await bot.process_commands(message)

# ===== CİHAZ YÖNETİMİ KOMUTLARI =====
@bot.command(name="keşfet", aliases=["scan", "search"])
async def discover(ctx, ip_range: str = "192.168.1"):
    """Ağdaki hologram cihazlarını bul
    
    Kullanım: !keşfet [ip_range]
    Örnek: !keşfet 192.168.1
    """
    stats["commands_executed"] += 1
    
    msg = await ctx.send(f"🔍 `{ip_range}.x` ağı taranıyor...")
    
    found = await scan_network(ip_range)
    
    if not found:
        await msg.edit(content="❌ Hiç cihaz bulunamadı.")
        return
    
    embed = discord.Embed(
        title="🌐 Bulunan Hologram Cihazları",
        description=f"Toplam {len(found)} cihaz bulundu",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    
    for i, device in enumerate(found, 1):
        embed.add_field(
            name=f"Cihaz {i}",
            # IP GÖRÜNÜMÜNE 8080 EKLENDİ
            value=f"🆔 ID: `{device['device_id']}`\n📡 IP: `{device['ip']}:8080`",
            inline=False
        )
    
    embed.set_footer(text="Cihaz eklemek için: !ekle <nickname> <device_id> <ip>")
    
    await msg.edit(content=None, embed=embed)

@bot.command(name="ekle", aliases=["add"])
async def add(ctx, nickname: str, device_id: str, ip: str):
    """Yeni bir hologram cihazı ekle
    
    Kullanım: !ekle <nickname> <device_id> <ip>
    Örnek: !ekle holo1 DEVICE_192_168_1_100 192.168.1.100
    """
    stats["commands_executed"] += 1
    
    # Cihazı kaydet
    HOLOGRAM_DEVICES[nickname] = {
        "device_id": device_id,
        "ip": ip,
        "added_by": str(ctx.author),
        "added_at": datetime.now().isoformat()
    }
    
    # Config'e kaydet
    save_config()
    
    # WebSocket bağlantısını başlat
    task = bot.loop.create_task(connect_websocket(nickname))
    websocket_tasks[nickname] = task
    
    embed = discord.Embed(
        title="✅ Cihaz Eklendi",
        color=discord.Color.green()
    )
    embed.add_field(name="Nickname", value=f"`{nickname}`", inline=True)
    embed.add_field(name="Device ID", value=f"`{device_id}`", inline=True)
    # GÖRÜNÜME 8080 EKLENDİ
    embed.add_field(name="IP", value=f"`{ip}:8080`", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="çıkar", aliases=["remove", "sil"])
async def remove(ctx, nickname: str):
    """Bir cihazı listeden çıkar
    
    Kullanım: !çıkar <nickname>
    Örnek: !çıkar holo1
    """
    stats["commands_executed"] += 1
    
    if nickname not in HOLOGRAM_DEVICES:
        await ctx.send(f"❌ `{nickname}` bulunamadı!")
        return
    
    # WebSocket bağlantısını durdur
    websocket_connected_dict[nickname] = False
    if nickname in websocket_tasks:
        websocket_tasks[nickname].cancel()
        del websocket_tasks[nickname]
    
    # Cihazı sil
    del HOLOGRAM_DEVICES[nickname]
    save_config()
    
    await ctx.send(f"✅ `{nickname}` çıkarıldı.")

@bot.command(name="liste", aliases=["list", "devices"])
async def list_devices(ctx):
    """Tüm kayıtlı cihazları listele
    
    Kullanım: !liste
    """
    stats["commands_executed"] += 1
    
    if not HOLOGRAM_DEVICES:
        await ctx.send("📭 Henüz kayıtlı cihaz yok. `!keşfet` ile cihaz bulabilirsin.")
        return
    
    embed = discord.Embed(
        title="📋 Kayıtlı Cihazlar",
        description=f"Toplam {len(HOLOGRAM_DEVICES)} cihaz",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for nickname, info in HOLOGRAM_DEVICES.items():
        status = "🟢 Bağlı" if websocket_connected_dict.get(nickname, False) else "🔴 Bağlı Değil"
        # GÖRÜNÜME 8080 EKLENDİ
        value = f"{status}\n📡 IP: `{info['ip']}:8080`\n🆔 ID: `{info['device_id']}`"
        embed.add_field(name=nickname, value=value, inline=False)
    
    await ctx.send(embed=embed)

# ===== KONTROL KOMUTLARI =====
@bot.command(name="model")
async def model(ctx, url: str, *, params: str = ""):
    """Bir 3D model yükle
    
    Kullanım: !model <url> [repeat=N] [loop]
    Örnek: !model https://example.com/model.glb repeat=3
    """
    stats["commands_executed"] += 1
    
    # Parametreleri parse et
    command = f"model {url}"
    if params:
        command += f" {params}"
    
    success, total = await send_command_to_all(command)
    
    if success > 0:
        await ctx.send(f"🎬 Model yükleniyor: {url}\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

@bot.command(name="video")
async def video(ctx, url: str):
    """Bir video oynat
    
    Kullanım: !video <url>
    Örnek: !video https://example.com/video.ogv
    """
    stats["commands_executed"] += 1
    
    success, total = await send_command_to_all(f"video {url}")
    
    if success > 0:
        await ctx.send(f"🎥 Video oynatılıyor: {url}\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

@bot.command(name="durdur", aliases=["stop"])
async def stop_video(ctx):
    """Videoyu durdur
    
    Kullanım: !durdur
    """
    stats["commands_executed"] += 1
    
    success, total = await send_command_to_all("stop_video")
    
    if success > 0:
        await ctx.send(f"⏹️ Video durduruldu\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

@bot.command(name="rpm")
async def rpm(ctx, value: float):
    """Dönüş hızını ayarla
    
    Kullanım: !rpm <değer>
    Örnek: !rpm 450
    """
    stats["commands_executed"] += 1
    
    success, total = await send_command_to_all(f"rpm {value}")
    
    if success > 0:
        await ctx.send(f"⚡ RPM ayarlandı: {value}\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

@bot.command(name="faz", aliases=["phase"])
async def phase(ctx, value: int):
    """Faz açısını ayarla
    
    Kullanım: !faz <derece>
    Örnek: !faz 90
    """
    stats["commands_executed"] += 1
    
    success, total = await send_command_to_all(f"phase {value}")
    
    if success > 0:
        await ctx.send(f"🔄 Faz ayarlandı: {value}°\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

@bot.command(name="ışık", aliases=["light"])
async def light(ctx, value: float):
    """Işık yoğunluğunu ayarla
    
    Kullanım: !ışık <değer>
    Örnek: !ışık 1.5
    """
    stats["commands_executed"] += 1
    
    success, total = await send_command_to_all(f"light {value}")
    
    if success > 0:
        await ctx.send(f"💡 Işık ayarlandı: {value}\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

@bot.command(name="sıfırla", aliases=["reset"])
async def reset(ctx):
    """Animasyonu sıfırla
    
    Kullanım: !sıfırla
    """
    stats["commands_executed"] += 1
    
    success, total = await send_command_to_all("reset")
    
    if success > 0:
        await ctx.send(f"🔄 Animasyon sıfırlandı\n📡 Gönderildi: {success}/{total} cihaz")
    else:
        await ctx.send("❌ Hiçbir cihaz bağlı değil!")

# ===== KISAYOL YÖNETİMİ =====
@bot.command(name="kısayol_ekle", aliases=["shortcut_add"])
async def shortcut_add(ctx, keyword: str, url: str, *, description: str = ""):
    """Model için kısayol ekle
    
    Kullanım: !kısayol_ekle <kelime> <url> [açıklama]
    Örnek: !kısayol_ekle küp https://example.com/cube.glb Dönen küp
    """
    stats["commands_executed"] += 1
    
    keyword = keyword.lower()
    
    MODEL_SHORTCUTS[keyword] = {
        "url": url,
        "description": description,
        "added_by": str(ctx.author),
        "added_at": datetime.now().isoformat()
    }
    
    save_config()
    
    await ctx.send(f"✅ Kısayol eklendi: `!{keyword}` → {url}")

@bot.command(name="kısayol_sil", aliases=["shortcut_remove"])
async def shortcut_remove(ctx, keyword: str):
    """Kısayol sil
    
    Kullanım: !kısayol_sil <kelime>
    Örnek: !kısayol_sil küp
    """
    stats["commands_executed"] += 1
    
    keyword = keyword.lower()
    
    if keyword not in MODEL_SHORTCUTS:
        await ctx.send(f"❌ `{keyword}` kısayolu bulunamadı!")
        return
    
    del MODEL_SHORTCUTS[keyword]
    save_config()
    
    await ctx.send(f"✅ Kısayol silindi: `{keyword}`")

@bot.command(name="kısayollar", aliases=["shortcuts"])
async def shortcuts_list(ctx):
    """Tüm kısayolları listele
    
    Kullanım: !kısayollar
    """
    stats["commands_executed"] += 1
    
    if not MODEL_SHORTCUTS:
        await ctx.send("📭 Henüz kısayol yok. `!kısayol_ekle` ile ekleyebilirsin.")
        return
    
    embed = discord.Embed(
        title="🔖 Model Kısayolları",
        description=f"Toplam {len(MODEL_SHORTCUTS)} kısayol",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    
    for keyword, info in MODEL_SHORTCUTS.items():
        desc = info.get('description', 'Açıklama yok')
        value = f"🔗 {info['url']}\n📝 {desc}"
        embed.add_field(name=f"!{keyword}", value=value, inline=False)
    
    await ctx.send(embed=embed)

# ===== BİLGİ KOMUTLARI =====
@bot.command(name="durum", aliases=["status"])
async def status(ctx):
    """Bot ve cihaz durumunu göster
    
    Kullanım: !durum
    """
    stats["commands_executed"] += 1
    
    # Uptime hesapla
    if stats["uptime_start"]:
        uptime = datetime.now() - stats["uptime_start"]
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}s {minutes}d {seconds}sn"
    else:
        uptime_str = "Bilinmiyor"
    
    embed = discord.Embed(
        title="📊 Bot Durumu",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Genel bilgiler
    embed.add_field(
        name="📈 İstatistikler",
        value=f"⏱️ Uptime: {uptime_str}\n"
              f"💬 Komut: {stats['commands_executed']}\n"
              f"📤 Mesaj: {stats['messages_sent']}\n"
              f"🔍 Keşif: {stats['devices_discovered']} cihaz",
        inline=False
    )
    
    # Cihaz durumları
    if HOLOGRAM_DEVICES:
        device_status = []
        for nickname, info in HOLOGRAM_DEVICES.items():
            status_icon = "🟢" if websocket_connected_dict.get(nickname, False) else "🔴"
            # GÖRÜNÜME 8080 EKLENDİ
            device_status.append(f"{status_icon} **{nickname}** - {info['ip']}:8080")
        
        embed.add_field(
            name=f"🌐 Cihazlar ({len(HOLOGRAM_DEVICES)})",
            value="\n".join(device_status),
            inline=False
        )
    else:
        embed.add_field(name="🌐 Cihazlar", value="Henüz cihaz yok", inline=False)
    
    # Kısayollar
    embed.add_field(
        name="🔖 Kısayollar",
        value=f"{len(MODEL_SHORTCUTS)} kısayol tanımlı",
        inline=True
    )
    
    # Sunucu sayısı
    embed.add_field(
        name="🏢 Sunucular",
        value=f"{len(bot.guilds)} sunucu",
        inline=True
    )
    
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    """Bot gecikmesini göster
    
    Kullanım: !ping
    """
    stats["commands_executed"] += 1
    
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Gecikme: **{latency}ms**",
        color=discord.Color.green() if latency < 100 else discord.Color.orange()
    )
    
    await ctx.send(embed=embed)

@bot.command(name="yardım", aliases=["help"])
async def help_cmd(ctx, command_name: str = None):
    """Yardım menüsünü göster
    
    Kullanım: !yardım [komut]
    Örnek: !yardım model
    """
    stats["commands_executed"] += 1
    
    if command_name:
        # Belirli bir komut için yardım
        cmd = bot.get_command(command_name)
        if not cmd:
            await ctx.send(f"❌ `{command_name}` komutu bulunamadı!")
            return
        
        embed = discord.Embed(
            title=f"📖 !{cmd.name}",
            description=cmd.help or "Açıklama yok",
            color=discord.Color.blue()
        )
        
        if cmd.aliases:
            embed.add_field(
                name="Alternatifler",
                value=", ".join([f"`!{alias}`" for alias in cmd.aliases]),
                inline=False
            )
        
        await ctx.send(embed=embed)
        return
    
    # Genel yardım menüsü
    embed = discord.Embed(
        title="🤖 Hologram Bot Yardım",
        description="Tüm komutlar ve kullanımları",
        color=discord.Color.blue()
    )
    
    # Cihaz yönetimi
    embed.add_field(
        name="🌐 Cihaz Yönetimi",
        value="```\n"
              "!keşfet [ip]      - Ağdaki cihazları bul\n"
              "!ekle <nick> <id> <ip> - Cihaz ekle\n"
              "!çıkar <nick>    - Cihaz çıkar\n"
              "!liste            - Cihazları listele\n"
              "!durum            - Durum göster\n"
              "```",
        inline=False
    )
    
    # Kontrol
    embed.add_field(
        name="🎮 Kontrol",
        value="```\n"
              "!model <url>      - 3D model yükle\n"
              "!video <url>      - Video oynat\n"
              "!durdur           - Videoyu durdur\n"
              "!rpm <değer>      - Dönüş hızı\n"
              "!faz <derece>    - Faz açısı\n"
              "!ışık <değer>    - Işık yoğunluğu\n"
              "!sıfırla          - Animasyonu sıfırla\n"
              "```",
        inline=False
    )
    
    # Kısayollar
    embed.add_field(
        name="🔖 Kısayollar",
        value="```\n"
              "!kısayol_ekle <kelime> <url> - Kısayol ekle\n"
              "!kısayol_sil <kelime>  - Kısayol sil\n"
              "!kısayollar      - Kısayolları listele\n"
              "```",
        inline=False
    )
    
    # Diğer
    embed.add_field(
        name="ℹ️ Diğer",
        value="```\n"
              "!ping             - Bot gecikmesi\n"
              "!yardım [komut]  - Yardım menüsü\n"
              "```",
        inline=False
    )
    
    embed.set_footer(text="Detaylı yardım için: !yardım <komut>")
    
    await ctx.send(embed=embed)

# ===== ARKAPLAN GÖREVLERİ =====
@tasks.loop(minutes=5)
async def update_status():
    """Bot durumunu periyodik olarak güncelle"""
    try:
        connected = sum(1 for v in websocket_connected_dict.values() if v)
        total = len(HOLOGRAM_DEVICES)
        
        activity_text = f"🌐 {connected}/{total} cihaz | !yardım"
        await bot.change_presence(
            activity=discord.Game(name=activity_text)
        )
    except Exception as e:
        logger.error(f"Status güncelleme hatası: {e}")

# ===== BOT BAŞLAT =====
if __name__ == "__main__":
    try:
        logger.info("🚀 Bot başlatılıyor...")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("⏹️ Bot kapatılıyor...")
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}", exc_info=True)