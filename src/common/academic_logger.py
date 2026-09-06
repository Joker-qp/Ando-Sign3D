"""
================================================================================
DOSYA: src/common/academic_logger.py
PROJE: AndoSign - Multimodal Sign Language AI Ecosystem
ROLÜ  : Deney Takibi, Donanım & Çevre Telemetrisi, Gradyan/VRAM Günlüğü 
        ve Green AI Karbon Ayak İzi Ölçümü
TÜKETİCİ MODÜLLER:
  - src/models/m01_asl_letters/train.py (Model M-01 / Börü)
  - src/common/report_generator.py (Model Kartı Üreticisi)
  - Tüm 16+1 Modelin Eğitim Boru Hatları

AÇIKLAMA:
  Bu modül, derin öğrenme eğitim süreçlerinin IEEE ve Green AI standartlarında
  kayıt altına alınmasını sağlar. Klasik eğitim loglamasının ötesine geçerek:
  1. Deney başlangıcında donanım (GPU modeli, CUDA sürümü, OS), mimari parametre
     sayısı (Toplam/Eğitilebilir) ve hiperparametreleri 'run_config.json' olarak kaydeder.
  2. Her epoch'ta Train/Val Loss, Doğruluk, Cosine Öğrenme Oranı (LR), L2 Gradyan
     Normu, Tepe VRAM Kullanımı (MB) ve tur süresini 'train_metrics.csv' tablosuna yazar.
  3. 'codecarbon' kütüphanesi ile GPU/CPU enerji tüketimini (kWh) ve tahmini karbon
     salınımını (kg CO2eq) ölçerek 'carbon_emissions.csv' kütüğünü oluşturur.

GİRDİLER (INPUTS):
  - experiment_dir (Path): Modelin çıktı ve loglarının yazılacağı ana dizin (artifacts/...).
  - model_id (str): Modelin evrensel kimlik kodu (Örn: 'L-ASL-01').
  - seed (int): Rastgelelik tohum değeri (Determinizm kontrolü).
  - config (Dict[str, Any]): Eğitim hiperparametreleri sözlüğü.
  - model (torch.nn.Module): Eğitilen PyTorch model nesnesi.
  - Epoch bazlı metrikler: (epoch, train_loss, val_loss, train_acc, val_acc, lr, grad_norm, epoch_time_sec).

ÇIKTILAR (OUTPUTS):
  - run_config.json: Donanım, tohum, parametre boyutu ve hiperparametre kütüğü.
  - train_metrics.csv: Epoch bazlı zaman serisi eğitim ve kaynak kullanım tablosu.
  - carbon_emissions.csv: Enerji tüketimi (kWh) ve CO2 salınım raporu.
================================================================================
"""

import json
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import torch
from codecarbon import EmissionsTracker


