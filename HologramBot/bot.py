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

# ===== LOGGİNG AYARLARI =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== AYARLAR =====
DISCORD_TOKEN = "MTQyODM3NTk4MjMzNDY3NzAxMg.G0rXSk.niwWYDzo2NoYZecx2X7A6YBRrx_GPfnZwswJ_g"  # Token'ınızı buraya ekleyin

# Hologram cihazlarının bilgileri
# Format: takma_ad -> {"device_id": "...", "ip": "..."}
HOLOGRAM_DEVICES: Dict[str, Dict[str, str]] = {}

# Kelime-Model eşleştirmeleri
# Format: kelime -> {"url": "...", "repeat": 1}
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
    """Bir IP'nin Hologram cihazı olup olmadığını kontrol et ve Device ID'yi al"""
    try:
        ws_url = f"ws://{ip}/ws"
        async with asyncio.timeout(2):
            ws = await websockets.connect(ws_url)
            
            try:
                # PING gönder ve cevap bekle
                await ws.send("PING")
                async with asyncio.timeout(2):
                    response = await ws.recv()
                
                # Device ID'yi almaya çalış
                await ws.send("GET_ID")
                try:
                    async with asyncio.timeout(1):
                        id_response = await ws.recv()
                        device_id = id_response.strip()
                except asyncio.TimeoutError:
                    # ID alamadıysak, IP'den türet
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
    """Ağdaki Hologram cihazlarını tara"""
    logger.info(f"Network scan started: {ip_range}.x")
    found_devices: List[Dict[str, Any]] = []
    
    # İlk olarak hızlı ping taraması yap
    active_ips: List[str] = []
    
    # Ping taraması için tasks oluştur
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
    
    # Paralel ping taraması
    ping_tasks = [ping_ip(i) for i in range(1, 255)]
    ping_results = await asyncio.gather(*ping_tasks)
    active_ips = [ip for ip in ping_results if ip is not None]
    
    logger.info(f"Found {len(active_ips)} active IPs")
    
    # WebSocket kontrolü yap
    ws_tasks = [check_hologram_device(ip) for ip in active_ips]
    ws_results = await asyncio.gather(*ws_tasks)
    
    found_devices = [device for device in ws_results if device["found"]]
    logger.info(f"Found {len(found_devices)} Hologram devices")
    
    return found_devices


# ===== WEBSOCKET BAĞLANTISI =====
async def connect_websocket(nickname: str) -> None:
    """WebSocket'e bağlan ve heartbeat gönder"""
    device_info = HOLOGRAM_DEVICES.get(nickname)
    if not device_info:
        logger.error(f"Device not found: {nickname}")
        return
    
    device_id = device_info["device_id"]
    websocket_url = f"ws://{device_info['ip']}/ws"
    
    while nickname in HOLOGRAM_DEVICES:  # Cihaz kayıtlı olduğu sürece
        try:
            logger.info(f"[{nickname}] Connecting to {websocket_url}")
            async with websockets.connect(websocket_url) as ws:
                websockets_dict[nickname] = ws
                websocket_connected_dict[nickname] = True
                logger.info(f"✅ [{nickname}] Connected to {device_info['ip']}")
                
                # Heartbeat loop
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
            
            # Yeniden bağlanma denemesi
            await asyncio.sleep(3)
    
    # Cleanup
    websocket_connected_dict[nickname] = False
    if nickname in websockets_dict:
        del websockets_dict[nickname]
    logger.info(f"[{nickname}] Connection task stopped")


async def send_command_to_all(command: str) -> bool:
    """Tüm kayıtlı cihazlara komut gönder"""
    if not HOLOGRAM_DEVICES:
        logger.warning("No devices registered")
        return False
    
    sent = False
    
    for nickname, device_info in HOLOGRAM_DEVICES.items():
        ws = websockets_dict.get(nickname)
        is_connected = websocket_connected_dict.get(nickname, False)
        
        if not ws or not is_connected:
            logger.warning(f"❌ [{nickname}] Not connected")
            continue
        
        try:
            device_id = device_info["device_id"]
            message = f"{device_id} {command}"
            await ws.send(message)
            
            logger.info(f"📤 [{nickname}] Command sent: {command}")
            sent = True
        except Exception as e:
            logger.error(f"❌ [{nickname}] Send error: {e}")
            websocket_connected_dict[nickname] = False
    
    return sent


