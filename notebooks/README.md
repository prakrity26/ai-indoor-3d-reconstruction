# notebooks

Colab notebooks for GPU work. They **clone this same GitHub repository**. There is no second project.

| File | Use |
|------|-----|
| `colab_gpu_worker.ipynb` | **Recommended.** Turns a Colab GPU into a worker for the platform: picks up queued splat jobs through the worker gateway, trains them with Nerfstudio splatfacto, uploads the result. See the root README, *Photoreal splats on a GPU*. |
| `colab_splatfacto_img7916.ipynb` | One-off splatfacto training of the IMG_7916 clip from Google Drive (manual download). |
| `colab_gaussian_splat.ipynb` | One-off training with the in-repo COLMAP + gsplat trainer (manual upload/download). |

Open in Colab: File → Open notebook → GitHub → `prakrity26/ai-indoor-3d-reconstruction`, then pick the notebook. Choose a GPU runtime first.