class AcademicExperimentTracker:
    """
    IEEE ve Green AI standartlarında deney takibi, donanım kaynak telemetrisi
    ve karbon salınımı ölçüm motoru.
    """

    def __init__(self, experiment_dir: Path, model_id: str, seed: int = 42) -> None:
        """
        AcademicExperimentTracker sınıfını başlatır ve alt dizinleri hazırlar.

        Args:
            experiment_dir (Path): Deney çıktılarının saklanacağı ana dizin (Örn: artifacts/L-ASL-01/).
            model_id (str): Modelin resmi kodu (Örn: 'L-ASL-01').
            seed (int): Determinizm ve tekrarlanabilirlik tohumu (Varsayılan: 42).
        """
        self.exp_dir: Path = Path(experiment_dir)
        self.exp_dir.mkdir(parents=True, exist_ok=True)
        
        # Grafik ve kontrol noktası (checkpoint) alt klasörlerini oluştur
        (self.exp_dir / "plots").mkdir(parents=True, exist_ok=True)
        (self.exp_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

        self.model_id: str = model_id
        self.seed: int = seed
        self.start_time: float = time.time()
        self.metrics_history: List[Dict[str, Any]] = []

        # CodeCarbon Emisyon Takipçisini Başlatma (Arka plan servisi)
        self.emissions_file: Path = self.exp_dir / "carbon_emissions.csv"
        try:
            self.tracker: Optional[EmissionsTracker] = EmissionsTracker(
                output_dir=str(self.exp_dir),
                output_file="carbon_emissions.csv",
                log_level="error",
                save_to_file=True
            )
            self.tracker.start()
            self.has_tracker: bool = True
        except Exception as e:
            # WSL veya kısıtlı ortamlarda sensör yoksa eğitimi çökertmeden devam et
            print(f"⚠️ [Green AI] CodeCarbon sensörü başlatılamadı (Simülasyon moduna geçildi): {e}")
            self.tracker = None
            self.has_tracker = False

    def log_run_configuration(self, config: Dict[str, Any], model: torch.nn.Module) -> None:
        """
        Eğitimin başlangıcında donanım, kütüphane sürümleri, parametre sayıları ve
        hiperparametreleri 'run_config.json' olarak kaydeder.

        Args:
            config (Dict[str, Any]): Eğitim ve mimari hiperparametre sözlüğü.
            model (torch.nn.Module): Parametre sayısı hesaplanacak PyTorch model nesnesi.
        """
        total_params: int = sum(p.numel() for p in model.parameters())
        trainable_params: int = sum(p.numel() for p in model.parameters() if p.requires_grad)

        # 32-bit Float tensör boyutu hesabı: Parametre Başına 4 Bayt
        model_size_kb: float = round(total_params * 4.0 / 1024.0, 2)

        meta_data: Dict[str, Any] = {
            "model_id": self.model_id,
            "seed": self.seed,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "environment": {
                "python_version": platform.python_version(),
                "torch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
                "operating_system": f"{platform.system()} {platform.release()}"
            },
            "parameters": {
                "total_params": total_params,
                "trainable_params": trainable_params,
                "non_trainable_params": total_params - trainable_params,
                "model_size_kb": model_size_kb
            },
            "hyperparameters": config
        }

        output_json_path: Path = self.exp_dir / "run_config.json"
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=4)

    def log_epoch(
        self,
        epoch: int,
        train_loss: float,
        val_loss: float,
        train_acc: float,
        val_acc: float,
        lr: float,
        grad_norm: float,
        epoch_time_sec: float
    ) -> None:
        """
        Her epoch sonunda eğitim kaybı, doğruluk, öğrenme oranı, L2 gradyan normu ve
        tepe GPU bellek kullanımını (VRAM) bellek listesine ekler.

        Args:
            epoch (int): Mevcut eğitim turu indeksi (1-indexed).
            train_loss (float): Eğitim seti ortalama kaybı (Loss).
            val_loss (float): Doğrulama seti ortalama kaybı (Validation Loss).
            train_acc (float): Eğitim seti doğruluk yüzdesi (%0 - %100).
            val_acc (float): Doğrulama seti doğruluk yüzdesi (%0 - %100).
            lr (float): Mevcut optimizer öğrenme oranı (Learning Rate).
            grad_norm (float): Katmanların L2 gradyan normu toplamı (Optimizasyon sağlığı).
            epoch_time_sec (float): Epoch'un tamamlanma süresi (Saniye).
        """
        # CUDA Tepe Bellek Telemetrisi (MB cinsinden)
        vram_mb: float = 0.0
        if torch.cuda.is_available():
            vram_mb = round(torch.cuda.max_memory_allocated() / (1024.0 * 1024.0), 2)

        epoch_record: Dict[str, Any] = {
            "epoch": epoch,
            "train_loss": round(float(train_loss), 5),
            "val_loss": round(float(val_loss), 5),
            "train_acc": round(float(train_acc), 3),
            "val_acc": round(float(val_acc), 3),
            "learning_rate": float(lr),
            "grad_norm": round(float(grad_norm), 4),
            "vram_allocated_mb": vram_mb,
            "epoch_time_sec": round(float(epoch_time_sec), 2)
        }
        self.metrics_history.append(epoch_record)

    def finish_training(self) -> Dict[str, Any]:
        """
        Eğitim oturumunu sonlandırır, toplanan zaman serisi metriklerini CSV tablosuna yazar,
        CodeCarbon motorunu durdurarak toplam enerji tüketimi ve CO2 salınımını döner.

        Returns:
            Dict[str, Any]: Toplam eğitim süresi, CO2 salınımı (kg) ve tüketilen enerjiyi (kWh) içeren özet sözlük.
        """
        # 1. Metrik Geçmişini CSV Tablosuna Serileştirme
        df_metrics: pd.DataFrame = pd.DataFrame(self.metrics_history)
        metrics_csv_path: Path = self.exp_dir / "train_metrics.csv"
        df_metrics.to_csv(metrics_csv_path, index=False)

        # 2. Toplam Süre ve Karbon Salınımı Hesabı
        total_duration: float = time.time() - self.start_time
        emissions_kg: float = 0.0
        energy_kwh: float = 0.0

        if self.has_tracker and self.tracker is not None:
            try:
                emissions_kg = float(self.tracker.stop() or 0.0)
                if self.emissions_file.exists():
                    df_carbon: pd.DataFrame = pd.read_csv(self.emissions_file)
                    if "energy_consumed" in df_carbon.columns:
                        energy_kwh = float(df_carbon["energy_consumed"].sum())
            except Exception as e:
                print(f"⚠️ [Green AI] Emisyon kütüğü sonlandırılırken hata: {e}")

        summary_report: Dict[str, Any] = {
            "total_duration_sec": round(total_duration, 2),
            "co2_emissions_kg": round(emissions_kg, 6),
            "energy_consumed_kwh": round(energy_kwh, 6)
        }
        return summary_report