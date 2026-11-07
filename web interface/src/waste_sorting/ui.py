import base64
import io
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw
import streamlit as st

from .services.demo import SAMPLES

ROOT = Path(__file__).resolve().parents[2]


def html(value):
    st.html(value)


def setup_page(mode):
    st.set_page_config(page_title="ReSort · A little clarity. A greener day.", page_icon="♻", layout="wide")
    html("<style>" + (ROOT / "assets/styles.css").read_text(encoding="utf-8") + "</style>")
    badge = "INTERACTIVE DEMO" if mode == "demo" else "CONNECTED SERVICES"
    html(f'''<div class="topbar"><div class="brand"><div class="brand-mark">♧</div><div>Re<span>Sort</span></div></div>
        <nav class="nav" aria-label="Main navigation"><a href="#sort-your-waste">Sort your waste</a>
        <a href="#how-it-works">How it works</a><a href="#good-to-know">Good to know</a>
        <span class="demo-badge">● &nbsp; {badge}</span></nav></div>
        <div class="hero" id="sort-your-waste"><div class="eyebrow">LESS GUESSWORK. MORE GOOD.</div>
        <h1>A little clarity.<br><span>A greener day.</span></h1>
        <p>Not sure where it goes? Snap a photo, choose your city,<br class="desktop-break"> and give your waste the right next chapter.</p></div>''')


def scene():
    svg = base64.b64encode((ROOT / "assets/sorting-scene.svg").read_bytes()).decode()
    html(f'''<div class="scene"><img alt="Illustration of a recyclable green drink can surrounded by leaves"
        src="data:image/svg+xml;base64,{svg}"></div>
        <div class="scene-caption"><span>A small step for you.</span><span>A lighter footprint for all.</span></div>
        <div class="tip"><span class="tip-icon" aria-hidden="true">✧</span><div><strong>A better photo, a better start.</strong>
        <p>One item. Good lighting. A clear background.<br>Keep labels visible and the whole item in frame.</p></div></div>''')


@st.cache_data(show_spinner=False)
def sample_image(key):
    image = Image.new("RGB", (640, 400), "#eaf0e5")
    draw = ImageDraw.Draw(image)
    draw.ellipse((180, 340, 460, 365), fill="#d3dfca")
    if key == "can":
        draw.rounded_rectangle((250, 65, 390, 345), radius=28, fill="#4e8a68")
        draw.ellipse((250, 65, 390, 99), fill="#c6d4c7")
        draw.ellipse((292, 73, 348, 89), fill="#8ba694")
        draw.line((280, 254, 360, 254), fill="#c6d4c7", width=5)
        draw.line((290, 274, 350, 274), fill="#c6d4c7", width=5)
    elif key == "paper":
        draw.rounded_rectangle((240, 140, 400, 345), radius=5, fill="#c5a677")
        draw.arc((275, 70, 365, 200), 180, 360, fill="#8f7650", width=12)
        draw.line((260, 168, 380, 168), fill="#a98a5c", width=4)
    else:
        draw.rounded_rectangle((292, 52, 348, 180), radius=12, fill="#72a390")
        draw.rounded_rectangle((260, 150, 380, 345), radius=35, fill="#72a390")
        draw.rectangle((291, 50, 349, 70), fill="#466d59")
        draw.rounded_rectangle((274, 215, 366, 290), radius=5, fill="#ecedce")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def result_view(result, region_name):
    if result.status == "processing":
        st.info("This request is already being processed. Please wait for it to finish.")
        return
    if result.status == "failed":
        st.error(result.error or "Something went wrong. Please try again.")
        return
    recognition = result.recognition
    if result.status in {"uncertain", "unsupported"}:
        st.warning("We need a little more clarity" if result.status == "uncertain" else "This item is not supported yet")
        st.write("Demo mode cannot identify uploaded photos. Try an illustrated example, or connect the recognition service."
                 if result.is_demo else "Try a closer, well-lit photo of one item. If it might be a battery or electronics, ask your local waste provider before disposal.")
        return
    guidance = result.guidance
    html(f'''<div class="result-heading">{'EXAMPLE RESULT' if result.is_demo else 'YOUR SORTING RESULT'}</div>
        <div class="result-name">{escape(recognition.item_name)}</div>''')
    st.caption(f"{recognition.material} · {recognition.condition.capitalize()} · {region_name}")
    st.caption(f"Waste category: {guidance.category}")
    if recognition.predicted_category != "unknown":
        st.caption(f"AI predicted category: {recognition.predicted_category} · Final category follows local rules.")
    if result.is_demo:
        st.info("Demonstration result: this uses an illustrated item or example regional rules. Disposal advice is not verified locally.")
    elif recognition.special or guidance.status == "special":
        st.warning("Special handling required. Follow your local provider's instructions.")
    elif guidance.status == "missing_rule":
        st.warning("No verified local rule was found. Confirm disposal with your local provider.")
    if result.is_demo or guidance.status in {"matched", "special"}:
        html(f'''<div class="result-bin"><small>{'EXAMPLE COLLECTION' if result.is_demo else 'RECOMMENDED DISPOSAL'}</small>
            <strong>{escape(guidance.bin_label)}</strong></div>''')
        st.markdown("**Before you let it go**")
        for index, step in enumerate(guidance.preparation_steps, start=1):
            st.write(f"{index}. {step}")
    with st.expander("Why this recommendation?"):
        st.write(guidance.explanation)
        if guidance.source_url:
            st.link_button("View official source ↗", str(guidance.source_url))
        if guidance.reviewed_at:
            st.caption(f"Reviewed {guidance.reviewed_at} · Rule version {guidance.rule_version}")
        if guidance.is_fallback:
            st.caption("Approved fallback explanation supplied by the regional service.")
    confidence_label = "Recognition confidence (demo outcome)" if result.is_demo else "Recognition confidence"
    st.caption(f"{confidence_label}: {recognition.confidence:.0%} · Reference {result.id[:8]}")


def bottom_sections():
    html('''<div class="section-heading" id="how-it-works"><h2>Good habits start with simple steps.</h2>
        <span>FROM A PHOTO TO THE RIGHT PLACE</span></div>''')
    steps = [("01", "Show us your item", "Upload a clear photo of one waste item. A little detail goes a long way."),
             ("02", "Make it local", "Choose your city. Recycling rules can change from one place to the next."),
             ("03", "Sort with confidence", "Get a clear next step, preparation tips and the reasoning behind them.")]
    for column, (number, title, text) in zip(st.columns(3), steps):
        with column:
            html(f'<div class="step"><div class="step-number">{number}</div><div><h3>{title}</h3><p>{text}</p></div></div>')
    html('<div id="good-to-know" style="height:22px"></div>')
    with st.expander("Good to know · photos, privacy & local rules"):
        st.write("Photos stay in memory and are sent only to the configured recognition service when you submit. "
                 "This app saves submission metadata, sorting outcomes and optional feedback, never your photo or filename. "
                 "In demo mode no external service receives your photo. Your hosting provider and service operators must configure their own retention policies.")
        st.write("Results depend on photo quality and the available local rules. Uncertain items need another photo. "
                 "Batteries, electronics and other hazardous waste require special handling. Demo examples are not verified regional rules.")
    html('''<div class="footer"><span>ReSort &nbsp; / &nbsp; A better place for every piece.</span>
        <span>Built for everyday choices. Designed for a better tomorrow.</span></div>''')
