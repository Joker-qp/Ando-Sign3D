"""
Hologram Kontrol GUI - CustomTkinter
Discord bot özelliklerinin tamamını içeren masaüstü uygulaması
+ Gelişmiş Çeviri ve Ses Tanıma Modülü
+ Akıllı Kısayol Eşleştirme Sistemi
"""

import customtkinter as ctk
import asyncio
import websockets
import json
import os
import threading
import socket
import platform
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

# Yeni kütüphaneler
try:
    from deep_translator import GoogleTranslator
    from langdetect import detect, LangDetectException
    TRANSLATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Çeviri modülü yüklenemedi: {e}")
    print("Lütfen şu komutu çalıştırın: pip install deep-translator langdetect")
    TRANSLATION_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    print("⚠️ Ses tanıma modülü yüklenemedi")
    print("Lütfen şu komutu çalıştırın: pip install SpeechRecognition pyaudio")
    SPEECH_AVAILABLE = False

# ===== LOGGING AYARLARI =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gui.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== KONFİGÜRASYON =====
CONFIG_FILE = "gui_config.json"
SETTINGS_FILE = "gui_settings.json"

class HologramConfig:
    """Konfigürasyon yöneticisi"""
    
    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.shortcuts: Dict[str, Dict[str, Any]] = {}
        self.settings: Dict[str, Any] = {
            "theme": "dark",
            "color_theme": "blue",
            "default_port": 8080,
            "scan_timeout": 2,
            "reconnect_delay": 3,
            "heartbeat_interval": 5,
            "default_ip_range": "192.168.1",
            "translation_source": "auto",
            "translation_target": "tr",
            "mic_timeout": 5,
            "mic_phrase_time": 3
        }
        self.load_all()
    
    def load_all(self):
        """Tüm ayarları yükle"""
        self.load_config()
        self.load_settings()
    
    def load_config(self):
        """Cihaz ve kısayol ayarlarını yükle"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.devices = data.get('devices', {})
                    self.shortcuts = data.get('shortcuts', {})
                logger.info(f"✅ Config yüklendi: {len(self.devices)} cihaz, {len(self.shortcuts)} kısayol")
        except Exception as e:
            logger.error(f"Config yükleme hatası: {e}")
    
    def save_config(self):
        """Cihaz ve kısayol ayarlarını kaydet"""
        try:
            data = {
                'devices': self.devices,
                'shortcuts': self.shortcuts
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("✅ Config kaydedildi")
        except Exception as e:
            logger.error(f"Config kaydetme hatası: {e}")
    
    def load_settings(self):
        """Uygulama ayarlarını yükle"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
                logger.info("✅ Ayarlar yüklendi")
        except Exception as e:
            logger.error(f"Ayarlar yükleme hatası: {e}")
    
    def save_settings(self):
        """Uygulama ayarlarını kaydet"""
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.info("✅ Ayarlar kaydedildi")
        except Exception as e:
            logger.error(f"Ayarlar kaydetme hatası: {e}")


class TranslationModule:
    """Çeviri ve ses tanıma modülü"""
    
    def __init__(self, config: HologramConfig):
        self.config = config
        self.recognizer = None
        self.microphone = None
        self.is_listening = False
        
        if SPEECH_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                logger.info("✅ Ses tanıma modülü hazır")
            except Exception as e:
                logger.error(f"❌ Ses tanıma başlatılamadı: {e}")
    
    def translate_content(self, text: str, target_lang: str = None) -> Dict[str, Any]:
        """Metni otomatik algılayıp hedef dile çevir"""
        if not TRANSLATION_AVAILABLE:
            return {
                "success": False,
                "original": text,
                "translated": "",
                "detected_lang": "",
                "error": "Çeviri modülü yüklü değil."
            }
        
        if not text or not text.strip():
            return {
                "success": False,
                "original": "",
                "translated": "",
                "detected_lang": "",
                "error": "Boş metin çevrilemez!"
            }
        
        if target_lang is None:
            target_lang = self.config.settings.get("translation_target", "tr")
        
        try:
            try:
                detected_lang = detect(text)
            except LangDetectException:
                detected_lang = "en"
            
            logger.info(f"🔍 Algılanan dil: {detected_lang}")
            
            if detected_lang == target_lang:
                return {
                    "success": True,
                    "original": text,
                    "translated": text,
                    "detected_lang": detected_lang,
                    "error": ""
                }
            
            translator = GoogleTranslator(source=detected_lang, target=target_lang)
            translated_text = translator.translate(text)
            
            logger.info(f"✅ Çeviri başarılı: {detected_lang} → {target_lang}")
            
            return {
                "success": True,
                "original": text,
                "translated": translated_text,
                "detected_lang": detected_lang,
                "error": ""
            }
            
        except Exception as e:
            error_msg = f"Çeviri hatası: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "original": text,
                "translated": "",
                "detected_lang": "",
                "error": error_msg
            }
    
    def translate_content_manual(self, text: str, source_lang: str, target_lang: str) -> Dict[str, Any]:
        """Manuel kaynak ve hedef dil ile çevir"""
        if not TRANSLATION_AVAILABLE:
            return {
                "success": False,
                "original": text,
                "translated": "",
                "detected_lang": "",
                "error": "Çeviri modülü yüklü değil."
            }
        
        if not text or not text.strip():
            return {
                "success": False,
                "original": "",
                "translated": "",
                "detected_lang": "",
                "error": "Boş metin çevrilemez!"
            }
        
        try:
            if source_lang == target_lang:
                return {
                    "success": True,
                    "original": text,
                    "translated": text,
                    "detected_lang": source_lang,
                    "error": "Kaynak ve hedef dil aynı, çeviri yapılmadı."
                }
            
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated_text = translator.translate(text)
            
            logger.info(f"✅ Çeviri başarılı: {source_lang} → {target_lang}")
            
            return {
                "success": True,
                "original": text,
                "translated": translated_text,
                "detected_lang": source_lang,
                "error": ""
            }
            
        except Exception as e:
            error_msg = f"Çeviri hatası: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "original": text,
                "translated": "",
                "detected_lang": "",
                "error": error_msg
            }
    
    def capture_voice(self, timeout: int = None, phrase_time_limit: int = None) -> Dict[str, Any]:
        """Mikrofonu dinleyip sesi metne dönüştür"""
        if not SPEECH_AVAILABLE:
            return {
                "success": False,
                "text": "",
                "error": "Ses tanıma modülü yüklü değil."
            }
        
        if self.recognizer is None or self.microphone is None:
            return {
                "success": False,
                "text": "",
                "error": "Ses tanıma modülü kullanılamıyor."
            }
        
        if timeout is None:
            timeout = self.config.settings.get("mic_timeout", 5)
        
        if phrase_time_limit is None:
            phrase_time_limit = self.config.settings.get("mic_phrase_time", 3)
        
        try:
            self.is_listening = True
            logger.info("🎤 Mikrofon dinleniyor...")
            
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
            
            self.is_listening = False
            logger.info("🔊 Ses kaydedildi, tanınıyor...")
            
            text = self.recognizer.recognize_google(audio, language='tr-TR')
            
            logger.info(f"✅ Ses tanındı: {text}")
            
            return {
                "success": True,
                "text": text,
                "error": ""
            }
            
        except sr.WaitTimeoutError:
            self.is_listening = False
            error_msg = "Zaman aşımı: Mikrofon sesi algılamadı"
            logger.warning(f"⏱️ {error_msg}")
            return {
                "success": False,
                "text": "",
                "error": error_msg
            }
        
        except sr.UnknownValueError:
            self.is_listening = False
            error_msg = "Ses anlaşılamadı, lütfen tekrar deneyin"
            logger.warning(f"❓ {error_msg}")
            return {
                "success": False,
                "text": "",
                "error": error_msg
            }
        
        except sr.RequestError as e:
            self.is_listening = False
            error_msg = f"Google API hatası: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "text": "",
                "error": error_msg
            }
        
        except Exception as e:
            self.is_listening = False
            error_msg = f"Bilinmeyen hata: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "text": "",
                "error": error_msg
            }


