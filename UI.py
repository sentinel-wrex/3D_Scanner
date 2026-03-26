# ui.py

import sys
import os
from PyQt5 import QtWidgets, QtCore
import pyvista as pv
from pyvistaqt import QtInteractor
from colmap_worker import ColmapWorker


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Battery Reconstruction Platform")
        self.resize(1300, 900)

        self.image_folder = None
        self.worker = None
        self.workspace = "colmap_workspace"

        # ---------- Central UI ----------
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # ---------- Controls ----------
        controls = QtWidgets.QHBoxLayout()

        self.import_images_btn = QtWidgets.QPushButton("Import Images")
        self.import_images_btn.clicked.connect(self.import_images)

        self.run_btn = QtWidgets.QPushButton("Run COLMAP")
        self.run_btn.clicked.connect(self.run_colmap)
        self.run_btn.setEnabled(False)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_colmap)
        self.cancel_btn.setEnabled(False)

        controls.addWidget(self.import_images_btn)
        controls.addWidget(self.run_btn)
        controls.addWidget(self.cancel_btn)
        controls.addStretch()

        layout.addLayout(controls)

        # ---------- Split View ----------
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        layout.addWidget(splitter, 1)

        # ---------- PyVista ----------
        self.plotter = QtInteractor(self)
        splitter.addWidget(self.plotter.interactor)

        # ---------- Log Viewer ----------
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(10000)
        splitter.addWidget(self.log_view)

        splitter.setSizes([700, 200])

        # ---------- Status Bar ----------
        self.status = self.statusBar()
        self.status.showMessage("Ready")

    def import_images(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Images Folder")
        if folder:
            self.image_folder = folder
            self.run_btn.setEnabled(True)
            self.status.showMessage("Images loaded")

    def run_colmap(self):
        self.log_view.clear()
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker = ColmapWorker(self.image_folder, self.workspace)
        self.worker.log_signal.connect(self.log_view.appendPlainText)
        self.worker.status_signal.connect(self.status.showMessage)
        self.worker.finished_signal.connect(self.colmap_finished)
        self.worker.error_signal.connect(self.colmap_failed)

        self.worker.start()
        self.status.showMessage("COLMAP started")

    def cancel_colmap(self):
        if self.worker:
            self.worker.abort()
            self.status.showMessage("Aborting COLMAP...")

    def colmap_finished(self, mesh_path):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status.showMessage("COLMAP finished")

        if os.path.exists(mesh_path):
            mesh = pv.read(mesh_path)
            self.plotter.clear()
            self.plotter.add_mesh(mesh, color="lightgray")
            self.plotter.reset_camera()

    def colmap_failed(self, error):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status.showMessage("COLMAP failed")
        QtWidgets.QMessageBox.critical(self, "Error", error)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
