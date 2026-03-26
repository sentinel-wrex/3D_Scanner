import sys
import os
import numpy as np
import pyvista as pv
import imageio.v2 as imageio

from PyQt5.QtWidgets import QTextEdit
from datetime import datetime

from pyvistaqt import QtInteractor

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QLabel, QFileDialog,
    QFrame, QSplitter, QCheckBox
)
from PyQt5.QtCore import Qt


# ============================================================
# DIGITAL TWIN CORE
# ============================================================

class DigitalTwin:
    def __init__(self):
        self.external_mesh = None
        self.ct_volume = None
        self.ct_surface = None
        self.transforms = {}
        self.inspection_metrics = {}


# ============================================================
# MAIN GUI
# ============================================================

class UnifiedInspectionGUI(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Multimodal Battery Inspection System")
        self.resize(1280, 720)

        self.digital_twin = DigitalTwin()

        self.external_actor = None
        self.ct_surface_actor = None
        self.volume_actor = None

        self.init_ui()

    # --------------------------------------------------------
    # UI SETUP
    # --------------------------------------------------------

    def init_ui(self):

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)

        self.left_panel = self.build_left_panel()
        self.plotter = QtInteractor(self)
        self.right_panel = self.build_right_panel()

        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.plotter)
        splitter.addWidget(self.right_panel)

        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

    # LOG Functionality
    def log(self, message):

        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"

        self.log_window.append(formatted)


    # --------------------------------------------------------
    # LEFT PANEL – DATA
    # --------------------------------------------------------

    def build_left_panel(self):
        panel = QFrame()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Data Management"))

        btn_load_mesh = QPushButton("Load External Mesh")
        btn_load_mesh.clicked.connect(self.load_mesh)

        btn_load_ct = QPushButton("Load CT Stack Folder")
        btn_load_ct.clicked.connect(self.load_ct_stack)

        btn_extract_surface = QPushButton("Extract CT Surface")
        btn_extract_surface.clicked.connect(self.extract_ct_surface)

        btn_align = QPushButton("Run ICP Alignment")
        btn_align.clicked.connect(self.run_alignment)

        layout.addWidget(btn_load_mesh)
        layout.addWidget(btn_load_ct)
        layout.addWidget(btn_extract_surface)
        layout.addWidget(btn_align)

        layout.addStretch()
        return panel

    # --------------------------------------------------------
    # RIGHT PANEL – INSPECTION
    # --------------------------------------------------------

    def build_right_panel(self):
        panel = QFrame()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Inspection Panel"))

        btn_deviation = QPushButton("Compute Surface Deviation")
        btn_deviation.clicked.connect(self.compute_deviation)

        btn_void = QPushButton("Detect Internal Voids")
        btn_void.clicked.connect(self.detect_voids)

        self.checkbox_external = QCheckBox("Show External Mesh")
        self.checkbox_external.setChecked(True)
        self.checkbox_external.stateChanged.connect(self.toggle_external)

        self.checkbox_ct = QCheckBox("Show CT Surface")
        self.checkbox_ct.setChecked(True)
        self.checkbox_ct.stateChanged.connect(self.toggle_ct_surface)

        self.metric_label = QLabel("Metrics:\n")

        # -------- LOG WINDOW --------
        layout.addWidget(QLabel("System Log"))

        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setMinimumHeight(250)

        # Optional styling
        self.log_window.setStyleSheet("""
            background-color: black;
            color: #00FF00;
            font-family: Consolas;
            font-size: 10pt;
        """)

        layout.addWidget(btn_deviation)
        layout.addWidget(btn_void)
        layout.addWidget(self.checkbox_external)
        layout.addWidget(self.checkbox_ct)
        layout.addWidget(self.metric_label)
        layout.addWidget(self.log_window)

        layout.addStretch()

        return panel


    # ============================================================
    # FUNCTIONALITY
    # ============================================================

    # --------------------------------------------------------
    # Load External Mesh
    # --------------------------------------------------------

    def load_mesh(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Mesh", "", "Mesh Files (*.ply *.obj *.stl)"
        )

        if not file_path:
            return

        mesh = pv.read(file_path)
        self.digital_twin.external_mesh = mesh

        if self.external_actor:
            self.plotter.remove_actor(self.external_actor)

        self.external_actor = self.plotter.add_mesh(mesh, color="white")
        self.plotter.reset_camera()

        self.log("External mesh loaded.")

    # --------------------------------------------------------
    # Load CT Stack
    # --------------------------------------------------------



    def load_ct_stack(self):

        folder = QFileDialog.getExistingDirectory(self, "Select CT Slice Folder")
        if not folder:
            return

        files = sorted([
            f for f in os.listdir(folder)
            if f.lower().endswith((".png", ".jpg", ".tif", ".tiff"))
        ])

        if len(files) == 0:
            self.statusBar().showMessage("No image slices found.")
            return

        slices = []

        for f in files:
            full_path = os.path.join(folder, f)

            try:
                # ----------------------------
                # ORIGINAL METHOD (PyVista)
                # ----------------------------
                img = pv.read(full_path)

                if "ImageScalars" in img.point_data:
                    arr = img.point_data["ImageScalars"]
                    arr = arr.reshape(img.dimensions[:2])
                    slices.append(arr)
                    continue

                # If PyVista loads but without ImageScalars
                if len(img.point_data) > 0:
                    key = list(img.point_data.keys())[0]
                    arr = img.point_data[key]
                    arr = arr.reshape(img.dimensions[:2])
                    slices.append(arr)
                    continue

                raise Exception("No scalar data found in PyVista object.")

            except Exception:
                # ----------------------------
                # FALLBACK METHOD (Standard PNG)
                # ----------------------------
                img = imageio.imread(full_path)

                # Convert RGB → grayscale if needed
                if len(img.shape) == 3:
                    img = img[:, :, 0]

                slices.append(img)

        volume = np.stack(slices, axis=0).astype(np.float32)

        self.log(f"CT volume loaded. Shape: {volume.shape}")


        # Safe normalization
        if volume.max() > volume.min():
            volume = (volume - volume.min()) / (volume.max() - volume.min())

        self.digital_twin.ct_volume = volume

        self.statusBar().showMessage(
            f"CT Volume Loaded Successfully: Shape = {volume.shape}"
        )

        


    # --------------------------------------------------------
    # Extract CT Surface
    # --------------------------------------------------------

    # def extract_ct_surface(self):

    #     volume = self.digital_twin.ct_volume
    #     if volume is None:
    #         return

    #     z, y, x = volume.shape

    #     grid = pv.ImageData()
    #     grid.dimensions = (x, y, z)
    #     grid.spacing = (1, 1, 1)
    #     grid.point_data["density"] = volume.flatten(order="F")

    #     surface = grid.contour(isosurfaces=[0.5])

    #     self.digital_twin.ct_surface = surface

    #     if self.ct_surface_actor:
    #         self.plotter.remove_actor(self.ct_surface_actor)

    #     self.ct_surface_actor = self.plotter.add_mesh(surface, color="lightblue")
    #     self.plotter.reset_camera()

    def extract_ct_surface(self):

        volume = self.digital_twin.ct_volume
        if volume is None:
            return

        # Match reference file orientation
        volume = np.transpose(volume, (2, 1, 0))

        z, y, x = volume.shape

        grid = pv.ImageData()
        grid.dimensions = (x, y, z)

        # Normalized spacing (CRITICAL)
        grid.spacing = (1.0 / x, 1.0 / y, 1.0 / z)

        # Center at origin (CRITICAL)
        grid.origin = (-0.5, -0.5, -0.5)

        grid.point_data["density"] = volume.flatten(order="F")

        surface = grid.contour(isosurfaces=[0.4])

        self.log("CT surface extracted using marching cubes.")


        self.digital_twin.ct_surface = surface

        if self.ct_surface_actor:
            self.plotter.remove_actor(self.ct_surface_actor)

        self.ct_surface_actor = self.plotter.add_mesh(
            surface,
            color="lightblue",
            opacity=0.5
        )

        self.plotter.reset_camera()


    # --------------------------------------------------------
    # ICP Alignment
    # --------------------------------------------------------

    def run_alignment(self):

        if self.digital_twin.external_mesh is None or self.digital_twin.ct_surface is None:
            return

        aligned, matrix = self.digital_twin.ct_surface.align(
            self.digital_twin.external_mesh,
            return_matrix=True
        )

        self.log("ICP alignment completed.")

        self.digital_twin.ct_surface = aligned
        self.digital_twin.transforms["ct_to_mesh"] = matrix

        self.plotter.remove_actor(self.ct_surface_actor)
        self.ct_surface_actor = self.plotter.add_mesh(aligned, color="lightblue")

        self.statusBar().showMessage("ICP Alignment Completed")

    # --------------------------------------------------------
    # Surface Deviation Heatmap
    # --------------------------------------------------------

    def compute_deviation(self):

        if self.digital_twin.external_mesh is None or self.digital_twin.ct_surface is None:
            return

        aligned = self.digital_twin.ct_surface.compute_implicit_distance(
            self.digital_twin.external_mesh
        )

        deviation = np.abs(aligned["implicit_distance"])
        aligned["deviation"] = deviation

        self.log(f"Mean deviation: {mean_dev:.5f}")
        self.log(f"Max deviation: {max_dev:.5f}")


        mean_dev = np.mean(deviation)
        max_dev = np.max(deviation)

        self.digital_twin.inspection_metrics["mean_deviation"] = mean_dev
        self.digital_twin.inspection_metrics["max_deviation"] = max_dev

        self.plotter.remove_actor(self.ct_surface_actor)

        self.ct_surface_actor = self.plotter.add_mesh(
            aligned,
            scalars="deviation",
            cmap="jet",
            show_scalar_bar=True
        )

        self.metric_label.setText(
            f"Metrics:\nMean Deviation: {mean_dev:.4f}\nMax Deviation: {max_dev:.4f}"
        )

    # --------------------------------------------------------
    # Void Detection
    # --------------------------------------------------------

    def detect_voids(self):

        volume = self.digital_twin.ct_volume
        if volume is None:
            return

        threshold = np.percentile(volume, 5)
        void_mask = volume < threshold

        void_volume = np.sum(void_mask)

        self.digital_twin.inspection_metrics["void_volume"] = void_volume

        self.metric_label.setText(
            self.metric_label.text() +
            f"\nVoid Volume (voxels): {void_volume}"
        )

        self.log(f"Void voxels detected: {void_volume}")


    # --------------------------------------------------------
    # Toggle Visibility
    # --------------------------------------------------------

    def toggle_external(self, state):
        if self.external_actor:
            self.external_actor.SetVisibility(state == Qt.Checked)

    def toggle_ct_surface(self, state):
        if self.ct_surface_actor:
            self.ct_surface_actor.SetVisibility(state == Qt.Checked)


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UnifiedInspectionGUI()
    window.show()
    sys.exit(app.exec_())
