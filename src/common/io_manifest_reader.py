"""
================================================================================
DOSYA: src/common/io_manifest_reader.py
PROJE: AndoSign - Multimodal Sign Language AI Ecosystem
ROLÜ  : Çoklu Veri Seti Entegrasyonu, Kriptografik Kopya Eleme (Deduplication),
        Bulanıklık ve Biyometrik El QA Filtreleme, Hibrit Stratifiye Bölümleme 
        ve Apache Parquet Serileştirmesi
TÜKETİCİ MODÜLLER:
  - src/models/m01_asl_letters/train.py (Model M-01 / Börü)
  - src/tools/generate_dataset_qa_report.py (Veri Kürasyonu Analizcisi)
  - Tüm ASL/TİD Harf ve Rakam Modülleri

AÇIKLAMA:
  Bu modül, AndoSign veri ambarının (data lake) omurgasını oluşturur. Heterojen 
  ve ham işaret dili veri setlerini (ASL Alphabet, dataset5) tarar ve şu 
  akademik kalite güvencesi (QA) aşamalarını uygular:
  1. Kriptografik Kopya Eleme (SHA-256): Aynı görselin kopyalarını O(1) aramayla eler (Veri Sızıntısını Önler).
  2. Keskinlik / Bulanıklık Filtresi: Laplacian varyansı Var(∇²I) < 80.0 olan odak dışı kareleri eler.
  3. Biyometrik El ve Kadraj Doğrulaması: MediaPipe ile el varlığını ve 21 eklemin [0.02, 0.98]
     kadraj sınırları içinde kaldığını doğrular (Parmak kesilmelerini eler).
  4. Hibrit Stratifiye Bölümleme: dataset5 Kişi E'yi hiç görülmemiş test kümesi (Unseen Subject) yapar;
     Kişi E'de bulunmayan sınıflar için ise diğer kaynaklardan %15 stratified pay aktararak 
     tüm 26 sınıfta dengeli bir Train (%72.2) / Val (%12.8) / Test (%15.0) dağılımı üretir.

GİRDİLER (INPUTS):
  - data/raw/asl_letters/ altındaki ham görseller (.jpg, .png, .bmp).
  - configs/preprocessing_rules.yaml (Filtreleme eşikleri ve oranları).

ÇIKTILAR (OUTPUTS):
  - data/manifests/m01_asl_letters_clean.parquet: Modele girecek temiz veri tablosu.
  - data/manifests/asl_letters_audit_full.parquet: Elenen/kabul edilen tüm örneklerin denetim kütüğü.
  - logs/dataset_curation_audit.log: Kürasyon işlem günlüğü.
================================================================================
"""

import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from tqdm import tqdm
import yaml

# MediaPipe Hands Çözümünün İçe Aktarılması
mp_hands = mp.solutions.hands

# Monorepo Kök Dizinini (AndoSign/) Çözümleme
ROOT_DIR: Path = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Özel Denetim Loglayıcısının Yapılandırılması
LOG_DIR: Path = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_DIR / "dataset_curation_audit.log"),
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger: logging.Logger = logging.getLogger("ManifestManager")


