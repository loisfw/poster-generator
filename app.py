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
# SESSION STATE (LOCKED)
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
# WRAP TEXT
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

    generate = st.button("Generate Poster")

# -----------------------
# HELPERS
# -----------------------

def is_wide_image(img):
    """True if image is significantly wider than a portrait card (i.e. two photos stitched)."""
    src_ratio = img.size[0] / img.size[1]
    card_ratio = CARD_IMG_WIDTH / CARD_IMG_HEIGHT
    return src_ratio > card_ratio + 0.2


def place_image(poster, img, x, y, card_w):
    """
    Paste img into the poster at (x, y) fitting exactly card_w x CARD_IMG_HEIGHT.
    - Wide images (two photos): scale to fit height, both faces fully visible,
      centred on white background.
    - Portrait/square: scale to fill, centre-crop (no distortion).
    """
    src_w, src_h = img.size

    if is_wide_image(img):
        # Scale so height matches card height exactly — width may be less than card_w
        scale = CARD_IMG_HEIGHT / src_h
        scaled_w = int(src_w * scale)
        scaled_h = CARD_IMG_HEIGHT
        img_resized = img.resize((scaled_w, scaled_h), Image.LANCZOS)
        # Place on white background, centred horizontally
        card = Image.new("RGB", (card_w, CARD_IMG_HEIGHT), "white")
        paste_x = (card_w - scaled_w) // 2
        card.paste(img_resized, (paste_x, 0))
        poster.paste(card, (x, y))
    else:
        # Scale to fill card, centre-crop — no distortion
        scale = max(card_w / src_w, CARD_IMG_HEIGHT / src_h)
        scaled_w = int(src_w * scale)
        scaled_h = int(src_h * scale)
        img_resized = img.resize((scaled_w, scaled_h), Image.LANCZOS)
        crop_x = (scaled_w - card_w) // 2
        crop_y = (scaled_h - CARD_IMG_HEIGHT) // 2
        img_cropped = img_resized.crop((crop_x, crop_y, crop_x + card_w, crop_y + CARD_IMG_HEIGHT))
        poster.paste(img_cropped, (x, y))


# -----------------------
# RENDER ENGINE
# -----------------------

def render(df, images_dict):

    title_font = load_font(int(title_size * text_scale))
    name_font  = load_font(int(26 * text_scale))
    meta_font  = load_font(int(16 * text_scale))

    # ------------------------------------------------------------------
    # PASS 1: work out card width and x position for every entry.
    # Two-photo cards get double width (2 * CARD_IMG_WIDTH + PADDING)
    # so both faces are always fully visible.
    # We lay cards out row by row, never exceeding the poster width.
    # ------------------------------------------------------------------

    poster_width = COLS * (CARD_IMG_WIDTH + PADDING) + PADDING

    card_widths = []
    for _, row in df.iterrows():
        filename = str(row["filename"]).lower().strip()
        img = images_dict.get(filename)
        if img and is_wide_image(img):
            card_widths.append(CARD_IMG_WIDTH * 2 + PADDING)  # double-wide
        else:
            card_widths.append(CARD_IMG_WIDTH)

    # Layout: pack cards left-to-right; start new row when full
    y_offset = 40
    if show_title:
        y_offset += 120

    positions  = []   # (x, y, card_w) per entry
    row_x      = PADDING
    row_y      = y_offset + PADDING
    row_height = CARD_IMG_HEIGHT + TEXT_AREA_HEIGHT + PADDING

    for card_w in card_widths:
        # If this card doesn't fit on the current row, wrap
        if row_x + card_w > poster_width - PADDING and row_x > PADDING:
            row_x  = PADDING
            row_y += row_height

        positions.append((row_x, row_y, card_w))
        row_x += card_w + PADDING

    total_rows = (row_y - (y_offset + PADDING)) // row_height + 1
    poster_height = y_offset + PADDING + total_rows * row_height + 200

    poster = Image.new("RGB", (poster_width, poster_height), "white")
    draw   = ImageDraw.Draw(poster)

    # Title
    if show_title:
        w = draw.textlength(title_text, font=title_font)
        draw.text(((poster_width - w) / 2, 40), title_text, fill=title_colour, font=title_font)

    # ------------------------------------------------------------------
    # PASS 2: draw each card
    # ------------------------------------------------------------------

    for i, (_, row) in enumerate(df.iterrows()):
        x, y, card_w = positions[i]
        filename = str(row["filename"]).lower().strip()

        if filename in images_dict:
            place_image(poster, images_dict[filename], x, y, card_w)

        text_y       = y + CARD_IMG_HEIGHT + 8
        max_text_bot = y + CARD_IMG_HEIGHT + TEXT_AREA_HEIGHT
        wide         = card_w > CARD_IMG_WIDTH  # True for two-photo cards

        def draw_line_centred(text, font, line_h):
            """Draw text centred across the full card width."""
            nonlocal text_y
            if text_y + line_h > max_text_bot:
                return False
            tw = draw.textlength(text, font=font)
            tx = x + (card_w - tw) // 2
            draw.text((tx, text_y), text, fill=body_colour, font=font)
            text_y += line_h
            return True

        def draw_line_left(text, font, line_h):
            """Draw text left-aligned."""
            nonlocal text_y
            if text_y + line_h > max_text_bot:
                return False
            draw.text((x, text_y), text, fill=body_colour, font=font)
            text_y += line_h
            return True

        draw_line = draw_line_centred if wide else draw_line_left

        # For two-photo cards, add a clear banner so viewers know it's one person
        if wide:
            banner = "— Both photos are of the same person —"
            bw = draw.textlength(banner, font=meta_font)
            bx = x + (card_w - bw) // 2
            draw.text((bx, text_y), banner, fill="#888888", font=meta_font)
            text_y += 20

        # Name
        for line in wrap_text(draw, row["fullname"], name_font, card_w):
            if not draw_line(line, name_font, 26):
                break

        text_y += 6

        for label in [
            f"Tag: {row['tag']}",
            f"Missing: {row['missing_since']}",
            f"Location: {row['location']}",
            f"Age: {row['age']} | Sex: {row['sex']}",
        ]:
            if not draw_line(label, meta_font, 18):
                break

        notes = str(row.get("notes", "")).strip()
        if notes and notes.lower() != "nan":
            for line in wrap_text(draw, notes, meta_font, card_w):
                if not draw_line(line, meta_font, 16):
                    break

    return poster

# -----------------------
# LOAD + PREVIEW
# -----------------------

preview = None

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

# -----------------------
# GENERATE (FIXED STATE FLOW)
# -----------------------

with tab1:
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

# -----------------------
# DOWNLOADS (ALWAYS VISIBLE)
# -----------------------

with tab1:
    if st.session_state.generated:

        st.download_button(
            "⬇️ Download PNG",
            data=st.session_state.png,
            file_name="poster.png",
            mime="image/png"
        )

        st.download_button(
            "⬇️ Download PDF",
            data=st.session_state.pdf,
            file_name="poster.pdf",
            mime="application/pdf"
        )

# -----------------------
# HELP TAB
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
- filename → image filename (must match upload)
- fullname → full name
- tag → ID label
- missing_since → last seen date
- location → last known location
- age → age
- sex → gender
- notes → optional extra details

---

## ⚠️ Important rules
- filenames must match uploaded images exactly
- CSV must include required fields
- images uploaded separately
""")

    st.download_button(
        "Download CSV Template",
        data="""filename,fullname,tag,missing_since,location,age,sex,notes
example.png,Example Name,ID001,2025-01-01,London,12,Male,Blue jacket""",
        file_name="template.csv",
        mime="text/csv"
    )
