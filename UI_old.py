import sys
import os
import subprocess
import threading
from PyQt5 import QtWidgets, QtGui, QtCore
import pyvista as pv
from pyvistaqt import QtInteractor
from PIL import Image


SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Battery Inspection & 3D Reconstruction UI")
        self.resize(1200, 800)

        # --------------------- Paths & Config ----------------
        self.colmap_workspace = "colmap_workspace"

        # ---------------- Central Widget ----------------
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout()
        central.setLayout(main_layout)

        # ---------------- Left Sidebar ----------------
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setFixedWidth(300)
        sidebar_layout = QtWidgets.QVBoxLayout()
        self.sidebar.setLayout(sidebar_layout)

        sidebar_title = QtWidgets.QLabel("Image Inspector")
        sidebar_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        sidebar_layout.addWidget(sidebar_title)

        # Image list (thumbnails)
        self.image_list = QtWidgets.QListWidget()
        self.image_list.setIconSize(QtCore.QSize(120, 90))
        self.image_list.itemClicked.connect(self.show_image_preview)
        sidebar_layout.addWidget(self.image_list, stretch=1)

        # Image preview
        self.image_preview = QtWidgets.QLabel("Select an image")
        self.image_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.image_preview.setFixedHeight(200)
        self.image_preview.setStyleSheet("border: 1px solid gray;")
        sidebar_layout.addWidget(self.image_preview)

        main_layout.addWidget(self.sidebar)

        # ---------------- Right Panel ----------------
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout()
        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel, stretch=1)

        # ---------------- Top Controls ----------------
        controls = QtWidgets.QHBoxLayout()

        self.import_model_btn = QtWidgets.QPushButton("Import 3D Model")
        self.import_model_btn.clicked.connect(self.import_model)

        self.import_images_btn = QtWidgets.QPushButton("Import Images Folder")
        self.import_images_btn.clicked.connect(self.import_images_folder)

        self.run_colmap_btn = QtWidgets.QPushButton("Run COLMAP")
        self.run_colmap_btn.clicked.connect(self.run_colmap)
        self.run_colmap_btn.setEnabled(False)  # enabled once images loaded

        controls.addWidget(self.import_model_btn)
        controls.addWidget(self.import_images_btn)
        controls.addWidget(self.run_colmap_btn)
        controls.addStretch()

        right_layout.addLayout(controls)

        # ---------------- PyVista Renderer ----------------
        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")
        self.plotter.add_axes()
        right_layout.addWidget(self.plotter.interactor, stretch=1)

        # ---------------- Data ----------------
        self.image_folder = None
        self.images = []

    # ---------------- Image Handling ----------------
    def import_images_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Images Folder"
        )

        if not folder:
            return

        self.image_folder = folder
        self.images = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(SUPPORTED_IMAGE_EXTS)
        ]

        self.image_list.clear()

        for img_path in self.images:
            icon = QtGui.QIcon(self.create_thumbnail(img_path))
            item = QtWidgets.QListWidgetItem(icon, os.path.basename(img_path))
            item.setData(QtCore.Qt.UserRole, img_path)
            self.image_list.addItem(item)

        self.run_colmap_btn.setEnabled(len(self.images) > 0)

    def create_thumbnail(self, img_path):
        img = Image.open(img_path)
        img.thumbnail((120, 90))
        thumb_path = img_path + "_thumb.png"
        img.save(thumb_path)
        return thumb_path

    def show_image_preview(self, item):
        img_path = item.data(QtCore.Qt.UserRole)
        pixmap = QtGui.QPixmap(img_path)
        self.image_preview.setPixmap(
            pixmap.scaled(
                self.image_preview.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    # ---------------- 3D Model Handling ----------------
    def import_model(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import 3D Model",
            "",
            "3D Models (*.ply *.obj *.stl *.vtk *.vtp *.vtu *.glb *.gltf)"
        )

        if not file_path:
            return

        try:
            mesh = pv.read(file_path)
            self.display_mesh(mesh)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def display_mesh(self, mesh):
        self.plotter.clear()

        if mesh.n_cells > 0:
            self.plotter.add_mesh(mesh, color="lightgray")
        else:
            self.plotter.add_points(mesh, point_size=2)

        self.plotter.add_axes()
        self.plotter.reset_camera()
    
    # def run_colmap(self):
    #     if not self.image_folder:
    #         QtWidgets.QMessageBox.warning(
    #             self, "No Images", "Please import an images folder first."
    #         )
    #         return

    #     self.run_colmap_btn.setEnabled(False)
    #     self.import_images_btn.setEnabled(False)

    #     self.progress = QtWidgets.QProgressDialog(
    #         "Running COLMAP reconstruction...",
    #         None,
    #         0,
    #         0,
    #         self
    #     )
    #     self.progress.setWindowTitle("COLMAP")
    #     self.progress.setWindowModality(QtCore.Qt.WindowModal)
    #     self.progress.show()

    #     thread = threading.Thread(target=self._run_colmap_pipeline)
    #     thread.start()

    def run_colmap(self):
        if not self.image_folder:
            QtWidgets.QMessageBox.warning(
                self, "No Images", "Please import an images folder first."
            )
            return

        self.run_colmap_btn.setEnabled(False)
        self.import_images_btn.setEnabled(False)

        # Optional progress dialog
        self.progress = QtWidgets.QProgressDialog(
            "Running COLMAP (CLI)...",
            None,
            0,
            0,
            self
        )
        self.progress.setWindowTitle("COLMAP")
        self.progress.setWindowModality(QtCore.Qt.WindowModal)
        self.progress.show()

        threading.Thread(target=self._run_colmap_cli).start()


    # def _run_colmap_pipeline(self):
    #     workspace = self.colmap_workspace
    #     images = self.image_folder

    #     os.makedirs(workspace, exist_ok=True)

    #     commands = [
    #         [
    #             "colmap", "feature_extractor",
    #             "--database_path", f"{workspace}/database.db",
    #             "--image_path", images,
    #             "--ImageReader.single_camera", "1"
    #         ],
    #         [
    #             "colmap", "exhaustive_matcher",
    #             "--database_path", f"{workspace}/database.db"
    #         ],
    #         [
    #             "colmap", "mapper",
    #             "--database_path", f"{workspace}/database.db",
    #             "--image_path", images,
    #             "--output_path", f"{workspace}/sparse"
    #         ],
    #         [
    #             "colmap", "image_undistorter",
    #             "--image_path", images,
    #             "--input_path", f"{workspace}/sparse/0",
    #             "--output_path", f"{workspace}/dense",
    #             "--output_type", "COLMAP"
    #         ],
    #         [
    #             "colmap", "patch_match_stereo",
    #             "--workspace_path", f"{workspace}/dense"
    #         ],
    #         [
    #             "colmap", "stereo_fusion",
    #             "--workspace_path", f"{workspace}/dense",
    #             "--output_path", f"{workspace}/dense/fused.ply"
    #         ],
    #         [
    #             "colmap", "poisson_mesher",
    #             "--input_path", f"{workspace}/dense/fused.ply",
    #             "--output_path", f"{workspace}/dense/meshed-poisson.ply"
    #         ],
    #     ]

    #     try:
    #         for cmd in commands:
    #             subprocess.run(cmd, check=True)

    #         mesh_path = f"{workspace}/dense/meshed-poisson.ply"

    #         QtCore.QMetaObject.invokeMethod(
    #             self,
    #             "on_colmap_finished",
    #             QtCore.Qt.QueuedConnection,
    #             QtCore.Q_ARG(str, mesh_path)
    #         )

    #     except subprocess.CalledProcessError as e:
    #         QtCore.QMetaObject.invokeMethod(
    #             self,
    #             "on_colmap_failed",
    #             QtCore.Qt.QueuedConnection,
    #             QtCore.Q_ARG(str, str(e))
    #         )

    def _run_colmap_cli(self):
        try:
            os.makedirs(self.colmap_workspace, exist_ok=True)

            cmd = [
                "colmap",
                "automatic_reconstructor",
                "--image_path", self.image_folder,
                "--workspace_path", self.colmap_workspace,
                "--quality", "medium"
            ]

            subprocess.run(cmd, check=True)

            mesh_path = os.path.join(
                self.colmap_workspace,
                "dense",
                "meshed-poisson.ply"
            )

            QtCore.QMetaObject.invokeMethod(
                self,
                "on_colmap_finished",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, mesh_path)
            )

        except subprocess.CalledProcessError as e:
            QtCore.QMetaObject.invokeMethod(
                self,
                "on_colmap_failed",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )

    
    @QtCore.pyqtSlot(str)
    def on_colmap_finished(self, mesh_path):
        self.progress.close()
        self.run_colmap_btn.setEnabled(True)
        self.import_images_btn.setEnabled(True)

        if os.path.exists(mesh_path):
            mesh = pv.read(mesh_path)
            self.display_mesh(mesh)
        else:
            QtWidgets.QMessageBox.warning(
                self, "COLMAP Finished", "Mesh file not found."
            )

    @QtCore.pyqtSlot(str)
    def on_colmap_failed(self, error):
        self.progress.close()
        self.run_colmap_btn.setEnabled(True)
        self.import_images_btn.setEnabled(True)

        QtWidgets.QMessageBox.critical(
            self, "COLMAP Error", error
        )






if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