class ManifestManager:
    """
    İşaret dili ham verilerini tarayan, akademik filtreleri uygulayan,
    bölümleyen ve Parquet manifestoları üreten merkezi veri kürasyon motoru.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        ManifestManager sınıfını başlatır ve filtreleme parametrelerini yükler.

        Args:
            config_path (Optional[str]): preprocessing_rules.yaml dosya yolu.
        """
        if config_path is None:
            config_path = str(ROOT_DIR / "configs" / "preprocessing_rules.yaml")

        self.config_path: Path = Path(config_path)
        self.cfg: Dict[str, Any] = self._load_cfg()

        # Kalite Güvencesi Parametreleri
        self.blur_threshold: float = float(self.cfg.get("blur_threshold", 80.0))
        self.frame_margin: float = float(self.cfg.get("frame_margin", 0.02))
        self.min_detection_confidence: float = float(self.cfg.get("min_detection_confidence", 0.65))

        # MediaPipe Hands Detektörü (Statik Görüntü Modu)
        self.detector: mp.solutions.hands.Hands = mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=self.min_detection_confidence
        )
        logger.info("ManifestManager ve MediaPipe Hands detektörü başarıyla başlatıldı.")

    def _load_cfg(self) -> Dict[str, Any]:
        """Yapılandırma dosyasını yükler veya varsayılan güvenli parametreleri döner."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("asl_letters_curation", {})
        
        logger.warning(f"Yapılandırma bulunamadı: {self.config_path}. Varsayılan parametreler devrede.")
        return {
            "raw_data_dir": "data/raw/asl_letters",
            "output_clean_manifest": "data/manifests/m01_asl_letters_clean.parquet",
            "output_audit_manifest": "data/manifests/asl_letters_audit_full.parquet",
            "blur_threshold": 80.0,
            "frame_margin": 0.02,
            "min_detection_confidence": 0.65,
            "val_split_ratio": 0.15,
            "test_split_ratio": 0.15,
            "random_seed": 42
        }

    @staticmethod
    def compute_sha256(b: bytes) -> str:
        """
        Görselin ham bayt dizisi üzerinden SHA-256 özetini (hash) hesaplar.

        Args:
            b (bytes): Görsel dosyasının ikili (binary) içeriği.

        Returns:
            str: 64 karakterlik onaltılık (hexadecimal) benzersiz hash dizesi.
        """
        return hashlib.sha256(b).hexdigest()

    def check_blur(self, img_bgr: np.ndarray) -> Tuple[float, bool]:
        """
        Laplacian varyansı ile keskinlik/bulanıklık analizi yapar.
        Formül: Var(∇²I) = (1/M*N) * Σ (∇²I(x,y) - μ)²

        Args:
            img_bgr (np.ndarray): BGR formatında görsel matrisi.

        Returns:
            Tuple[float, bool]: (laplacian_varyansı, keskinlik_gecerli_mi).
        """
        gray: np.ndarray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        var: float = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_sharp: bool = bool(var >= self.blur_threshold)
        return var, is_sharp

    def check_hand_pose(self, img_bgr: np.ndarray) -> Tuple[bool, str]:
        """
        MediaPipe ile elin varlığını ve eklemlerin kadraj sınırlarını denetler.

        Args:
            img_bgr (np.ndarray): BGR formatında görsel matrisi.

        Returns:
            Tuple[bool, str]: (gecerli_mi, durum_kodu).
            Durum Kodları: 'PASSED', 'NO_HAND_DETECTED', 'HAND_OUT_OF_FRAME'.
        """
        rgb: np.ndarray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        res = self.detector.process(rgb)

        if not res.multi_hand_landmarks:
            return False, "NO_HAND_DETECTED"

        lms = res.multi_hand_landmarks[0].landmark
        xs: List[float] = [lm.x for lm in lms]
        ys: List[float] = [lm.y for lm in lms]

        # [0.02, 0.98] Güvenlik Sınırı Kontrolü
        if (min(xs) < self.frame_margin or max(xs) > (1.0 - self.frame_margin) or
            min(ys) < self.frame_margin or max(ys) > (1.0 - self.frame_margin)):
            return False, "HAND_OUT_OF_FRAME"

        return True, "PASSED"

    def build_asl_letters_manifest(self) -> pd.DataFrame:
        """
        Ham veri dizinini tarar, kopyaları/bulanıkları eler, dengeli Train/Val/Test
        bölümlerini oluşturur ve sıkıştırılmış Apache Parquet formatında serileştirir.

        Returns:
            pd.DataFrame: Eğitime hazır, doğrulanmış temiz veri tablosu.
        """
        raw_root: Path = ROOT_DIR / self.cfg.get("raw_data_dir", "data/raw/asl_letters")
        clean_out: Path = ROOT_DIR / self.cfg.get("output_clean_manifest", "data/manifests/m01_asl_letters_clean.parquet")
        audit_out: Path = ROOT_DIR / self.cfg.get("output_audit_manifest", "data/manifests/asl_letters_audit_full.parquet")
        clean_out.parent.mkdir(parents=True, exist_ok=True)

        if not raw_root.exists():
            error_msg: str = f"Ham veri dizini bulunamadı: {raw_root}"
            logger.error(error_msg)
            print(f"❌ HATA: {error_msg}")
            return pd.DataFrame()

        valid_exts: Set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".JPG", ".PNG"}
        all_paths: List[Path] = [p for p in raw_root.rglob("*") if p.suffix in valid_exts and "zip" not in p.parts]

        print(f"\n================================================================================")
        print(f"🚀 ANDOSIGN VERİ KÜRASYONU VE KALİTE GÜVENCESİ BAŞLATILDI")
        print(f"📂 Taranacak Dizin : {raw_root}")
        print(f"📊 Toplam Ham Dosya: {len(all_paths):,} adet görsel")
        print(f"================================================================================\n")

        seen_hashes: Set[str] = set()
        audit_records: List[Dict[str, Any]] = []

        # ----------------------------------------------------------------------
        # 1. HAM GÖRSELLERİ TARAMA VE FİLTRELEME DÖNGÜSÜ
        # ----------------------------------------------------------------------
        for p in tqdm(all_paths, desc="🔍 Kalite & İskelet Doğrulaması"):
            str_path: str = str(p.resolve())
            parts: Tuple[str, ...] = p.parts

            # A. Kriptografik Kopya Eleme (SHA-256 Deduplication)
            try:
                with open(p, "rb") as f:
                    b: bytes = f.read()
                img_hash: str = self.compute_sha256(b)
                short_hash: str = img_hash[:8]
            except Exception as e:
                audit_records.append({
                    "original_path": str_path, "canonical_filename": "NONE",
                    "canonical_label": "NONE", "category": "INVALID",
                    "status": "DROPPED", "drop_reason": "READ_ERROR",
                    "source": "UNKNOWN"
                })
                continue

            if img_hash in seen_hashes:
                audit_records.append({
                    "original_path": str_path, "canonical_filename": "NONE",
                    "canonical_label": "NONE", "category": "INVALID",
                    "status": "DROPPED", "drop_reason": "EXACT_DUPLICATE",
                    "source": "UNKNOWN"
                })
                continue

            # B. Kaynak Veri Kümesi ve Kişi Ayrımı
            if "ASL Alphabet" in parts:
                source: str = "ASLAlphabet"
                subject: str = "NA"
                is_person_e: bool = False
                raw_label: str = p.parent.name if "asl_alphabet_train" in parts else p.stem.split("_")[0]
            elif "dataset5" in parts:
                source = "dataset5"
                subj: str = parts[-3].upper()
                subject = f"SUBJ_{subj}"
                is_person_e = (subj == "E")  # Kişi E test kümesi benchmarkıdır
                raw_label = p.parent.name
            else:
                source, subject, is_person_e, raw_label = "UNKNOWN", "NA", False, p.parent.name

            # C. Sınıf ve Kategori Standardizasyonu (Canonical Labeling)
            clean_lbl: str = raw_label.strip().upper()
            if clean_lbl in ["SPACE", "DEL", "DELETE", "NOTHING"]:
                canonical_label: str = "DELETE" if clean_lbl in ["DEL", "DELETE"] else clean_lbl
                category: str = "CONTROL"
            elif len(clean_lbl) == 1 and clean_lbl.isalpha():
                canonical_label = clean_lbl
                category = "LETTER"
            else:
                audit_records.append({
                    "original_path": str_path, "canonical_filename": "NONE",
                    "canonical_label": clean_lbl, "category": "INVALID",
                    "status": "DROPPED", "drop_reason": "INVALID_CLASS",
                    "source": source
                })
                continue

            # BIDS / ISO Uyumlu Standart Dosya İsmi
            canonical_fn: str = f"ASL_{category}_{canonical_label}_{source}_{subject}_{short_hash}{p.suffix.lower()}"

            # D. Görsel Çözümleme & Bulanıklık Testi
            img_bgr: Optional[np.ndarray] = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            if img_bgr is None:
                audit_records.append({
                    "original_path": str_path, "canonical_filename": canonical_fn,
                    "canonical_label": canonical_label, "category": category,
                    "status": "DROPPED", "drop_reason": "CORRUPTED_IMAGE",
                    "source": source
                })
                continue

            blur_score, is_sharp = self.check_blur(img_bgr)
            if not is_sharp:
                audit_records.append({
                    "original_path": str_path, "canonical_filename": canonical_fn,
                    "canonical_label": canonical_label, "category": category,
                    "status": "DROPPED", "drop_reason": "BLURRY",
                    "blur_score": blur_score, "source": source
                })
                continue

            # E. Biyometrik El ve Kadraj Testi (NOTHING Hariç)
            if canonical_label != "NOTHING":
                is_hand_ok, hand_reason = self.check_hand_pose(img_bgr)
                if not is_hand_ok:
                    audit_records.append({
                        "original_path": str_path, "canonical_filename": canonical_fn,
                        "canonical_label": canonical_label, "category": category,
                        "status": "DROPPED", "drop_reason": hand_reason,
                        "blur_score": blur_score, "source": source
                    })
                    continue

            # Tüm testleri geçen kabul edilmiş örnek
            seen_hashes.add(img_hash)
            audit_records.append({
                "original_path": str_path,
                "canonical_filename": canonical_fn,
                "canonical_label": canonical_label,
                "category": category,
                "is_core_alphabet": bool(category == "LETTER"),
                "source": source,
                "subject_id": subject,
                "is_person_e": is_person_e,
                "sha256": img_hash,
                "blur_score": round(blur_score, 2),
                "status": "ACCEPTED",
                "drop_reason": "NONE"
            })

        df_all: pd.DataFrame = pd.DataFrame(audit_records)
        df_clean: pd.DataFrame = df_all[df_all["status"] == "ACCEPTED"].copy()

        # ----------------------------------------------------------------------
        # 2. HİBRİT STRATİFİYE BÖLÜMLEME (SUBJECT-AWARE HYBRID SPLITTER)
        # ----------------------------------------------------------------------
        print("\n⚖️ Dengeli Train/Val/Test bölümleme hesaplanıyor...")
        df_clean["split"] = "train"
        seed: int = self.cfg.get("random_seed", 42)

        # Adım 1: dataset5 Kişi E'yi test kümesi (Unseen Subject) olarak ayır
        df_clean.loc[df_clean["is_person_e"] == True, "split"] = "test"

        # Adım 2: Kişi E'de bulunmayan sınıflar için test kümesini dengele (%15 hedef)
        for label, group in df_clean.groupby("canonical_label"):
            total_c: int = len(group)
            target_test: int = int(total_c * 0.15)
            curr_test: int = int((group["split"] == "test").sum())
            
            if curr_test < target_test:
                needed: int = target_test - curr_test
                avail = group[group["split"] == "train"].index
                if len(avail) > 0:
                    sample_idx = group.loc[avail].sample(n=min(needed, len(avail)), random_state=seed).index
                    df_clean.loc[sample_idx, "split"] = "test"

        # Adım 3: Kalan eğitim havuzundan %15 stratified validation ayır
        train_pool = df_clean[df_clean["split"] == "train"]
        val_idx = train_pool.groupby("canonical_label").sample(frac=0.15, random_state=seed).index
        df_clean.loc[val_idx, "split"] = "val"

        # ----------------------------------------------------------------------
        # 3. APACHE PARQUET FORMATINDA SIKIŞTIRARAK KAYDETME
        # ----------------------------------------------------------------------
        df_clean.to_parquet(clean_out, index=False, engine="pyarrow", compression="zstd")
        df_all.to_parquet(audit_out, index=False, engine="pyarrow")

        print(f"\n✅ Temiz Parquet manifestosu oluşturuldu: {clean_out} ({len(df_clean):,} örnek)")
        logger.info(f"Kürasyon tamamlandı. Temiz örnek: {len(df_clean)}, Elenen örnek: {len(df_all) - len(df_clean)}")
        return df_clean

    @staticmethod
    def load_manifest(
        manifest_path: str,
        core_letters_only: bool = True,
        split: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Eğitim modüllerinin temiz Parquet manifestosunu okuması için hızlı yükleyici.

        Args:
            manifest_path (str): Okunacak .parquet dosyasının yolu.
            core_letters_only (bool): True ise sadece A-Z harflerini filtreler.
            split (Optional[str]): 'train', 'val' veya 'test' bölüm filtresi.

        Returns:
            pd.DataFrame: Filtrelenmiş veri tablosu.
        """
        df: pd.DataFrame = pd.read_parquet(manifest_path)
        if core_letters_only and "is_core_alphabet" in df.columns:
            df = df[df["is_core_alphabet"] == True]
        if split and "split" in df.columns:
            df = df[df["split"] == split]
        return df


# ==============================================================================
# DOĞRUDAN ÇALIŞTIRMA GİRİŞ NOKTASI (STANDALONE CLI)
# ==============================================================================
if __name__ == "__main__":
    manager = ManifestManager()
    manager.build_asl_letters_manifest()