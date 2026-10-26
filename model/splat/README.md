# splat

**Path:** Gaussian splat (Captures-like appearance)  
**Status:** in-repo engine; train on CUDA (Colab)

This package lives in **this** git repository. Google Colab is only a GPU. Do not start a second project.

It does **not** replace the mesh path on your Mac. Those still produce `mesh.glb`. This path is the photoreal walkable output: COLMAP, undistorted frames, then 3D Gaussians.

The look of the room is decided when you film, before training. Captures Studio’s own routine is the reference: [Create 3D from smartphone video](https://www.captures.studio/blogs/how-to-create-3d-from-smartphone-video) and the [interactive capture tutorial](https://www.captures.studio/interactive-capture-tutorial). About five minutes, ultrawide, 4K if the phone has it, focus and exposure locked, then three slow loops of the same room (chest height, overhead looking down, knee height). A fast one-minute pan cannot become that result.

## On your Mac (no NVIDIA GPU)

```bash
python -m model.splat data/uploads/your_room.mp4 --job-id room_splat --prepare-only
```

That writes `data/frames/<job>/splat/images/`.

## On Colab (GPU runtime)

Open `notebooks/colab_gaussian_splat.ipynb` **from this repo**. The notebook clones or uploads **this** repository and runs:

```bash
python -m model.splat /content/your_room.mp4 --job-id room_splat
```

Download `data/frames/<job>/splat/point_cloud.ply` and open it with `ui/splat_viewer.html`.

## Outputs

| Artifact | Location |
|----------|----------|
| Training images | `data/frames/<job>/splat/images/` |
| COLMAP TXT | `data/frames/<job>/splat/colmap/sparse_txt/` |
| Splat PLY | `data/frames/<job>/splat/point_cloud.ply` |
| Manifest | `data/frames/<job>/splat/splat.json` |
