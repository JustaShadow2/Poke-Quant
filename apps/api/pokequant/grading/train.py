"""Training pipeline for the card-grading CNN.

Strategy: generate a synthetic labeled dataset by rendering card-like images with
controlled defects (off-center borders, corner whitening, edge wear, surface noise)
and labeling them with known ground-truth subscores. This bootstraps the model
without requiring real PSA-labeled card photos.

Once real labeled data is available (e.g., cards with known PSA subgrades), the
same pipeline can fine-tune the pretrained model on real images via the
`--real-data-dir` flag.

Usage (via CLI):
    pokequant vision-train --epochs 12 --samples 4000
"""

from __future__ import annotations

import logging
import random
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw, ImageFilter
from torch.utils.data import DataLoader, Dataset

from pokequant.grading.model import (
    SCORE_MAX,
    SCORE_MIN,
    SUBGRADE_NAMES,
    CardGradeNet,
    get_training_transform,
    model_path,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synthetic dataset generation
# ---------------------------------------------------------------------------


def _random_color() -> tuple[int, int, int]:
    """Random saturated color for card borders/artwork."""
    return (random.randint(20, 240), random.randint(20, 240), random.randint(20, 240))


def _generate_synthetic_card(
    width: int = 400,
    height: int = 560,
) -> tuple[Image.Image, dict[str, float]]:
    """Render a synthetic card image with controlled defects and return ground-truth scores.

    Returns:
        (PIL Image, dict of subscores {centering, corners, edges, surface})
    """
    # --- Centering ---
    # Perfect centering: border is uniform. We vary the offset to create off-center cards.
    # Border width as fraction of card dimension (typical Pokemon card ~4-6%).
    border_frac = random.uniform(0.04, 0.08)
    border_w = int(width * border_frac)
    border_h = int(height * border_frac)

    # Offset from center: 0 = perfect, up to 0.5 = maximally off-center.
    lr_offset = random.gauss(0, 0.08)  # left-right shift as fraction of border
    tb_offset = random.gauss(0, 0.08)

    lr_offset = max(-0.45, min(0.45, lr_offset))
    tb_offset = max(-0.45, min(0.45, tb_offset))

    # Compute actual borders.
    left_b = int(border_w * (1 + lr_offset))
    right_b = int(border_w * (1 - lr_offset))
    top_b = int(border_h * (1 + tb_offset))
    bottom_b = int(border_h * (1 - tb_offset))

    # Centering score: based on deviation from perfect 50/50.
    lr_dev = abs(lr_offset) / 2  # normalize to 0-0.225 range
    tb_dev = abs(tb_offset) / 2
    max_dev = max(lr_dev, tb_dev)
    # Map deviation to score: 0 deviation -> 10, 0.22 -> 6
    centering_score = float(np.clip(10.0 - max_dev * 18.0, SCORE_MIN, SCORE_MAX))

    # --- Create image ---
    border_color = _random_color()
    artwork_color = _random_color()
    img = Image.new("RGB", (width, height), border_color)
    draw = ImageDraw.Draw(img)

    # Draw artwork interior.
    art_x0 = max(1, left_b)
    art_y0 = max(1, top_b)
    art_x1 = min(width - 1, width - right_b)
    art_y1 = min(height - 1, height - bottom_b)
    draw.rectangle([art_x0, art_y0, art_x1, art_y1], fill=artwork_color)

    # --- Corners wear (whitening) ---
    corner_severity = random.uniform(0, 1)  # 0=pristine, 1=heavy wear
    corner_size = max(4, int(width * random.uniform(0.01, 0.04) * (1 + corner_severity * 2)))
    if corner_severity > 0.05:
        white = (255, 255, 255)
        alpha = int(180 * corner_severity)
        # Apply whitening patches to corners.
        for cx, cy in [(0, 0), (width - corner_size, 0),
                       (0, height - corner_size), (width - corner_size, height - corner_size)]:
            if random.random() < 0.3 + corner_severity * 0.7:
                overlay = Image.new("RGBA", (corner_size, corner_size), (*white, alpha))
                img.paste(
                    Image.alpha_composite(
                        img.crop((cx, cy, cx + corner_size, cy + corner_size)).convert("RGBA"),
                        overlay,
                    ).convert("RGB"),
                    (cx, cy),
                )
    corners_score = float(np.clip(10.0 - corner_severity * 4.0, SCORE_MIN, SCORE_MAX))

    # --- Edge wear ---
    edge_severity = random.uniform(0, 1)
    if edge_severity > 0.1:
        edge_width = max(2, int(3 * edge_severity))
        alpha = int(140 * edge_severity)
        white = (255, 255, 255)
        # Top and bottom edge strips.
        for y_start in [0, height - edge_width]:
            if random.random() < 0.4 + edge_severity * 0.5:
                strip = Image.new("RGBA", (width, edge_width), (*white, alpha))
                region = img.crop((0, y_start, width, y_start + edge_width)).convert("RGBA")
                blended = Image.alpha_composite(region, strip).convert("RGB")
                img.paste(blended, (0, y_start))
        # Left and right edge strips.
        for x_start in [0, width - edge_width]:
            if random.random() < 0.4 + edge_severity * 0.5:
                strip = Image.new("RGBA", (edge_width, height), (*white, alpha))
                region = img.crop((x_start, 0, x_start + edge_width, height)).convert("RGBA")
                blended = Image.alpha_composite(region, strip).convert("RGB")
                img.paste(blended, (x_start, 0))
    edges_score = float(np.clip(10.0 - edge_severity * 3.8, SCORE_MIN, SCORE_MAX))

    # --- Surface defects ---
    surface_severity = random.uniform(0, 1)
    if surface_severity > 0.1:
        # Add noise/scratches to interior.
        arr = np.array(img, dtype=np.float32)
        noise_region = arr[art_y0:art_y1, art_x0:art_x1]
        noise = np.random.normal(0, surface_severity * 25, noise_region.shape)
        noise_region += noise
        arr[art_y0:art_y1, art_x0:art_x1] = np.clip(noise_region, 0, 255)
        img = Image.fromarray(arr.astype(np.uint8))

        # Occasional scratch lines.
        if surface_severity > 0.4 and random.random() < surface_severity:
            draw = ImageDraw.Draw(img)
            for _ in range(random.randint(1, 3)):
                x1 = random.randint(art_x0, art_x1)
                y1 = random.randint(art_y0, art_y1)
                x2 = x1 + random.randint(-60, 60)
                y2 = y1 + random.randint(-60, 60)
                draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=1)
    surface_score = float(np.clip(10.0 - surface_severity * 3.5, SCORE_MIN, SCORE_MAX))

    # --- Post-processing: slight blur to simulate phone camera ---
    if random.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 1.0)))

    # Random JPEG compression artifacts.
    if random.random() < 0.4:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=random.randint(60, 90))
        buf.seek(0)
        img = Image.open(buf).convert("RGB")

    scores = {
        "centering": centering_score,
        "corners": corners_score,
        "edges": edges_score,
        "surface": surface_score,
    }
    return img, scores


