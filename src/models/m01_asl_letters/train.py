"""
================================================================================
DOSYA: src/models/m01_asl_letters/train.py
PROJE: AndoSign - Multimodal Sign Language AI Ecosystem
MODEL KİMLİĞİ: L-ASL-01
MODEL ADI: Börü (ASL 26-Letter Residual Landmark Classifier)
ROLÜ  : Uçtan Uca Akademik Eğitim, Donanım & Karbon Telemetrisi, Ayrıştırılmış
        Değerlendirme, Model Kartı Üretimi ve ONNX İhraç Boru Hattı
TÜKETİCİ MODÜLLER:
  - Terminal CLI (pixi run -e env-cluster1 python -m src.models.m01_asl_letters.train)
  - Otomatik Kıyaslama ve CI/CD Test Sistemleri

AÇIKLAMA:
  Bu modül, 'Börü' (L-ASL-01) modelinin sıfırdan canlıya alınmasına kadar olan
  tüm süreci tek merkezden yöneten ana orkestratördür:
  1. Veri ve Önbellek Denetimi: Temiz Parquet manifestosunu doğrular, 101k görselin
     21 koordinat noktasını MediaPipe ile bir kez çıkarıp sıkıştırılmış .npz formatında önbelleğe alır.
  2. Sınıf Dengesizliği Çözümü: 3.7:1 oranındaki frekans farkını dengelemek için ters sınıf ağırlıkları
     (Inverse Class Frequency Weights) hesaplar.
  3. Akademik Eğitim Döngüsü: AdamW, Cosine Annealing LR, Label Smoothing (0.05) ve L2 Gradyan
     Kırpma (Gradient Clipping = 5.0) ile eğitir; her epoch'un Loss, Acc, Grad Norm ve VRAM'ini kaydeder.
  4. Green AI Karbon Takibi: CodeCarbon motoru ile GPU/CPU enerji tüketimini (kWh) ve CO2 salınımını ölçer.
  5. Ayrıştırılmış Değerlendirme (Mitchell et al.): %95 Güven Aralığı (Wilson Score), Brier Skoru,
     Hiç Görülmemiş Denek (Kişi E) başarımını hesaplar ve 5 adet 300 DPI akademik grafik üretir.
  6. Model Kartı & ONNX Üretimi: Hugging Face YAML metadata içeren resmi Model Kartını (.md) derler
     ve modeli canlı kamera çıkarımı için Opset 17 formatında ihraç eder.

GİRDİLER (INPUTS):
  - configs/models/m01_asl_letters.yaml: Model mimari ve eğitim hiperparametreleri.
  - data/manifests/m01_asl_letters_clean.parquet: Doğrulanmış temiz veri tablosu.
  - data/raw/asl_letters/: Ham görseller (.jpg, .png).

ÇIKTILAR (OUTPUTS):
  - data/processed/m01_asl_letters_21p/m01_asl_letters_21p_cache.npz: 63-D Tensör Önbelleği.
  - artifacts/m01_asl_letters/checkpoints/best_model.pth: En iyi PyTorch ağırlıkları.
  - artifacts/m01_asl_letters/checkpoints/m01_asl_letters_best.onnx: Optimize ONNX motoru.
  - artifacts/m01_asl_letters/run_config.json: Donanım ve mimari parametre kütüğü.
  - artifacts/m01_asl_letters/train_metrics.csv: Epoch bazlı zaman serisi metrikleri.
  - artifacts/m01_asl_letters/evaluation_report.json: Ayrıştırılmış test raporu.
  - artifacts/m01_asl_letters/carbon_emissions.csv: CodeCarbon çevre raporu.
  - artifacts/m01_asl_letters/plots/: 5 Adet 300 DPI Akademik Grafik (PNG).
  - docs/model_cards/M01_asl_letters_card.md: Resmi Hugging Face Model Kartı.
================================================================================
"""

import os
import string
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
import yaml

# Monorepo Kök Dizinini (AndoSign/) Sisteme Ekleme
ROOT_DIR: Path = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Ortak Akademik Altyapı Modülleri
from src.common.academic_evaluator import AcademicEvaluator
from src.common.academic_logger import AcademicExperimentTracker
from src.common.io_manifest_reader import ManifestManager
from src.common.math_normalizer import HandPoseNormalizer
from src.common.report_generator import generate_huggingface_model_card
from src.models.m01_asl_letters.model import ASLLettersNet


