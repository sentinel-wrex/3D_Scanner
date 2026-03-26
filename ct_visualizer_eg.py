from ct_loader import CTLoader
import matplotlib.pyplot as plt

ct = CTLoader.load_slice_stack(
    folder_path=r"C:\Users\PC\Downloads\battery_figshare_eg\Pouch\slices\2929\xy_images",
    spacing=(1.0, 1.0, 1.0),   # placeholder
    orientation="xy"
)

print("CT volume shape:", ct.shape)
print("Orientation:", ct.orientation)

z = ct.shape[0] // 2
plt.imshow(ct.volume[z], cmap="gray")
plt.title("Middle axial slice")
plt.axis("off")
plt.show()