# ===== DISCORD BOT OLAYLARI =====
@bot.event
async def on_ready() -> None:
    """Bot başlatıldığında"""
    logger.info(f"✅ Logged in as {bot.user}")
    
    # Tüm cihazlara bağlan
    for nickname in HOLOGRAM_DEVICES.keys():
        bot.loop.create_task(connect_websocket(nickname))


@bot.event
async def on_message(message: discord.Message) -> None:
    """Her mesajda çalışır"""
    if message.author == bot.user:
        return
    
    # Komutları işle
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Komut hatalarını yakala"""
    if isinstance(error, commands.CommandNotFound):
        # Komut bulunamadı, belki kelime kısayoludur?
        message_parts = ctx.message.content[1:].strip().split()
        if not message_parts:
            return
        
        keyword = message_parts[0].lower()
        
        # Tekrar parametresi var mı kontrol et
        repeat_count = 1  # Varsayılan
        for part in message_parts[1:]:
            if part.startswith("tekrar="):
                repeat_value = part.split("=")[1]
                if repeat_value in ("∞", "inf"):
                    repeat_count = -1  # Sonsuz
                else:
                    try:
                        repeat_count = int(repeat_value)
                    except ValueError:
                        await ctx.send("❌ Geçersiz tekrar sayısı! Örn: `tekrar=5` veya `tekrar=∞`")
                        return
        
        if keyword in MODEL_SHORTCUTS:
            shortcut_data = MODEL_SHORTCUTS[keyword]
            url = shortcut_data["url"]
            
            # Komutu oluştur
            if repeat_count == -1:
                command = f"model {url} loop"
            elif repeat_count > 1:
                command = f"model {url} repeat={repeat_count}"
            else:
                command = f"model {url}"
            
            success = await send_command_to_all(command)
            if success:
                repeat_text = "∞ (sonsuz)" if repeat_count == -1 else str(repeat_count)
                embed = discord.Embed(
                    title=f"🎬 '{keyword}' Yükleniyor",
                    description=f"**URL:** `{url}`\n**Tekrar:** {repeat_text}",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Komut gönderilemedi!")
        else:
            await ctx.send(
                f"❌ Komut bulunamadı: `{ctx.message.content}`\n"
                "`!yardım` yazarak komutları görüntüle."
            )
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"❌ Hata: {error}")


# ===== CİHAZ YÖNETİMİ =====
@bot.command(name="keşfet", help="!keşfet [ip_aralığı] - Ağdaki Hologram cihazlarını keşfet")
async def discover_devices(ctx: commands.Context, ip_range: str = "192.168.1") -> None:
    """Ağdaki Hologram cihazlarını keşfet"""
    msg = await ctx.send(
        f"🔍 Ağ taranıyor: `{ip_range}.x`\n"
        "Bu 1-2 dakika sürebilir..."
    )
    
    found_devices = await scan_network(ip_range)
    
    if not found_devices:
        await msg.edit(content="❌ Hologram cihazı bulunamadı!")
        return
    
    embed = discord.Embed(
        title=f"🎉 Bulunan Hologram Cihazları ({len(found_devices)})",
        description="Aşağıdaki cihazları ekleyebilirsin:",
        color=discord.Color.green()
    )
    
    for idx, device in enumerate(found_devices, 1):
        # Zaten ekliyse belirt
        already_added = any(
            dev_info["device_id"] == device["device_id"]
            for dev_info in HOLOGRAM_DEVICES.values()
        )
        
        status = "✅ Ekli" if already_added else "➕ Eklenebilir"
        
        embed.add_field(
            name=f"{idx}. {status}",
            value=(
                f"**Device ID:** `{device['device_id']}`\n"
                f"**IP:** `{device['ip']}`\n"
                f"**Eklemek için:** `!ekle cihaz{idx} {device['device_id']} {device['ip']}`"
            ),
            inline=False
        )
    
    await msg.edit(content=None, embed=embed)


@bot.command(name="tara", help="!tara [ip_aralığı] - Ağdaki aktif IP'leri göster")
async def scan_simple(ctx: commands.Context, ip_range: str = "192.168.1") -> None:
    """Basit IP taraması"""
    await ctx.send(f"🔍 Basit tarama başlatılıyor: `{ip_range}.x`...")
    
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
    
    if not active_ips:
        await ctx.send("❌ Aktif cihaz bulunamadı!")
        return
    
    embed = discord.Embed(
        title=f"📡 Aktif IP'ler ({len(active_ips)})",
        description="\n".join([f"`{ip}`" for ip in active_ips]),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Hologram cihazlarını bulmak için: !keşfet")
    await ctx.send(embed=embed)


@bot.command(name="ekle", help="!ekle <takma_ad> <device_id> <ip> - Cihaz ekle")
async def add_device(ctx: commands.Context, nickname: str, device_id: str, ip: str) -> None:
    """Cihaz ekle"""
    if nickname in HOLOGRAM_DEVICES:
        await ctx.send(f"⚠️ Bu takma ad zaten kullanılıyor: `{nickname}`")
        return
    
    # IP formatını kontrol et
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        await ctx.send("❌ Geçerli IP gir! (örn: 192.168.1.143)")
        return
    
    HOLOGRAM_DEVICES[nickname] = {
        "device_id": device_id,
        "ip": ip
    }
    
    # Bağlantıyı başlat
    bot.loop.create_task(connect_websocket(nickname))
    
    embed = discord.Embed(
        title="✅ Cihaz Eklendi",
        description=f"**Takma Ad:** `{nickname}`\n**Device ID:** `{device_id}`\n**IP:** `{ip}`",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    logger.info(f"Device added: {nickname} ({device_id}) @ {ip}")


@bot.command(name="isimdeğiştir", help="!isimdeğiştir <eski_ad> <yeni_ad> - Cihaz ismini değiştir")
async def rename_device(ctx: commands.Context, old_nickname: str, new_nickname: str) -> None:
    """Cihazın takma adını değiştir"""
    if old_nickname not in HOLOGRAM_DEVICES:
        await ctx.send(f"❌ Cihaz bulunamadı: `{old_nickname}`")
        return
    
    if new_nickname in HOLOGRAM_DEVICES:
        await ctx.send(f"⚠️ Bu takma ad zaten kullanılıyor: `{new_nickname}`")
        return
    
    # Cihaz bilgilerini kopyala
    HOLOGRAM_DEVICES[new_nickname] = HOLOGRAM_DEVICES[old_nickname]
    del HOLOGRAM_DEVICES[old_nickname]
    
    # WebSocket bağlantılarını güncelle
    if old_nickname in websockets_dict:
        websockets_dict[new_nickname] = websockets_dict[old_nickname]
        del websockets_dict[old_nickname]
    
    if old_nickname in websocket_connected_dict:
        websocket_connected_dict[new_nickname] = websocket_connected_dict[old_nickname]
        del websocket_connected_dict[old_nickname]
    
    embed = discord.Embed(
        title="✅ İsim Değiştirildi",
        description=f"`{old_nickname}` → `{new_nickname}`",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    logger.info(f"Device renamed: {old_nickname} → {new_nickname}")


@bot.command(name="çıkar", help="!çıkar <takma_ad> - Cihazı çıkar")
async def remove_device(ctx: commands.Context, nickname: str) -> None:
    """Cihaz çıkar"""
    if nickname not in HOLOGRAM_DEVICES:
        await ctx.send(f"❌ Cihaz bulunamadı: `{nickname}`")
        return
    
    device_info = HOLOGRAM_DEVICES[nickname]
    del HOLOGRAM_DEVICES[nickname]
    
    # WebSocket'i kapat
    if nickname in websockets_dict:
        try:
            await websockets_dict[nickname].close()
        except Exception:
            pass
        del websockets_dict[nickname]
    
    websocket_connected_dict[nickname] = False
    
    embed = discord.Embed(
        title="✅ Cihaz Çıkarıldı",
        description=(
            f"**Takma Ad:** `{nickname}`\n"
            f"**Device ID:** `{device_info['device_id']}`\n"
            f"**IP:** `{device_info['ip']}`"
        ),
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)
    logger.info(f"Device removed: {nickname}")


@bot.command(name="listele", help="!listele - Tüm cihazları listele")
async def list_devices(ctx: commands.Context) -> None:
    """Cihazları listele"""
    if not HOLOGRAM_DEVICES:
        await ctx.send("📭 Hiç cihaz yok!\n`!keşfet` komutuyla ağı tarayabilirsin.")
        return
    
    embed = discord.Embed(
        title="📋 Kayıtlı Cihazlar",
        color=discord.Color.blue()
    )
    
    for nickname, device_info in HOLOGRAM_DEVICES.items():
        is_connected = websocket_connected_dict.get(nickname, False)
        status_icon = "🟢" if is_connected else "🔴"
        status_text = "Bağlı" if is_connected else "Bağlı Değil"
        
        embed.add_field(
            name=f"{status_icon} {nickname}",
            value=(
                f"Device ID: `{device_info['device_id']}`\n"
                f"IP: `{device_info['ip']}`\n"
                f"Durum: {status_text}"
            ),
            inline=False
        )
    
    embed.set_footer(text=f"Toplam: {len(HOLOGRAM_DEVICES)} cihaz")
    await ctx.send(embed=embed)


# ===== MODEL/VIDEO KOMUTLARI =====
@bot.command(name="model", help="!model <url> - Tüm cihazlara model yükle")
async def load_model(ctx: commands.Context, *, url: str) -> None:
    """Model yükle"""
    if not (url.startswith("http://") or url.startswith("https://")):
        await ctx.send("❌ Geçerli URL gir!")
        return
    
    success = await send_command_to_all(f"model {url}")
    if success:
        embed = discord.Embed(
            title="🎬 Model Yükleniyor",
            description=f"`{url}`",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Komut gönderilemedi!")


@bot.command(name="video", help="!video <url> - Tüm cihazlara video yükle")
async def load_video(ctx: commands.Context, *, url: str) -> None:
    """Video yükle"""
    if not (url.startswith("http://") or url.startswith("https://")):
        await ctx.send("❌ Geçerli URL gir!")
        return
    
    success = await send_command_to_all(f"video {url}")
    if success:
        embed = discord.Embed(
            title="🎬 Video Yükleniyor",
            description=f"`{url}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Komut gönderilemedi!")


@bot.command(name="dur", help="!dur - Video'yu durdur")
async def stop_video(ctx: commands.Context) -> None:
    """Video durdur"""
    success = await send_command_to_all("stop_video")
    if success:
        await ctx.send("⏹️ Video durduruldu!")
    else:
        await ctx.send("❌ Komut gönderilemedi!")


# ===== AYAR KOMUTLARI =====
@bot.command(name="rpm", help="!rpm <sayı> - RPM ayarla")
async def set_rpm(ctx: commands.Context, rpm: int) -> None:
    """RPM ayarla"""
    if rpm < 0 or rpm > 2000:
        await ctx.send("❌ RPM 0-2000 arasında olmalı!")
        return
    
    success = await send_command_to_all(f"rpm {rpm}")
    if success:
        embed = discord.Embed(
            title="⚡ RPM Ayarlandı",
            description=f"**{rpm}** RPM",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Komut gönderilemedi!")


@bot.command(name="ışık", help="!ışık <sayı> - Işık şiddeti (0-5)")
async def set_light(ctx: commands.Context, light: float) -> None:
    """Işık ayarla"""
    if light < 0 or light > 5:
        await ctx.send("❌ Işık 0-5 arasında olmalı!")
        return
    
    success = await send_command_to_all(f"light {light}")
    if success:
        embed = discord.Embed(
            title="💡 Işık Ayarlandı",
            description=f"**{light}** şiddeti",
            color=discord.Color.yellow()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Komut gönderilemedi!")


@bot.command(name="faz", help="!faz <derece> - Faz açısı (0-360)")
async def set_phase(ctx: commands.Context, phase: int) -> None:
    """Faz ayarla"""
    if phase < 0 or phase > 360:
        await ctx.send("❌ Faz 0-360 arası olmalı!")
        return
    
    success = await send_command_to_all(f"phase {phase}")
    if success:
        await ctx.send(f"🔄 Faz **{phase}°** olarak ayarlandı!")
    else:
        await ctx.send("❌ Komut gönderilemedi!")


@bot.command(name="sıfırla", help="!sıfırla - Animasyonu başa al")
async def reset(ctx: commands.Context) -> None:
    """Sıfırla"""
    success = await send_command_to_all("reset")
    if success:
        await ctx.send("🔄 Sıfırlandı!")
    else:
        await ctx.send("❌ Komut gönderilemedi!")


@bot.command(name="durum", help="!durum - Bot durumunu göster")
async def status(ctx: commands.Context) -> None:
    """Durum göster"""
    if not HOLOGRAM_DEVICES:
        embed = discord.Embed(
            title="📊 Hologram Bot Durumu",
            description="❌ Hiç cihaz kayıtlı değil!\n`!keşfet` komutuyla ağı tarayabilirsin.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="📊 Hologram Bot Durumu",
        color=discord.Color.green()
    )
    
    for nickname, device_info in HOLOGRAM_DEVICES.items():
        is_connected = websocket_connected_dict.get(nickname, False)
        status_icon = "🟢" if is_connected else "🔴"
        status_text = "Bağlı" if is_connected else "Bağlı Değil"
        
        embed.add_field(
            name=f"{status_icon} {nickname}",
            value=(
                f"Device ID: `{device_info['device_id']}`\n"
                f"IP: `{device_info['ip']}`\n"
                f"Durum: {status_text}"
            ),
            inline=False
        )
    
    embed.set_footer(text=f"Toplam: {len(HOLOGRAM_DEVICES)} cihaz")
    await ctx.send(embed=embed)


# ===== KELİME KISAYOLLARI =====
@bot.command(name="kelime_ekle", help="!kelime_ekle kedi=url1 köpek=url2")
async def add_keywords(ctx: commands.Context, *, keywords: str) -> None:
    """Kelime-model eşleştirmesi ekle"""
    parts = re.split(r'[,\s]+', keywords)
    
    added: List[str] = []
    errors: List[str] = []
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if '=' not in part:
            errors.append(f"❌ Hatalı format: `{part}` (kelime=url olmalı)")
            continue
        
        keyword, url = part.split('=', 1)
        keyword = keyword.strip().lower()
        url = url.strip()
        
        if not (url.startswith("http://") or url.startswith("https://")):
            errors.append(f"❌ Geçersiz URL: `{keyword}` → `{url}`")
            continue
        
        MODEL_SHORTCUTS[keyword] = {
            "url": url,
            "repeat": 1
        }
        added.append(f"✅ `!{keyword}` → Model yükler")
    
    if added or errors:
        embed = discord.Embed(
            title="📝 Kelime Kısayolları Eklendi",
            color=discord.Color.green() if added else discord.Color.red()
        )
        
        if added:
            embed.add_field(
                name="Eklenen Kısayollar",
                value="\n".join(added),
                inline=False
            )
        
        if errors:
            embed.add_field(
                name="Hatalar",
                value="\n".join(errors),
                inline=False
            )
        
        embed.set_footer(text="Kullanım: !kelime | !kelime tekrar=5 | !kelime tekrar=∞")
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Hiçbir kelime eklenemedi! Format: `kelime=url`")


@bot.command(name="kelime_sil", help="!kelime_sil kedi köpek")
async def remove_keywords(ctx: commands.Context, *keywords: str) -> None:
    """Kelime kısayollarını sil"""
    if not keywords:
        await ctx.send("❌ En az bir kelime belirt! Örn: `!kelime_sil kedi köpek`")
        return
    
    removed: List[str] = []
    not_found: List[str] = []
    
    for keyword in keywords:
        keyword = keyword.lower().strip()
        if keyword in MODEL_SHORTCUTS:
            del MODEL_SHORTCUTS[keyword]
            removed.append(f"✅ `!{keyword}` silindi")
        else:
            not_found.append(f"❌ `!{keyword}` bulunamadı")
    
    embed = discord.Embed(
        title="🗑️ Kelime Kısayolları Silindi",
        color=discord.Color.orange()
    )
    
    if removed:
        embed.add_field(name="Silinenler", value="\n".join(removed), inline=False)
    
    if not_found:
        embed.add_field(name="Bulunamayanlar", value="\n".join(not_found), inline=False)
    
    await ctx.send(embed=embed)


@bot.command(name="kelimeler", help="!kelimeler - Tüm kelime kısayollarını listele")
async def list_keywords(ctx: commands.Context) -> None:
    """Kayıtlı kelime kısayollarını listele"""
    if not MODEL_SHORTCUTS:
        await ctx.send("📭 Hiç kelime kısayolu yok!\n`!kelime_ekle` komutuyla ekleyebilirsin.")
        return
    
    embed = discord.Embed(
        title="📖 Kayıtlı Kelime Kısayolları",
        description=f"Toplam: **{len(MODEL_SHORTCUTS)}** kısayol",
        color=discord.Color.purple()
    )
    
    keywords_list: List[str] = []
    for keyword, data in sorted(MODEL_SHORTCUTS.items()):
        url = data["url"]
        short_url = url[:50] + "..." if len(url) > 50 else url
        keywords_list.append(f"`!{keyword}` → {short_url}")
    
    # 10'ar 10'ar grupla
    for i in range(0, len(keywords_list), 10):
        chunk = keywords_list[i:i + 10]
        embed.add_field(
            name=f"Grup {i // 10 + 1}",
            value="\n".join(chunk),
            inline=False
        )
    
    embed.set_footer(text="Kullanım: !kelime | !kelime tekrar=5 | !kelime tekrar=∞")
    await ctx.send(embed=embed)


@bot.command(name="yardım", help="!yardım - Komutları göster")
async def help_command(ctx: commands.Context) -> None:
    """Yardım"""
    embed = discord.Embed(
        title="🤖 Hologram Bot Komutları",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🔍 Cihaz Bulma",
        value=(
            "`!keşfet [ip_aralığı]` - Hologram cihazlarını keşfet\n"
            "`!tara [ip_aralığı]` - Sadece aktif IP'leri göster"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔐 Cihaz Yönetimi",
        value=(
            "`!ekle <takma_ad> <device_id> <ip>` - Cihaz ekle\n"
            "`!isimdeğiştir <eski> <yeni>` - İsim değiştir\n"
            "`!çıkar <takma_ad>` - Cihaz çıkar\n"
            "`!listele` - Tüm cihazları göster"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚡ Kelime Kısayolları",
        value=(
            "`!kelime_ekle kedi=url1 köpek=url2` - Kısayol ekle\n"
            "`!kelimeler` - Tüm kısayolları listele\n"
            "`!kelime_sil kedi köpek` - Kısayol sil\n\n"
            "**Kullanım:**\n"
            "`!kedi` - 1 kere oynat\n"
            "`!kedi tekrar=5` - 5 kere oynat\n"
            "`!kedi tekrar=∞` - Sonsuz döngü 🔄"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎬 Model/Video",
        value=(
            "`!model <url>` - Model yükle\n"
            "`!video <url>` - Video yükle\n"
            "`!dur` - Video durdur"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎛️ Ayarlar",
        value=(
            "`!rpm <sayı>` - RPM ayarla\n"
            "`!ışık <sayı>` - Işık ayarla\n"
            "`!faz <derece>` - Faz ayarla"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Diğer",
        value=(
            "`!sıfırla` - Animasyon başa al\n"
            "`!durum` - Bot durumu"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)


# ===== BOT BAŞLAT =====
if __name__ == "__main__":
    logger.info("🤖 Hologram Bot başlatılıyor...")
    
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN boş! Lütfen token'ınızı ekleyin.")
        exit(1)
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Token geçersiz!")
    except Exception as e:
        logger.error(f"❌ Hata: {e}")