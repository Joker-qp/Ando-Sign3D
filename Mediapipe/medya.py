import customtkinter as ctk
import cv2
import threading
from PIL import Image
from customtkinter import CTkImage
import mediapipe as mp

# MediaPipe Konfigürasyonu
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

class AndoSignApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ando-Sign 3D: Akıllı İşaret Tanıma Sistemi")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        self.is_running = False
        self.cap = None

        # --- ARAYÜZ ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=200)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=10, pady=10)
        
        self.btn_start = ctk.CTkButton(self.sidebar, text="SİSTEMİ BAŞLAT", command=self.start_camera, fg_color="#2ecc71", hover_color="#27ae60")
        self.btn_start.pack(pady=20, padx=10)

        self.btn_stop = ctk.CTkButton(self.sidebar, text="DURDUR", command=self.stop_camera, fg_color="#e74c3c", state="disabled")
        self.btn_stop.pack(pady=10, padx=10)

        self.video_label = ctk.CTkLabel(self, text="Kamera Bekleniyor...", fg_color="#1a1a1a", corner_radius=15)
        self.video_label.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.output_box = ctk.CTkTextbox(self, height=150, font=("Consolas", 14))
        self.output_box.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="nsew")
        
        self.last_gesture = "" # Sürekli aynı şeyi yazmasın diye kontrol

    def log(self, message):
        self.output_box.insert("end", f"> {message}\n")
        self.output_box.see("end")

    # --- MANTIK MOTORU: İŞARET TANIMA ---
    def detect_gesture(self, hand_landmarks, hand_label):
        # MediaPipe Parmak Uçları: Baş(4), İşaret(8), Orta(12), Yüzük(16), Serçe(20)
        tips = [4, 8, 12, 16, 20]
        fingers = []

        # 1. Baş Parmak Kontrolü (X ekseni)
        # Sağ/Sol el aynalandığı için x koordinatı el etiketine göre kontrol edilir
        if hand_label == "Right":
            fingers.append(1 if hand_landmarks.landmark[tips[0]].x < hand_landmarks.landmark[tips[0] - 1].x else 0)
        else:
            fingers.append(1 if hand_landmarks.landmark[tips[0]].x > hand_landmarks.landmark[tips[0] - 1].x else 0)

        # 2. Diğer 4 Parmak (Y ekseni - Yukarı/Aşağı)
        for i in range(1, 5):
            if hand_landmarks.landmark[tips[i]].y < hand_landmarks.landmark[tips[i] - 2].y:
                fingers.append(1) # Açık
            else:
                fingers.append(0) # Kapalı

        # 3. İşaret Eşleştirme (👊👌👍👎👇👆👉👈)
        gesture_map = {
            (0, 0, 0, 0, 0): "Yumruk (👊)",
            (1, 1, 1, 1, 1): "open palm (✋)",
            (0, 1, 0, 0, 0): "POINTS (👆)",
            (1, 0, 0, 0, 0): "cool (👍)",
            (0, 1, 1, 0, 0): "win (✌️)",
            (1, 1, 0, 0, 1): "okey  (👌)",
            (0, 0, 0, 0, 1): "wants to speak. (☝️)"
        }
        
        return gesture_map.get(tuple(fingers), "none")

    def start_camera(self):
        if not self.is_running:
            self.is_running = True
            self.cap = cv2.VideoCapture(0)
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            threading.Thread(target=self.video_loop, daemon=True).start()

    def stop_camera(self):
        self.is_running = False
        if self.cap: self.cap.release()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def video_loop(self):
        with mp_hands.Hands(model_complexity=0, min_detection_confidence=0.7, min_tracking_confidence=0.7) as hands:
            while self.is_running:
                ret, frame = self.cap.read()
                if not ret: break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_frame)

                if results.multi_hand_landmarks:
                    for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                        hand_info = results.multi_handedness[idx].classification[0].label
                        
                        # Renk ve Etiket
                        color = (0, 255, 0) if hand_info == "Left" else (255, 0, 0)
                        
                        # İŞARETİ TANI
                        gesture = self.detect_gesture(hand_landmarks, hand_info)
                        
                        # İskeleti Çiz
                        mp_drawing.draw_landmarks(rgb_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        
                        # Ekrana Yazdır
                        h, w, _ = rgb_frame.shape
                        cx, cy = int(hand_landmarks.landmark[0].x * w), int(hand_landmarks.landmark[0].y * h)
                        cv2.putText(rgb_frame, f"{hand_info}: {gesture}", (cx, cy - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                        # Log Paneline Sadece Değişim Olduğunda Yaz
                        if gesture != self.last_gesture and gesture != "none":
                            self.after(0, lambda g=gesture, h=hand_info: self.log(f"{h} EL: {g}"))
                            self.last_gesture = gesture

                img_pil = Image.fromarray(rgb_frame)
                ctk_img = CTkImage(light_image=img_pil, dark_image=img_pil, size=(800, 500))
                self.video_label.configure(image=ctk_img)
                self.video_label.image = ctk_img

    def on_closing(self):
        self.stop_camera()
        self.destroy()

if __name__ == "__main__":
    app = AndoSignApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()