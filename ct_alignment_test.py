import numpy as np
import pyvista as pv
import os
import imageio.v2 as imageio


# ==============================
# USER SETTINGS
# ==============================

ORIGINAL_MESH_PATH = r"C:\Users\PC\Downloads\crankcase_ply\Crankcase.ply"
SYNTHETIC_CT_FOLDER = r"C:\Users\PC\Desktop\3D_Scanner\voxel_output"


# ==============================
# LOAD CT STACK
# ==============================

def load_ct_stack(folder):

    files = sorted([
        f for f in os.listdir(folder)
        if f.endswith(".png")
    ])

    slices = []
    for f in files:
        img = imageio.imread(os.path.join(folder, f))
        slices.append(img)

    volume = np.stack(slices, axis=2).astype(np.float32)

    # Normalize
    volume -= volume.min()
    volume /= volume.max()

    return volume


# ==============================
# CT → GRID
# ==============================

def volume_to_grid(volume):

    z, y, x = volume.shape

    grid = pv.ImageData()
    grid.dimensions = (x, y, z)
    grid.spacing = (1.0 / x, 1.0 / y, 1.0 / z)
    grid.origin = (-0.5, -0.5, -0.5)

    grid.point_data["density"] = volume.flatten(order="F")

    return grid


# ==============================
# MAIN
# ==============================

def main():

    print("Loading original mesh...")
    original = pv.read(ORIGINAL_MESH_PATH)

    # Center & scale same as voxelizer
    center = np.array(original.center)
    original.translate(-center)

    bounds = original.bounds
    size = max(bounds[1] - bounds[0],
               bounds[3] - bounds[2],
               bounds[5] - bounds[4])
    original.scale(1.0 / size)

    print("Loading synthetic CT...")
    volume = load_ct_stack(SYNTHETIC_CT_FOLDER)

    grid = volume_to_grid(volume)

    print("Extracting surface from CT...")
    ct_surface = grid.contour(isosurfaces=[0.4])

    # Rough alignment
    ct_center = np.array(ct_surface.center)
    orig_center = np.array(original.center)

    ct_surface.translate(-ct_center)
    original.translate(-orig_center)


    print("Running ICP alignment...")
    aligned_ct, matrix = ct_surface.align(original, return_matrix=True)

    print("Computing error...")
    distances = aligned_ct.compute_implicit_distance(original)
    error = np.abs(distances["implicit_distance"])

    print("Mean alignment error:", error.mean())
    print("Max alignment error:", error.max())

    # Visualization
    plotter = pv.Plotter()
    plotter.add_mesh(original, color="red", opacity=0.5)
    plotter.add_mesh(aligned_ct, color="green", opacity=0.5)
    plotter.add_axes()
    plotter.show()


if __name__ == "__main__":
    main()
