"""Streamlit client. It talks only to the API and does not run reconstruction."""

from __future__ import annotations

import os

from ui.board import describe


def render() -> None:
    import httpx
    import streamlit as st

    api = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")
    st.set_page_config(page_title="Indoor scenes", layout="centered")
    st.title("Indoor scenes")
    st.link_button("Open the interactive studio", f"{api}/")
    st.caption("Uploads go to the API. The GPU worker trains them. Distances are relative, not metres.")

    uploaded = st.file_uploader("Indoor video", type=["mp4", "mov", "avi", "mkv", "webm", "m4v"])
    if uploaded is not None and st.button("Upload"):
        try:
            response = httpx.post(
                f"{api}/jobs",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "video/mp4")},
                timeout=120.0,
            )
        except httpx.HTTPError as exc:
            st.error(f"The API is not reachable at {api}. Start it with python -m api. {exc}")
            return
        if response.status_code >= 400:
            detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else response.text
            st.error(str(detail or "Upload failed."))
        else:
            body = response.json()
            st.success(f"{body['filename']} is queued as {body['job_id']}.")

    try:
        listing = httpx.get(f"{api}/jobs", timeout=10.0)
        listing.raise_for_status()
        jobs = listing.json().get("jobs") or []
    except httpx.HTTPError as exc:
        st.error(f"The API is not reachable at {api}. Start it with python -m api. {exc}")
        return

    if not jobs:
        st.info("No scenes yet.")
        return

    for job in jobs:
        st.subheader(job.get("filename") or job.get("job_id"))
        st.write(describe(job))
        if job.get("error"):
            st.error(job["error"])
        columns = st.columns(2)
        if job.get("mesh_url"):
            columns[0].link_button("Orbit mesh", f"{api}/orbit?mesh={job['mesh_url']}")
        if job.get("splat_url"):
            columns[1].link_button("Walk splat", f"{api}/viewer?ply={job['splat_url']}")
        summary = job.get("summary") or {}
        if summary:
            st.json(summary)


if __name__ == "__main__":
    render()