def extract_and_cache(df: pd.DataFrame, cache_path: Path, detector: Any) -> None:
    """
    Temizlenmiş veri setindeki tüm görsellerin 21 el eklem noktasını MediaPipe ile çıkarır,
    HandPoseNormalizer ile normalize eder ve sıkıştırılmış .npz formatında kaydeder.

    Args:
        df (pd.DataFrame): Temizlenmiş Parquet veri tablosu.
        cache_path (Path): .npz önbellek dosyasının hedef konumu.
        detector (Any): MediaPipe Hands detektör nesnesi.

    Returns:
        None: Dosyayı diske yazar.
    """
    print(f"\n⚡ [Önbellekleme] {len(df):,} temiz görsel için 21 koordinat noktası ön-çıkarılıyor...")
    
    classes: List[str] = sorted(df["canonical_label"].unique())
    label_to_idx: Dict[str, int] = {c: i for i, c in enumerate(classes)}
    
    X_list: List[np.ndarray] = []
    y_list: List[int] = []
    split_list: List[str] = []
    person_e_list: List[bool] = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Koordinatlar Çıkarılıyor & Normalize Ediliyor"):
        img_bgr: Optional[np.ndarray] = cv2.imread(row["original_path"])
        if img_bgr is None:
            continue
            
        img_rgb: np.ndarray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        res = detector.process(img_rgb)
        
        if res.multi_hand_landmarks:
            raw_pts: List[Tuple[float, float, float]] = [
                (lm.x, lm.y, lm.z) for lm in res.multi_hand_landmarks[0].landmark
            ]
            # Bilek merkezleme ve ölçek değişmezliği dönüşümü (63-D Vektör)
            norm_vec: np.ndarray = HandPoseNormalizer.normalize_keypoints(raw_pts)
            
            X_list.append(norm_vec)
            y_list.append(label_to_idx[row["canonical_label"]])
            split_list.append(row["split"])
            person_e_list.append(bool(row.get("is_person_e", False)))

    # NumPy Matrislerine Dönüştürme
    X: np.ndarray = np.array(X_list, dtype=np.float32)
    y: np.ndarray = np.array(y_list, dtype=np.int64)
    splits: np.ndarray = np.array(split_list)
    person_e: np.ndarray = np.array(person_e_list)

    train_mask: np.ndarray = (splits == "train")
    val_mask: np.ndarray = (splits == "val")
    test_mask: np.ndarray = (splits == "test")

    # Sıkıştırılmış NPZ Olarak Kaydetme
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        X_train=X[train_mask], y_train=y[train_mask],
        X_val=X[val_mask], y_val=y[val_mask],
        X_test=X[test_mask], y_test=y[test_mask],
        person_e_test=person_e[test_mask]
    )
    print(f"✅ Koordinat önbelleği başarıyla kaydedildi: {cache_path}")


