import os
import numpy as np
import imageio.v2 as imageio


class CTVolume:
    def __init__(self, volume, spacing=(1.0, 1.0, 1.0), orientation="xy"):
        """
        volume: 3D numpy array (Z, Y, X)
        spacing: voxel spacing (dz, dy, dx)
        orientation: 'xy', 'xz', or 'yz'
        """
        self.volume = volume
        self.spacing = spacing
        self.orientation = orientation

    @property
    def shape(self):
        return self.volume.shape


class CTLoader:
    SUPPORTED_EXTS = (".tif", ".tiff", ".png")

    @staticmethod
    def load_slice_stack(folder_path, spacing=(1.0, 1.0, 1.0), orientation="xy"):
        """
        Load a folder of CT slices (PNG/TIFF) into a 3D volume.
        """

        if not os.path.isdir(folder_path):
            raise ValueError(f"Folder does not exist: {folder_path}")

        files = sorted([
            f for f in os.listdir(folder_path)
            if f.lower().endswith(CTLoader.SUPPORTED_EXTS)
        ])

        if not files:
            raise ValueError(
                f"No CT slice images found in {folder_path}"
            )

        slices = []
        for f in files:
            img = imageio.imread(os.path.join(folder_path, f))
            slices.append(img)

        volume = np.stack(slices, axis=0)  # (Z, Y, X)

        return CTVolume(
            volume=volume,
            spacing=spacing,
            orientation=orientation
        )
