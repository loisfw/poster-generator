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
    # Helper: measure how many px of text a card needs
    # ------------------------------------------------------------------

    def val(v):
        """Return clean string or empty string — never 'nan'."""
        s = str(v).strip()
        return "" if s.lower() in ("nan", "none", "") else s

    def measure_text_height(row, card_w, dummy_draw):
        """Calculate the pixel height needed for all text in a card."""
        wide = card_w > CARD_IMG_WIDTH
        h = 8  # top gap

        if wide:
            h += 20  # banner line

        # Name lines
        name_lines = wrap_text(dummy_draw, val(row["fullname"]), name_font, card_w)
        h += len(name_lines) * 26 + 6

        # Fixed meta fields — only include non-empty ones
        tag      = val(row.get("tag", ""))
        missing  = val(row.get("missing_since", ""))
        location = val(row.get("location", ""))
        age      = val(row.get("age", ""))
        sex      = val(row.get("sex", ""))

        if tag:      h += 18
        if missing:  h += 18
        if location: h += 18
        age_sex = " | ".join(filter(None, [
            f"Age: {age}" if age else "",
            f"Sex: {sex}" if sex else ""
        ]))
        if age_sex:  h += 18

        # Notes
        notes = val(row.get("notes", ""))
        if notes:
            note_lines = wrap_text(dummy_draw, notes, meta_font, card_w)
            h += len(note_lines) * 16

        return h

    # ------------------------------------------------------------------
    # PASS 1: card widths
    # ------------------------------------------------------------------

    poster_width = COLS * (CARD_IMG_WIDTH + PADDING) + PADDING

    card_widths = []
    for _, row in df.iterrows():
        filename = str(row["filename"]).lower().strip()
        img = images_dict.get(filename)
        if img and is_wide_image(img):
            card_widths.append(CARD_IMG_WIDTH * 2 + PADDING)
        else:
            card_widths.append(CARD_IMG_WIDTH)

    # ------------------------------------------------------------------
    # PASS 2: measure text height per card, then compute per-poster-row
    # height as the tallest card in that row
    # ------------------------------------------------------------------

    y_offset = 40
    if show_title:
        y_offset += 120

    # Dummy image + draw just for text measurement
    dummy_img  = Image.new("RGB", (poster_width, 100), "white")
    dummy_draw = ImageDraw.Draw(dummy_img)

    # Assign each card to a poster row
    row_x = PADDING
    card_rows = []   # which poster-row each card belongs to
    poster_row = 0
    for card_w in card_widths:
        if row_x + card_w > poster_width - PADDING and row_x > PADDING:
            row_x = PADDING
            poster_row += 1
        card_rows.append(poster_row)
        row_x += card_w + PADDING

    num_poster_rows = poster_row + 1

    # For each poster row, find the tallest text block
    row_text_heights = [0] * num_poster_rows
    for i, (_, row) in enumerate(df.iterrows()):
        th = measure_text_height(row, card_widths[i], dummy_draw)
        pr = card_rows[i]
        if th > row_text_heights[pr]:
            row_text_heights[pr] = th

    # Row heights = image height + tallest text in that row + padding
    row_heights = [CARD_IMG_HEIGHT + row_text_heights[r] + PADDING
                   for r in range(num_poster_rows)]

    # Compute y start of each poster row
    row_y_starts = []
    cy = y_offset + PADDING
    for rh in row_heights:
        row_y_starts.append(cy)
        cy += rh

    # Now assign final (x, y, card_w) positions
    row_x = PADDING
    cur_row = 0
    positions = []
    for i, card_w in enumerate(card_widths):
        if row_x + card_w > poster_width - PADDING and row_x > PADDING:
            row_x = PADDING
            cur_row += 1
        positions.append((row_x, row_y_starts[cur_row], card_w))
        row_x += card_w + PADDING

    poster_height = cy + 80

    # ------------------------------------------------------------------
    # PASS 3: draw everything
    # ------------------------------------------------------------------

    poster = Image.new("RGB", (poster_width, poster_height), "white")
    draw   = ImageDraw.Draw(poster)

    if show_title:
        w = draw.textlength(title_text, font=title_font)
        draw.text(((poster_width - w) / 2, 40), title_text, fill=title_colour, font=title_font)

    for i, (_, row) in enumerate(df.iterrows()):
        x, y, card_w = positions[i]
        filename = str(row["filename"]).lower().strip()

        if filename in images_dict:
            place_image(poster, images_dict[filename], x, y, card_w)

        text_y = y + CARD_IMG_HEIGHT + 8
        wide   = card_w > CARD_IMG_WIDTH

        def draw_centred(text, font, line_h):
            nonlocal text_y
            tw = draw.textlength(text, font=font)
            tx = x + (card_w - tw) // 2
            draw.text((tx, text_y), text, fill=body_colour, font=font)
            text_y += line_h

        def draw_left(text, font, line_h):
            nonlocal text_y
            draw.text((x, text_y), text, fill=body_colour, font=font)
            text_y += line_h

        draw_line = draw_centred if wide else draw_left

        # Banner for two-photo cards
        if wide:
            banner = "— Both photos are of the same person —"
            bw = draw.textlength(banner, font=meta_font)
            bx = x + (card_w - bw) // 2
            draw.text((bx, text_y), banner, fill="#888888", font=meta_font)
            text_y += 20

        # Name
        for line in wrap_text(draw, val(row["fullname"]), name_font, card_w):
            draw_line(line, name_font, 26)
        text_y += 6

        # Meta fields — skip entirely if empty
        tag      = val(row.get("tag", ""))
        missing  = val(row.get("missing_since", ""))
        location = val(row.get("location", ""))
        age      = val(row.get("age", ""))
        sex      = val(row.get("sex", ""))

        if tag:      draw_line(f"Tag: {tag}",           meta_font, 18)
        if missing:  draw_line(f"Missing: {missing}",   meta_font, 18)
        if location: draw_line(f"Location: {location}", meta_font, 18)

        age_sex = " | ".join(filter(None, [
            f"Age: {age}" if age else "",
            f"Sex: {sex}" if sex else ""
        ]))
        if age_sex: draw_line(age_sex, meta_font, 18)

        # Notes
        notes = val(row.get("notes", ""))
        if notes:
            for line in wrap_text(draw, notes, meta_font, card_w):
                draw_line(line, meta_font, 16)

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
