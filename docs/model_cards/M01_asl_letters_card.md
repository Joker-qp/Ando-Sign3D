---
language:
- en
- tr
license: mit
tags:
- sign-language-recognition
- asl
- mediapipe
- ieee-compliant
- mitchell-model-card
datasets:
- ASL-Alphabet
- dataset5-fingerspelling
metrics:
- accuracy: 0.9541
- f1: 0.9507
- brier_score: 0.0732
model-index:
- name: m01_asl_letters
  results:
  - task:
      type: image-classification
      name: Sign Language Fingerspelling
    dataset:
      name: ASL-Standardized-Clean
      type: test
    metrics:
      - type: accuracy
        value: 0.9541
      - type: f1
        value: 0.9507
co2_eq_emissions:
  emissions: 0.0019166161214843
  source: CodeCarbon
  hardware: "NVIDIA GeForce RTX 3060 Laptop GPU"
---

# 📑 Model Card: m01_asl_letters | ASL-Letters-Net

## 1. Model Details & Architecture
* **Model Identifier:** `m01_asl_letters`
* **Architecture:** Residual Multi-Layer Perceptron (Res-MLP with Skip Connections & GELU)
* **Parameters:** 210,074 (820.6 KB)
* **Framework:** PyTorch 2.14.0+cu130 & MediaPipe Hands
* **Random Seed:** 42

## 2. Quantitative Performance (Disaggregated Evaluation)
* **Overall Test Accuracy (95% CI):** **%95.41** (CI: [95.07% - 95.75%])
* **Macro F1-Score:** **0.9507**
* **Expected Calibration / Brier Score:** **0.0732**
* **Unseen Subject Generalization (Subject E):** **%92.66**

## 3. Environmental Impact (Green AI)
* **Hardware:** `NVIDIA GeForce RTX 3060 Laptop GPU`
* **Estimated CO2 Emissions:** `0.001917 kg CO2eq`

## 4. Evaluation Plots
Plots are archived in `artifacts/m01_asl_letters/plots/`:
* `fig1_learning_curves.png`
* `fig2_optimization_health.png`
* `fig3_confusion_matrix.png`
* `fig4_calibration_curve.png`
* `fig5_disaggregated_f1.png`
