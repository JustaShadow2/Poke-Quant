"""CNN model for card grading: MobileNetV2 backbone with multi-head regression.

Predicts four PSA-style subscores (centering, corners, edges, surface) from a
224x224 card photo. The final predicted_grade is a learned weighted combination
of the subscores, matching the contract in vision.py.

Architecture:
    MobileNetV2 (ImageNet-pretrained features) -> shared bottleneck (256) ->
    4 independent regression heads (each outputs a single float in [6, 10]).

The model file is stored at: {artifact_dir}/vision/grade_model.pt
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from torchvision import models, transforms


# Standard ImageNet normalization used with MobileNetV2 pretrained weights.
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
INPUT_SIZE = 224

# The four subscores the model predicts (order matters for output indexing).
SUBGRADE_NAMES = ("centering", "corners", "edges", "surface")
NUM_HEADS = len(SUBGRADE_NAMES)

# Score range the model outputs (clamped to PSA-relevant range).
SCORE_MIN = 6.0
SCORE_MAX = 10.0


def get_inference_transform() -> transforms.Compose:
    """Transform for inference: resize, center-crop, normalize."""
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(INPUT_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_training_transform() -> transforms.Compose:
    """Transform for training: augmented resize, flip, color jitter, normalize."""
    return transforms.Compose([
        transforms.RandomResizedCrop(INPUT_SIZE, scale=(0.85, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1, hue=0.02),
        transforms.RandomRotation(degrees=3),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


class GradeHead(nn.Module):
    """Single regression head: shared features -> 1 subscore in [SCORE_MIN, SCORE_MAX]."""

    def __init__(self, in_features: int, hidden: int = 128) -> None:
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(in_features, hidden),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raw = self.fc(x).squeeze(-1)
        # Sigmoid maps to [0,1], then scale to [SCORE_MIN, SCORE_MAX].
        return SCORE_MIN + (SCORE_MAX - SCORE_MIN) * torch.sigmoid(raw)


class CardGradeNet(nn.Module):
    """MobileNetV2 backbone with 4 independent regression heads for PSA subscores.

    Also learns a small weighting layer that combines subscores into a single
    predicted_grade (mimicking the PSA final-grade formula).
    """

    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        # Use MobileNetV2 features (lightweight, fast inference on CPU).
        backbone = models.mobilenet_v2(
            weights=models.MobileNet_V2_Weights.DEFAULT if pretrained else None
        )
        # Remove the classifier head; keep the feature extractor.
        self.features = backbone.features
        self.pool = nn.AdaptiveAvgPool2d(1)

        # MobileNetV2 last channel count is 1280.
        backbone_out = 1280
        bottleneck = 256

        self.bottleneck = nn.Sequential(
            nn.Linear(backbone_out, bottleneck),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
        )

        # Independent heads for each subscore.
        self.heads = nn.ModuleDict({
            name: GradeHead(bottleneck) for name in SUBGRADE_NAMES
        })

        # Learnable weights for combining subscores into predicted_grade.
        # Initialized to approximate PSA weighting: centering=0.22, corners=0.26,
        # edges=0.20, surface=0.32.
        self.grade_weights = nn.Parameter(
            torch.tensor([0.22, 0.26, 0.20, 0.32], dtype=torch.float32)
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """Forward pass.

        Returns:
            Dict with keys 'centering', 'corners', 'edges', 'surface' (each shape [B]),
            and 'predicted_grade' (shape [B]).
        """
        feat = self.features(x)
        feat = self.pool(feat).flatten(1)  # [B, 1280]
        feat = self.bottleneck(feat)  # [B, 256]

        subscores: dict[str, torch.Tensor] = {}
        score_stack = []
        for i, name in enumerate(SUBGRADE_NAMES):
            s = self.heads[name](feat)  # [B]
            subscores[name] = s
            score_stack.append(s)

        # Weighted combination (softmax ensures weights are positive and sum to 1).
        weights = torch.softmax(self.grade_weights, dim=0)
        stacked = torch.stack(score_stack, dim=-1)  # [B, 4]
        predicted = (stacked * weights.unsqueeze(0)).sum(dim=-1)  # [B]
        # Clamp to valid range.
        predicted = predicted.clamp(SCORE_MIN, SCORE_MAX)
        subscores["predicted_grade"] = predicted
        return subscores


def model_path(artifact_dir: Path) -> Path:
    """Standard path for the trained grade model checkpoint."""
    return artifact_dir / "vision" / "grade_model.pt"


def load_model(artifact_dir: Path, device: Optional[torch.device] = None) -> Optional[CardGradeNet]:
    """Load a trained CardGradeNet from disk, or return None if not found.

    Args:
        artifact_dir: The root artifacts directory (e.g., ./data/artifacts).
        device: Device to load the model onto (defaults to CPU).

    Returns:
        The loaded model in eval mode, or None if the checkpoint doesn't exist.
    """
    path = model_path(artifact_dir)
    if not path.exists():
        return None
    if device is None:
        device = torch.device("cpu")
    net = CardGradeNet(pretrained=False)
    state = torch.load(path, map_location=device, weights_only=True)
    net.load_state_dict(state)
    net.to(device)
    net.eval()
    return net
