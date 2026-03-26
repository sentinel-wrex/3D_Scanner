import os
import numpy as np
import imageio.v2 as imageio
import pyvista as pv
from scipy.ndimage import gaussian_filter

# ===============================
# -------- CT LOADER ------------
# ===============================

def load_ct_slice_stack(folder_path, spacing=(1.0, 1.0, 1.0), downsample=True):
    """
    Load PNG/TIFF slice stack into a 3D numpy volume.

    Returns:
        volume (Z, Y, X)
        spacing (dz, dy, dx)
    """

    if not os.path.isdir(folder_path):
        raise ValueError(f"Folder does not exist: {folder_path}")

    files = sorted([
        f for f in os.listdir(folder_path)
        if f.lower().endswith((".png", ".tif", ".tiff"))
    ])

    if not files:
        raise ValueError("No image slices found in folder.")

    print(f"Loading {len(files)} CT slices...")
    
    slices = []
    for f in files:
        img = imageio.imread(os.path.join(folder_path, f))
        slices.append(img)

    volume = np.stack(slices, axis=0)  # shape (Z, Y, X)
 
    print("Original volume shape:", volume.shape)

    # Optional downsampling for performance
    if downsample:
        volume = volume[:, ::2, ::2]
        print("Downsampled volume shape:", volume.shape)

    return volume, spacing


# ===============================
# ------ CT → PYVISTA GRID ------
# ===============================

def ct_to_uniform_grid(volume, spacing):
    """
    Convert numpy volume (Z, Y, X) to PyVista UniformGrid.
    """

    z, y, x = volume.shape
    

    grid = pv.ImageData()

    # Dimensions must be (nx, ny, nz)
    grid.dimensions = (x, y, z)

    # Spacing must be (dx, dy, dz)
    grid.spacing = (spacing[2], spacing[1], spacing[0])

    grid.origin = (0.0, 0.0, 0.0)

    # Flatten in Fortran order
    grid.point_data["density"] = volume.flatten(order="F")

    return grid


# ===============================
# --------- MAIN VIEWER ---------
# ===============================

def main():

    # 🔹 xy plane - axial
    CT_FOLDER = r"C:\Users\PC\Downloads\battery_figshare_eg\Pouch\slices\2918\xy_images"

    # Load CT volume
    volume, spacing = load_ct_slice_stack(
        CT_FOLDER,
        spacing=(1.0, 1.0, 1.0),
        downsample=True
    )

       
    # new changes for making intensity better
    volume = volume.astype(np.float32)

    low = np.percentile(volume, 2)
    high = np.percentile(volume, 98)

    volume = np.clip(volume, low, high)
    volume = (volume - low) / (high - low)
    
    #slight gaussian smoothing to reduce noise
    volume = gaussian_filter(volume, sigma=0.5)

    # Convert to PyVista grid
    grid = ct_to_uniform_grid(volume, spacing)

    # Render volume
    plotter = pv.Plotter(window_size=(1200, 800))

    # opacity = [0.0, 0.0, 0.01, 0.03, 0.08, 0.2, 0.6, 1.0]
    #new opacity
    opacity = [0.0, 0.0, 0.02, 0.1, 0.3, 0.7, 1.0]

    plotter.add_volume(
        grid,
        scalars="density",
        cmap="gray",
        opacity=opacity,      # <-- used custom opacity
        shade=True,
        blending="composite",
        ambient=0.3,
        diffuse=0.8,
        specular=0.2
    )

    surface = grid.contour(isosurfaces=[0.4])

    plotter.add_mesh(surface, color="white", opacity=1.0)

    plotter.add_axes()
    plotter.add_text("CT Volume Rendering", font_size=14)

    # Optional: interactive clipping box
    plotter.add_box_widget(
        callback=lambda box: grid.clip_box(box, invert=False),
        use_planes=True
    )

    plotter.show()


# ===============================
# -------- ENTRY POINT ----------
# ===============================

if __name__ == "__main__":
    main()
