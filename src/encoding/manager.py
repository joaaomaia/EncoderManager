from __future__ import annotations

from typing import Dict, Type, Iterable, Protocol, Optional, Any

import numpy as np

import pandas as pd
import joblib

VERSION_HEADER = 1

from .memory_manager import MemoryManager
from .encoders import WOEGuard, TargetEncoder, LeaveOneOutEncoder, OneHotEncoder
from .missing import MissingHandler

class Encoder(Protocol):
    def fit(self, X: pd.DataFrame, y: pd.Series): ...
    def transform(self, X: pd.DataFrame): ...


class EncodingManager:
    """Factory and orchestrator for categorical encoders."""

    _registry: Dict[str, Type[Encoder]] = {
        "woe": WOEGuard,
        "target": TargetEncoder,
        "leave_one_out": LeaveOneOutEncoder,
        "onehot": OneHotEncoder,
    }

    def __init__(
        self,
        encoding: str = "onehot",
        memory_manager: Optional[MemoryManager] = None,
        missing_sentinel: str | int | float | None = np.nan,
        **encoder_kwargs,
    ) -> None:
        if encoding not in self._registry:
            raise ValueError(f"Encoding '{encoding}' not registered")
        self.encoder_cls = self._registry[encoding]
        self.encoder: Encoder = self.encoder_cls(**encoder_kwargs)  # type: ignore[call-arg]
        self.memory_manager = memory_manager or MemoryManager()
        self.missing_handler = MissingHandler(sentinel=missing_sentinel)

    @classmethod
    def register(cls, name: str, encoder_cls: Type[Encoder]) -> None:
        cls._registry[name] = encoder_cls

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "EncodingManager":
        X_prep = self.missing_handler.fit_transform(X)
        with self.memory_manager.profile("fit"):
            self.encoder.fit(X_prep, y)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X_prep = self.missing_handler.transform(X)
        with self.memory_manager.profile("transform"):
            return self.encoder.transform(X_prep)

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        self.fit(X, y)
        return self.transform(X)

    # Serialization -------------------------------------------------
    def save(self, path: str) -> None:
        payload = {
            "version": VERSION_HEADER,
            "encoder": self.encoder,
            "missing_handler": self.missing_handler,
        }
        joblib.dump(payload, path)

    @classmethod
    def load(cls, path: str) -> "EncodingManager":
        payload: dict[str, Any] = joblib.load(path)
        _version = payload.get("version", 0)
        enc = payload["encoder"]
        mh = payload.get("missing_handler", MissingHandler())
        manager = cls(enc.__class__.__name__.lower())
        manager.encoder = enc
        manager.missing_handler = mh
        return manager
