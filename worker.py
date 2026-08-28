# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QThread, pyqtSignal


class AnalysisWorker(QThread):
    """Runs the water-quality pipeline in a background thread so the QGIS
    UI stays responsive. Emits progress (0-100), status messages, a result
    dict on success, and an error string on failure."""

    progress = pyqtSignal(int)
    message  = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            from . import pipeline

            self.message.emit("Initialising pipeline…")
            self.progress.emit(5)

            result = pipeline.run_water_quality(
                points_list=self.params.get("points_list"),
                aoi_geojson=self.params.get("aoi_geojson"),
                date_str=self.params["date_str"],
                algorithm=self.params["algorithm"],
                max_cloud_tile=self.params["max_cloud_tile"],
                max_cloud_tolerance=self.params["max_cloud_tolerance"],
                excluded_flags=self.params.get("excluded_flags", []),
                restrict_to_water=self.params.get("restrict_to_water", True),
                also_save_raw=self.params.get("also_save_raw", True),
                output_directory=self.params["output_directory"],
                create_report=self.params.get("create_report", True),
                progress_callback=self._emit_progress,
            )

            self.progress.emit(100)
            self.finished.emit(result)

        except Exception as exc:
            import traceback
            self.error.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")

    def _emit_progress(self, value: int, msg: str = ""):
        self.progress.emit(value)
        if msg:
            self.message.emit(msg)
