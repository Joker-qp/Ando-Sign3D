# main_controller.py - Farklı klasörlerdeki dosyalar için

import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import subprocess
import sys
from datetime import datetime
import os
import json

class SimpleController:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎮 Sunucu & Bot Kontrol")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        self.root.configure(bg="#ecf0f1")
        
        # Process'ler
        self.server_process = None
        self.bot_process = None
        
        # Dosya yolları
        self.config_file = "controller_config.json"
        self.server_path = ""
        self.bot_path = ""
        
        # Ayarları yükle
        self.load_config()
        
        self.setup_ui()
        self.update_status()
        
    def load_config(self):
        """Kayıtlı ayarları yükle"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.server_path = config.get('server_path', '')
                    self.bot_path = config.get('bot_path', '')
            except:
                pass
    
    def save_config(self):
        """Ayarları kaydet"""
        config = {
            'server_path': self.server_path,
            'bot_path': self.bot_path
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except:
            pass
        
    def setup_ui(self):
        # Başlık
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title = tk.Label(
            title_frame,
            text="🎮 Kontrol Paneli",
            font=("Arial", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=18)
        
        # Ana alan
        main_frame = tk.Frame(self.root, bg="#ecf0f1")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Godot Server (holoserv.exe)
        server_card = tk.Frame(main_frame, bg="white", relief=tk.RAISED, borderwidth=2)
        server_card.pack(fill=tk.X, pady=(0, 15))
        
        server_header = tk.Frame(server_card, bg="#667eea")
        server_header.pack(fill=tk.X)
        
        tk.Label(
            server_header,
            text="🌐 Godot Server (holoserv.exe)",
            font=("Arial", 12, "bold"),
            bg="#667eea",
            fg="white"
        ).pack(side=tk.LEFT, padx=15, pady=12)
        
        self.server_status = tk.Label(
            server_header,
            text="● Kapalı",
            font=("Arial", 10, "bold"),
            bg="#667eea",
            fg="#ff6b6b"
        )
        self.server_status.pack(side=tk.RIGHT, padx=15)
        
        # Server yol gösterimi
        server_path_frame = tk.Frame(server_card, bg="white")
        server_path_frame.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        tk.Label(
            server_path_frame,
            text="📁 Yol:",
            font=("Arial", 9),
            bg="white",
            fg="#666"
        ).pack(side=tk.LEFT)
        
        self.server_path_label = tk.Label(
            server_path_frame,
            text=self.server_path if self.server_path else "Yol seçilmedi",
            font=("Arial", 8),
            bg="white",
            fg="#999" if not self.server_path else "#333",
            wraplength=450,
            justify=tk.LEFT
        )
        self.server_path_label.pack(side=tk.LEFT, padx=5)
        
        server_btns = tk.Frame(server_card, bg="white")
        server_btns.pack(fill=tk.X, padx=15, pady=15)
        
        tk.Button(
            server_btns,
            text="📂 Dosya Seç",
            command=self.select_server_path,
            bg="#3498db",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(
            server_btns,
            text="▶️ Başlat",
            command=self.start_server,
            bg="#27ae60",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            server_btns,
            text="⏹️ Durdur",
            command=self.stop_server,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        ).pack(side=tk.LEFT, padx=5)
        
        # Discord Bot (bot.py)
        bot_card = tk.Frame(main_frame, bg="white", relief=tk.RAISED, borderwidth=2)
        bot_card.pack(fill=tk.X, pady=(0, 15))
        
        bot_header = tk.Frame(bot_card, bg="#7289da")
        bot_header.pack(fill=tk.X)
        
        tk.Label(
            bot_header,
            text="🤖 Discord Bot (bot.py)",
            font=("Arial", 12, "bold"),
            bg="#7289da",
            fg="white"
        ).pack(side=tk.LEFT, padx=15, pady=12)
        
        self.bot_status = tk.Label(
            bot_header,
            text="● Kapalı",
            font=("Arial", 10, "bold"),
            bg="#7289da",
            fg="#ff6b6b"
        )
        self.bot_status.pack(side=tk.RIGHT, padx=15)
        
        # Bot yol gösterimi
        bot_path_frame = tk.Frame(bot_card, bg="white")
        bot_path_frame.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        tk.Label(
            bot_path_frame,
            text="📁 Yol:",
            font=("Arial", 9),
            bg="white",
            fg="#666"
        ).pack(side=tk.LEFT)
        
        self.bot_path_label = tk.Label(
            bot_path_frame,
            text=self.bot_path if self.bot_path else "Yol seçilmedi",
            font=("Arial", 8),
            bg="white",
            fg="#999" if not self.bot_path else "#333",
            wraplength=450,
            justify=tk.LEFT
        )
        self.bot_path_label.pack(side=tk.LEFT, padx=5)
        
        bot_btns = tk.Frame(bot_card, bg="white")
        bot_btns.pack(fill=tk.X, padx=15, pady=15)
        
        tk.Button(
            bot_btns,
            text="📂 Dosya Seç",
            command=self.select_bot_path,
            bg="#3498db",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(
            bot_btns,
            text="▶️ Başlat",
            command=self.start_bot,
            bg="#27ae60",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            bot_btns,
            text="⏹️ Durdur",
            command=self.stop_bot,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        ).pack(side=tk.LEFT, padx=5)
        
        # Log alanı
        log_label = tk.Label(
            main_frame,
            text="📋 İşlem Geçmişi",
            font=("Arial", 9, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        log_label.pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            height=6,
            font=("Consolas", 8),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="white"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def select_server_path(self):
        """holoserv.exe dosyasını seç"""
        filepath = filedialog.askopenfilename(
            title="holoserv.exe Dosyasını Seç",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        
        if filepath:
            self.server_path = filepath
            self.server_path_label.config(text=self.server_path, fg="#333")
            self.save_config()
            self.log(f"✅ Server yolu seçildi: {filepath}")
    
    def select_bot_path(self):
        """bot.py dosyasını seç"""
        filepath = filedialog.askopenfilename(
            title="bot.py Dosyasını Seç",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        
        if filepath:
            self.bot_path = filepath
            self.bot_path_label.config(text=self.bot_path, fg="#333")
            self.save_config()
            self.log(f"✅ Bot yolu seçildi: {filepath}")
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
    def start_server(self):
        if self.server_process and self.server_process.poll() is None:
            self.log("⚠️ Sunucu zaten çalışıyor!")
            return
        
        if not self.server_path:
            self.log("❌ Önce holoserv.exe dosya yolunu seçin!")
            messagebox.showwarning("Uyarı", "Önce 'Dosya Seç' butonuna tıklayarak holoserv.exe'yi seçin!")
            return
        
        if not os.path.exists(self.server_path):
            self.log("❌ holoserv.exe dosyası bulunamadı!")
            messagebox.showerror("Hata", f"Dosya bulunamadı:\n{self.server_path}")
            return
        
        try:
            # Dosyanın bulunduğu klasörü al
            server_dir = os.path.dirname(self.server_path)
            
            # .exe dosyasını yeni konsol penceresinde başlat
            self.server_process = subprocess.Popen(
                [self.server_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=server_dir
            )
            self.log(f"✅ Godot Server başlatıldı! (PID: {self.server_process.pid})")
        except Exception as e:
            self.log(f"❌ Server başlatılamadı: {e}")
            messagebox.showerror("Hata", f"Server başlatılamadı:\n{e}")
    
    def stop_server(self):
        if not self.server_process:
            self.log("⚠️ Sunucu zaten kapalı!")
            return
        
        try:
            self.server_process.terminate()
            self.server_process.wait(timeout=3)
            self.log("✅ Godot Server durduruldu!")
            self.server_process = None
        except:
            try:
                self.server_process.kill()
                self.log("✅ Godot Server zorla kapatıldı!")
                self.server_process = None
            except Exception as e:
                self.log(f"❌ Server durdurulamadı: {e}")
    
    def start_bot(self):
        if self.bot_process and self.bot_process.poll() is None:
            self.log("⚠️ Bot zaten çalışıyor!")
            return
        
        if not self.bot_path:
            self.log("❌ Önce bot.py dosya yolunu seçin!")
            messagebox.showwarning("Uyarı", "Önce 'Dosya Seç' butonuna tıklayarak bot.py'yi seçin!")
            return
        
        if not os.path.exists(self.bot_path):
            self.log("❌ bot.py dosyası bulunamadı!")
            messagebox.showerror("Hata", f"Dosya bulunamadı:\n{self.bot_path}")
            return
        
        try:
            # Python yolunu bul
            python_exe = sys.executable
            
            # Dosyanın bulunduğu klasörü al
            bot_dir = os.path.dirname(self.bot_path)
            
            # bot.py'yi yeni konsol penceresinde başlat
            self.bot_process = subprocess.Popen(
                [python_exe, self.bot_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=bot_dir
            )
            self.log(f"✅ Discord Bot başlatıldı! (PID: {self.bot_process.pid})")
        except Exception as e:
            self.log(f"❌ Bot başlatılamadı: {e}")
            messagebox.showerror("Hata", f"Bot başlatılamadı:\n{e}")
    
    def stop_bot(self):
        if not self.bot_process:
            self.log("⚠️ Bot zaten kapalı!")
            return
        
        try:
            self.bot_process.terminate()
            self.bot_process.wait(timeout=3)
            self.log("✅ Discord Bot durduruldu!")
            self.bot_process = None
        except:
            try:
                self.bot_process.kill()
                self.log("✅ Discord Bot zorla kapatıldı!")
                self.bot_process = None
            except Exception as e:
                self.log(f"❌ Bot durdurulamadı: {e}")
    
    def update_status(self):
        # Server durumu
        if self.server_process and self.server_process.poll() is None:
            self.server_status.config(text="● Çalışıyor", fg="#51cf66")
        else:
            self.server_status.config(text="● Kapalı", fg="#ff6b6b")
            if self.server_process and self.server_process.poll() is not None:
                exit_code = self.server_process.poll()
                if exit_code != 0:
                    self.log(f"⚠️ Server beklenmedik şekilde kapandı! (Exit code: {exit_code})")
                self.server_process = None
        
        # Bot durumu
        if self.bot_process and self.bot_process.poll() is None:
            self.bot_status.config(text="● Çalışıyor", fg="#51cf66")
        else:
            self.bot_status.config(text="● Kapalı", fg="#ff6b6b")
            if self.bot_process and self.bot_process.poll() is not None:
                exit_code = self.bot_process.poll()
                if exit_code != 0:
                    self.log(f"⚠️ Bot beklenmedik şekilde kapandı! (Exit code: {exit_code})")
                self.bot_process = None
        
        self.root.after(1000, self.update_status)
    
    def on_closing(self):
        # Kapatırken process'leri temizle
        if self.server_process:
            try:
                self.server_process.terminate()
            except:
                pass
        
        if self.bot_process:
            try:
                self.bot_process.terminate()
            except:
                pass
        
        self.root.destroy()
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == '__main__':
    app = SimpleController()
    app.run()