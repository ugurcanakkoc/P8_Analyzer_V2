"""
Cluster Detection Settings

Centralized configuration for cluster-based component detection.
All parameters can be adjusted here or overridden via JSON file.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# Default settings file location
DEFAULT_SETTINGS_FILE = Path(__file__).parent.parent.parent / "cluster_settings.json"


@dataclass
class ClusterSettings:
    """
    Settings for cluster-based component detection.

    Clustering Parameters:
        vertical_weight: How much more to penalize vertical distance vs horizontal.
                        Higher values make clusters prefer horizontal alignment.
        absolute_min_gap: Always merge clusters if gap is smaller than this (PDF units).
        density_factor: Merge if gap < internal_spacing * this factor.
                       Higher values = more aggressive merging.
        max_gap: Never merge if gap exceeds this (weighted distance, PDF units).
        cross_color_penalty: Multiply gap by this for different-color merges.
                            Higher values = less likely to merge different colors.

    Label Matching Parameters:
        label_max_distance: Base max distance for label-to-cluster matching (PDF units).
        label_cluster_size_factor: Additional distance allowance per unit of cluster diagonal.
                                   Allows labels to be further from larger clusters.
        label_subsume_threshold: Forbid merges that subsume a label by more than this fraction.
                                 0.5 = don't merge if it would cover >50% of a label.
    """

    # Clustering parameters
    vertical_weight: float = 1.5
    absolute_min_gap: float = 90.0
    density_factor: float = 5.5
    max_gap: float = 270.0
    cross_color_penalty: float = 2.0

    # Label matching parameters
    label_max_distance: float = 150.0
    label_cluster_size_factor: float = 0.5
    label_subsume_threshold: float = 0.5

    # Visualization parameters
    visualization_scale: float = 2.0

    def to_dict(self) -> dict:
        """Convert settings to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClusterSettings":
        """Create settings from dictionary, ignoring unknown keys."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def save(self, path: Optional[Path] = None):
        """Save settings to JSON file."""
        path = path or DEFAULT_SETTINGS_FILE
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ClusterSettings":
        """
        Load settings from JSON file.
        Returns default settings if file doesn't exist.
        """
        path = path or DEFAULT_SETTINGS_FILE
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load cluster settings from {path}: {e}")
                return cls()
        return cls()

    def get_summary(self) -> str:
        """Get a human-readable summary of settings."""
        return f"""Cluster Detection Settings:
  Clustering:
    vertical_weight: {self.vertical_weight}
    absolute_min_gap: {self.absolute_min_gap} PDF units
    density_factor: {self.density_factor}
    max_gap: {self.max_gap} PDF units
    cross_color_penalty: {self.cross_color_penalty}

  Label Matching:
    label_max_distance: {self.label_max_distance} PDF units
    label_cluster_size_factor: {self.label_cluster_size_factor}
    label_subsume_threshold: {self.label_subsume_threshold}

  Visualization:
    scale: {self.visualization_scale}x"""


# Global default settings instance
_default_settings: Optional[ClusterSettings] = None


def get_default_settings() -> ClusterSettings:
    """Get the default cluster settings, loading from file if available."""
    global _default_settings
    if _default_settings is None:
        _default_settings = ClusterSettings.load()
    return _default_settings


def reload_settings():
    """Force reload of settings from file."""
    global _default_settings
    _default_settings = ClusterSettings.load()
    return _default_settings
