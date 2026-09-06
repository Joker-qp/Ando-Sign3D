"""
================================================================================
DOSYA: src/models/m01_asl_letters/model.py
PROJE: AndoSign - Multimodal Sign Language AI Ecosystem
MODEL KİMLİĞİ: L-ASL-01
MODEL ADI: Börü (ASL 26-Letter Residual Landmark Classifier)
ROLÜ  : Residual Multi-Layer Perceptron (Res-MLP) Derin Öğrenme Mimarisi
TÜKETİCİ MODÜLLER:
  - src/models/m01_asl_letters/train.py (Eğitim ve ONNX Dışa Aktarma)
  - src/models/m01_asl_letters/test_cam.py (Canlı Kamera Çıkarım Arayüzü)
  - src/common/academic_logger.py (Model Parametre Boyutu Analizcisi)

AÇIKLAMA:
  Bu modül, 63 boyutlu normalize edilmiş biyometrik el iskeleti özniteliklerini
  (21 eklem x [x, y, z]) girdi olarak alıp 26 Amerikan İşaret Dili (ASL) harfinin
  ham sınıf logitlerini (logits) üreten 'Börü' (L-ASL-01) model mimarisini tanımlar.

MİMARİ PRENSİPLER VE MATEMATİKSEL TEMELLER:
  1. Residual Skip Connections (Artık Bağlantılar):
     y = GELU( F(x, {W_i}) + W_s * x )
     Derin katmanlarda gradyan kaybolmasını (Vanishing Gradient) engeller ve
     daha kararlı bir optimizasyon yüzeyi sunar.
  2. 1D Batch Normalization (BatchNorm1d):
     Katmanlar arasındaki dahili ortak değişken değişimini (Internal Covariate Shift)
     azaltarak modelin yüksek öğrenme oranlarında hızla yakınsamasını sağlar.
  3. GELU (Gaussian Error Linear Unit) Aktivasyonu:
     Standart ReLU yerine negatif değerlere yumuşak ve olasılıksal bir gradyan akışı sunar.
  4. Dropout Regularization (p = 0.25):
     Eğitim anında nöronları rastgele devre dışı bırakarak aşırı ezberlemeyi (overfitting) önler.

GİRDİLER (INPUTS):
  - x (torch.Tensor): (Batch_Size, 63) Boyutunda Float32 normalize landmark tensörü.

ÇIKTILAR (OUTPUTS):
  - logits (torch.Tensor): (Batch_Size, 26) Boyutunda ham harf logit tensörü.
================================================================================
"""

from typing import List
import torch
import torch.nn as nn