class SyntheticCardDataset(Dataset):  # type: ignore[type-arg]
    """On-the-fly synthetic card dataset for training."""

    def __init__(self, num_samples: int, transform: Optional[object] = None) -> None:
        self.num_samples = num_samples
        self.transform = transform
        # Pre-generate all samples for reproducibility within an epoch.
        self._cache: list[tuple[Image.Image, dict[str, float]]] = []
        for _ in range(num_samples):
            img, scores = _generate_synthetic_card()
            self._cache.append((img, scores))

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        img, scores = self._cache[idx]
        if self.transform is not None:
            img = self.transform(img)  # type: ignore[assignment]
        # Target tensor: [centering, corners, edges, surface]
        target = torch.tensor(
            [scores[name] for name in SUBGRADE_NAMES], dtype=torch.float32
        )
        return img, target  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------


def train_model(
    artifact_dir: Path,
    *,
    num_samples: int = 4000,
    val_samples: int = 500,
    epochs: int = 12,
    batch_size: int = 32,
    lr: float = 1e-3,
    device: Optional[torch.device] = None,
) -> dict[str, float]:
    """Train the CardGradeNet on synthetic data and save the checkpoint.

    Args:
        artifact_dir: Root artifacts directory.
        num_samples: Number of synthetic training images to generate.
        val_samples: Number of synthetic validation images.
        epochs: Training epochs.
        batch_size: Batch size.
        lr: Learning rate.
        device: Training device (defaults to CUDA if available, else CPU).

    Returns:
        Dict with final training and validation loss.
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(
        "Training card grading model: %d samples, %d epochs, device=%s",
        num_samples, epochs, device,
    )

    transform = get_training_transform()
    train_ds = SyntheticCardDataset(num_samples, transform=transform)
    val_ds = SyntheticCardDataset(val_samples, transform=transform)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = CardGradeNet(pretrained=True).to(device)

    # Freeze backbone early layers for faster convergence on small data.
    for param in model.features[:14].parameters():
        param.requires_grad = False

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr,
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.SmoothL1Loss()

    best_val_loss = float("inf")
    best_state: Optional[dict[str, object]] = None

    for epoch in range(epochs):
        # --- Train ---
        model.train()
        train_loss = 0.0
        for images, targets in train_loader:
            images = images.to(device)
            targets = targets.to(device)  # [B, 4]
            optimizer.zero_grad()
            preds = model(images)
            # Compute loss on each subscore.
            pred_tensor = torch.stack(
                [preds[name] for name in SUBGRADE_NAMES], dim=-1
            )  # [B, 4]
            loss = criterion(pred_tensor, targets)
            # Also supervise predicted_grade as weighted target.
            weights = torch.softmax(model.grade_weights.detach(), dim=0)
            target_grade = (targets * weights.unsqueeze(0)).sum(dim=-1)
            grade_loss = criterion(preds["predicted_grade"], target_grade)
            total_loss = loss + 0.5 * grade_loss
            total_loss.backward()
            optimizer.step()
            train_loss += total_loss.item() * images.size(0)
        train_loss /= len(train_ds)

        # --- Validate ---
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for images, targets in val_loader:
                images = images.to(device)
                targets = targets.to(device)
                preds = model(images)
                pred_tensor = torch.stack(
                    [preds[name] for name in SUBGRADE_NAMES], dim=-1
                )
                loss = criterion(pred_tensor, targets)
                val_loss += loss.item() * images.size(0)
        val_loss /= len(val_ds)

        scheduler.step()
        logger.info(
            "Epoch %d/%d — train_loss=%.4f  val_loss=%.4f  lr=%.2e",
            epoch + 1, epochs, train_loss, val_loss, scheduler.get_last_lr()[0],
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = model.state_dict()

    # Save best checkpoint.
    save_path = model_path(artifact_dir)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if best_state is not None:
        torch.save(best_state, save_path)
    else:
        torch.save(model.state_dict(), save_path)
    logger.info("Saved grade model to %s (val_loss=%.4f)", save_path, best_val_loss)

    return {"train_loss": train_loss, "val_loss": best_val_loss}
