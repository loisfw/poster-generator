import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import os
import tempfile
import io

# -----------------------
# APP SETUP
# -----------------------

st.set_page_config(page_title="Poster Generator", layout="wide")
st.title("Poster Generator")

CARD_IMG_WIDTH = 260
CARD_IMG_HEIGHT = 330
TEXT_AREA_HEIGHT = 220
PADDING = 18

DEFAULT_FONT = "/System/Library/Fonts/Helvetica.ttc"

tab1, tab2, tab3 = st.tabs(["Create Poster", "Design", "Help"])

# -----------------------
# HELPERS
# -----------------------

def load_font(size):
    if font_file is not None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ttf")
        tmp.write(font_file.read())
        tmp.close()
        return ImageFont.truetype(tmp.name, size)
    return ImageFont.truetype(DEFAULT_FONT, size)


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
# TAB 2 - DESIGN
# -----------------------

with tab2:

    st.subheader("Design Settings")

    title_colour = st.color_picker("Title colour", "#111111")
    body_colour = st.color_picker("Text colour (cards)", "#000000")

    show_title = st.checkbox("Show title", value=True)

    title_text = "MISSING PERSONS NOTICE"
    subtitle_text = ""
    title_size = 60

    if show_title:
        title_text = st.text_input("Title", title_text)
        subtitle_text = st.text_input("Subtitle (optional)", "")
        title_size = st.slider("Title size", 20, 120, 60)

    text_scale = st.slider("Text size (overall scaling)", 0.7, 1.5, 1.0)

    font_file = st.file_uploader("Upload .ttf / .otf font", type=["ttf", "otf"])

# -----------------------
# TAB 1
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
# CORE RENDER ENGINE
# -----------------------

def render(df, images_dict):

    df = df.copy()

    if "group_id" not in df.columns:
        df["group_id"] = ""

    df["group_id"] = df["group_id"].fillna("").astype(str)

    empty = df["group_id"].str.strip() == ""
    df.loc[empty, "group_id"] = "single_" + df.index[empty].astype(str)

    rows = (len(df) + COLS - 1) // COLS

    width = COLS * (CARD_IMG_WIDTH + PADDING) + PADDING
    height = rows * (CARD_IMG_HEIGHT + TEXT_AREA_HEIGHT + PADDING) + PADDING + 400

    poster = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(poster)

    title_font = load_font(int(title_size * text_scale))
    name_font = load_font(int(22 * text_scale))
    body_font = load_font(int(16 * text_scale))

    y_offset = 40

    if show_title:
        w = draw.textlength(title_text, font=title_font)
        draw.text(((width - w) / 2, y_offset), title_text, fill=title_colour, font=title_font)
        y_offset += 120

        if subtitle_text:
            sub_font = load_font(int(28 * text_scale))
            sw = draw.textlength(subtitle_text, font=sub_font)
            draw.text(((width - sw) / 2, y_offset - 50), subtitle_text, fill=title_colour, font=sub_font)

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

        text_y = y + CARD_IMG_HEIGHT + 6

        # NAME
        for line in wrap_text(draw, row["fullname"], name_font, CARD_IMG_WIDTH):
            draw.text((x, text_y), line, fill=body_colour, font=name_font)
            text_y += 24

        # DETAILS (SPACED + READABLE)
        draw.text((x, text_y), f"Tag: {row['tag']}", fill=body_colour, font=body_font)
        text_y += 22

        draw.text((x, text_y), f"Missing: {row['missing_since']}", fill=body_colour, font=body_font)
        text_y += 22

        draw.text((x, text_y), f"Location: {row['location']}", fill=body_colour, font=body_font)
        text_y += 22

        draw.text((x, text_y), f"Age: {row['age']}", fill=body_colour, font=body_font)
        text_y += 22

        draw.text((x, text_y), f"Sex: {row['sex']}", fill=body_colour, font=body_font)
        text_y += 26

        # NOTES (FIXED - NEVER DROPS NOW)
        notes_text = row.get("notes", "")

        if pd.notna(notes_text):
            notes_text = str(notes_text).strip()

            if notes_text and notes_text.lower() != "nan":
                for line in wrap_text(draw, notes_text, body_font, CARD_IMG_WIDTH):
                    draw.text((x, text_y), line, fill=body_colour, font=body_font)
                    text_y += 18

    return poster

# -----------------------
# LOAD + OUTPUT
# -----------------------

if csv_file and image_files:

    df = pd.read_csv(csv_file)

    images_dict = {
        img.name.lower().strip(): Image.open(img).convert("RGB")
        for img in image_files
    }

    preview = render(df, images_dict)

    with tab1:
        st.subheader("Live Preview")
        st.image(preview)

    with tab2:
        st.subheader("Live Preview")
        st.image(preview)

    # -----------------------
    # DOWNLOADS (FIXED)
    # -----------------------

    png_buffer = io.BytesIO()
    pdf_buffer = io.BytesIO()

    preview.save(png_buffer, format="PNG")
    png_buffer.seek(0)

    preview.convert("RGB").save(pdf_buffer, format="PDF", resolution=300)
    pdf_buffer.seek(0)

    with tab1:

        if generate:
            st.success("Poster generated!")

        st.download_button(
            "Download PNG",
            data=png_buffer,
            file_name="poster.png",
            mime="image/png"
        )

        st.download_button(
            "Download PDF",
            data=pdf_buffer,
            file_name="poster.pdf",
            mime="application/pdf"
        )

# -----------------------
# HELP TAB (UNCHANGED EXACTLY)
# -----------------------

with tab3:

    st.markdown("""
## 📘 How to use this tool

This tool generates structured posters from a CSV file and uploaded images.

### Steps:
1. Upload your CSV file
2. Upload matching images
3. Adjust design settings
4. Preview updates instantly
5. Click “Generate Poster” for final export

---

## 📄 Required CSV fields

Each row represents ONE person.

### Required fields:
- filename → exact image file name (must match uploaded image)
- fullname → full name of the person
- tag → reference ID / label
- missing_since → date last seen
- location → last known location
- age → age
- sex → gender
- notes → case details (e.g. clothing, distinguishing features)

---

## 👥 Grouping (data only, optional)

- group_id = logical grouping only (not visual)
- group_note = optional shared context (not displayed unless needed in export logic)

---

## ⚠️ Important rules

- Image filenames must match CSV exactly (case-insensitive)
- CSV must include all required fields or generation will fail
- Images must be uploaded separately
- Grouping is optional and does not affect layout
""")

    st.download_button(
        "Download CSV Template",
        """filename,fullname,tag,missing_since,location,age,sex,notes,group_id,group_note
matthewb.png,Matthew B,NCIC#001,2025-06-02,Atlanta,12,Male,Believed to be wearing dark hoodie,group_1,These individuals are believed to be travelling together.
zara.png,Zara L,NCIC#002,2025-06-02,Atlanta,10,Female,Believed to be wearing pink jacket,group_1,These individuals are believed to be travelling together.
nadine.png,Nadine Lindo,NCIC#003,2025-06-02,Atlanta,34,Female,No additional details available,group_1,These individuals are believed to be travelling together.
solo.png,Example Solo,NCIC#004,2025-06-01,Atlanta,17,Male,Believed to be wearing red coat,,
pair1.png,Example Pair A,NCIC#005,2025-06-01,Atlanta,16,Female,Last seen near station,group_2,Pair travelling together.
pair2.png,Example Pair B,NCIC#006,2025-06-01,Atlanta,16,Male,Last seen near station,group_2,Pair travelling together.
""",
        file_name="template.csv"
    )
