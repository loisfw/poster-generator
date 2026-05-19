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
# FONT SAFE LOAD (NO CRASHES)
# -----------------------

def load_font(size):
    try:
        return ImageFont.truetype("fonts/StackSansText-Regular.ttf", size)
    except:
        return ImageFont.load_default()

# -----------------------
# TEXT WRAP (IMPORTANT FIX FOR OVERFLOW)
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
# DESIGN TAB
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
# CREATE TAB
# -----------------------

with tab1:

    COLS = st.slider("Images per row", 3, 12, 8)

    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    image_files = st.file_uploader(
        "Upload Images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    generate = st.button("Generate Poster", key="generate_btn")

# -----------------------
# RENDER ENGINE
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

    # ---------------- TITLE ----------------
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

    # ---------------- DRAW CARDS ----------------
    for i, row in df.iterrows():

        x, y = positions[i]

        filename = str(row["filename"]).lower().strip()

        if filename in images_dict:
            img = images_dict[filename].resize((CARD_IMG_WIDTH, CARD_IMG_HEIGHT))
            poster.paste(img, (x, y))

        text_y = y + CARD_IMG_HEIGHT + 8

        # FULL NAME (WRAPPED FIX)
        for line in wrap_text(draw, row["fullname"], name_font, CARD_IMG_WIDTH):
            draw.text((x, text_y), line, fill=body_colour, font=name_font)
            text_y += 26

        text_y += 6  # spacing so it doesn't collide (your issue)

        draw.text((x, text_y), f"Tag: {row['tag']}", fill=body_colour, font=meta_font)
        text_y += 18

        draw.text((x, text_y), f"Missing: {row['missing_since']}", fill=body_colour, font=meta_font)
        text_y += 18

        draw.text((x, text_y), f"Location: {row['location']}", fill=body_colour, font=meta_font)
        text_y += 18

        draw.text((x, text_y), f"Age: {row['age']} | Sex: {row['sex']}", fill=body_colour, font=meta_font)
        text_y += 18

        # NOTES FIX (was previously inconsistent)
        notes = str(row.get("notes", "")).strip()
        if notes and notes.lower() != "nan":
            for line in wrap_text(draw, notes, meta_font, CARD_IMG_WIDTH):
                draw.text((x, text_y), line, fill=body_colour, font=meta_font)
                text_y += 16

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
# GENERATE + DOWNLOAD (FIXED RELIABILITY)
# -----------------------

if generate and preview is not None:

    png_buffer = BytesIO()
    pdf_buffer = BytesIO()

    preview.save(png_buffer, format="PNG")
    png_buffer.seek(0)

    preview.convert("RGB").save(pdf_buffer, format="PDF", resolution=300)
    pdf_buffer.seek(0)

    st.success("Poster generated")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "Download PNG",
            data=png_buffer,
            file_name="poster.png",
            mime="image/png"
        )

    with col2:
        st.download_button(
            "Download PDF",
            data=pdf_buffer,
            file_name="poster.pdf",
            mime="application/pdf"
        )

# -----------------------
# HELP TAB (RESTORED EXACT STYLE)
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
- filename → exact image file name (must match uploaded image)
- fullname → full name of the person
- tag → reference ID / label
- missing_since → date last seen
- location → last known location
- age → age
- sex → gender
- notes → case details (e.g. clothing, distinguishing features)

---

## ⚠️ Important rules
- Image filenames must match CSV exactly (case-insensitive)
- CSV must include all required fields or generation will fail
- Images must be uploaded separately
""")

    st.download_button(
        "Download CSV Template",
        data="""filename,fullname,tag,missing_since,location,age,sex,notes
example.png,Example Name,ID001,2025-01-01,London,12,Male,Blue jacket""",
        file_name="template.csv",
        mime="text/csv"
    )
