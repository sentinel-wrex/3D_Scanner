import sys
import os
import numpy as np
import pyvista as pv
import imageio.v2 as imageio
import open3d as o3d

from PyQt5.QtWidgets import QTextEdit
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt5.QtWidgets import QProgressBar


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

# worker signal class
class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

# worker class for running heavu items
class Worker(QRunnable):

    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.function(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

# spinner overlay class for progress loading

class SpinnerOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
        """)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.spinner = QProgressBar(self)
        self.spinner.setRange(0, 0)  # Indeterminate mode
        self.spinner.setFixedWidth(250)
        self.spinner.setStyleSheet("""
            QProgressBar {
                background-color: #2e2e2e;
                border: 1px solid #444;
                border-radius: 10px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #2e8bff;
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.spinner)

        self.hide()

# ============================================================
# MAIN GUI
# ============================================================

class UnifiedInspectionGUI(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1f22;
            }

            /* Labels */
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }

            /* Panels */
            QFrame {
                background-color: #25262b;
                border-radius: 8px;
            }

            /* Default Buttons */
            QPushButton {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3f4b,
                    stop:1 #2b2f38
                );
                color: white;
                border: 1px solid #3f4450;
                padding: 6px;
                border-radius: 8px;
                font-weight: 500;
            }

            QPushButton:hover {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4b5363,
                    stop:1 #353b45
                );
            }

            QPushButton:pressed {
                background-color: #2e8bff;
            }

            /* Action Buttons */
            QPushButton#primary {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4aa3ff,
                    stop:1 #2e8bff
                );
                border: none;
                font-weight: bold;
            }

            QPushButton#primary:hover {
                background-color: #5cb0ff;
            }

            /* Checkboxes */
            QCheckBox {
                color: #dddddd;
            }

            /* Log Window */
            QTextEdit {
                background-color: #111214;
                color: #00ff88;
                border: 1px solid #333;
                border-radius: 6px;
                font-family: Consolas;
            }
            """)



        self.setWindowTitle("Multimodal Battery Inspection System")
        self.resize(1280, 720)

        self.digital_twin = DigitalTwin()

        self.external_actor = None
        self.ct_surface_actor = None
        self.volume_actor = None

        # initializing worker and overlay class
        self.threadpool = QThreadPool()
        self.overlay = SpinnerOverlay(self)

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

        #plotter styling
        self.plotter.set_background("#1c1d21")
        self.plotter.add_axes(
            line_width=2,
            color='white',
            xlabel='X',
            ylabel='Y',
            zlabel='Z'
        )



        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.plotter)
        splitter.addWidget(self.right_panel)

        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)


    # For overriding resizing
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay"):
            self.overlay.setGeometry(self.rect())

    # start_task helper
    def start_task(self, function, on_finish=None):
        self.overlay.show()
        self.setEnabled(False)

        worker = Worker(function)

        worker.signals.finished.connect(
            lambda result: self.task_finished(result, on_finish)
        )
        worker.signals.error.connect(self.task_error)

        self.threadpool.start(worker)

    # task finished
    def task_finished(self, result, callback):

        self.overlay.hide()
        self.setEnabled(True)

        if callback:
            callback(result)

    # error handling
    def task_error(self, message):

        self.overlay.hide()
        self.setEnabled(True)
        self.log(f"Error: {message}")



    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.log_window.append(formatted)
        self.log_window.verticalScrollBar().setValue(
            self.log_window.verticalScrollBar().maximum()
        )

    # --------------------------------------------------------
    # LEFT PANEL – DATA
    # --------------------------------------------------------

    def build_left_panel(self):

        panel = QFrame()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Data Management"))

        btn_load_mesh = QPushButton("Load External Mesh")
        # btn_load_mesh.clicked.connect(self.load_mesh)
        btn_load_mesh.clicked.connect(
            lambda: self.start_task(self.load_mesh_task, self.load_mesh_ui)
        )

        btn_load_ct = QPushButton("Load CT Stack Folder")
        # btn_load_ct.clicked.connect(self.load_ct_stack)
        btn_load_ct.clicked.connect(
            lambda: self.start_task(self.load_ct_stack_task, self.load_ct_stack_ui)
        )

        btn_load_ct_mesh = QPushButton("Load CT Mesh (OBJ)")
        # btn_load_ct_mesh.clicked.connect(self.load_ct_mesh)
        btn_load_ct_mesh.clicked.connect(
            lambda: self.start_task(self.load_ct_mesh_task, self.load_ct_mesh_ui)
        )

        btn_extract_surface = QPushButton("Extract CT Surface")
        # btn_extract_surface.clicked.connect(self.extract_ct_surface)
        btn_extract_surface.clicked.connect(
            lambda: self.start_task(self.extract_ct_surface_task, self.extract_ct_surface_ui)
        )

        btn_align = QPushButton("Run ICP Alignment")
        # btn_align.clicked.connect(self.run_alignment)
        btn_align.clicked.connect(
            lambda: self.start_task(self.run_alignment_task, self.run_alignment_ui)
        )


        self.btn_align = btn_align
        self.btn_align.setObjectName("primary")


        layout.addWidget(btn_load_mesh)
        layout.addWidget(btn_load_ct)
        layout.addWidget(btn_load_ct_mesh)
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

        layout.addWidget(btn_deviation)
        layout.addWidget(btn_void)
        layout.addWidget(self.checkbox_external)
        layout.addWidget(self.checkbox_ct)
        layout.addWidget(self.metric_label)

        layout.addWidget(QLabel("System Log"))

        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setMinimumHeight(250)
        self.log_window.setStyleSheet("""
            background-color: black;
            color: #00FF00;
            font-family: Consolas;
            font-size: 10pt;
        """)

        layout.addWidget(self.log_window)
        layout.addStretch()

        return panel

    # ============================================================
    # FUNCTIONALITY
    # ============================================================

    # def load_mesh(self):
    #     file_path, _ = QFileDialog.getOpenFileName(
    #         self, "Select Mesh", "", "Mesh Files (*.ply *.obj *.stl)"
    #     )
    #     if not file_path:
    #         return

    #     mesh = pv.read(file_path)
    #     self.digital_twin.external_mesh = mesh

    #     if self.external_actor:
    #         self.plotter.remove_actor(self.external_actor)

    #     self.external_actor = self.plotter.add_mesh(mesh, color="white")
    #     self.plotter.reset_camera()
    #     self.log("External mesh loaded.")
    def load_mesh_task(self):
        file_name, _ = QFileDialog.getOpenFileName(
            None,
            "Open External Mesh",
            "",
            "Mesh Files (*.obj *.stl *.ply)"
        )

        if not file_name:
            return {"error": "No file selected."}

        mesh = pv.read(file_name)

        return {
            "mesh": mesh,
            "file_name": file_name
        }
    
    def load_mesh_ui(self, result):
        if "error" in result:
            self.log(result["error"])
            return

        mesh = result["mesh"]

        self.digital_twin.external_mesh = mesh

        if self.external_actor:
            self.plotter.remove_actor(self.external_actor)

        self.external_actor = self.plotter.add_mesh(
            mesh,
            color="white",
            opacity=0.7,
            smooth_shading=True
        )

        self.plotter.reset_camera()

        self.log(f"External mesh loaded: {result['file_name']}")
        self.log(f"Vertices: {mesh.n_points}")
        self.log(f"Faces: {mesh.n_cells}")



    # def load_ct_mesh(self):

    #     file_path, _ = QFileDialog.getOpenFileName(
    #         self, "Select CT Mesh", "", "Mesh Files (*.obj *.ply *.stl)"
    #     )

    #     if not file_path:
    #         return

    #     mesh = pv.read(file_path)
    #     self.digital_twin.ct_surface = mesh

    #     if self.ct_surface_actor:
    #         self.plotter.remove_actor(self.ct_surface_actor)

    #     # Check for UV coordinates
    #     has_uv = mesh.GetPointData().GetTCoords() is not None

    #     texture = None
    #     directory = os.path.dirname(file_path)

    #     if has_uv:
    #         try:
    #             for file in os.listdir(directory):
    #                 if file.lower().endswith((".jpg", ".png", ".jpeg")):
    #                     texture_path = os.path.join(directory, file)
    #                     texture = pv.read_texture(texture_path)
    #                     break
    #         except:
    #             pass
        
    #     if texture and has_uv:
    #         self.ct_surface_actor = self.plotter.add_mesh(mesh, texture=texture)
    #         self.log("CT mesh loaded with texture (UV detected).")
    #     else:
    #         self.ct_surface_actor = self.plotter.add_mesh(
    #             mesh,
    #             color="lightblue",
    #             opacity=0.8,
    #             smooth_shading=True
    #         )

    #         if not has_uv:
    #             self.log("CT mesh has no UV coordinates. Loaded without texture.")
    #         else:
    #             self.log("Texture not found. Loaded CT mesh without texture.")

    #     self.plotter.reset_camera()

    def load_ct_mesh_task(self):
        file_name, _ = QFileDialog.getOpenFileName(
            None,
            "Open CT Mesh",
            "",
            "Mesh Files (*.obj *.stl *.ply)"
        )

        if not file_name:
            return {"error": "No file selected."}

        mesh = pv.read(file_name)

        return {
            "mesh": mesh,
            "file_name": file_name
        }
    
    def load_ct_mesh_ui(self, result):
        if "error" in result:
            self.log(result["error"])
            return

        mesh = result["mesh"]

        self.digital_twin.ct_surface = mesh

        if self.ct_surface_actor:
            self.plotter.remove_actor(self.ct_surface_actor)

        self.ct_surface_actor = self.plotter.add_mesh(
            mesh,
            color="#6ec1ff",
            opacity=0.3,
            smooth_shading=True
        )

        self.plotter.reset_camera()

        self.log(f"CT mesh loaded: {result['file_name']}")
        self.log(f"Vertices: {mesh.n_points}")
        self.log(f"Faces: {mesh.n_cells}")


    
    # def load_ct_stack(self):
    #     folder = QFileDialog.getExistingDirectory(self, "Select CT Slice Folder")
    #     if not folder:
    #         return

    #     files = sorted([
    #         f for f in os.listdir(folder)
    #         if f.lower().endswith((".png", ".jpg", ".tif", ".tiff"))
    #     ])

    #     if len(files) == 0:
    #         self.log("No CT slices found.")
    #         return

    #     slices = []
    #     for f in files:
    #         img = imageio.imread(os.path.join(folder, f))
    #         if len(img.shape) == 3:
    #             img = img[:, :, 0]
    #         slices.append(img)

    #     volume = np.stack(slices, axis=0).astype(np.float32)

    #     if volume.max() > volume.min():
    #         volume = (volume - volume.min()) / (volume.max() - volume.min())

    #     self.digital_twin.ct_volume = volume

    #     self.log(f"CT volume loaded. Shape: {volume.shape}")

    def load_ct_stack_task(self):
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select CT Slice Folder"
        )

        if not folder:
            return {"error": "No folder selected."}

        import os
        import glob
        from PIL import Image

        files = sorted(glob.glob(os.path.join(folder, "*.png")))

        if not files:
            return {"error": "No PNG slices found."}

        slices = []

        for f in files:
            img = Image.open(f).convert("L")
            slices.append(np.array(img))

        volume = np.stack(slices, axis=-1)

        return {
            "volume": volume,
            "folder": folder
        }

    def load_ct_stack_ui(self, result):
        if "error" in result:
            self.log(result["error"])
            return

        self.digital_twin.ct_volume = result["volume"]

        self.log(f"CT stack loaded from: {result['folder']}")
        self.log(f"Volume shape: {result['volume'].shape}")

    # def extract_ct_surface(self):
    #     volume = self.digital_twin.ct_volume
    #     if volume is None:
    #         self.log("No CT volume loaded.")
    #         return

    #     volume = np.transpose(volume, (2, 1, 0))

    #     z, y, x = volume.shape

    #     grid = pv.ImageData()
    #     grid.dimensions = (x, y, z)
    #     grid.spacing = (1.0 / x, 1.0 / y, 1.0 / z)
    #     grid.origin = (-0.5, -0.5, -0.5)
    #     grid.point_data["density"] = volume.flatten(order="F")

    #     surface = grid.contour(isosurfaces=[0.4])

    #     self.digital_twin.ct_surface = surface

    #     if self.ct_surface_actor:
    #         self.plotter.remove_actor(self.ct_surface_actor)

    #     self.ct_surface_actor = self.plotter.add_mesh(
    #         surface, color="lightblue", opacity=0.8
    #     )

    #     self.plotter.reset_camera()
    #     self.log("CT surface extracted using marching cubes.")

    def extract_ct_surface_task(self):
        if self.digital_twin.ct_volume is None:
            return {"error": "No CT volume loaded."}

        grid = pv.wrap(self.digital_twin.ct_volume)

        contour = grid.contour(isosurfaces=[np.mean(self.digital_twin.ct_volume)])

        return {"surface": contour}
    
    def extract_ct_surface_ui(self, result):
        if "error" in result:
            self.log(result["error"])
            return

        surface = result["surface"]

        self.digital_twin.ct_surface = surface

        if self.ct_surface_actor:
            self.plotter.remove_actor(self.ct_surface_actor)

        self.ct_surface_actor = self.plotter.add_mesh(
            surface,
            color="#6ec1ff",
            opacity=0.3,
            smooth_shading=True
        )

        self.plotter.reset_camera()

        self.log("CT surface extracted.")
        self.log(f"Vertices: {surface.n_points}")

   
    def run_alignment_ui(self, result):
        if "error" in result:
            self.log(result["error"])
            return

        self.digital_twin.external_mesh = result["aligned_mesh"]
        self.digital_twin.transforms["open3d_icp"] = result["transformation"]

        if self.external_actor:
            self.plotter.remove_actor(self.external_actor)

        self.external_actor = self.plotter.add_mesh(
            self.digital_twin.external_mesh,
            color="white",
            opacity=0.7,
            smooth_shading=True
        )

        self.plotter.reset_camera()

        self.log(f"External mesh scaled by factor: {result['scale_factor']:.6f}")
        self.log(f"Best orientation: {result['orientation']}")
        self.log(f"RMSE: {result['rmse']:.6f}")
        self.log("Open3D ICP alignment completed.")


    def run_alignment_task(self):

        if self.digital_twin.external_mesh is None or self.digital_twin.ct_surface is None:
            return {"error": "Alignment requires both meshes loaded."}

        # Make working copies (important for thread safety)
        ext_mesh = self.digital_twin.external_mesh.copy()
        ct_mesh = self.digital_twin.ct_surface.copy()

        # -------------------------------------------------
        # Center meshes
        # -------------------------------------------------
        ext_center = np.array(ext_mesh.center)
        ct_center = np.array(ct_mesh.center)

        ext_mesh.translate(-ext_center, inplace=True)
        ct_mesh.translate(-ct_center, inplace=True)

        # -------------------------------------------------
        # Scale external to CT
        # -------------------------------------------------
        ext_bounds = ext_mesh.bounds
        ct_bounds = ct_mesh.bounds

        ext_size = max(
            ext_bounds[1] - ext_bounds[0],
            ext_bounds[3] - ext_bounds[2],
            ext_bounds[5] - ext_bounds[4]
        )

        ct_size = max(
            ct_bounds[1] - ct_bounds[0],
            ct_bounds[3] - ct_bounds[2],
            ct_bounds[5] - ct_bounds[4]
        )

        if ext_size == 0 or ct_size == 0:
            return {"error": "Invalid mesh size detected."}

        scale_factor = ct_size / ext_size
        ext_mesh.scale(scale_factor, inplace=True)

        # -------------------------------------------------
        # Convert to Open3D
        # -------------------------------------------------
        ext_pcd = o3d.geometry.PointCloud()
        ext_pcd.points = o3d.utility.Vector3dVector(ext_mesh.points)

        ct_pcd = o3d.geometry.PointCloud()
        ct_pcd.points = o3d.utility.Vector3dVector(ct_mesh.points)

        voxel_size = max(ext_mesh.length, ct_mesh.length) * 0.01

        ext_down = ext_pcd.voxel_down_sample(voxel_size)
        ct_down = ct_pcd.voxel_down_sample(voxel_size)

        ext_down.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=voxel_size * 2,
                max_nn=30
            )
        )

        ct_down.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=voxel_size * 2,
                max_nn=30
            )
        )

        threshold = voxel_size * 3

        def get_flip_matrix(axis):
            R = np.eye(4)
            if axis == 'x':
                R[1,1] = -1
                R[2,2] = -1
            elif axis == 'y':
                R[0,0] = -1
                R[2,2] = -1
            elif axis == 'z':
                R[0,0] = -1
                R[1,1] = -1
            return R

        candidates = {
            "identity": np.eye(4),
            "flip_x": get_flip_matrix('x'),
            "flip_y": get_flip_matrix('y'),
            "flip_z": get_flip_matrix('z'),
        }

        best_rmse = np.inf
        best_transformation = None
        best_name = None

        for name, init_transform in candidates.items():

            reg = o3d.pipelines.registration.registration_icp(
                ext_down,
                ct_down,
                threshold,
                init_transform,
                o3d.pipelines.registration.TransformationEstimationPointToPlane(),
                o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=100)
            )

            if reg.inlier_rmse < best_rmse:
                best_rmse = reg.inlier_rmse
                best_transformation = reg.transformation
                best_name = name

        # Apply best transformation to full-res mesh
        ext_points = np.asarray(ext_mesh.points)
        ext_points_h = np.hstack([ext_points, np.ones((ext_points.shape[0], 1))])
        ext_points_aligned = (best_transformation @ ext_points_h.T).T[:, :3]
        ext_mesh.points = ext_points_aligned

        return {
            "aligned_mesh": ext_mesh,
            "rmse": float(best_rmse),
            "orientation": best_name,
            "scale_factor": float(scale_factor),
            "transformation": best_transformation
        }



    # def run_alignment_task(self):

    #     if self.digital_twin.external_mesh is None or self.digital_twin.ct_surface is None:
    #         self.log("Alignment requires both meshes loaded.")
    #         return

    #     self.log("Running Open3D point-to-plane ICP alignment.")
    #     self.log("CT mesh treated as reference.")

    #     # ----------------------------------------
    #     # STEP 1: Get PyVista meshes
    #     # ----------------------------------------
    #     ext_mesh = self.digital_twin.external_mesh
    #     ct_mesh = self.digital_twin.ct_surface

    #     ext_center = np.array(ext_mesh.center)
    #     ct_center = np.array(ct_mesh.center)

    #     ext_mesh.translate(-ext_center, inplace=True)
    #     ct_mesh.translate(-ct_center, inplace=True)

    #     self.log("Meshes centered before alignment.")

    #     # ----------------------------------------
    #     # STEP 1.5: SCALE EXTERNAL TO CT
    #     # ----------------------------------------
    #     ext_bounds = ext_mesh.bounds
    #     ct_bounds = ct_mesh.bounds

    #     ext_size = max(
    #         ext_bounds[1] - ext_bounds[0],
    #         ext_bounds[3] - ext_bounds[2],
    #         ext_bounds[5] - ext_bounds[4]
    #     )

    #     ct_size = max(
    #         ct_bounds[1] - ct_bounds[0],
    #         ct_bounds[3] - ct_bounds[2],
    #         ct_bounds[5] - ct_bounds[4]
    #     )

    #     if ext_size == 0 or ct_size == 0:
    #         self.log("Invalid mesh size detected.")
    #         return

    #     scale_factor = ct_size / ext_size
    #     ext_mesh.scale(scale_factor, inplace=True)

    #     self.log(f"External mesh scaled by factor: {scale_factor:.6f}")

    #     # ----------------------------------------
    #     # STEP 2: Convert to Open3D point clouds
    #     # ----------------------------------------
    #     ext_pcd = o3d.geometry.PointCloud()
    #     ext_pcd.points = o3d.utility.Vector3dVector(ext_mesh.points)

    #     ct_pcd = o3d.geometry.PointCloud()
    #     ct_pcd.points = o3d.utility.Vector3dVector(ct_mesh.points)

    #     # ----------------------------------------
    #     # STEP 3: Downsample (critical for stability)
    #     # ----------------------------------------
    #     voxel_size = max(ext_mesh.length, ct_mesh.length) * 0.01

    #     ext_down = ext_pcd.voxel_down_sample(voxel_size)
    #     ct_down = ct_pcd.voxel_down_sample(voxel_size)

    #     self.log(f"Voxel downsample size: {voxel_size:.6f}")

    #     # ----------------------------------------
    #     # STEP 4: Estimate normals
    #     # ----------------------------------------
    #     ext_down.estimate_normals(
    #         search_param=o3d.geometry.KDTreeSearchParamHybrid(
    #             radius=voxel_size * 2,
    #             max_nn=30
    #         )
    #     )

    #     ct_down.estimate_normals(
    #         search_param=o3d.geometry.KDTreeSearchParamHybrid(
    #             radius=voxel_size * 2,
    #             max_nn=30
    #         )
    #     )

    #     # ----------------------------------------
    #     # STEP 5: Run Point-to-Plane ICP
    #     # ----------------------------------------
    #     threshold = voxel_size * 3

    #     # ----------------------------------------
    #     # STEP 5: Multi-Hypothesis ICP
    #     # ----------------------------------------

    #     def get_flip_matrix(axis):
    #         R = np.eye(4)
    #         if axis == 'x':
    #             R[1,1] = -1
    #             R[2,2] = -1
    #         elif axis == 'y':
    #             R[0,0] = -1
    #             R[2,2] = -1
    #         elif axis == 'z':
    #             R[0,0] = -1
    #             R[1,1] = -1
    #         return R

    #     candidates = {
    #         "flip_x": get_flip_matrix('x'),
    #         "flip_y": get_flip_matrix('y'),
    #         "flip_z": get_flip_matrix('z'),
    #     }

    #     best_rmse = np.inf
    #     best_transformation = None
    #     best_name = None

    #     threshold = voxel_size * 3

    #     for name, init_transform in candidates.items():

    #         reg = o3d.pipelines.registration.registration_icp(
    #             ext_down,
    #             ct_down,
    #             threshold,
    #             init_transform,
    #             o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    #             o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=100)
    #         )

    #         self.log(f"{name} → RMSE: {reg.inlier_rmse:.6f}")

    #         if reg.inlier_rmse < best_rmse:
    #             best_rmse = reg.inlier_rmse
    #             best_transformation = reg.transformation
    #             best_name = name

    #     self.log(f"Best orientation: {best_name}")
    #     self.log(f"Best RMSE: {best_rmse:.6f}")

    #     transformation = best_transformation

    #     ext_points = np.asarray(ext_mesh.points)

    #     ext_points_h = np.hstack([ext_points, np.ones((ext_points.shape[0], 1))])
    #     ext_points_aligned = (transformation @ ext_points_h.T).T[:, :3]

    #     ext_mesh.points = ext_points_aligned

    #     self.digital_twin.transforms["open3d_icp"] = transformation
 
    #     # ----------------------------------------
    #     # STEP 7: Update visualization
    #     # ----------------------------------------
    #     if self.external_actor:
    #         self.plotter.remove_actor(self.external_actor)

    #     self.external_actor = self.plotter.add_mesh(
    #         ext_mesh,
    #         color="white",
    #         opacity=0.7
    #     )

    #     self.log("Open3D ICP alignment completed.")

    def compute_deviation(self):
        if self.digital_twin.external_mesh is None or self.digital_twin.ct_surface is None:
            self.log("Deviation requires aligned meshes.")
            return

        aligned = self.digital_twin.ct_surface.compute_implicit_distance(
            self.digital_twin.external_mesh
        )

        deviation = np.abs(aligned["implicit_distance"])
        aligned["deviation"] = deviation

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

        self.log(f"Mean deviation: {mean_dev:.5f}")
        self.log(f"Max deviation: {max_dev:.5f}")

    def detect_voids(self):
        volume = self.digital_twin.ct_volume
        if volume is None:
            self.log("No CT volume loaded for void detection.")
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
