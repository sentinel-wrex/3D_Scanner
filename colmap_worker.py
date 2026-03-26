# colmap_worker.py

import os
import subprocess
from PyQt5 import QtCore


class ColmapWorker(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    status_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal(str)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, images_dir, workspace):
        super().__init__()
        self.images_dir = images_dir
        self.workspace = workspace
        self._abort = False
        self.process = None

    def abort(self):
        self._abort = True
        if self.process:
            self.process.terminate()

    def run(self):
        try:
            os.makedirs(self.workspace, exist_ok=True)

            commands = [
                ["colmap", "feature_extractor",
                 "--database_path", f"{self.workspace}/database.db",
                 "--image_path", self.images_dir,
                 "--ImageReader.single_camera", "1"],

                ["colmap", "exhaustive_matcher",
                 "--database_path", f"{self.workspace}/database.db"],

                ["colmap", "mapper",
                 "--database_path", f"{self.workspace}/database.db",
                 "--image_path", self.images_dir,
                 "--output_path", f"{self.workspace}/sparse"],

                ["colmap", "image_undistorter",
                 "--image_path", self.images_dir,
                 "--input_path", f"{self.workspace}/sparse/0",
                 "--output_path", f"{self.workspace}/dense",
                 "--output_type", "COLMAP"],

                ["colmap", "patch_match_stereo",
                 "--workspace_path", f"{self.workspace}/dense"],

                ["colmap", "stereo_fusion",
                 "--workspace_path", f"{self.workspace}/dense",
                 "--output_path", f"{self.workspace}/dense/fused.ply"],

                ["colmap", "poisson_mesher",
                 "--input_path", f"{self.workspace}/dense/fused.ply",
                 "--output_path", f"{self.workspace}/dense/meshed-poisson.ply"],
            ]

            for cmd in commands:
                if self._abort:
                    self.status_signal.emit("COLMAP aborted by user")
                    return

                self.status_signal.emit("Running: " + cmd[1])
                self._run_process(cmd)

            mesh_path = f"{self.workspace}/dense/meshed-poisson.ply"
            self.finished_signal.emit(mesh_path)

        except Exception as e:
            self.error_signal.emit(str(e))

    def _run_process(self, cmd):
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in self.process.stdout:
            if self._abort:
                self.process.terminate()
                return
            self.log_signal.emit(line.rstrip())

        self.process.wait()
