"""WaveformTool executing deterministic COMTRADE parsing and signal feature extraction."""
import os
import re
from typing import Optional
from domain.models.results import ComtradeAnalysisResult
from services.comtrade.parser import ComtradeParser
from services.comtrade.analyzer import ComtradeSignalAnalyzer
from services.config import COMTRADE_DIR


class WaveformTool:
    """Specialized tool for COMTRADE oscillography signal analysis."""

    def __init__(self, comtrade_data_dir: str = str(COMTRADE_DIR)):
        self.data_dir = comtrade_data_dir

    async def execute(
        self,
        incident_id: str,
        pickup_threshold_a: float = 2500.0,
        cfg_path: Optional[str] = None,
        dat_path: Optional[str] = None,
    ) -> ComtradeAnalysisResult:
        if cfg_path is None or dat_path is None:
            if not re.fullmatch(r'[A-Z0-9][A-Z0-9\-_]*', incident_id.upper()):
                return ComtradeAnalysisResult(
                    incident_id=incident_id,
                    sample_rate_hz=0.0,
                    total_samples=0,
                    duration_ms=0.0,
                    is_truncated=True,
                    analysis_notes=[f"Invalid incident identifier '{incident_id}'."],
                )
        c_path = cfg_path or os.path.join(self.data_dir, f"{incident_id}.CFG")
        d_path = dat_path or os.path.join(self.data_dir, f"{incident_id}.DAT")

        if not os.path.exists(c_path) or not os.path.exists(d_path):
            return ComtradeAnalysisResult(
                incident_id=incident_id,
                sample_rate_hz=0.0,
                total_samples=0,
                duration_ms=0.0,
                is_truncated=True,
                analysis_notes=[f"Waveform files for {incident_id} not found in storage."],
            )

        try:
            record = ComtradeParser.parse_files(c_path, d_path)
            analysis = ComtradeSignalAnalyzer.analyze_record(
                record=record,
                incident_id=incident_id,
                pickup_threshold_a=pickup_threshold_a,
            )
            return analysis
        except Exception as e:
            return ComtradeAnalysisResult(
                incident_id=incident_id,
                sample_rate_hz=0.0,
                total_samples=0,
                duration_ms=0.0,
                is_truncated=True,
                analysis_notes=[f"COMTRADE parsing failure: {str(e)}"],
            )
