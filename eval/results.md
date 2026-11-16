# Evaluation

28 questions (25 answerable). Index: 1359 chunks from 6 files. Embeddings: `bge-m3`.

## Retrieval: does the right page appear in the top 6?

| Questions | n | vector hit@1 | vector hit@6 | vector MRR | keyword hit@1 | keyword hit@6 | keyword MRR | hybrid hit@1 | hybrid hit@6 | hybrid MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 25 | 68% | 88% | 0.78 | 72% | 72% | 0.73 | 60% | 92% | 0.72 |
| cross-language | 6 | 83% | 83% | 0.85 | 17% | 17% | 0.17 | 0% | 83% | 0.38 |
| exact-term | 5 | 60% | 100% | 0.80 | 100% | 100% | 1.00 | 100% | 100% | 1.00 |
| same-language | 14 | 64% | 86% | 0.74 | 86% | 86% | 0.87 | 71% | 93% | 0.78 |

Hybrid misses: `x-purchasing` (rank None), `en-nasa-trl6` (rank None)

### Fusion weight (hybrid uses 0.5)

| keyword weight | all hit@6 | all MRR | cross-language hit@6 | exact-term hit@6 |
|---:|---:|---:|---:|---:|
| 1.0 | 88% | 0.73 | 83% | 100% |
| 0.5 | 92% | 0.72 | 83% | 100% |
| 0.25 | 88% | 0.77 | 83% | 100% |

## Answers (`qwen2.5:7b`)

Correct means every expected fact appears in the answer, or, for unanswerable questions, that the answer says the documents do not cover it.

| Questions | n | correct | cites the right file | median seconds |
|---|---:|---:|---:|---:|
| all | 28 | 82% | 96% | 0.8 |
| cross-language | 6 | 67% | 83% | 1.0 |
| exact-term | 5 | 100% | 100% | 0.7 |
| same-language | 14 | 79% | 100% | 0.8 |
| unanswerable | 3 | 100% | 100% | 0.6 |

### Wrong answers

- `x-purchasing`: The purchasing department is responsible for preparing and submitting change requests, proposing reviewers, receiving and logging requests, screening change packages, and releasing them for review. They also collect, tra
- `tr-open-qa`: Kalite Güvence biriminin açık aksiyonları şunlardır:  - EPA giriş levhalarının yenilenmesi (AKS-004) - Depo nem ölçerlerinin kalibrasyonu (AKS-005) [5, 6]
- `x-open-maintenance`: The actions still in progress are: - AKS-003: Kondansatör tedarikçisinin kırmızı kategoriye düşmesi (AKS-003) [3] - AKS-011: Hat 1 AOI makinesi yanlış ret oranının düşürülmesi (AKS-011) [4]
- `en-fda-six`: The six systems in the FDA's inspection model are: 1. Management Responsibilities 2. Resources 3. Manufacturing Operations 4. Evaluation Activities 5. Corrective and Preventive Action (CAPA) 6. Change Control [4]
- `en-fda-review`: A management review of the quality system should include assessments of the process, product, and customer needs [3, 4]. Additionally, the review should consider the appropriateness of the quality policy and objectives, 
