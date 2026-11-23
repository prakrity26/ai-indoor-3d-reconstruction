# ui

The product page is the interactive studio served by the API. The scene fills the screen. Orbit turns the mesh. Walk moves through a splat with W A S D. Streamlit is a second client that calls the same API.

**Phase:** 13  
**Status:** studio page and Streamlit client

Neither client imports `model/` or runs reconstruction.

```bash
pip install -e ".[api]"
python -m api
```

Open http://127.0.0.1:8000/. The sample mesh has an Orbit button. Walk appears after a splat file exists.

Streamlit, against that API:

```bash
pip install -e ".[ui]"
streamlit run ui/app.py
```

`API_URL` defaults to http://127.0.0.1:8000.

Local previews that do not use the API:

```bash
python -m ui.demo --job-id img7916
python -m ui.splat_demo --job-id img7916
```
