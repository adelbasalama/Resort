"""Run with: streamlit run app.py"""
import hashlib
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st

from waste_sorting.config import Settings
from waste_sorting.models import Feedback
from waste_sorting.services.clients import HttpGuidanceClient, HttpRecognitionClient, ServiceError
from waste_sorting.services.demo import DemoGuidanceClient, DemoRecognitionClient, SAMPLES
from waste_sorting.storage import Repository
from waste_sorting.ui import bottom_sections, html, result_view, sample_image, scene, setup_page
from waste_sorting.uploads import ImageUpload, UploadError
from waste_sorting.workflow import SortCoordinator


@st.cache_resource
def resources(settings):
    repository = Repository(settings.database_path)
    if settings.mode == "demo":
        return repository, DemoGuidanceClient()
    return repository, HttpGuidanceClient(settings.guidance_url, settings.guidance_key, settings.guidance_timeout)


@st.cache_data(ttl=300, show_spinner=False)
def load_regions(settings):
    return resources(settings)[1].regions()


def reset():
    for key in ["result", "fingerprint", "request_id", "feedback_saved"]:
        st.session_state.pop(key, None)
    st.session_state["upload_version"] = st.session_state.get("upload_version", 0) + 1


def main():
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        st.set_page_config(page_title="ReSort · Configuration")
        st.error(str(exc))
        st.stop()
    setup_page(settings.mode)
    try:
        repository, guidance = resources(settings)
        regions = load_regions(settings)
    except ServiceError as exc:
        st.error(str(exc))
        if st.button("Reload regions"):
            load_regions.clear()
            st.rerun()
        st.stop()
    except (OSError, sqlite3.Error):
        st.error("Storage could not be opened. Check DATABASE_PATH and folder permissions.")
        st.stop()

    left, right = st.columns([1.08, 1], gap="large")
    with right:
        scene()
    with left:
        with st.container(border=True, key="sort_card"):
            result = st.session_state.get("result")
            if result:
                region_name = next((r.name for r in regions if r.id == result.region_id), result.region_id)
                result_view(result, region_name)
                if result.status == "completed":
                    st.divider()
                    st.markdown("**Was this helpful?**")
                    yes, no = st.columns(2)
                    for column, label, value in [(yes, "Yes, thank you", True), (no, "Not quite", False)]:
                        with column:
                            if st.button(label, use_container_width=True):
                                try:
                                    repository.save_feedback(Feedback(submission_id=result.id, helpful=value))
                                    st.session_state.feedback_saved = True
                                except (OSError, sqlite3.Error, ValueError):
                                    st.error("Feedback could not be saved. Please try again.")
                    if st.session_state.get("feedback_saved"):
                        st.success("Thanks. Your feedback has been saved.")
                    st.download_button("Download result", result.model_dump_json(indent=2),
                        file_name=f"resort-{result.id[:8]}.json", mime="application/json", use_container_width=True)
                st.button("↻  Sort another item", type="primary", use_container_width=True, on_click=reset)
            else:
                html('''<div class="card-kicker">YOUR NEXT SMALL GOOD THING</div>
                    <div class="card-title">Let's sort it out.</div>
                    <div class="card-copy">One photo. Your city. A clearer next step.</div>''')
                mode = st.radio("Choose your photo source", ["Upload a photo", "Try an example"],
                    horizontal=True, label_visibility="collapsed", key="source_mode")
                region = st.selectbox("Where are you sorting?", regions, format_func=lambda r: r.name,
                    help="Local guidance comes from the regional rules service.", key="region")
                image = None
                sample_key = None
                if mode == "Try an example":
                    sample_key = st.selectbox("Pick an illustrated item", list(SAMPLES),
                        format_func=lambda k: SAMPLES[k]["name"], key="sample")
                    image = ImageUpload(sample_image(sample_key), f"{sample_key}.png")
                    st.image(image.content, caption="Illustrated sample · not a real photo", width=300)
                    if settings.mode != "demo":
                        st.caption("This example uses demo fixtures. Switch to Upload a photo for connected services.")
                else:
                    uploaded = st.file_uploader("Add a photo of your item", type=["jpg", "jpeg", "png"],
                        key=f"photo_{st.session_state.get('upload_version', 0)}",
                        help="JPG or PNG, up to 10 MB. One item per photo.")
                    if uploaded:
                        image = ImageUpload(uploaded.getvalue(), uploaded.name)
                        try:
                            image.validate()
                            st.image(image.content, caption="Your photo · ready for a closer look", width=300)
                        except UploadError as exc:
                            st.error(str(exc))
                            image = None
                    st.caption("JPG, JPEG or PNG · Maximum 10 MB · One item at a time")
                if settings.mode == "demo":
                    st.caption("Demo mode: try an example to explore results. Uploaded photos need a connected recognition service.")
                if st.button("Find the right place  →", type="primary", use_container_width=True,
                             disabled=image is None):
                    fingerprint = hashlib.sha256(image.content + region.id.encode() + str(sample_key).encode()).hexdigest()
                    if st.session_state.get("fingerprint") != fingerprint:
                        st.session_state.fingerprint = fingerprint
                        st.session_state.request_id = str(uuid4())
                    is_demo = settings.mode == "demo" or sample_key is not None
                    recognition = DemoRecognitionClient(sample_key) if is_demo else HttpRecognitionClient(
                        settings.recognition_url, settings.recognition_key, settings.recognition_timeout)
                    coordinator = SortCoordinator(repository, recognition,
                        DemoGuidanceClient() if is_demo else guidance, is_demo=is_demo)
                    try:
                        with st.spinner("Taking a closer look and checking the next step…"):
                            st.session_state.result = coordinator.identify(image, region.id, st.session_state.request_id)
                        st.rerun()
                    except UploadError as exc:
                        st.error(str(exc))
                    except (OSError, sqlite3.Error):
                        st.error("The result could not be saved. Check storage and try again.")
                html('<div class="privacy">⌑ &nbsp; Your photo stays in memory. Never saved to disk.</div>')
    bottom_sections()


if __name__ == "__main__":
    main()
