"""
MODULE: test_cam.py (Real-time 60 FPS Camera Test & Word Builder)
"""
import sys
import string
from pathlib import Path
import cv2
import numpy as np
import torch
import torch.nn.functional as F
import mediapipe as mp

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.common.math_normalizer import HandPoseNormalizer
from src.models.m01_asl_letters.model import ASLLettersNet


def run_live_test():
    ckpt_p = ROOT_DIR / "artifacts" / "m01_asl_letters" / "checkpoints" / "best_model.pth"
    if not ckpt_p.exists():
        print(f"❌ HATA: Model ağırlığı bulunamadı! ({ckpt_p})")
        return

    classes = list(string.ascii_uppercase)
    model = ASLLettersNet(input_dim=63, hidden_dims=[256, 128, 64], num_classes=26, dropout_rate=0.0)
    model.load_state_dict(torch.load(ckpt_p, map_location="cpu"))
    model.eval()

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    det = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Kamera açılamadı!")
        return

    current_word, last_char, stable_cnt = "", "", 0

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        res = det.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        disp_char, disp_conf = "-", 0.0

        if res.multi_hand_landmarks:
            for hl in res.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
                raw = [(lm.x, lm.y, lm.z) for lm in hl.landmark]
                inp = torch.tensor(HandPoseNormalizer.normalize_keypoints(raw)).unsqueeze(0)
                with torch.no_grad():
                    probs = F.softmax(model(inp), dim=1).squeeze().numpy()
                    pred_i = np.argmax(probs)
                    disp_conf = probs[pred_i] * 100
                    disp_char = classes[pred_i]

                if probs[pred_i] >= 0.80:
                    if disp_char == last_char:
                        stable_cnt += 1
                        if stable_cnt == 18:
                            current_word += disp_char
                            stable_cnt = 0
                    else:
                        last_char = disp_char; stable_cnt = 1
                else: stable_cnt = 0
        else:
            stable_cnt, last_char = 0, ""

        # UI
        cv2.rectangle(frame, (20, 20), (320, 100), (30, 30, 30), -1)
        cv2.rectangle(frame, (20, 20), (320, 100), (0, 255, 128), 2)
        cv2.putText(frame, f"Tahmin: {disp_char}", (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
        cv2.putText(frame, f"Guven: %{disp_conf:.1f}", (35, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 1)

        cv2.rectangle(frame, (20, h - 90), (w - 20, h - 20), (20, 20, 20), -1)
        cv2.rectangle(frame, (20, h - 90), (w - 20, h - 20), (255, 255, 255), 2)
        cv2.putText(frame, f"Kelime: {current_word}", (35, h - 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        cv2.imshow("AndoSign - Live Test", frame)
        k = cv2.waitKey(1) & 0xFF
        if k in [ord('q'), 27]: break
        elif k == 32: current_word += " "
        elif k in [8, ord('d')]: current_word = current_word[:-1]
        elif k == ord('c'): current_word = ""

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_live_test()