class ResidualBlock(nn.Module):
    """
    Doğrusal projeksiyon, Batch Normalization, GELU aktivasyonu ve
    artık atlama bağlantısı (skip connection) içeren Residual MLP Bloğu.
    
    Matematiksel Akış:
      x_main = GELU( BatchNorm( Linear2( Dropout( GELU( BatchNorm( Linear1(x) ) ) ) ) ) )
      x_skip = BatchNorm( Linear_proj(x) ) if in_features != out_features else x
      output = GELU( x_main + x_skip )
    """

    def __init__(self, in_features: int, out_features: int, dropout_rate: float = 0.25) -> None:
        """
        ResidualBlock sınıfını başlatır.

        Args:
            in_features (int): Bloğa giren öznitelik vektörünün boyutu.
            out_features (int): Bloktan çıkan öznitelik vektörünün boyutu.
            dropout_rate (float): Aşırı ezberlemeyi önleyen Dropout olasılığı (Varsayılan: 0.25).
        """
        super().__init__()

        # Ana Kol (Main Residual Branch) - 1. Katman
        self.fc1: nn.Linear = nn.Linear(in_features, out_features)
        self.bn1: nn.BatchNorm1d = nn.BatchNorm1d(out_features)
        self.act1: nn.GELU = nn.GELU()
        self.dropout: nn.Dropout = nn.Dropout(dropout_rate)

        # Ana Kol - 2. Katman
        self.fc2: nn.Linear = nn.Linear(out_features, out_features)
        self.bn2: nn.BatchNorm1d = nn.BatchNorm1d(out_features)
        self.act2: nn.GELU = nn.GELU()

        # Atlama Kolu (Shortcut / Residual Branch)
        # Girdi ve çıktı boyutları uyuşmuyorsa lineer projeksiyon katmanı kullanılır
        self.shortcut: nn.Module = nn.Sequential()
        if in_features != out_features:
            self.shortcut = nn.Sequential(
                nn.Linear(in_features, out_features),
                nn.BatchNorm1d(out_features)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Bloğun ileri geçiş (forward pass) hesaplaması.

        Args:
            x (torch.Tensor): (Batch_Size, in_features) Boyutunda girdi tensörü.

        Returns:
            torch.Tensor: (Batch_Size, out_features) Boyutunda işlenmiş tensör.
        """
        residual: torch.Tensor = self.shortcut(x)

        out: torch.Tensor = self.fc1(x)
        out = self.bn1(out)
        out = self.act1(out)
        out = self.dropout(out)

        out = self.fc2(out)
        out = self.bn2(out)

        # Artık bağlantı ile ana kolun toplanması ve son aktivasyon
        out = self.act2(out + residual)
        return out


class ASLLettersNet(nn.Module):
    """
    Model L-ASL-01 (Kod Adı: Börü) - ASL 26-Harf Sınıflandırıcı Ağ.
    
    Mimari Yapı:
      1. Feature Extractor: 3 Kademeli Residual Blok Dizisi (63 ➜ 256 ➜ 128 ➜ 64)
      2. Classification Head: 2 Kademeli Yoğun Sınıflandırma Kafası (64 ➜ 64 ➜ 26)
    """

    def __init__(
        self,
        input_dim: int = 63,
        hidden_dims: List[int] = [256, 128, 64],
        num_classes: int = 26,
        dropout_rate: float = 0.25
    ) -> None:
        """
        ASLLettersNet mimarisini başlatır ve katmanları oluşturur.

        Args:
            input_dim (int): Girdi öznitelik boyutu (21 landmark * 3 = 63).
            hidden_dims (List[int]): Residual blokların gizli katman boyutları listesi.
            num_classes (int): Sınıflandırılacak toplam harf sayısı (A-Z için 26).
            dropout_rate (float): Regularizasyon için Dropout oranı (Varsayılan: 0.25).
        """
        super().__init__()

        # ======================================================================
        # 1. ÖZNİTELİK ÇIKARICI GÖVDE (RESIDUAL FEATURE EXTRACTOR)
        # ======================================================================
        layers: List[nn.Module] = []
        current_dim: int = input_dim

        for h_dim in hidden_dims:
            layers.append(ResidualBlock(
                in_features=current_dim,
                out_features=h_dim,
                dropout_rate=dropout_rate
            ))
            current_dim = h_dim

        self.extractor: nn.Sequential = nn.Sequential(*layers)

        # ======================================================================
        # 2. SINIFLANDIRMA KAFASI (DENSE CLASSIFICATION HEAD)
        # ======================================================================
        self.head: nn.Sequential = nn.Sequential(
            nn.Linear(current_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout_rate * 0.5),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Modelin uçtan uca ileri geçiş (forward pass) fonksiyonu.

        Args:
            x (torch.Tensor): (Batch_Size, 63) Boyutunda normalize edilmiş float tensör.

        Returns:
            torch.Tensor: (Batch_Size, 26) Boyutunda ham sınıf logitleri (Logits).
        """
        # Tensör Şekil Dönüşümü: (B, 63) ➜ (B, 64)
        features: torch.Tensor = self.extractor(x)
        
        # Tensör Şekil Dönüşümü: (B, 64) ➜ (B, 26)
        logits: torch.Tensor = self.head(features)
        
        return logits