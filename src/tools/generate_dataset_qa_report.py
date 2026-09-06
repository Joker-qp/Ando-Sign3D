"""
MODULE: generate_dataset_qa_report.py
PURPOSE: Generate dataset curation analysis, survival charts, and Markdown dataset cards.
"""
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

PLOTS_DIR = ROOT_DIR / "docs" / "academic_research" / "figures_and_plots"
DOCS_DIR = ROOT_DIR / "docs" / "dataset_cards"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def generate_report():
    audit_p = ROOT_DIR / "data" / "manifests" / "asl_letters_audit_full.parquet"
    clean_p = ROOT_DIR / "data" / "manifests" / "m01_asl_letters_clean.parquet"
    if not audit_p.exists() or not clean_p.exists():
        print(f"❌ HATA: Manifest bulunamadı! ({audit_p})")
        return

    df_all = pd.read_parquet(audit_p)
    df_clean = pd.read_parquet(clean_p)
    df_all["drop_reason_clean"] = df_all["drop_reason"].astype(str).apply(lambda x: x.split("(")[0].strip())

    # FIG 1: Elenme Nedenleri
    plt.figure(figsize=(10, 5))
    df_drop = df_all[df_all["status"] == "DROPPED"]
    counts = df_drop["drop_reason_clean"].value_counts()
    sns.barplot(x=counts.values, y=counts.index, palette="mako")
    plt.title("ASL Veri Seti: Elenme Nedenleri Dağılımı", weight="bold")
    plt.savefig(PLOTS_DIR / "fig1_asl_curation_drop_reasons.png", dpi=300); plt.close()

    # FIG 2: Sınıf Dağılımı
    plt.figure(figsize=(15, 6))
    pd.crosstab(df_clean["canonical_label"], df_clean["split"])[["train", "val", "test"]].plot(
        kind="bar", stacked=True, color=["#2b5c8f", "#d95f02", "#7570b3"], figsize=(15, 6)
    )
    plt.title("ASL Harf Veri Seti: Sınıf Başına Dağılım", weight="bold")
    plt.savefig(PLOTS_DIR / "fig2_asl_clean_class_distribution.png", dpi=300); plt.close()

    print(f"✅ Grafikler ve analiz oluşturuldu: {PLOTS_DIR}")


if __name__ == "__main__":
    generate_report()