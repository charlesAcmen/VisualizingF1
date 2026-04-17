"""
Data models for telemetry data structures.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Any


@dataclass
class CornerInfo:
    """
    Corner information model.
    """
    distance: float
    number: str
    letter: str


@dataclass
class TelemetryMeta:
    """
    Metadata for telemetry data.
    """
    season: int
    event: str
    session: str
    driver: str
    lap_number: Optional[int]
    lap_time: Optional[str]


@dataclass
class TelemetryData:
    """
    Complete telemetry data model.
    """
    meta: TelemetryMeta
    channels: List[str]
    channel_units: Dict[str, str]
    data: Dict[str, List[float]]
    corners: List[CornerInfo]


@dataclass
class SpeedDiffMeta:
    """
    Metadata for speed difference comparison.
    """
    season: int
    event: str
    session: str
    reference_driver: str
    drivers: List[str]
    lap_selectors: Dict[str, str]
    sample_frequency: str
    k_neighbors: int
    max_distance_threshold: float


@dataclass
class MatchStatistics:
    """
    Statistics for KD-tree matching.
    """
    total_points: int
    valid_matches: int
    match_rate: float
    mean_speed_diff: Optional[float]
    std_speed_diff: Optional[float]
    max_speed_diff: Optional[float]


@dataclass
class ComparisonResult:
    """
    Result of comparing two drivers.
    """
    speed_differences: List[float]
    reference_speeds: List[float]
    comparison_speeds_estimated: List[float]
    distance_coordinates: List[float]
    match_statistics: MatchStatistics


@dataclass
class SpeedDiffData:
    """
    Complete speed difference comparison data.
    """
    meta: SpeedDiffMeta
    comparisons: Dict[str, ComparisonResult]
    reference_data: Dict[str, List[float]]
