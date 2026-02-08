import customtkinter as ctk
import subprocess
import threading
import os

# Görsel ayarlar
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AndoSignPro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ando-Sign 3D - Kontrol Paneli (Hata Ayıklama Modu)")
        self.geometry("650x550")
        
        # Başlık
        self.label = ctk.CTkLabel(self, text="Ando-Sign 3D Sistem Yönetimi", font=("Arial", 22, "bold"))
        self.label.pack(pady=20)

        # Butonlar için çerçeve
        self.frame = ctk.CTkFrame(self)
        self.frame.pack(pady=10, padx=20, fill="x")

        # 1. SERVER: Discord Botu
        self.btn_bot = ctk.CTkButton(self.frame, text="1. Discord Botunu Başlat", 
                                     command=self.start_bot_thread, fg_color="#2ecc71")
        self.btn_bot.grid(row=0, column=0, padx=20, pady=20)

        # 2. SERVER: Holoserv (Burada hata ayıklama aktif)
        self.btn_engine = ctk.CTkButton(self.frame, text="2. Holoserv Motorunu Aç", 
                                        command=self.start_engine_thread, fg_color="#3498db")
        self.btn_engine.grid(row=0, column=1, padx=20, pady=20)

        # Bilgi Notu
        self.info_label = ctk.CTkLabel(self, text="Not: Motor açılıp kapanıyorsa siyah penceredeki hatayı okuyun.", text_color="orange")
        self.info_label.pack(pady=5)
        
        # Log Ekranı
        self.log_view = ctk.CTkTextbox(self, width=600, height=250, font=("Consolas", 12))
        self.log_view.pack(pady=20, padx=20)

    def start_bot_thread(self):
        threading.Thread(target=self.run_bot, daemon=True).start()

    def start_engine_thread(self):
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_bot(self):
        # Discord Bot Yolu
        bot_path = r"C:\Users\mhmdd\Desktop\Ando-Sign3D\HologramBot"
        self.log_view.insert("end", "[SİSTEM]: Bot başlatılıyor (DNS 1.1.1.1 kontrol edin)...\n")
        
        try:
            # Botun loglarını hala buradaki pencereden görebilirsin
            process = subprocess.Popen(['python', 'bot.py'], cwd=bot_path, 
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                       text=True, shell=True)
            for line in process.stdout:
                self.log_view.insert("end", f"[BOT]: {line}")
                self.log_view.see("end")
        except Exception as e:
            self.log_view.insert("end", f"[HATA]: Bot çalıştırılamadı: {str(e)}\n")

    def run_engine(self):
        # Holoserv Motor Yolu
        engine_path = r"C:\Users\mhmdd\Desktop\Ando-Sign3D\server"
        exe_name = "holoserv.exe" 
        
        self.log_view.insert("end", f"[SİSTEM]: {exe_name} ayrı bir pencerede açılıyor...\n")
        
        try:
            # GÜNCELLEME: stdout=subprocess.PIPE kaldırıldı! 
            # Böylece hata mesajı siyah ekranda (konsolda) kalacak ve görebileceksin.
            subprocess.Popen([exe_name], cwd=engine_path, shell=True)
            
            self.log_view.insert("end", "[BİLGİ]: Motor tetiklendi. Eğer siyah ekran hemen kapanıyorsa klasör yolunu kontrol edin.\n")
        except Exception as e:
            self.log_view.insert("end", f"[HATA]: Motor EXE'si başlatılamadı! Detay: {str(e)}\n")

if __name__ == "__main__":
    app = AndoSignPro()
    app.mainloop()