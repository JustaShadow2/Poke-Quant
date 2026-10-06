# Card Grading — Vision Model

The Grade tab provides a CNN-based pre-grade for Pokemon cards from a phone photo. It predicts four PSA-style subscores (centering, corners, edges, surface) and combines them into an overall predicted grade (6–10 scale).

## Architecture

- **Model:** MobileNetV2 (ImageNet-pretrained) with a shared 256-dim bottleneck and 4 independent regression heads.
- **Output:** `centering`, `corners`, `edges`, `surface` (each 6.0–10.0) plus a learned weighted `predicted_grade`.
- **Fallback:** If no trained checkpoint exists, the system transparently falls back to a heuristic (Pillow + NumPy) pipeline. The API contract is identical either way.
- **Method field:** Responses include `"method": "cnn_v1"` (trained model) or `"method": "heuristic_v0"` (fallback).

## Files

| File | Purpose |
|------|---------|
| `model.py` | `CardGradeNet` architecture, transforms, `load_model()` |
| `train.py` | Synthetic dataset generator + training loop |
| `vision.py` | Public API: `grade_image()` (CNN → heuristic fallback) |
| `roi.py` | Grading ROI calculator (consumes `predicted_grade`) |
| `service.py` | Orchestrates vision + card lookup + ROI |

## Running

### Docker (recommended — one command)

```bash
docker compose down -v          # clear volumes if re-bootstrapping
docker compose up --build       # builds, trains, serves
```

On first boot the entrypoint runs: `seed → synth → features → train → forecast → vision-train`. The vision model trains on 800 synthetic card images for 5 epochs (~2–3 min on CPU). Once complete:

- **UI:** http://localhost:3000/grade
- **API docs:** http://localhost:8000/docs
- **Vision endpoint:** `POST http://localhost:8000/api/v1/cards/vision-grade`

The healthcheck has a 10-minute start period to accommodate the bootstrap + training time on CPU.

### Local (without Docker)

Requires a running Postgres/TimescaleDB on port 5432 (e.g., `docker compose up -d db`).

```bash
make setup              # creates .venv, installs all deps including torch/torchvision
make bootstrap          # full pipeline: migrate → seed → synth → features → train → vision-train → forecast
make api                # starts FastAPI on :8000
# in a separate terminal:
make web                # starts Next.js on :3000
```

### Training the vision model independently

```bash
# Default (good for CPU, fast):
make vision-train

# Custom (more data, more epochs — better model, slower):
pokequant vision-train --epochs 12 --samples 4000 --batch-size 32

# Retrain inside a running Docker container:
docker compose exec api pokequant vision-train --epochs 12 --samples 4000
```

The trained checkpoint is saved to `data/artifacts/vision/grade_model.pt` (local) or `/data/artifacts/vision/grade_model.pt` (Docker volume). The API hot-loads it on next request after training.

### CLI options

```
pokequant vision-train [OPTIONS]

  --epochs       INT   Training epochs (default: 12)
  --samples      INT   Synthetic training images (default: 4000)
  --val-samples  INT   Validation images (default: 500)
  --batch-size   INT   Batch size (default: 32)
  --lr           FLOAT Learning rate (default: 0.001)
```

## API Endpoints

### `POST /api/v1/cards/vision-grade`

Upload a card photo, get subscores.

**Request:** Multipart form — `front` (required), `back` (optional). Max 8 MB each.

**Response:**
```json
{
  "predicted_grade": 9.12,
  "centering": {"name": "centering", "score": 9.45, "notes": "Excellent centering detected."},
  "corners": {"name": "corners", "score": 8.91, "notes": "Very good corner condition."},
  "edges": {"name": "edges", "score": 9.20, "notes": "Excellent edge condition."},
  "surface": {"name": "surface", "score": 9.03, "notes": "Very good surface condition."},
  "method": "cnn_v1",
  "disclaimer": "CNN-based pre-grade from a photo. Not a PSA grade..."
}
```

### `POST /api/v1/cards/{card_id}/grade-roi`

Upload a photo + card ID to get vision-conditioned grading ROI (should I submit to PSA?).

**Request:** Multipart form — `front`, optional `back`, `grading_fee` (default $25), `shipping` (default $15).

**Response:** Vision scores + card prices + ROI verdict (`grade` / `borderline` / `lean_raw` / `sell_raw`).

## How it works

### Training data (synthetic)

Since there's no public dataset of card photos labeled with PSA subgrades, the model bootstraps on synthetic data:

1. Renders card-like images (colored border + darker artwork interior)
2. Applies controlled defects with known severity:
   - **Centering:** shifts the artwork off-center by a measured amount
   - **Corners:** white patches of varying alpha and size
   - **Edges:** white strips along card edges
   - **Surface:** Gaussian noise, scratch lines, JPEG compression
3. Maps defect severity linearly to ground-truth subscores (6–10)
4. Augments with rotation, color jitter, random crops, blur

This produces a model that learns the visual patterns of each defect type. Once real labeled data is available (cards with known PSA subgrades), the model can be fine-tuned on real images for significantly better accuracy.

### Inference

1. Image is resized to 256px, center-cropped to 224×224, ImageNet-normalized
2. Forward pass through MobileNetV2 features → bottleneck → 4 regression heads
3. Each head outputs a score via sigmoid scaled to [6, 10]
4. Learned softmax weights combine subscores into `predicted_grade`
5. If back image is provided, it's graded independently and min(front, back) is taken per subscore

### Grade → ROI integration

The `predicted_grade` feeds into `probs_from_predicted_grade()` which maps it to a probability distribution over PSA 10/9/8-or-lower, then calculates expected value of grading vs. selling raw.

## Limitations

- **Not a real PSA grade.** The model scores photos, not cards. Lighting, glare, angle, and camera quality all affect results.
- **Trained on synthetic data.** Accuracy improves significantly with real labeled training data.
- **Cannot detect:** print lines, holo scratches invisible to cameras, factory defects, surface issues below phone-camera resolution.
- **PSA only.** BGS/CGC subgrade scales are not modeled.
- **Single card per photo.** No multi-card detection.

## Upgrading to real data

When labeled card photos become available:

1. Place images in a directory with a CSV mapping `filename → centering, corners, edges, surface` scores
2. Create a `RealCardDataset` class (same interface as `SyntheticCardDataset`)
3. Fine-tune from the synthetic checkpoint: `torch.load("grade_model.pt")` → train with lower LR (1e-4)
4. The API contract stays the same — just replace the checkpoint file
