import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# -----------------------
# APP SETUP
# -----------------------

st.set_page_config(page_title="Poster Generator", layout="wide")
st.title("Poster Generator")

CARD_IMG_WIDTH = 260
CARD_IMG_HEIGHT = 330
TEXT_AREA_HEIGHT = 240
PADDING = 18

tab1, tab2, tab3 = st.tabs(["Create Poster", "Design", "Help"])

# -----------------------
# SESSION STATE
# -----------------------

if "png" not in st.session_state:
    st.session_state.png = None

if "pdf" not in st.session_state:
    st.session_state.pdf = None

if "generated" not in st.session_state:
    st.session_state.generated = False

# -----------------------
# FONT
# -----------------------

def load_font(size):
    try:
        return ImageFont.truetype("fonts/StackSansText-Regular.ttf", size)
    except:
        return ImageFont.load_default()

# -----------------------
# TEXT WRAP
# -----------------------

def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for w in words:
        test = f"{current} {w}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w

    if current:
        lines.append(current)

    return lines

# -----------------------
# DESIGN
# -----------------------

with tab2:
    st.subheader("Design Settings")

    title_colour = st.color_picker("Title colour", "#111111")
    body_colour = st.color_picker("Text colour (cards)", "#000000")

    show_title = st.checkbox("Show title", True)

    title_text = "MISSING PERSONS NOTICE"
    subtitle_text = ""
    title_size = st.slider("Title size", 20, 120, 60)

    if show_title:
        title_text = st.text_input("Title", title_text)
        subtitle_text = st.text_input("Subtitle", "")

    text_scale = st.slider("Text size", 0.7, 1.5, 1.0)

# -----------------------
# CREATE
# -----------------------

with tab1:

    COLS = st.slider("Images per row", 3, 12, 8)

    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    image_files = st.file_uploader(
        "Upload Images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    generate = st.button("Generate Poster")

# -----------------------
# RENDER ENGINE (FIXED OVERFLOW)
# -----------------------

def render(df, images_dict):

    rows = (len(df) + COLS - 1) // COLS

    width = COLS * (CARD_IMG_WIDTH + PADDING) + PADDING
    height = rows * (CARD_IMG_HEIGHT + TEXT_AREA_HEIGHT + PADDING) + 500

    poster = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(poster)

    title_font = load_font(int(title_size * text_scale))
    name_font = load_font(int(26 * text_scale))
    meta_font = load_font(int(16 * text_scale))

    y_offset = 40

    if show_title:
        w = draw.textlength(title_text, font=title_font)
        draw.text(((width - w) / 2, y_offset), title_text, fill=title_colour, font=title_font)
        y_offset += 120

    positions = {}

    for i in range(len(df)):
        col = i % COLS
        row = i // COLS

        x = PADDING + col * (CARD_IMG_WIDTH + PADDING)
        y = y_offset + PADDING + row * (CARD_IMG_HEIGHT + TEXT_AREA_HEIGHT + PADDING)

        positions[i] = (x, y)

    for i, row in df.iterrows():

        x, y = positions[i]

        filename = str(row["filename"]).lower().strip()

        if filename in images_dict:
            img = images_dict[filename].resize((CARD_IMG_WIDTH, CARD_IMG_HEIGHT))
            poster.paste(img, (x, y))

        # -----------------------
        # CLIPPING BOX (KEY FIX)
        # -----------------------
        max_text_height = TEXT_AREA_HEIGHT - 10
        text_y = y + CARD_IMG_HEIGHT + 8
        start_y = text_y

        def safe_draw(text, font, step):
            nonlocal text_y
            if text_y - start_y > max_text_height:
                return
            draw.text((x, text_y), text, fill=body_colour, font=font)
            text_y += step

        # NAME (slightly larger + spacing fix)
        for line in wrap_text(draw, row["fullname"], name_font, CARD_IMG_WIDTH):
            safe_draw(line, name_font, 26)

        text_y += 6  # extra breathing room

        safe_draw(f"Tag: {row['tag']}", meta_font, 18)
        safe_draw(f"Missing: {row['missing_since']}", meta_font, 18)
        safe_draw(f"Location: {row['location']}", meta_font, 18)
        safe_draw(f"Age: {row['age']} | Sex: {row['sex']}", meta_font, 18)

        notes = str(row.get("notes", "")).strip()
        if notes and notes.lower() != "nan":
            for line in wrap_text(draw, notes, meta_font, CARD_IMG_WIDTH):
                safe_draw(line, meta_font, 16)

    return poster

# -----------------------
# LOAD DATA
# -----------------------

preview = None

if csv_file and image_files:

    df = pd.read_csv(csv_file)

    images_dict = {
        img.name.lower().strip(): Image.open(img).convert("RGB")
        for img in image_files
    }

    preview = render(df, images_dict)

    st.subheader("Live Preview")
    st.image(preview)

# -----------------------
# GENERATE + DOWNLOADS (FIXED)
# -----------------------

if generate and preview is not None:

    png_buffer = BytesIO()
    pdf_buffer = BytesIO()

    preview.save(png_buffer, format="PNG")
    png_buffer.seek(0)

    preview.convert("RGB").save(pdf_buffer, format="PDF", resolution=300)
    pdf_buffer.seek(0)

    st.session_state.png = png_buffer
    st.session_state.pdf = pdf_buffer
    st.session_state.generated = True

    st.success("Poster generated")

# ALWAYS SHOW DOWNLOADS WHEN READY
if st.session_state.generated:

    st.download_button(
        "Download PNG",
        data=st.session_state.png,
        file_name="poster.png",
        mime="image/png"
    )

    st.download_button(
        "Download PDF",
        data=st.session_state.pdf,
        file_name="poster.pdf",
        mime="application/pdf"
    )

# -----------------------
# HELP TAB (UNCHANGED)
# -----------------------

with tab3:

    st.markdown("""
## 📘 How to use this tool

This tool generates structured posters from a CSV file and uploaded images.

### Steps:
1. Upload CSV
2. Upload images
3. Adjust settings
4. Generate poster
5. Download PNG or PDF

---

## 📄 Required CSV fields
Each row represents ONE person.

Required fields:
- filename → exact image file name
- fullname → full name
- tag → reference ID
- missing_since → last seen
- location → last known location
- age → age
- sex → gender
- notes → optional case details

---

## ⚠️ Important rules
- filenames must match images exactly
- CSV must include required fields
- images uploaded separately
""")

    st.download_button(
        "Download CSV Template",
        data="filename,fullname,tag,missing_since,location,age,sex,notes\nexample.png,Example Name,ID001,2025-01-01,London,12,Male,Blue jacket",
        file_name="template.csv",
        mime="text/csv"
    )