def run_training_pipeline() -> None:
    """
    Model L-ASL-01 (Börü) için tüm eğitim, telemetri, değerlendirme,
    model kartı üretimi ve ONNX ihracı adımlarını yürüten ana boru hattı fonksiyonu.

    Returns:
        None
    """
    # ==========================================================================
    # 1. YAPILANDIRMA VE DİZİN YOLLARININ HAZIRLANMASI
    # ==========================================================================
    config_path: Path = ROOT_DIR / "configs" / "models" / "m01_asl_letters.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg: Dict[str, Any] = yaml.safe_load(f)

    model_id: str = cfg.get("model_id", "L-ASL-01")
    model_name: str = cfg.get("model_name", "Börü")
    artifacts_dir: Path = ROOT_DIR / "artifacts" / "m01_asl_letters"
    manifest_path: Path = ROOT_DIR / cfg["data"]["manifest_path"]
    cache_path: Path = ROOT_DIR / cfg["data"]["processed_dir"] / "m01_asl_letters_21p_cache.npz"
    card_path: Path = ROOT_DIR / "docs" / "model_cards" / "M01_asl_letters_card.md"

    # ==========================================================================
    # 2. VERİ VE ÖNBELLEK DENETİMİ
    # ==========================================================================
    # Parquet manifestosu yoksa otomatik kürasyon çalıştır
    if not manifest_path.exists():
        print(f"[{manifest_path}] bulunamadı! Veri kürasyonu başlatılıyor...")
        ManifestManager().build_asl_letters_manifest()

    # Koordinat önbelleği yoksa MediaPipe ile bir kez çıkar
    if not cache_path.exists():
        df_clean: pd.DataFrame = ManifestManager.load_manifest(str(manifest_path), core_letters_only=True)
        detector = mp.solutions.hands.Hands(
            static_image_mode=True, max_num_hands=1, min_detection_confidence=0.65
        )
        extract_and_cache(df_clean, cache_path, detector)

    # ==========================================================================
    # 3. DENEY TAKİPÇİSİ (TRACKER) VE VERİ YÜKLEYİCİLERİ (DATALOADERS)
    # ==========================================================================
    seed: int = int(cfg["training"].get("seed", 42))
    torch.manual_seed(seed)
    np.random.seed(seed)

    tracker: AcademicExperimentTracker = AcademicExperimentTracker(
        experiment_dir=artifacts_dir, model_id=model_id, seed=seed
    )

    data: np.lib.npyio.NpzFile = np.load(cache_path)
    X_train: torch.Tensor = torch.tensor(data["X_train"])
    y_train: torch.Tensor = torch.tensor(data["y_train"])
    X_val: torch.Tensor = torch.tensor(data["X_val"])
    y_val: torch.Tensor = torch.tensor(data["y_val"])
    X_test: torch.Tensor = torch.tensor(data["X_test"])
    y_test: torch.Tensor = torch.tensor(data["y_test"])
    person_e_test: np.ndarray = data["person_e_test"]

    batch_size: int = int(cfg["training"]["batch_size"])
    train_loader: DataLoader = DataLoader(TensorDataset(X_train, y_train), batch_size=batch_size, shuffle=True)
    val_loader: DataLoader = DataLoader(TensorDataset(X_val, y_val), batch_size=batch_size, shuffle=False)
    test_loader: DataLoader = DataLoader(TensorDataset(X_test, y_test), batch_size=batch_size, shuffle=False)

    print(f"\n📊 Veri Dağılımı: Train = {len(X_train):,} | Val = {len(X_val):,} | Test = {len(X_test):,}")

    # ==========================================================================
    # 4. SINIF AĞIRLIKLANDIRMASI VE MODEL BAŞLATMA
    # ==========================================================================
    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 3.7:1 Dengesizliğe Karşı Ters Sınıf Frekans Ağırlıkları (Inverse Class Weights)
    class_counts: np.ndarray = np.bincount(y_train.numpy())
    class_weights: np.ndarray = len(y_train) / (len(class_counts) * class_counts.astype(np.float32))
    weights_tensor: torch.Tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)

    model: ASLLettersNet = ASLLettersNet(
        input_dim=int(cfg["architecture"]["input_dim"]),
        hidden_dims=list(cfg["architecture"]["hidden_dims"]),
        num_classes=int(cfg["data"]["num_classes"]),
        dropout_rate=float(cfg["architecture"]["dropout_rate"])
    ).to(device)

    # Donanım ve Hiperparametre Kütüğünü Kaydet (run_config.json)
    tracker.log_run_configuration(cfg, model)

    criterion: nn.CrossEntropyLoss = nn.CrossEntropyLoss(
        weight=weights_tensor,
        label_smoothing=float(cfg["training"]["label_smoothing"])
    )
    optimizer: torch.optim.AdamW = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["training"]["learning_rate"]),
        weight_decay=float(cfg["training"]["weight_decay"])
    )
    epochs: int = int(cfg["training"]["epochs"])
    scheduler: torch.optim.lr_scheduler.CosineAnnealingLR = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=1e-5
    )

    # ==========================================================================
    # 5. AKADEMİK EĞİTİM DÖNGÜSÜ (TRAINING LOOP)
    # ==========================================================================
    print(f"\n🚀 [AndoSign] {model_id} ({model_name}) Akademik Eğitimi Başlatıldı [{device}]...")
    best_val_acc: float = 0.0
    patience_counter: int = 0
    early_stop_patience: int = int(cfg["training"].get("early_stopping_patience", 10))
    best_ckpt_path: Path = artifacts_dir / "checkpoints" / "best_model.pth"

    for epoch in range(1, epochs + 1):
        t0: float = time.time()
        model.train()
        total_loss: float = 0.0
        correct: int = 0
        total_grad_norm: float = 0.0

        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            out: torch.Tensor = model(bx)
            loss: torch.Tensor = criterion(out, by)
            loss.backward()

            # Optimizasyon Sağlığı İçin L2 Gradyan Kırpma (Gradient Clipping)
            grad_norm: float = float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0).item())
            total_grad_norm += grad_norm

            optimizer.step()
            total_loss += loss.item() * len(by)
            correct += int((out.argmax(1) == by).sum().item())

        scheduler.step()
        train_acc: float = (correct / len(X_train)) * 100.0
        avg_grad_norm: float = total_grad_norm / len(train_loader)

        # Doğrulama (Validation)
        model.eval()
        val_loss: float = 0.0
        val_correct: int = 0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device)
                val_out: torch.Tensor = model(bx)
                v_loss: torch.Tensor = criterion(val_out, by)
                val_loss += v_loss.item() * len(by)
                val_correct += int((val_out.argmax(1) == by).sum().item())

        val_acc: float = (val_correct / len(X_val)) * 100.0
        epoch_sec: float = time.time() - t0

        # Epoch Metriklerini Logla
        tracker.log_epoch(
            epoch=epoch,
            train_loss=total_loss / len(X_train),
            val_loss=val_loss / len(X_val),
            train_acc=train_acc,
            val_acc=val_acc,
            lr=scheduler.get_last_lr()[0],
            grad_norm=avg_grad_norm,
            epoch_time_sec=epoch_sec
        )

        if epoch % 5 == 0 or epoch == 1:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] | Loss: {total_loss/len(X_train):.4f} - Acc: %{train_acc:.2f} | Val Acc: %{val_acc:.2f} | Grad: {avg_grad_norm:.2f}")

        # En İyi Modeli Saklama & Erken Durdurma
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_ckpt_path)
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= early_stop_patience:
                print(f"⏹️ Erken durdurma tetiklendi! (En iyi Val Acc: %{best_val_acc:.2f})")
                break

    # ==========================================================================
    # 6. GREEN AI KAPANIŞI VE KARBON RAPORU
    # ==========================================================================
    train_summary: Dict[str, Any] = tracker.finish_training()
    print(f"\n⚡ Eğitim Bitti! Toplam Süre: {train_summary['total_duration_sec']}s | CO2: {train_summary['co2_emissions_kg']} kg")

    # ==========================================================================
    # 7. AYRIŞTIRILMIŞ BENCHMARK VE AKADEMİK GRAFİKLER
    # ==========================================================================
    model.load_state_dict(torch.load(best_ckpt_path))
    model.eval()

    all_probs_list: List[np.ndarray] = []
    with torch.no_grad():
        for bx, _ in test_loader:
            bx = bx.to(device)
            probs: np.ndarray = torch.softmax(model(bx), dim=1).cpu().numpy()
            all_probs_list.append(probs)
            
    all_probs: np.ndarray = np.concatenate(all_probs_list, axis=0)

    classes: List[str] = list(string.ascii_uppercase)
    evaluator: AcademicEvaluator = AcademicEvaluator(output_dir=artifacts_dir, class_names=classes)
    df_metrics: pd.DataFrame = pd.read_csv(artifacts_dir / "train_metrics.csv")
    
    report: Dict[str, Any] = evaluator.evaluate_and_plot(
        y_true=y_test.numpy(),
        y_pred_probs=all_probs,
        unseen_mask=person_e_test,
        df_train_metrics=df_metrics
    )

    print("\n" + "="*80)
    print(f"🏆 AKADEMİK BENCHMARK SONUÇLARI ({model_id} - {model_name})")
    print(f"🎯 Genel Test Doğruluğu: %{report['overall_accuracy']*100:.2f} (95% CI: [{report['confidence_interval_95'][0]}% - {report['confidence_interval_95'][1]}%])")
    print(f"📊 Macro F1-Skoru: {report['macro_f1']:.4f} | Brier Kalibrasyon Skoru: {report['brier_score']:.4f}")
    if report["unseen_subject_accuracy"] != "N/A":
        print(f"👤 Hiç Görülmemiş Denek (Kişi E) Doğruluğu: %{report['unseen_subject_accuracy']*100:.2f}")
    print("="*80)

    # ==========================================================================
    # 8. HUGGING FACE MODEL KARTI VE ONNX DIŞA AKTARIMI
    # ==========================================================================
    # A. Model Kartı Üretimi (.md)
    generate_huggingface_model_card(artifacts_dir, card_path)

    # B. ONNX İhracı (Opset 17)
    onnx_filename: str = cfg["export"].get("onnx_filename", "m01_asl_letters_best.onnx")
    onnx_path: Path = artifacts_dir / "checkpoints" / onnx_filename
    model_cpu: ASLLettersNet = model.to("cpu")
    model_cpu.eval()
    dummy_input: torch.Tensor = torch.randn(1, 63, device="cpu")

    try:
        torch.onnx.export(
            model_cpu,
            dummy_input,
            str(onnx_path),
            input_names=["landmarks_63p"],
            output_names=["letter_logits"],
            dynamic_axes={"landmarks_63p": {0: "batch_size"}, "letter_logits": {0: "batch_size"}},
            opset_version=int(cfg["export"].get("onnx_opset", 17)),
            dynamo=False
        )
        print(f"✅ ONNX Canlı Çıkarım Motoru Başarıyla Kaydedildi: {onnx_path}\n")
    except Exception as e:
        print(f"⚠️ ONNX ihracı sırasında hata oluştu: {e}")


# ==============================================================================
# CLI GİRİŞ NOKTASI
# ==============================================================================
if __name__ == "__main__":
    run_training_pipeline()