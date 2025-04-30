from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

# use high-performance C loader when available
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # pragma: no cover – PyPy / pure-Python envs
    from yaml import SafeLoader  # type: ignore


@dataclass(frozen=True, slots=True)
class IngestorConfig:
    ip: str
    listen_port: int


@dataclass(frozen=True, slots=True)
class JetsonConfig:
    ip: str
    ingest_comm_port: int
    bmi_comm_port: int


@dataclass(frozen=True, slots=True)
class BMIConfig:
    ip: str
    comm_port: int
    listen_port: int


@dataclass(frozen=True, slots=True)
class BufferConfig:
    buffer_length: int
    framerate: int


@dataclass(frozen=True, slots=True)
class AudioConfig:
    channels: int
    format: str
    rate: int


@dataclass(frozen=True, slots=True)
class SpeakerConfig:
    channels: int
    block_size: int
    amplitude: float


@dataclass(frozen=True, slots=True)
class SensorConfig:
    i2c_addr: tuple[int, int]


@dataclass(frozen=True, slots=True)
class CameraConfig:
    ident: tuple[int, int]


@dataclass(frozen=True, slots=True)
class DataPathsConfig:
    sensor: Path
    camera: Path
    audio: Path
    logs: Path


class RatballConfig:
    """
    strongly-typed load/read handler class for settings.yaml

    Parameters
    ----------
    config_path :
        Optional override for the YAML file location.  Defaults to
        ``<package_root>/../settings.yaml`` – i.e. one level above the module
        directory so that user-authored config sits outside the code tree.
    """

    def __init__(self, config_path: str | os.PathLike | None = None) -> None:
        self._config_path = (
            Path(config_path).expanduser()
            if config_path is not None
            else Path(__file__).resolve().parent.parent / "settings.yaml"
        )

        raw_cfg = self._read_settings_yaml()

        self.ingestor: IngestorConfig = IngestorConfig(**raw_cfg["ingestor"])
        self.jetson: JetsonConfig = JetsonConfig(**raw_cfg["jetson"])
        self.bmi: BMIConfig = BMIConfig(**raw_cfg["bmi"])
        self.buffer: BufferConfig = BufferConfig(**raw_cfg["buffer"])
        self.audio: AudioConfig = AudioConfig(**raw_cfg["audio"])
        self.speaker: SpeakerConfig = SpeakerConfig(**raw_cfg["speaker"])
        self.sensor: SensorConfig = SensorConfig(tuple(raw_cfg["sensor"]["i2c_addr"]))
        self.camera: CameraConfig = CameraConfig(tuple(raw_cfg["camera"]["ident"]))
        # cast data-path strings to Path for safer downstream use
        self.data_paths: DataPathsConfig = DataPathsConfig(
            **{k: Path(v) for k, v in raw_cfg["data_paths"].items()}
        )

        # retain an immutable deep copy in case callers need the raw mapping
        self._raw_cfg: Dict[str, Any] = copy.deepcopy(raw_cfg)

    def as_dict(self) -> Dict[str, Any]:
        """Return an immutable deep copy of the entire configuration."""
        return copy.deepcopy(self._raw_cfg)

    def _read_settings_yaml(self) -> Dict[str, Any]:
        """Parse the YAML file and perform basic structural validation."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Settings file not found: {self._config_path!s}")

        with self._config_path.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh, Loader=SafeLoader)

        if not isinstance(data, dict):
            raise ValueError(
                f"Settings file {self._config_path!s} must contain a "
                f"top-level mapping, got {type(data).__name__}"
            )

        # assert required top-level keys exist
        required_keys = {
            "ingestor",
            "jetson",
            "bmi",
            "buffer",
            "audio",
            "speaker",
            "sensor",
            "camera",
            "data_paths",
        }
        missing = required_keys.difference(data)
        if missing:
            raise KeyError(
                f"Missing top-level sections in settings.yaml: {', '.join(missing)}"
            )

        return data