class WebSocketManager:
    """WebSocket bağlantı yöneticisi"""
    
    def __init__(self, config: HologramConfig):
        self.config = config
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.connected: Dict[str, bool] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stats = {
            "messages_sent": 0,
            "devices_discovered": 0,
            "uptime_start": datetime.now()
        }
    
    def start_loop(self):
        """Asyncio event loop'u başlat"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        
        import time
        time.sleep(0.1)
    
    def run_coroutine(self, coro):
        """Coroutine'i event loop'ta çalıştır"""
        if self.loop:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None
    
    async def scan_network(self, ip_range: str) -> List[Dict[str, Any]]:
        """Ağdaki cihazları tara"""
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
        
        ping_tasks = [ping_ip(i) for i in range(1, 255)]
        ping_results = await asyncio.gather(*ping_tasks)
        active_ips = [ip for ip in ping_results if ip is not None]
        
        logger.info(f"📡 {len(active_ips)} aktif IP bulundu")
        
        ws_tasks = [self.check_device(ip) for ip in active_ips]
        ws_results = await asyncio.gather(*ws_tasks)
        found_devices = [device for device in ws_results if device["found"]]
        
        logger.info(f"✅ {len(found_devices)} hologram cihazı bulundu")
        self.stats["devices_discovered"] += len(found_devices)
        
        return found_devices
    
    async def check_device(self, ip: str) -> Dict[str, Any]:
        """Bir IP'de hologram cihazı olup olmadığını kontrol et"""
        port = self.config.settings["default_port"]
        try:
            ws_url = f"ws://{ip}:{port}/ws"
            async with asyncio.timeout(self.config.settings["scan_timeout"]):
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
    
    async def connect_device(self, nickname: str):
        """Bir cihaza bağlan ve heartbeat başlat"""
        device_info = self.config.devices.get(nickname)
        if not device_info:
            return
        
        port = self.config.settings["default_port"]
        device_id = device_info["device_id"]
        websocket_url = f"ws://{device_info['ip']}:{port}/ws"
        reconnect_delay = self.config.settings["reconnect_delay"]
        max_reconnect_delay = 30
        
        while nickname in self.config.devices:
            try:
                async with websockets.connect(websocket_url, ping_interval=None) as ws:
                    self.connections[nickname] = ws
                    self.connected[nickname] = True
                    reconnect_delay = self.config.settings["reconnect_delay"]
                    
                    logger.info(f"✅ [{nickname}] Bağlandı: {device_info['ip']}")
                    
                    try:
                        while self.connected.get(nickname, False):
                            await ws.send(f"PING {device_id}")
                            logger.debug(f"[{nickname}] PING gönderildi")
                            await asyncio.sleep(self.config.settings["heartbeat_interval"])
                            
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(f"⚠️ [{nickname}] Bağlantı kapandı")
                    except Exception as e:
                        logger.error(f"❌ [{nickname}] Heartbeat hatası: {e}")
                        
            except Exception as e:
                logger.error(f"❌ [{nickname}] Bağlantı hatası: {e}")
                self.connected[nickname] = False
                
                logger.info(f"🔄 [{nickname}] {reconnect_delay}s sonra yeniden bağlanılacak...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
        
        self.connected[nickname] = False
        if nickname in self.connections:
            del self.connections[nickname]
        logger.info(f"🔌 [{nickname}] Bağlantı sonlandırıldı")
    
    async def send_command(self, nickname: str, command: str) -> bool:
        """Bir cihaza komut gönder"""
        device_info = self.config.devices.get(nickname)
        if not device_info:
            return False
        
        ws = self.connections.get(nickname)
        if not ws or not self.connected.get(nickname, False):
            logger.warning(f"⚠️ [{nickname}] Bağlı değil")
            return False
        
        try:
            message = f"{device_info['device_id']} {command}"
            await ws.send(message)
            logger.info(f"📤 [{nickname}] Komut gönderildi: {command}")
            self.stats["messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"❌ [{nickname}] Gönderme hatası: {e}")
            self.connected[nickname] = False
            return False
    
    async def send_command_all(self, command: str) -> tuple[int, int]:
        """Tüm cihazlara komut gönder"""
        if not self.config.devices:
            return 0, 0
        
        tasks = []
        for nickname in self.config.devices.keys():
            tasks.append(self.send_command(nickname, command))
        
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r)
        total_count = len(self.config.devices)
        
        return success_count, total_count
    
    def connect_device_sync(self, nickname: str):
        """Senkron şekilde cihaza bağlan"""
        if self.loop:
            task = asyncio.run_coroutine_threadsafe(
                self.connect_device(nickname), 
                self.loop
            )
            self.tasks[nickname] = task
    
    def disconnect_device(self, nickname: str):
        """Cihaz bağlantısını kes"""
        self.connected[nickname] = False
        if nickname in self.tasks:
            self.tasks[nickname].cancel()
            del self.tasks[nickname]
    
    def get_connected_count(self) -> int:
        """Bağlı cihaz sayısı"""
        return sum(1 for v in self.connected.values() if v)


class HologramGUI:
    """Ana GUI sınıfı"""
    
    def __init__(self):
        self.config = HologramConfig()
        self.ws_manager = WebSocketManager(self.config)
        self.translation_module = TranslationModule(self.config)
        
        ctk.set_appearance_mode(self.config.settings["theme"])
        ctk.set_default_color_theme(self.config.settings["color_theme"])
        
        self.root = ctk.CTk()
        self.root.title("🌐 Hologram Kontrol Merkezi")
        self.root.geometry("1200x800")
        
        self.ws_manager.start_loop()
        
        self.create_gui()
        self.connect_saved_devices()
        self.update_status()
    
    def create_gui(self):
        """GUI bileşenlerini oluştur"""
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        self.create_sidebar()
        
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        self.show_devices_page()
    
    def create_sidebar(self):
        """Sol menü çubuğunu oluştur"""
        sidebar = ctk.CTkFrame(self.root, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(11, weight=1)
        
        title = ctk.CTkLabel(
            sidebar, 
            text="🌐 Hologram\nKontrol",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=20, pady=20)
        
        buttons = [
            ("📋 Cihazlar", self.show_devices_page),
            ("🎮 Kontrol", self.show_control_page),
            ("🔖 Kısayollar", self.show_shortcuts_page),
            ("🔍 Tarama", self.show_scan_page),
            ("🗣️ Çeviri", self.show_translation_page),
            ("📊 Durum", self.show_status_page),
            ("⚙️ Ayarlar", self.show_settings_page),
        ]
        
        for i, (text, command) in enumerate(buttons, 1):
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                command=command,
                font=ctk.CTkFont(size=14),
                height=40
            )
            btn.grid(row=i, column=0, padx=20, pady=10, sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            sidebar,
            text="🔴 Bağlantı Yok",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=12, column=0, padx=20, pady=20)
    
    def clear_main_frame(self):
        """Ana içerik alanını temizle"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
    
    # ==================== YENİ: KISAYOL EŞLEŞTIRME FONKSİYONLARI ====================
    
    def find_matching_shortcut(self, translated_text: str) -> Optional[tuple[str, Dict[str, Any]]]:
        """Çeviri sonucuna göre eşleşen kısayol bul"""
        if not self.config.shortcuts:
            return None
        
        search_text = translated_text.lower().strip()
        
        # Tam eşleşme
        if search_text in self.config.shortcuts:
            return (search_text, self.config.shortcuts[search_text])
        
        # Kısmi eşleşme
        for keyword, info in self.config.shortcuts.items():
            if keyword in search_text or search_text in keyword:
                return (keyword, info)
        
        return None
    
    def show_shortcut_match_dialog(self, keyword: str, shortcut_info: Dict[str, Any], translated_text: str):
        """Kısayol bulundu dialog'u"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("🎯 Kısayol Bulundu!")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="✨ Eşleşen Kısayol Bulundu!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#4ECDC4"
        ).pack(pady=20)
        
        info_frame = ctk.CTkFrame(dialog)
        info_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text=f"📝 Çeviri Sonucu:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(10, 5))
        
        ctk.CTkLabel(
            info_frame,
            text=f'"{translated_text}"',
            font=ctk.CTkFont(size=14),
            text_color="#95A5A6"
        ).pack(pady=5)
        
        ctk.CTkLabel(
            info_frame,
            text=f"🔖 Bulunan Kısayol:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(15, 5))
        
        ctk.CTkLabel(
            info_frame,
            text=f"!{keyword}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#4ECDC4"
        ).pack(pady=5)
        
        ctk.CTkLabel(
            info_frame,
            text=f"🔗 {shortcut_info['url']}",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=5)
        
        if shortcut_info.get('description'):
            ctk.CTkLabel(
                info_frame,
                text=f"📄 {shortcut_info['description']}",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            ).pack(pady=5)
        
        ctk.CTkLabel(
            dialog,
            text="Bu modeli cihazlara göndermek ister misiniz?",
            font=ctk.CTkFont(size=13)
        ).pack(pady=15)
        
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=15)
        
        def play_shortcut():
            self.run_shortcut(keyword)
            dialog.destroy()
            self.update_translation_info(f"▶️ '{keyword}' kısayolu çalıştırıldı!", "green")
        
        def close_dialog():
            dialog.destroy()
            self.update_translation_info(f"ℹ️ Kısayol çalıştırılmadı", "gray")
        
        ctk.CTkButton(
            btn_frame,
            text="▶️ Oynat",
            command=play_shortcut,
            fg_color="#4ECDC4",
            hover_color="#3DA9A1",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ İptal",
            command=close_dialog,
            fg_color="#95A5A6",
            hover_color="#7F8C8D",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=10)
    
    def show_no_shortcut_dialog(self, translated_text: str):
        """Kısayol bulunamadı dialog'u"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("ℹ️ Kısayol Bulunamadı")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="🔍",
            font=ctk.CTkFont(size=50)
        ).pack(pady=20)
        
        ctk.CTkLabel(
            dialog,
            text="Kısayol Bulunamadı",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        
        ctk.CTkLabel(
            dialog,
            text=f'"{translated_text}" için\neşleşen bir kısayol bulunamadı.',
            font=ctk.CTkFont(size=13),
            text_color="gray"
        ).pack(pady=10)
        
        ctk.CTkButton(
            dialog,
            text="Tamam",
            command=dialog.destroy,
            width=150,
            height=40,
            font=ctk.CTkFont(size=14)
        ).pack(pady=20)
    
    def check_and_show_shortcut(self, translated_text: str):
        """Çeviri sonucunu kontrol et ve eşleşen kısayol varsa göster"""
        match = self.find_matching_shortcut(translated_text)
        
        if match:
            keyword, shortcut_info = match
            logger.info(f"🎯 Kısayol eşleşmesi bulundu: '{keyword}' → '{translated_text}'")
            self.show_shortcut_match_dialog(keyword, shortcut_info, translated_text)
        else:
            logger.info(f"🔍 '{translated_text}' için kısayol bulunamadı")
            self.show_no_shortcut_dialog(translated_text)
    
    # ==================== ÇEVİRİ SAYFASI ====================
    
    def show_translation_page(self):
        """Çeviri ve ses tanıma sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="🗣️ Çeviri ve Ses Tanıma",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        container = ctk.CTkFrame(self.main_frame)
        container.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # GİRİŞ ALANI
        input_frame = ctk.CTkFrame(container)
        input_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            input_frame,
            text="📝 Metin Girişi:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        self.translation_input = ctk.CTkTextbox(input_frame, height=120)
        self.translation_input.pack(fill="x", padx=20, pady=5)
        
        btn_frame = ctk.CTkFrame(input_frame)
        btn_frame.pack(pady=10)
        
        mic_container = ctk.CTkFrame(btn_frame, fg_color="transparent")
        mic_container.pack(side="left", padx=5)
        
        self.mic_button = ctk.CTkButton(
            mic_container,
            text="🎤 Sesi Dinle",
            command=self.start_voice_capture,
            fg_color="#FF6B6B",
            hover_color="#CC5555",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.mic_button.pack()
        
        self.mic_indicator = ctk.CTkLabel(
            mic_container,
            text="⚪ Hazır",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.mic_indicator.pack(pady=2)
        
        ctk.CTkButton(
            btn_frame,
            text="🌐 Çevir",
            command=self.translate_text,
            fg_color="#4ECDC4",
            hover_color="#3DA9A1",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Temizle",
            command=self.clear_translation,
            fg_color="#95A5A6",
            hover_color="#7F8C8D",
            width=120,
            height=40
        ).pack(side="left", padx=5)
        
        # ÇIKTI ALANI
        output_frame = ctk.CTkFrame(container)
        output_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(
            output_frame,
            text="🎯 Çeviri Sonucu:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        self.translation_output = ctk.CTkTextbox(output_frame, height=150)
        self.translation_output.pack(fill="both", expand=True, padx=20, pady=5)
        self.translation_output.configure(state="disabled")
        
        self.translation_info_label = ctk.CTkLabel(
            output_frame,
            text="ℹ️ Metin girin veya mikrofona konuşun",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.translation_info_label.pack(pady=10)
        
        # DİL AYARLARI
        settings_frame = ctk.CTkFrame(container)
        settings_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            settings_frame,
            text="⚙️ Çeviri Ayarları:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=10)
        
        lang_selection_frame = ctk.CTkFrame(settings_frame)
        lang_selection_frame.pack(pady=10)
        
        self.languages = [
            ("🔄 Otomatik Algıla", "auto"),
            ("🇹🇷 Türkçe", "tr"),
            ("🇬🇧 İngilizce", "en"),
            ("🇩🇪 Almanca", "de"),
            ("🇫🇷 Fransızca", "fr"),
            ("🇪🇸 İspanyolca", "es"),
            ("🇮🇹 İtalyanca", "it"),
            ("🇷🇺 Rusça", "ru"),
            ("🇨🇳 Çince (Basitleştirilmiş)", "zh-CN"),
            ("🇯🇵 Japonca", "ja"),
            ("🇰🇷 Korece", "ko"),
            ("🇸🇦 Arapça", "ar"),
            ("🇵🇹 Portekizce", "pt"),
            ("🇳🇱 Hollandaca", "nl"),
            ("🇵🇱 Lehçe", "pl"),
            ("🇬🇷 Yunanca", "el"),
            ("🇮🇳 Hintçe", "hi"),
            ("🇹🇭 Tayca", "th"),
            ("🇻🇳 Vietnamca", "vi"),
            ("🇮🇩 Endonezce", "id"),
            ("🇸🇪 İsveççe", "sv"),
            ("🇳🇴 Norveççe", "no"),
            ("🇩🇰 Danca", "da"),
            ("🇫🇮 Fince", "fi"),
            ("🇨🇿 Çekçe", "cs"),
            ("🇭🇺 Macarca", "hu"),
            ("🇷🇴 Rumence", "ro"),
            ("🇺🇦 Ukraynaca", "uk"),
            ("🇮🇷 Farsça", "fa"),
            ("🇮🇱 İbranice", "he")
        ]
        
        self.lang_codes = {lang[0]: lang[1] for lang in self.languages}
        self.lang_names = {lang[1]: lang[0] for lang in self.languages}
        
        # Kaynak Dil
        source_lang_frame = ctk.CTkFrame(lang_selection_frame)
        source_lang_frame.pack(side="left", padx=10)
        
        ctk.CTkLabel(
            source_lang_frame,
            text="📥 Kaynak Dil:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=5)
        
        self.source_lang_var = ctk.StringVar(
            value=self.config.settings.get("translation_source", "auto")
        )
        
        self.source_lang_menu = ctk.CTkOptionMenu(
            source_lang_frame,
            values=[lang[0] for lang in self.languages],
            variable=self.source_lang_var,
            command=self.update_source_language,
            width=250,
            font=ctk.CTkFont(size=12)
        )
        self.source_lang_menu.pack(pady=5)
        
        current_source = self.config.settings.get("translation_source", "auto")
        if current_source in self.lang_names:
            self.source_lang_menu.set(self.lang_names[current_source])
        
        # Ok
        arrow_frame = ctk.CTkFrame(lang_selection_frame, fg_color="transparent")
        arrow_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(
            arrow_frame,
            text="➡️",
            font=ctk.CTkFont(size=30)
        ).pack(pady=30)
        
        # Hedef Dil
        target_lang_frame = ctk.CTkFrame(lang_selection_frame)
        target_lang_frame.pack(side="left", padx=10)
        
        ctk.CTkLabel(
            target_lang_frame,
            text="📤 Hedef Dil:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=5)
        
        self.target_lang_var = ctk.StringVar(
            value=self.config.settings.get("translation_target", "tr")
        )
        
        target_languages = [lang for lang in self.languages if lang[1] != "auto"]
        
        self.target_lang_menu = ctk.CTkOptionMenu(
            target_lang_frame,
            values=[lang[0] for lang in target_languages],
            variable=self.target_lang_var,
            command=self.update_target_language,
            width=250,
            font=ctk.CTkFont(size=12)
        )
        self.target_lang_menu.pack(pady=5)
        
        current_target = self.config.settings.get("translation_target", "tr")
        if current_target in self.lang_names:
            self.target_lang_menu.set(self.lang_names[current_target])
        
        # Dil değiştir
        swap_btn_frame = ctk.CTkFrame(settings_frame)
        swap_btn_frame.pack(pady=10)
        
        ctk.CTkButton(
            swap_btn_frame,
            text="🔄 Dilleri Değiştir",
            command=self.swap_languages,
            width=200,
            height=35,
            font=ctk.CTkFont(size=13)
        ).pack()
        
        # Hızlı çeviri
        quick_frame = ctk.CTkFrame(settings_frame)
        quick_frame.pack(pady=10)
        
        ctk.CTkLabel(
            quick_frame,
            text="⚡ Hızlı Çeviri:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=10)
        
        quick_translations = [
            ("🇹🇷→🇬🇧", "tr", "en"),
            ("🇬🇧→🇹🇷", "en", "tr"),
            ("🇹🇷→🇩🇪", "tr", "de"),
            ("🇩🇪→🇹🇷", "de", "tr"),
        ]
        
        for label, source, target in quick_translations:
            ctk.CTkButton(
                quick_frame,
                text=label,
                command=lambda s=source, t=target: self.set_quick_translation(s, t),
                width=80,
                height=30,
                font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=3)
    
    def update_source_language(self, selected: str):
        """Kaynak dili güncelle"""
        lang_code = self.lang_codes.get(selected, "auto")
        self.config.settings["translation_source"] = lang_code
        self.config.save_settings()
        logger.info(f"📥 Kaynak dil değiştirildi: {lang_code}")
    
    def update_target_language(self, selected: str):
        """Hedef dili güncelle"""
        lang_code = self.lang_codes.get(selected, "tr")
        
        if lang_code == "auto":
            self.update_translation_info("⚠️ Hedef dil 'Otomatik' olamaz!", "orange")
            self.target_lang_menu.set(self.lang_names["tr"])
            self.config.settings["translation_target"] = "tr"
            return
        
        self.config.settings["translation_target"] = lang_code
        self.config.save_settings()
        logger.info(f"📤 Hedef dil değiştirildi: {lang_code}")
    
    def swap_languages(self):
        """Dilleri değiştir"""
        source = self.config.settings.get("translation_source", "auto")
        target = self.config.settings.get("translation_target", "tr")
        
        if source == "auto":
            self.update_translation_info("⚠️ Otomatik algılama aktifken dil değiştirilemez!", "orange")
            return
        
        self.config.settings["translation_source"] = target
        self.config.settings["translation_target"] = source
        self.config.save_settings()
        
        self.source_lang_menu.set(self.lang_names[target])
        self.target_lang_menu.set(self.lang_names[source])
        
        self.update_translation_info(f"🔄 Diller değiştirildi: {self.lang_names[target]} ↔️ {self.lang_names[source]}", "blue")
    
    def set_quick_translation(self, source: str, target: str):
        """Hızlı çeviri ayarla"""
        self.config.settings["translation_source"] = source
        self.config.settings["translation_target"] = target
        self.config.save_settings()
        
        self.source_lang_menu.set(self.lang_names[source])
        self.target_lang_menu.set(self.lang_names[target])
        
        self.update_translation_info(f"⚡ {self.lang_names[source]} → {self.lang_names[target]} ayarlandı", "green")
    
    def update_mic_indicator(self, status: str):
        """Mikrofon göstergesini güncelle"""
        if hasattr(self, 'mic_indicator'):
            if status == "listening":
                self.mic_indicator.configure(text="🔴 Dinleniyor...", text_color="#FF6B6B")
            elif status == "processing":
                self.mic_indicator.configure(text="⚙️ İşleniyor...", text_color="#FFA500")
            elif status == "idle":
                self.mic_indicator.configure(text="⚪ Hazır", text_color="gray")
            elif status == "error":
                self.mic_indicator.configure(text="❌ Hata", text_color="red")
    
    def start_voice_capture(self):
        """Ses yakalamayı başlat"""
        self.mic_button.configure(state="disabled", text="🎤 Dinleniyor...")
        self.update_translation_info("🎤 Lütfen konuşun...", "orange")
        self.update_mic_indicator("listening")
        
        def capture_thread():
            try:
                result = self.translation_module.capture_voice()
                self.root.after(0, lambda: self.handle_voice_result(result))
            except Exception as e:
                logger.error(f"Ses yakalama hatası: {e}")
                self.root.after(0, lambda: self.update_translation_info(f"❌ Hata: {str(e)}", "red"))
                self.root.after(0, lambda: self.update_mic_indicator("error"))
            finally:
                self.root.after(0, lambda: self.mic_button.configure(state="normal", text="🎤 Sesi Dinle"))
        
        thread = threading.Thread(target=capture_thread, daemon=True)
        thread.start()
    
    def handle_voice_result(self, result: Dict[str, Any]):
        """Ses tanıma sonucunu işle"""
        if result["success"]:
            self.update_mic_indicator("processing")
            
            self.translation_input.delete("1.0", "end")
            self.translation_input.insert("1.0", result["text"])
            
            self.update_translation_info(f"✅ Ses tanındı: \"{result['text']}\"", "green")
            
            self.translate_text()
            
            self.root.after(2000, lambda: self.update_mic_indicator("idle"))
        else:
            self.update_translation_info(f"❌ {result['error']}", "red")
            self.update_mic_indicator("error")
            self.root.after(2000, lambda: self.update_mic_indicator("idle"))
    
    def translate_text(self):
        """Metni çevir"""
        text = self.translation_input.get("1.0", "end-1c").strip()
        
        if not text:
            self.update_translation_info("⚠️ Lütfen metin girin!", "orange")
            return
        
        self.update_translation_info("🔄 Çevriliyor...", "blue")
        
        def translate_thread():
            try:
                source_lang = self.config.settings.get("translation_source", "auto")
                target_lang = self.config.settings.get("translation_target", "tr")
                
                if source_lang == "auto":
                    result = self.translation_module.translate_content(text, target_lang)
                else:
                    result = self.translation_module.translate_content_manual(text, source_lang, target_lang)
                
                self.root.after(0, lambda: self.handle_translation_result(result))
                
            except Exception as e:
                logger.error(f"Çeviri hatası: {e}")
                self.root.after(0, lambda: self.update_translation_info(f"❌ Hata: {str(e)}", "red"))
        
        thread = threading.Thread(target=translate_thread, daemon=True)
        thread.start()
    
    def handle_translation_result(self, result: Dict[str, Any]):
        """Çeviri sonucunu göster - KISAYOL KONTROLÜ EKLENDİ"""
        if result["success"]:
            self.translation_output.configure(state="normal")
            self.translation_output.delete("1.0", "end")
            self.translation_output.insert("1.0", result["translated"])
            self.translation_output.configure(state="disabled")
            
            source_lang = self.config.settings.get("translation_source", "auto")
            target_lang = self.config.settings.get("translation_target", "tr")
            
            if source_lang == "auto":
                detected = result["detected_lang"].upper()
                target = target_lang.upper()
                self.update_translation_info(f"✅ Çeviri tamamlandı (Algılanan: {detected} → {target})", "green")
            else:
                source = source_lang.upper()
                target = target_lang.upper()
                self.update_translation_info(f"✅ Çeviri tamamlandı ({source} → {target})", "green")
            
            # KISAYOL KONTROLÜ
            self.root.after(500, lambda: self.check_and_show_shortcut(result["translated"]))
            
        else:
            self.update_translation_info(f"❌ {result['error']}", "red")
    
    def clear_translation(self):
        """Çeviri alanlarını temizle"""
        self.translation_input.delete("1.0", "end")
        self.translation_output.configure(state="normal")
        self.translation_output.delete("1.0", "end")
        self.translation_output.configure(state="disabled")
        
        source = self.config.settings.get("translation_source", "auto")
        target = self.config.settings.get("translation_target", "tr")
        
        source_name = self.lang_names.get(source, "Bilinmiyor")
        target_name = self.lang_names.get(target, "Bilinmiyor")
        
        self.update_translation_info(f"ℹ️ Hazır: {source_name} → {target_name}", "gray")
        self.update_mic_indicator("idle")
    
    def update_translation_info(self, message: str, color: str = "gray"):
        """Bilgi etiketini güncelle"""
        if hasattr(self, 'translation_info_label'):
            self.translation_info_label.configure(text=message, text_color=color)
    
    # ==================== DİĞER SAYFALAR (AYNEN KALDI) ====================
    
    def show_devices_page(self):
        """Cihazlar sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="📋 Kayıtlı Cihazlar",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        btn_frame = ctk.CTkFrame(self.main_frame)
        btn_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkButton(
            btn_frame,
            text="➕ Cihaz Ekle",
            command=self.show_add_device_dialog,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🔄 Yenile",
            command=self.refresh_devices_list,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=5)
        
        self.devices_scroll = ctk.CTkScrollableFrame(self.main_frame)
        self.devices_scroll.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        self.refresh_devices_list()
    
    def refresh_devices_list(self):
        """Cihaz listesini yenile"""
        if not hasattr(self, 'devices_scroll'):
            return
        
        for widget in self.devices_scroll.winfo_children():
            widget.destroy()
        
        if not self.config.devices:
            ctk.CTkLabel(
                self.devices_scroll,
                text="Henüz kayıtlı cihaz yok.\n'Cihaz Ekle' veya 'Tarama' sayfasından cihaz ekleyebilirsiniz.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            ).pack(pady=50)
            return
        
        for nickname, info in self.config.devices.items():
            self.create_device_card(nickname, info)
    
    def create_device_card(self, nickname: str, info: Dict[str, Any]):
        """Cihaz kartı oluştur"""
        card = ctk.CTkFrame(self.devices_scroll)
        card.pack(fill="x", padx=10, pady=5)
        
        info_frame = ctk.CTkFrame(card)
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        is_connected = self.ws_manager.connected.get(nickname, False)
        status_icon = "🟢" if is_connected else "🔴"
        
        ctk.CTkLabel(
            info_frame,
            text=f"{status_icon} {nickname}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")
        
        port = self.config.settings["default_port"]
        ctk.CTkLabel(
            info_frame,
            text=f"📡 IP: {info['ip']}:{port}\n🆔 ID: {info['device_id']}\n📅 Eklenme: {info.get('added_at', 'Bilinmiyor')[:10]}",
            font=ctk.CTkFont(size=12),
            justify="left"
        ).pack(anchor="w", pady=5)
        
        btn_frame = ctk.CTkFrame(card)
        btn_frame.pack(side="right", padx=10, pady=10)
        
        if is_connected:
            ctk.CTkButton(
                btn_frame,
                text="🔌 Bağlantıyı Kes",
                command=lambda: self.disconnect_device(nickname),
                fg_color="red",
                hover_color="darkred",
                width=150
            ).pack(pady=2)
        else:
            ctk.CTkButton(
                btn_frame,
                text="🔗 Bağlan",
                command=lambda: self.connect_device(nickname),
                fg_color="green",
                hover_color="darkgreen",
                width=150
            ).pack(pady=2)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Sil",
            command=lambda: self.remove_device(nickname),
            fg_color="darkred",
            hover_color="red",
            width=150
        ).pack(pady=2)
    
    def show_add_device_dialog(self):
        """Cihaz ekleme dialog'u"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("➕ Yeni Cihaz Ekle")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Cihaz Bilgileri", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        
        ctk.CTkLabel(dialog, text="Takma Ad (Nickname):").pack(pady=5)
        nickname_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="örn: holo1")
        nickname_entry.pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Cihaz ID:").pack(pady=5)
        id_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="örn: DEVICE_192_168_1_100")
        id_entry.pack(pady=5)
        
        ctk.CTkLabel(dialog, text="IP Adresi:").pack(pady=5)
        ip_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="örn: 192.168.1.100")
        ip_entry.pack(pady=5)
        
        error_label = ctk.CTkLabel(dialog, text="", text_color="red")
        error_label.pack(pady=10)
        
        def add_device():
            nickname = nickname_entry.get().strip()
            device_id = id_entry.get().strip()
            ip = ip_entry.get().strip()
            
            if not nickname or not device_id or not ip:
                error_label.configure(text="❌ Tüm alanları doldurun!")
                return
            
            if nickname in self.config.devices:
                error_label.configure(text="❌ Bu takma ad zaten kullanılıyor!")
                return
            
            self.config.devices[nickname] = {
                "device_id": device_id,
                "ip": ip,
                "added_at": datetime.now().isoformat()
            }
            self.config.save_config()
            self.connect_device(nickname)
            self.refresh_devices_list()
            dialog.destroy()
        
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="✅ Ekle", command=add_device, width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="❌ İptal", command=dialog.destroy, width=120).pack(side="left", padx=5)
    
    def connect_device(self, nickname: str):
        """Cihaza bağlan"""
        self.ws_manager.connect_device_sync(nickname)
        self.root.after(1000, self.refresh_devices_list)
    
    def disconnect_device(self, nickname: str):
        """Cihaz bağlantısını kes"""
        self.ws_manager.disconnect_device(nickname)
        self.refresh_devices_list()
    
    def remove_device(self, nickname: str):
        """Cihazı sil"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("⚠️ Onay")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text=f"'{nickname}' cihazını silmek istediğinize emin misiniz?",
            font=ctk.CTkFont(size=14),
            wraplength=350
        ).pack(pady=30)
        
        def confirm():
            self.ws_manager.disconnect_device(nickname)
            del self.config.devices[nickname]
            self.config.save_config()
            self.refresh_devices_list()
            dialog.destroy()
        
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="✅ Evet, Sil", command=confirm, fg_color="red", width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="❌ İptal", command=dialog.destroy, width=120).pack(side="left", padx=5)
    
    def show_control_page(self):
        """Kontrol sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="🎮 Cihaz Kontrolü",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        top_panel = ctk.CTkScrollableFrame(self.main_frame)
        top_panel.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="nsew")
        
        bottom_panel = ctk.CTkFrame(self.main_frame)
        bottom_panel.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="nsew")
        
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=3)
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        model_frame = ctk.CTkFrame(top_panel)
        model_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(model_frame, text="🎬 3D Model Yükle", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        ctk.CTkLabel(model_frame, text="Model URL:").pack(pady=5)
        model_url_entry = ctk.CTkEntry(model_frame, width=400, placeholder_text="https://example.com/model.glb")
        model_url_entry.pack(pady=5)
        
        param_frame = ctk.CTkFrame(model_frame)
        param_frame.pack(pady=10)
        
        ctk.CTkLabel(param_frame, text="Tekrar:").pack(side="left", padx=5)
        repeat_var = ctk.StringVar(value="1")
        repeat_entry = ctk.CTkEntry(param_frame, width=80, textvariable=repeat_var)
        repeat_entry.pack(side="left", padx=5)
        
        loop_var = ctk.BooleanVar(value=False)
        loop_check = ctk.CTkCheckBox(param_frame, text="Sonsuz Döngü", variable=loop_var)
        loop_check.pack(side="left", padx=5)
        
        def send_model():
            url = model_url_entry.get().strip()
            if not url:
                self.log_command("❌ Model URL giriniz!", bottom_panel)
                return
            
            if loop_var.get():
                cmd = f"model {url} loop"
            else:
                repeat = repeat_var.get()
                if repeat != "1":
                    cmd = f"model {url} repeat={repeat}"
                else:
                    cmd = f"model {url}"
            
            self.send_command_to_all(cmd, bottom_panel)
        
        ctk.CTkButton(model_frame, text="📤 Gönder", command=send_model, width=200).pack(pady=10)
        
        video_frame = ctk.CTkFrame(top_panel)
        video_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(video_frame, text="🎥 Video Oynat", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        ctk.CTkLabel(video_frame, text="Video URL:").pack(pady=5)
        video_url_entry = ctk.CTkEntry(video_frame, width=400, placeholder_text="https://example.com/video.ogv")
        video_url_entry.pack(pady=5)
        
        btn_frame1 = ctk.CTkFrame(video_frame)
        btn_frame1.pack(pady=10)
        
        ctk.CTkButton(
            btn_frame1,
            text="▶️ Oynat",
            command=lambda: self.send_command_to_all(f"video {video_url_entry.get()}", bottom_panel),
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame1,
            text="⏹️ Durdur",
            command=lambda: self.send_command_to_all("stop_video", bottom_panel),
            width=120,
            fg_color="red"
        ).pack(side="left", padx=5)
        
        params_frame = ctk.CTkFrame(top_panel)
        params_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(params_frame, text="⚙️ Parametre Ayarları", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        rpm_frame = ctk.CTkFrame(params_frame)
        rpm_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(rpm_frame, text="⚡ RPM:").pack(side="left", padx=5)
        rpm_entry = ctk.CTkEntry(rpm_frame, width=100, placeholder_text="450")
        rpm_entry.insert(0, "450")
        rpm_entry.pack(side="left", padx=5)
        
        ctk.CTkButton(
            rpm_frame,
            text="📤 Gönder",
            command=lambda: self.send_command_to_all(f"rpm {rpm_entry.get()}", bottom_panel),
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(rpm_frame, text="(100-1000)", text_color="gray").pack(side="left", padx=5)
        
        phase_frame = ctk.CTkFrame(params_frame)
        phase_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(phase_frame, text="🔄 Faz:").pack(side="left", padx=5)
        phase_entry = ctk.CTkEntry(phase_frame, width=100, placeholder_text="0")
        phase_entry.insert(0, "0")
        phase_entry.pack(side="left", padx=5)
        
        ctk.CTkButton(
            phase_frame,
            text="📤 Gönder",
            command=lambda: self.send_command_to_all(f"phase {phase_entry.get()}", bottom_panel),
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(phase_frame, text="(0-360°)", text_color="gray").pack(side="left", padx=5)
        
        light_frame = ctk.CTkFrame(params_frame)
        light_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(light_frame, text="💡 Işık:").pack(side="left", padx=5)
        light_entry = ctk.CTkEntry(light_frame, width=100, placeholder_text="1.0")
        light_entry.insert(0, "1.0")
        light_entry.pack(side="left", padx=5)
        
        ctk.CTkButton(
            light_frame,
            text="📤 Gönder",
            command=lambda: self.send_command_to_all(f"light {light_entry.get()}", bottom_panel),
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(light_frame, text="(0.0-3.0)", text_color="gray").pack(side="left", padx=5)
        
        ctk.CTkButton(
            params_frame,
            text="🔄 Tümünü Sıfırla",
            command=lambda: self.send_command_to_all("reset", bottom_panel),
            width=200,
            fg_color="orange"
        ).pack(pady=20)
        
        ctk.CTkLabel(bottom_panel, text="📝 Komut Geçmişi", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.log_textbox = ctk.CTkTextbox(bottom_panel, height=150, state="disabled")
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        btn_frame_log = ctk.CTkFrame(bottom_panel)
        btn_frame_log.pack(pady=5)
        
        ctk.CTkButton(
            btn_frame_log,
            text="🗑️ Temizle",
            command=lambda: self.clear_log(),
            width=100
        ).pack(side="left", padx=5)
        
        auto_scroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            btn_frame_log,
            text="Otomatik Kaydır",
            variable=auto_scroll_var
        ).pack(side="left", padx=5)
    
    def send_command_to_all(self, command: str, log_panel):
        """Tüm cihazlara komut gönder"""
        future = self.ws_manager.run_coroutine(
            self.ws_manager.send_command_all(command)
        )
        
        def callback(fut):
            try:
                success, total = fut.result()
                self.log_command(f"✅ Komut: {command}\n📡 Gönderildi: {success}/{total} cihaz\n", log_panel)
            except Exception as e:
                self.log_command(f"❌ Hata: {e}\n", log_panel)
        
        if future:
            future.add_done_callback(callback)
    
    def log_command(self, message: str, log_panel=None):
        """Komut logla"""
        if hasattr(self, 'log_textbox'):
            self.log_textbox.configure(state="normal")
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
    
    def clear_log(self):
        """Log'u temizle"""
        if hasattr(self, 'log_textbox'):
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.configure(state="disabled")
    
    def show_shortcuts_page(self):
        """Kısayollar sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="🔖 Model Kısayolları",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        btn_frame = ctk.CTkFrame(self.main_frame)
        btn_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkButton(
            btn_frame,
            text="➕ Kısayol Ekle",
            command=self.show_add_shortcut_dialog,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🔄 Yenile",
            command=self.refresh_shortcuts_list,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=5)
        
        self.shortcuts_scroll = ctk.CTkScrollableFrame(self.main_frame)
        self.shortcuts_scroll.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        self.refresh_shortcuts_list()
    
    def refresh_shortcuts_list(self):
        """Kısayol listesini yenile"""
        if not hasattr(self, 'shortcuts_scroll'):
            return
        
        for widget in self.shortcuts_scroll.winfo_children():
            widget.destroy()
        
        if not self.config.shortcuts:
            ctk.CTkLabel(
                self.shortcuts_scroll,
                text="Henüz kısayol yok.\n'Kısayol Ekle' butonuna tıklayarak kısayol oluşturabilirsiniz.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            ).pack(pady=50)
            return
        
        for keyword, info in self.config.shortcuts.items():
            self.create_shortcut_card(keyword, info)
    
    def create_shortcut_card(self, keyword: str, info: Dict[str, Any]):
        """Kısayol kartı oluştur"""
        card = ctk.CTkFrame(self.shortcuts_scroll)
        card.pack(fill="x", padx=10, pady=5)
        
        info_frame = ctk.CTkFrame(card)
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text=f"🔖 !{keyword}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"🔗 {info['url']}",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=2)
        
        if info.get('description'):
            ctk.CTkLabel(
                info_frame,
                text=f"📝 {info['description']}",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            ).pack(anchor="w", pady=2)
        
        btn_frame = ctk.CTkFrame(card)
        btn_frame.pack(side="right", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="▶️ Çalıştır",
            command=lambda: self.run_shortcut(keyword),
            fg_color="green",
            width=120
        ).pack(pady=2)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Sil",
            command=lambda: self.remove_shortcut(keyword),
            fg_color="darkred",
            width=120
        ).pack(pady=2)
    
    def show_add_shortcut_dialog(self):
        """Kısayol ekleme dialog'u"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("➕ Yeni Kısayol Ekle")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Kısayol Bilgileri", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        
        ctk.CTkLabel(dialog, text="Kelime (Keyword):").pack(pady=5)
        keyword_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="örn: küp")
        keyword_entry.pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Model URL:").pack(pady=5)
        url_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="https://example.com/model.glb")
        url_entry.pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Açıklama (Opsiyonel):").pack(pady=5)
        desc_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="örn: Dönen küp modeli")
        desc_entry.pack(pady=5)
        
        error_label = ctk.CTkLabel(dialog, text="", text_color="red")
        error_label.pack(pady=10)
        
        def add_shortcut():
            keyword = keyword_entry.get().strip().lower()
            url = url_entry.get().strip()
            description = desc_entry.get().strip()
            
            if not keyword or not url:
                error_label.configure(text="❌ Kelime ve URL alanları zorunludur!")
                return
            
            if keyword in self.config.shortcuts:
                error_label.configure(text="❌ Bu kelime zaten kullanılıyor!")
                return
            
            self.config.shortcuts[keyword] = {
                "url": url,
                "description": description,
                "added_at": datetime.now().isoformat()
            }
            self.config.save_config()
            self.refresh_shortcuts_list()
            dialog.destroy()
        
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="✅ Ekle", command=add_shortcut, width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="❌ İptal", command=dialog.destroy, width=120).pack(side="left", padx=5)
    
    def run_shortcut(self, keyword: str):
        """Kısayolu çalıştır"""
        info = self.config.shortcuts.get(keyword)
        if not info:
            return
        
        cmd = f"model {info['url']}"
        
        future = self.ws_manager.run_coroutine(
            self.ws_manager.send_command_all(cmd)
        )
        
        def callback(fut):
            try:
                success, total = fut.result()
                logger.info(f"✅ Kısayol '{keyword}' çalıştırıldı: {success}/{total}")
            except Exception as e:
                logger.error(f"❌ Kısayol hatası: {e}")
        
        if future:
            future.add_done_callback(callback)
    
    def remove_shortcut(self, keyword: str):
        """Kısayolu sil"""
        del self.config.shortcuts[keyword]
        self.config.save_config()
        self.refresh_shortcuts_list()
    
    def show_scan_page(self):
        """Tarama sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="🔍 Ağ Taraması",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        settings_frame = ctk.CTkFrame(self.main_frame)
        settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(settings_frame, text="IP Aralığı:").pack(side="left", padx=10)
        ip_range_entry = ctk.CTkEntry(settings_frame, width=200, placeholder_text="192.168.1")
        ip_range_entry.insert(0, self.config.settings["default_ip_range"])
        ip_range_entry.pack(side="left", padx=10)
        
        scan_btn = ctk.CTkButton(
            settings_frame,
            text="🔍 Taramayı Başlat",
            command=lambda: self.start_scan(ip_range_entry.get(), result_frame),
            font=ctk.CTkFont(size=14),
            width=150
        )
        scan_btn.pack(side="left", padx=10)
        
        result_frame = ctk.CTkScrollableFrame(self.main_frame)
        result_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        ctk.CTkLabel(
            result_frame,
            text="Tarama başlatmak için yukarıdaki butona tıklayın.",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(pady=50)
    
    def start_scan(self, ip_range: str, result_frame):
        """Ağ taramasını başlat"""
        for widget in result_frame.winfo_children():
            widget.destroy()
        
        loading = ctk.CTkLabel(
            result_frame,
            text=f"🔍 {ip_range}.x ağı taranıyor...\nBu işlem birkaç dakika sürebilir.",
            font=ctk.CTkFont(size=14)
        )
        loading.pack(pady=50)
        
        future = self.ws_manager.run_coroutine(
            self.ws_manager.scan_network(ip_range)
        )
        
        def callback(fut):
            try:
                devices = fut.result()
                self.root.after(0, lambda: self.show_scan_results(devices, result_frame))
            except Exception as e:
                logger.error(f"Tarama hatası: {e}")
                self.root.after(0, lambda: self.show_scan_error(str(e), result_frame))
        
        if future:
            future.add_done_callback(callback)
    
    def show_scan_results(self, devices: List[Dict[str, Any]], result_frame):
        """Tarama sonuçlarını göster"""
        for widget in result_frame.winfo_children():
            widget.destroy()
        
        if not devices:
            ctk.CTkLabel(
                result_frame,
                text="❌ Hiçbir cihaz bulunamadı.",
                font=ctk.CTkFont(size=14),
                text_color="red"
            ).pack(pady=50)
            return
        
        title = ctk.CTkLabel(
            result_frame,
            text=f"✅ {len(devices)} Cihaz Bulundu",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="green"
        )
        title.pack(pady=20)
        
        for device in devices:
            self.create_scan_result_card(device, result_frame)
    
    def create_scan_result_card(self, device: Dict[str, Any], parent):
        """Tarama sonucu kartı"""
        card = ctk.CTkFrame(parent)
        card.pack(fill="x", padx=10, pady=5)
        
        info_frame = ctk.CTkFrame(card)
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        port = self.config.settings["default_port"]
        ctk.CTkLabel(
            info_frame,
            text=f"🌐 Cihaz Bulundu",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"📡 IP: {device['ip']}:{port}\n🆔 ID: {device['device_id']}",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=5)
        
        def add_scanned_device():
            nickname = f"holo_{device['ip'].split('.')[-1]}"
            counter = 1
            while nickname in self.config.devices:
                nickname = f"holo_{device['ip'].split('.')[-1]}_{counter}"
                counter += 1
            
            self.config.devices[nickname] = {
                "device_id": device['device_id'],
                "ip": device['ip'],
                "added_at": datetime.now().isoformat()
            }
            self.config.save_config()
            self.connect_device(nickname)
            
            for widget in card.winfo_children():
                widget.destroy()
            
            ctk.CTkLabel(
                card,
                text=f"✅ '{nickname}' olarak eklendi!",
                font=ctk.CTkFont(size=14),
                text_color="green"
            ).pack(padx=20, pady=20)
        
        ctk.CTkButton(
            card,
            text="➕ Ekle",
            command=add_scanned_device,
            fg_color="green",
            width=100
        ).pack(side="right", padx=10, pady=10)
    
    def show_scan_error(self, error: str, result_frame):
        """Tarama hatasını göster"""
        for widget in result_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            result_frame,
            text=f"❌ Tarama Hatası:\n{error}",
            font=ctk.CTkFont(size=14),
            text_color="red"
        ).pack(pady=50)
    
    def show_status_page(self):
        """Durum sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="📊 Sistem Durumu",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=20)
        
        stats_frame = ctk.CTkFrame(self.main_frame)
        stats_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        uptime = datetime.now() - self.ws_manager.stats["uptime_start"]
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}s {minutes}d {seconds}sn"
        
        stats = [
            ("⏱️ Çalışma Süresi", uptime_str),
            ("🌐 Toplam Cihaz", str(len(self.config.devices))),
            ("🟢 Bağlı Cihaz", str(self.ws_manager.get_connected_count())),
            ("📤 Gönderilen Mesaj", str(self.ws_manager.stats["messages_sent"])),
            ("🔍 Keşfedilen Cihaz", str(self.ws_manager.stats["devices_discovered"])),
            ("🔖 Kısayol Sayısı", str(len(self.config.shortcuts))),
        ]
        
        for i, (label, value) in enumerate(stats):
            row = i // 2
            col = i % 2
            
            card = ctk.CTkFrame(stats_frame)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(size=14)
            ).pack(pady=(20, 5))
            
            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(size=24, weight="bold")
            ).pack(pady=(5, 20))
        
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(
            self.main_frame,
            text="🔄 Yenile",
            command=self.show_status_page,
            width=200
        ).pack(pady=20)
    
    def show_settings_page(self):
        """Ayarlar sayfası"""
        self.clear_main_frame()
        
        title = ctk.CTkLabel(
            self.main_frame,
            text="⚙️ Ayarlar",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=20)
        
        settings_frame = ctk.CTkScrollableFrame(self.main_frame)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        theme_frame = ctk.CTkFrame(settings_frame)
        theme_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(theme_frame, text="🎨 Tema:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        theme_var = ctk.StringVar(value=self.config.settings["theme"])
        
        def change_theme():
            new_theme = theme_var.get()
            self.config.settings["theme"] = new_theme
            self.config.save_settings()
            ctk.set_appearance_mode(new_theme)
        
        for theme in ["dark", "light", "system"]:
            ctk.CTkRadioButton(
                theme_frame,
                text=theme.capitalize(),
                variable=theme_var,
                value=theme,
                command=change_theme
            ).pack(pady=2)
        
        color_frame = ctk.CTkFrame(settings_frame)
        color_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(color_frame, text="🎨 Renk Teması:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        color_var = ctk.StringVar(value=self.config.settings["color_theme"])
        
        def change_color():
            new_color = color_var.get()
            self.config.settings["color_theme"] = new_color
            self.config.save_settings()
            
            info = ctk.CTkLabel(
                color_frame,
                text="⚠️ Renk değişikliği için uygulamayı yeniden başlatın.",
                text_color="orange"
            )
            info.pack(pady=5)
        
        for color in ["blue", "green", "dark-blue"]:
            ctk.CTkRadioButton(
                color_frame,
                text=color.capitalize(),
                variable=color_var,
                value=color,
                command=change_color
            ).pack(pady=2)
        
        network_frame = ctk.CTkFrame(settings_frame)
        network_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(network_frame, text="🌐 Ağ Ayarları:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        port_frame = ctk.CTkFrame(network_frame)
        port_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(port_frame, text="Port:").pack(side="left", padx=5)
        port_entry = ctk.CTkEntry(port_frame, width=100)
        port_entry.insert(0, str(self.config.settings["default_port"]))
        port_entry.pack(side="left", padx=5)
        
        def save_port():
            self.config.settings["default_port"] = int(port_entry.get())
            self.config.save_settings()
        
        ctk.CTkButton(port_frame, text="💾 Kaydet", command=save_port, width=80).pack(side="left", padx=5)
        
        ip_frame = ctk.CTkFrame(network_frame)
        ip_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(ip_frame, text="Varsayılan IP Aralığı:").pack(side="left", padx=5)
        ip_entry = ctk.CTkEntry(ip_frame, width=150)
        ip_entry.insert(0, self.config.settings["default_ip_range"])
        ip_entry.pack(side="left", padx=5)
        
        def save_ip():
            self.config.settings["default_ip_range"] = ip_entry.get()
            self.config.save_settings()
        
        ctk.CTkButton(ip_frame, text="💾 Kaydet", command=save_ip, width=80).pack(side="left", padx=5)
        
        timeout_frame = ctk.CTkFrame(settings_frame)
        timeout_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(timeout_frame, text="⏱️ Zaman Aşımı Ayarları:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        scan_frame = ctk.CTkFrame(timeout_frame)
        scan_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(scan_frame, text="Tarama Timeout (sn):").pack(side="left", padx=5)
        scan_entry = ctk.CTkEntry(scan_frame, width=100)
        scan_entry.insert(0, str(self.config.settings["scan_timeout"]))
        scan_entry.pack(side="left", padx=5)
        
        def save_scan():
            self.config.settings["scan_timeout"] = int(scan_entry.get())
            self.config.save_settings()
        
        ctk.CTkButton(scan_frame, text="💾 Kaydet", command=save_scan, width=80).pack(side="left", padx=5)
        
        reconnect_frame = ctk.CTkFrame(timeout_frame)
        reconnect_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(reconnect_frame, text="Yeniden Bağlanma (sn):").pack(side="left", padx=5)
        reconnect_entry = ctk.CTkEntry(reconnect_frame, width=100)
        reconnect_entry.insert(0, str(self.config.settings["reconnect_delay"]))
        reconnect_entry.pack(side="left", padx=5)
        
        def save_reconnect():
            self.config.settings["reconnect_delay"] = int(reconnect_entry.get())
            self.config.save_settings()
        
        ctk.CTkButton(reconnect_frame, text="💾 Kaydet", command=save_reconnect, width=80).pack(side="left", padx=5)
        
        heartbeat_frame = ctk.CTkFrame(timeout_frame)
        heartbeat_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(heartbeat_frame, text="Heartbeat Aralığı (sn):").pack(side="left", padx=5)
        heartbeat_entry = ctk.CTkEntry(heartbeat_frame, width=100)
        heartbeat_entry.insert(0, str(self.config.settings["heartbeat_interval"]))
        heartbeat_entry.pack(side="left", padx=5)
        
        def save_heartbeat():
            self.config.settings["heartbeat_interval"] = int(heartbeat_entry.get())
            self.config.save_settings()
        
        ctk.CTkButton(heartbeat_frame, text="💾 Kaydet", command=save_heartbeat, width=80).pack(side="left", padx=5)
        
        commands_frame = ctk.CTkFrame(settings_frame)
        commands_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(commands_frame, text="📖 Komut Listesi:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        commands_text = """
🎬 model <url> [repeat=N] [loop] - 3D model yükle
🎥 video <url> - Video oynat
⏹️ stop_video - Videoyu durdur
⚡ rpm <değer> - Dönüş hızını ayarla (100-1000)
🔄 phase <derece> - Faz açısını ayarla (0-360)
💡 light <değer> - Işık yoğunluğunu ayarla (0-3)
🔄 reset - Animasyonu sıfırla
📋 GET_ID - Cihaz ID'sini al
🏓 PING - Bağlantı testi
        """
        
        commands_textbox = ctk.CTkTextbox(commands_frame, height=250)
        commands_textbox.pack(fill="x", padx=20, pady=10)
        commands_textbox.insert("1.0", commands_text.strip())
        commands_textbox.configure(state="disabled")
    
    def connect_saved_devices(self):
        """Kaydedilmiş cihazlara bağlan"""
        for nickname in self.config.devices.keys():
            self.connect_device(nickname)
    
    def update_status(self):
        """Durum çubuğunu güncelle"""
        connected = self.ws_manager.get_connected_count()
        total = len(self.config.devices)
        
        if connected > 0:
            status_text = f"🟢 {connected}/{total} Bağlı"
            self.status_label.configure(text=status_text, text_color="green")
        elif total > 0:
            status_text = f"🔴 {connected}/{total} Bağlı"
            self.status_label.configure(text=status_text, text_color="red")
        else:
            self.status_label.configure(text="🔴 Cihaz Yok", text_color="gray")
        
        self.root.after(2000, self.update_status)
    
    def run(self):
        """Uygulamayı çalıştır"""
        logger.info("🚀 GUI başlatılıyor...")
        self.root.mainloop()


if __name__ == "__main__":
    try:
        app = HologramGUI()
        app.run()
    except KeyboardInterrupt:
        logger.info("⏹️ Uygulama kapatılıyor...")
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}", exc_info=True)