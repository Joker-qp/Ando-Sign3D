"""
================================================================================
DOSYA: src/common/academic_evaluator.py
PROJE: AndoSign - Multimodal Sign Language AI Ecosystem
ROLÜ  : Ayrıştırılmış Model Değerlendirmesi, İstatistiksel Güven Analizi ve 
        Yayın Kalitesinde Akademik Grafiklerin Üretimi (300 DPI)
TÜKETİCİ MODÜLLER:
  - Tüm 16+1 Modelin Eğitim ve Doğrulama Boru Hatları

AÇIKLAMA:
  Bu modül, Mitchell et al. "Model Cards for Model Reporting" ve IEEE standartlarında
  belirtilen "Disaggregated Evaluation" (Ayrıştırılmış Değerlendirme) ilkelerini uygular.
  Modeli tek bir kaba doğruluk (accuracy) ile değerlendirmek yerine:
  1. %95 İstatistiksel Güven Aralığı (Wilson / Normal Yaklaşımı) hesaplar.
  2. Olasılık Kalibrasyonu ve Brier Skoru (Güvenilirlik Eğrisi) çıkarır.
  3. Hiç görülmemiş denek (Unseen Subject / Kişi E) sıfır atış başarımını ayrıştırır.
  4. 26 sınıfın her biri için F1, Precision, Recall ve Support değerlerini hesaplar.
  5. 5 adet 300 DPI çözünürlüğünde yayın kalitesinde akademik grafik (PNG) üretir.

GİRDİLER (INPUTS):
  - y_true (np.ndarray): (N,) boyutunda gerçek tamsayı sınıf etiketleri [0, Num_Classes - 1].
  - y_pred_probs (np.ndarray): (N, Num_Classes) boyutunda Softmax olasılık matrisi (Float32).
  - unseen_mask (Optional[np.ndarray]): (N,) boyutunda boolean maske (Hiç görülmemiş denek örnekleri).
  - df_train_metrics (Optional[pd.DataFrame]): Epoch bazlı Loss, Acc, Grad Norm ve LR zaman serisi tablosu.

ÇIKTILAR (OUTPUTS):
  - evaluation_report.json: Ayrıştırılmış metrikleri içeren tam JSON raporu.
  - plots/fig1_learning_curves.png: Train/Val Kayıp ve Doğruluk yakınsama eğrileri.
  - plots/fig2_optimization_health.png: L2 Gradyan Normu ve Cosine LR zamanlayıcı grafiği.
  - plots/fig3_confusion_matrix.png: 26x26 Normalize edilmiş Hata Matrisi Isı Haritası.
  - plots/fig4_calibration_curve.png: Model Güvenilirlik Diyagramı (Reliability Diagram).
  - plots/fig5_disaggregated_f1.png: 26 Harfin ayrı ayrı F1-Skoru çubuk grafiği.
================================================================================
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

# Akademik Yayın Görselleştirme Standartları (IEEE / Nature Style)
sns.set_theme(style="whitegrid", font="sans-serif")
plt.rcParams.update({
    "font.size": 11,
    "figure.autolayout": True,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8
})


class AcademicEvaluator:
    """
    Derin öğrenme modelleri için çok boyutlu akademik değerlendirme ve
    yayın kalitesinde görselleştirme motoru.
    """

    def __init__(self, output_dir: Path, class_names: List[str]) -> None:
        """
        AcademicEvaluator sınıfını başlatır.

        Args:
            output_dir (Path): Rapor ve grafiklerin kaydedileceği deney ana dizini (artifacts/...).
            class_names (List[str]): Sınıf isimlerinin listesi (Örn: ['A', 'B', ..., 'Z']).
        """
        self.out_dir: Path = Path(output_dir)
        self.plots_dir: Path = self.out_dir / "plots"
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        self.classes: List[str] = class_names
        self.num_classes: int = len(class_names)

    def evaluate_and_plot(
        self,
        y_true: np.ndarray,
        y_pred_probs: np.ndarray,
        unseen_mask: Optional[np.ndarray] = None,
        df_train_metrics: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Model tahminlerini kapsamlı istatistiksel testlerden geçirir,
        tüm metrikleri JSON olarak kaydeder ve 5 adet akademik grafik üretir.

        Args:
            y_true (np.ndarray): (N,) Boyutunda gerçek sınıf indeksleri.
            y_pred_probs (np.ndarray): (N, Num_Classes) Boyutunda Softmax çıkış olasılıkları.
            unseen_mask (Optional[np.ndarray]): (N,) Boyutunda Kişi E (Unseen Subject) filtre maskesi.
            df_train_metrics (Optional[pd.DataFrame]): Epoch bazlı eğitim metrikleri tablosu.

        Returns:
            Dict[str, Any]: Tüm doğruluk, güven aralıkları ve sınıf bazlı F1 metriklerini içeren sözlük.
        """
        # Argmax ile en yüksek olasılıklı sınıfın seçilmesi
        y_preds: np.ndarray = np.argmax(y_pred_probs, axis=1)
        n_samples: int = len(y_true)

        # ======================================================================
        # 1. TEMEL PERFORMANS METRİKLERİ VE GÜVEN ARALIĞI (%95 CI)
        # ======================================================================
        overall_acc: float = float(accuracy_score(y_true, y_preds))
        prec, rec, f1, support = precision_recall_fscore_support(
            y_true, y_preds, average=None, zero_division=0
        )
        macro_f1: float = float(np.mean(f1))
        weighted_f1: float = float(np.average(f1, weights=support))

        # Wilson / Normal Yaklaşımı ile %95 Güven Aralığı Formülü:
        # CI = p̂ ± z * sqrt((p̂ * (1 - p̂)) / n), (z = 1.96)
        z_score: float = 1.96
        ci_margin: float = z_score * np.sqrt((overall_acc * (1.0 - overall_acc)) / n_samples)
        ci_95: Tuple[float, float] = (
            round(float((overall_acc - ci_margin) * 100), 2),
            round(float((overall_acc + ci_margin) * 100), 2)
        )

        # ======================================================================
        # 2. OLASILIK KALİBRASYONU VE ÇOK SINIFLI BRIER SKORU
        # ======================================================================
        # Brier Skoru Formülü: BS = (1 / N) * Σ_i Σ_c (p_ic - y_ic)^2
        # (0.00 = Kusursuz Kalibrasyon, Değer büyüdükçe aşırı özgüvenli/hatalı tahmin artar)
        y_true_onehot: np.ndarray = np.zeros_like(y_pred_probs)
        y_true_onehot[np.arange(n_samples), y_true] = 1.0
        brier_score: float = float(np.mean(np.sum((y_pred_probs - y_true_onehot) ** 2, axis=1)))

        # ======================================================================
        # 3. HİÇ GÖRÜLMEMİŞ DENEK (UNSEEN SUBJECT / KİŞİ E) DEĞERLENDİRMESİ
        # ======================================================================
        unseen_acc: Optional[float] = None
        if unseen_mask is not None and np.any(unseen_mask):
            unseen_acc = float(accuracy_score(y_true[unseen_mask], y_preds[unseen_mask]))

        # ======================================================================
        # 4. AKADEMİK GRAFİKLERİN ÇİZİMİ (300 DPI YAYIN KALİTESİ)
        # ======================================================================
        
        # ----------------------------------------------------------------------
        # GRAFİK 1: Öğrenme Eğrileri (Learning Curves - Loss & Accuracy)
        # ----------------------------------------------------------------------
        if df_train_metrics is not None and not df_train_metrics.empty:
            fig, ax = plt.subplots(1, 2, figsize=(14, 5))
            
            # Loss Eğrisi
            ax[0].plot(df_train_metrics["epoch"], df_train_metrics["train_loss"], label="Train Loss", color="#1f77b4", lw=2)
            ax[0].plot(df_train_metrics["epoch"], df_train_metrics["val_loss"], label="Val Loss", color="#d62728", lw=2, ls="--")
            ax[0].set_title("Eğitim ve Doğrulama Kayıp Eğrisi (Loss)", weight="bold")
            ax[0].set_xlabel("Epoch")
            ax[0].set_ylabel("Cross-Entropy Loss")
            ax[0].legend(frameon=True)

            # Accuracy Eğrisi
            ax[1].plot(df_train_metrics["epoch"], df_train_metrics["train_acc"], label="Train Acc", color="#1f77b4", lw=2)
            ax[1].plot(df_train_metrics["epoch"], df_train_metrics["val_acc"], label="Val Acc", color="#2ca02c", lw=2, ls="--")
            ax[1].set_title("Eğitim ve Doğrulama Başarım Eğrisi (Accuracy)", weight="bold")
            ax[1].set_xlabel("Epoch")
            ax[1].set_ylabel("Doğruluk (%)")
            ax[1].legend(frameon=True)

            plt.savefig(self.plots_dir / "fig1_learning_curves.png", dpi=300)
            plt.close()

            # ------------------------------------------------------------------
            # GRAFİK 2: Optimizasyon Sağlığı (L2 Gradient Norm & Learning Rate)
            # ------------------------------------------------------------------
            fig, ax1 = plt.subplots(figsize=(10, 4.5))
            ax2 = ax1.twinx()
            ax1.plot(df_train_metrics["epoch"], df_train_metrics["grad_norm"], color="#9467bd", lw=2, label="Grad Norm (L2)")
            ax2.plot(df_train_metrics["epoch"], df_train_metrics["learning_rate"], color="#ff7f0e", lw=2, ls=":", label="Cosine LR")
            ax1.set_xlabel("Epoch")
            ax1.set_ylabel("L2 Gradyan Normu", color="#9467bd", weight="bold")
            ax2.set_ylabel("Öğrenme Oranı (Learning Rate)", color="#ff7f0e", weight="bold")
            plt.title("Optimizasyon Stabilitesi: Gradyan Normu ve LR Zamanlayıcı", weight="bold")
            plt.savefig(self.plots_dir / "fig2_optimization_health.png", dpi=300)
            plt.close()

        # ----------------------------------------------------------------------
        # GRAFİK 3: Normalize Edilmiş Hata Matrisi (Confusion Matrix Heatmap)
        # ----------------------------------------------------------------------
        cm: np.ndarray = confusion_matrix(y_true, y_preds, normalize="true")
        plt.figure(figsize=(12, 10))
        sns.heatmap(
            cm, annot=True, fmt=".2f", cmap="Blues",
            xticklabels=self.classes, yticklabels=self.classes, cbar=False
        )
        plt.title(f"Normalize Hata Matrisi (Confusion Matrix - {self.num_classes} Sınıf)", weight="bold", fontsize=14)
        plt.xlabel("Tahmin Edilen Sınıf (Predicted Class)")
        plt.ylabel("Gerçek Sınıf (Ground Truth)")
        plt.savefig(self.plots_dir / "fig3_confusion_matrix.png", dpi=300)
        plt.close()

        # ----------------------------------------------------------------------
        # GRAFİK 4: Olasılık Kalibrasyon Eğrisi (Reliability Diagram)
        # ----------------------------------------------------------------------
        plt.figure(figsize=(8, 6))
        confidences: np.ndarray = np.max(y_pred_probs, axis=1)
        accuracies: np.ndarray = (y_preds == y_true)
        prob_true, prob_pred = calibration_curve(accuracies, confidences, n_bins=10, strategy="uniform")
        
        plt.plot(prob_pred, prob_true, marker="o", lw=2, label="Model Kalibrasyonu", color="#2ca02c")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Kusursuz Kalibrasyon (Referans)")
        plt.title(f"Güvenilirlik Diyagramı (Brier Skoru: {brier_score:.4f})", weight="bold")
        plt.xlabel("Ortalama Tahmin Güveni (Mean Predicted Confidence)")
        plt.ylabel("Gözlemlenen Ampirik Doğruluk (Empirical Accuracy)")
        plt.legend(frameon=True)
        plt.savefig(self.plots_dir / "fig4_calibration_curve.png", dpi=300)
        plt.close()

        # ----------------------------------------------------------------------
        # GRAFİK 5: Ayrıştırılmış Sınıf Bazlı F1-Skoru Dağılımı (Disaggregated F1)
        # ----------------------------------------------------------------------
        plt.figure(figsize=(14, 5))
        df_f1 = pd.DataFrame({
            "Class": self.classes,
            "F1": f1,
            "Support": support
        }).sort_values(by="F1", ascending=False)
        
        sns.barplot(data=df_f1, x="Class", y="F1", palette="mako")
        plt.axhline(macro_f1, color="red", linestyle="--", label=f"Macro Ortalama F1: {macro_f1:.3f}")
        plt.title("Ayrıştırılmış Değerlendirme: Sınıf Başına F1-Skoru Dağılımı", weight="bold")
        plt.xlabel("Harf Sınıfı")
        plt.ylabel("F1 Skoru")
        plt.ylim(0.7, 1.02)
        plt.legend(frameon=True)
        plt.savefig(self.plots_dir / "fig5_disaggregated_f1.png", dpi=300)
        plt.close()

        # ======================================================================
        # 5. AYRIŞTIRILMIŞ METRİK RAPORUNUN JSON OLARAK SERİLEŞTİRİLMESİ
        # ======================================================================
        report_data: Dict[str, Any] = {
            "overall_accuracy": round(overall_acc, 4),
            "confidence_interval_95": ci_95,
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "brier_score": round(brier_score, 4),
            "unseen_subject_accuracy": round(unseen_acc, 4) if unseen_acc is not None else "N/A",
            "per_class_metrics": {
                c: {
                    "precision": round(float(p), 4),
                    "recall": round(float(r), 4),
                    "f1": round(float(f), 4),
                    "support": int(s)
                }
                for c, p, r, f, s in zip(self.classes, prec, rec, f1, support)
            }
        }

        report_json_path: Path = self.out_dir / "evaluation_report.json"
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=4)

        return report_data