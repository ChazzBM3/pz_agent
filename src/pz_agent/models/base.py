from __future__ import annotations

from typing import Any


class BaseSurrogateModel:
    name = "base"

    def predict(self, molecule: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
