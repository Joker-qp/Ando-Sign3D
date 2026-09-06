"""
================================================================================
DOSYA: src/common/math_normalizer.py
PROJE: AndoSign - Multimodal Sign Language AI Ecosystem
ROLÜ  : Biyometrik El İskeleti Matematiksel Normalizasyonu, Öteleme (Translation)
        ve Ölçek (Scale) Değişmezliği Motoru
TÜKETİCİ MODÜLLER:
  - src/models/m01_asl_letters/train.py (Model M-01 / Börü - Önbellekleme)
  - src/models/m01_asl_letters/test_cam.py (Canlı Çıkarım Arayüzü)
  - Tüm ASL/TİD İskelet Tabanlı Modeller (M-01 - M-07)

AÇIKLAMA:
  MediaPipe Hands kütüphanesinden elde edilen 21 el eklem noktası ham piksel
  veya normalize ekran koordinatlarında [0, 1] gelir. Bu ham koordinatlar:
  1. Elin ekranın solunda, sağında veya köşesinde olmasına (Öteleme / Konum),
  2. Kullanıcının kameraya çok yakın veya uzak durmasına (Ölçek / Boyut),
  3. Kullanıcının elinin fiziksel olarak büyük veya küçük olmasına göre değişir.

  Bu modül, el koordinatlarını bu dış etkenlerden tamamen arındırarak modele
  sadece "saf el hareket geometrisini" (parmakların birbirine göre açı ve mesafesini)
  aktarır.

MATEMATİKSEL DÖNÜŞÜM ADIMLARI:
  1. Bilek Merkezleme (Translation Invariance):
     P'_i = P_i - P_0  (Burada P_0 = Bilek Eklemi / WRIST, ∀i ∈ [0, 20])
     -> Bilek koordinatı orijin (0.0, 0.0, 0.0) noktasına çekilir.

  2. Öklid Ölçekleme (Scale Invariance):
     S = ||P'_9 - P'_0||_2  (P'_9 = Orta Parmak Kökü / MIDDLE_FINGER_MCP)
     P̂_i = P'_i / S
     -> Avuç içi referans uzunluğu 1.0 birim yapılarak el boyutu eşitlenir.

GİRDİLER (INPUTS):
  - landmarks_xyz (Union[np.ndarray, list]): 21 adet (x, y, z) koordinat demeti
    veya (21, 3) / (63,) boyutunda ham float matrisi.

ÇIKTILAR (OUTPUTS):
  - np.ndarray: (63,) boyutunda, 0 etrafında merkezlenmiş ve ölçeklenmiş 
    np.float32 öznitelik vektörü.
================================================================================
"""

from typing import List, Tuple, Union
import numpy as np


class HandPoseNormalizer:
    """
    21 el landmark noktasını konuma ve mesafeye karşı değişmez (invariant)
    kılan matematiksel normalizasyon motoru.
    """

    # MediaPipe Hands Referans İndeksleri
    WRIST_IDX: int = 0                  # Bilek eklemi (Orijin referansı)
    MIDDLE_MCP_IDX: int = 9             # Orta parmak kök eklemi (Ölçek referansı)

    @staticmethod
    def normalize_keypoints(landmarks_xyz: Union[np.ndarray, List[Tuple[float, float, float]], list]) -> np.ndarray:
        """
        21 adet 3D el eklemi koordinatını alır, bileğe göre merkezler, avuç içi
        boyutuna göre ölçekler ve 63 elemanlı düz bir vektör döner.

        Args:
            landmarks_xyz (Union[np.ndarray, list]): 
                - (21, 3) Boyutunda [x, y, z] koordinat matrisi, VEYA
                - (63,) Boyutunda düzleştirilmiş ham koordinat dizisi, VEYA
                - 21 elemanlı [(x, y, z), ...] Python listesi.

        Returns:
            np.ndarray: (63,) Boyutunda, normalize edilmiş 1D float32 öznitelik vektörü.

        Raises:
            ValueError: Girdi boyutu (21, 3) veya (63,) formatına dönüştürülemezse.
        """
        # 1. Girdi Tipini ve Şeklini Doğrulama
        pts: np.ndarray = np.array(landmarks_xyz, dtype=np.float32)

        if pts.shape == (63,):
            pts = pts.reshape(21, 3)
        elif pts.shape != (21, 3):
            raise ValueError(
                f"Geçersiz landmark boyutu! Beklenen: (21, 3) veya (63,), Alınan: {pts.shape}"
            )

        # ======================================================================
        # ADIM 1: BİLEK MERKEZLEME (TRANSLATION INVARIANCE)
        # ======================================================================
        # 0 numaralı bilek noktasını orijin (0, 0, 0) kabul edip tüm noktalardan çıkar
        wrist_origin: np.ndarray = pts[HandPoseNormalizer.WRIST_IDX, :].copy()
        centered_pts: np.ndarray = pts - wrist_origin

        # ======================================================================
        # ADIM 2: ÖKLİD ÖLÇEK NORMALİZASYONU (SCALE INVARIANCE)
        # ======================================================================
        # Bilek (0) ile Orta Parmak Kökü (9) arasındaki L2 Öklid mesafesini hesapla
        palm_size: float = float(np.linalg.norm(
            centered_pts[HandPoseNormalizer.MIDDLE_MCP_IDX, :] - centered_pts[HandPoseNormalizer.WRIST_IDX, :]
        ))

        # Sıfıra bölme hatasını (ZeroDivisionError) önleyen sayısal kararlılık kontrolü
        if palm_size < 1e-6:
            # Parmaklar üst üste binmişse maksimum açıklığı referans al
            palm_size = float(np.max(np.linalg.norm(centered_pts, axis=1))) + 1e-6

        # Tüm koordinatları avuç içi boyutuna bölerek ölçekle
        normalized_pts: np.ndarray = centered_pts / palm_size

        # ======================================================================
        # ADIM 3: 1D VEKTÖRE DÜZLEŞTİRME (FLATTENING)
        # ======================================================================
        # (21, 3) matrisini (63,) boyutunda 1D tensör girdisine dönüştür
        return normalized_pts.flatten().astype(np.float32)