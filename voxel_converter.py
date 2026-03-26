import os
import numpy as np
import pyvista as pv
from scipy.ndimage import gaussian_filter
import imageio.v2 as imageio


# ===============================
# USER SETTINGS
# ===============================

INPUT_MESH_PATH = r"C:\Users\PC\Downloads\crankcase_ply\Crankcase.ply"
OUTPUT_FOLDER = r"C:\Users\PC\Desktop\3D_Scanner\voxel_output"

VOXEL_RESOLUTION = 128     # increase for higher quality
GAUSSIAN_BLUR_SIGMA = 1.0  # simulates CT blur
NOISE_LEVEL = 0.02         # simulate CT noise (0 to disable)


# ===============================
# MAIN PROCESS
# ===============================

def main():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print("Loading mesh...")
    mesh = pv.read(INPUT_MESH_PATH)

    # Ensure mesh has faces
    if mesh.n_cells == 0:
        raise RuntimeError("Mesh has no cells. Use a proper surface mesh (.ply with triangles).")

    # Center mesh
    center = np.array(mesh.center)
    mesh.translate(-center)

    # Scale mesh to unit cube
    bounds = mesh.bounds
    size = max(bounds[1] - bounds[0],
               bounds[3] - bounds[2],
               bounds[5] - bounds[4])

    mesh.scale(1.0 / size)

    print("Creating uniform grid...")

    # Create uniform 3D grid
    x = y = z = VOXEL_RESOLUTION
    grid = pv.ImageData()
    grid.dimensions = (x, y, z)
    grid.spacing = (1.0 / x, 1.0 / y, 1.0 / z)
    grid.origin = (-0.5, -0.5, -0.5)

    print("Computing inside/outside mask...")

    # Determine which grid points are inside the mesh
    enclosed = grid.select_enclosed_points(mesh, tolerance=0.0)
    mask = enclosed.point_data["SelectedPoints"]

    # Reshape to 3D volume (VERY IMPORTANT: Fortran order)
    volume = mask.reshape((x, y, z), order="F").astype(np.float32)

    print("Applying blur...")
    volume = gaussian_filter(volume, sigma=GAUSSIAN_BLUR_SIGMA)

    if NOISE_LEVEL > 0:
        noise = np.random.normal(0, NOISE_LEVEL, volume.shape)
        volume += noise

    # Normalize to 0–255
    volume -= volume.min()
    volume /= volume.max()
    volume = (volume * 255).astype(np.uint8)

    print("Saving PNG slice stack...")

    for k in range(volume.shape[2]):
        slice_img = volume[:, :, k]
        filename = os.path.join(OUTPUT_FOLDER, f"{k:06d}.png")
        imageio.imwrite(filename, slice_img)

    print("Done.")
    print("Synthetic CT stack saved to:", OUTPUT_FOLDER)


# ===============================
# ENTRY
# ===============================

if __name__ == "__main__":
    main()
