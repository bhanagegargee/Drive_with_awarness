from dataclasses import dataclass
from typing import Optional


@dataclass
class SeverityPrediction:
    score: float
    severity: str


class SeverityModel:
    """Rule-based model with optional Ollama-based historical enrichment."""

    def __init__(self, ollama_client: Optional[object] = None) -> None:
        self.ollama_client = ollama_client

    async def predict(self, accidents: int, deaths: int, frequency: int, zone_name: str) -> SeverityPrediction:
        if self.ollama_client:
            ollama_prediction = await self.ollama_client.predict(
                accidents=accidents,
                deaths=deaths,
                frequency=frequency,
                zone_name=zone_name,
            )
            if ollama_prediction:
                return ollama_prediction

        return self._predict_fallback(accidents, deaths, frequency)

    def _predict_fallback(self, accidents: int, deaths: int, frequency: int) -> SeverityPrediction:
        # Weighted severity score requested for the MVP fallback.
        score = (accidents * 0.5) + (deaths * 2) + (frequency * 1.5)

        if score > 70:
            severity = "HIGH"
        elif score > 40:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return SeverityPrediction(score=round(score, 2), severity=severity)
