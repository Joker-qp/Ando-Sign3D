# main_controller.py - jQker Özel Sürüm (Gelişmiş Yol Seçimi)
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
        self.root.geometry("600x650") 
        self.root.resizable(False, False)
        self.root.configure(bg="#ecf0f1")
        
        self.server_process = None
        self.bot_process = None
        
        self.config_file = "controller_config.json"
        self.server_path = ""
        self.bot_path = ""
        self.req_path = "" # Requirements yolu için yeni değişken
        
        self.load_config()
        self.setup_ui()
        self.update_status()
        
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.server_path = config.get('server_path', '')
                    self.bot_path = config.get('bot_path', '')
                    self.req_path = config.get('req_path', '') # Yükle
            except: pass
    
    def save_config(self):
        config = {
            'server_path': self.server_path,
            'bot_path': self.bot_path,
            'req_path': self.req_path # Kaydet
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except: pass
        
    def setup_ui(self):
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="🎮 Kontrol Paneli", font=("Arial", 18, "bold"), bg="#2c3e50", fg="white").pack(pady=18)
        
        main_frame = tk.Frame(self.root, bg="#ecf0f1")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # --- Godot Server ---
        self.create_section(main_frame, "🌐 Godot Server (holoserv.exe)", "#667eea", self.server_path, self.select_server_path, self.start_server, self.stop_server, is_server=True)
        
        # --- Discord Bot ---
        self.create_section(main_frame, "🤖 Discord Bot (bot.py)", "#7289da", self.bot_path, self.select_bot_path, self.start_bot, self.stop_bot, is_server=False)

        # --- Requirements Kurulum Alanı ---
        req_card = tk.Frame(main_frame, bg="white", relief=tk.RAISED, borderwidth=2)
        req_card.pack(fill=tk.X, pady=(0, 15))
        req_header = tk.Frame(req_card, bg="#f39c12")
        req_header.pack(fill=tk.X)
        tk.Label(req_header, text="📦 Bağımlılık Yönetimi (requirements.txt)", font=("Arial", 10, "bold"), bg="#f39c12", fg="white").pack(side=tk.LEFT, padx=15, pady=8)
        
        req_path_frame = tk.Frame(req_card, bg="white")
        req_path_frame.pack(fill=tk.X, padx=15, pady=5)
        self.req_path_label = tk.Label(req_path_frame, text=self.req_path if self.req_path else "Requirements dosyası seçilmedi", font=("Arial", 8), bg="white", fg="#333", wraplength=450, justify=tk.LEFT)
        self.req_path_label.pack(side=tk.LEFT)
        
        req_btns = tk.Frame(req_card, bg="white")
        req_btns.pack(fill=tk.X, padx=15, pady=10)
        tk.Button(req_btns, text="📂 Dosya Seç", command=self.select_req_path, bg="#3498db", fg="white", font=("Arial", 8, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(req_btns, text="⚡ Kütüphaneleri Kur", command=self.install_requirements, bg="#e67e22", fg="white", font=("Arial", 8, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Log alanı
        tk.Label(main_frame, text="📋 İşlem Geçmişi", font=("Arial", 9, "bold"), bg="#ecf0f1", fg="#2c3e50").pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(main_frame, height=6, font=("Consolas", 8), bg="#1e1e1e", fg="#00ff00", insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def create_section(self, parent, title, color, path, select_cmd, start_cmd, stop_cmd, is_server):
        card = tk.Frame(parent, bg="white", relief=tk.RAISED, borderwidth=2)
        card.pack(fill=tk.X, pady=(0, 15))
        header = tk.Frame(card, bg=color)
        header.pack(fill=tk.X)
        tk.Label(header, text=title, font=("Arial", 11, "bold"), bg=color, fg="white").pack(side=tk.LEFT, padx=15, pady=10)
        
        status_label = tk.Label(header, text="● Kapalı", font=("Arial", 9, "bold"), bg=color, fg="#ff6b6b")
        status_label.pack(side=tk.RIGHT, padx=15)
        if is_server: self.server_status = status_label
        else: self.bot_status = status_label

        path_label = tk.Label(card, text=path if path else "Yol seçilmedi", font=("Arial", 8), bg="white", fg="#333", wraplength=450, justify=tk.LEFT)
        path_label.pack(fill=tk.X, padx=15, pady=5)
        if is_server: self.server_path_label = path_label
        else: self.bot_path_label = path_label

        btns = tk.Frame(card, bg="white")
        btns.pack(fill=tk.X, padx=15, pady=10)
        tk.Button(btns, text="📂 Seç", command=select_cmd, bg="#3498db", fg="white", font=("Arial", 8, "bold"), relief=tk.FLAT, cursor="hand2", width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="▶️ Başlat", command=start_cmd, bg="#27ae60", fg="white", font=("Arial", 8, "bold"), relief=tk.FLAT, cursor="hand2", width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="⏹️ Durdur", command=stop_cmd, bg="#e74c3c", fg="white", font=("Arial", 8, "bold"), relief=tk.FLAT, cursor="hand2", width=10).pack(side=tk.LEFT, padx=2)

    def select_req_path(self):
        filepath = filedialog.askopenfilename(title="requirements.txt Seç", filetypes=[("Text files", "*.txt")])
        if filepath:
            self.req_path = filepath
            self.req_path_label.config(text=self.req_path)
            self.save_config()
            self.log("✅ Requirements yolu seçildi.")

    def install_requirements(self):
        if not self.req_path or not os.path.exists(self.req_path):
            self.log("❌ Lütfen önce geçerli bir requirements.txt seçin!")
            return
        
        req_dir = os.path.dirname(self.req_path)
        self.log("⏳ Kurulum başlatılıyor...")
        try:
            subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "-r", self.req_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=req_dir
            )
            self.log("✅ Kurulum terminali açıldı.")
        except Exception as e: self.log(f"❌ Hata: {e}")

    def select_server_path(self):
        fp = filedialog.askopenfilename(title="holoserv.exe Seç", filetypes=[("EXE", "*.exe")])
        if fp: 
            self.server_path = fp
            self.server_path_label.config(text=fp)
            self.save_config()

    def select_bot_path(self):
        fp = filedialog.askopenfilename(title="bot.py Seç", filetypes=[("Python", "*.py")])
        if fp: 
            self.bot_path = fp
            self.bot_path_label.config(text=fp)
            self.save_config()

    def log(self, msg):
        tm = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{tm}] {msg}\n")
        self.log_text.see(tk.END)

    def start_server(self):
        if self.server_process and self.server_process.poll() is None: return
        if not self.server_path: return
        self.server_process = subprocess.Popen([self.server_path], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=os.path.dirname(self.server_path))
        self.log("✅ Server başlatıldı.")

    def stop_server(self):
        if self.server_process: self.server_process.terminate(); self.server_process = None; self.log("✅ Server durduruldu.")

    def start_bot(self):
        if self.bot_process and self.bot_process.poll() is None: return
        if not self.bot_path: return
        self.bot_process = subprocess.Popen([sys.executable, self.bot_path], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=os.path.dirname(self.bot_path))
        self.log("✅ Bot başlatıldı.")

    def stop_bot(self):
        if self.bot_process: self.bot_process.terminate(); self.bot_process = None; self.log("✅ Bot durduruldu.")

    def update_status(self):
        s_ok = self.server_process and self.server_process.poll() is None
        b_ok = self.bot_process and self.bot_process.poll() is None
        self.server_status.config(text="● Çalışıyor" if s_ok else "● Kapalı", fg="#51cf66" if s_ok else "#ff6b6b")
        self.bot_status.config(text="● Çalışıyor" if b_ok else "● Kapalı", fg="#51cf66" if b_ok else "#ff6b6b")
        self.root.after(1000, self.update_status)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", lambda: [self.stop_server(), self.stop_bot(), self.root.destroy()])
        self.root.mainloop()

if __name__ == '__main__':
    app = SimpleController()
    app.run()