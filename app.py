import streamlit as st
import pandas as pd
import fitz
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import re
from collections import OrderedDict

# -----------------------
# APP SETUP
# -----------------------

st.set_page_config(page_title="Poster Generator", layout="wide")
st.title("Poster Generator")

csv_tab, pdf_tab, design_tab, help_tab = st.tabs([
    "CSV + Images",
    "PDF Upload",
    "Design",
    "Help"
])

# -----------------------
# SESSION STATE
# -----------------------

for key in ["csv_png", "csv_pdf", "csv_generated", "pdf_png", "pdf_pdf", "pdf_generated"]:
    if key not in st.session_state:
        st.session_state[key] = False if "generated" in key else None

# -----------------------
# SHARED SETTINGS
# -----------------------

CSV_CARD_IMG_WIDTH = 260
CSV_CARD_IMG_HEIGHT = 330
CSV_PADDING = 18

PDF_CARD_WIDTH = 260
PDF_IMAGE_HEIGHT = 185
PDF_PADDING_X = 12
PDF_PADDING_Y = 22
PDF_TITLE_SPACE = 90

GROUP_PAD = 7
GROUP_NOTE_GAP = 6
GROUP_NOTE_LINE_HEIGHT = 15

PERSON_NOTE_GAP = 8
PERSON_NOTE_LINE_HEIGHT = 13

# -----------------------
# FONT / TEXT HELPERS
# -----------------------

def load_font(size):
    try:
        return ImageFont.truetype("fonts/StackSansText-Regular.ttf", size)
    except:
        return ImageFont.load_default()


def clean_text(text):
    return " ".join(str(text).replace("\ufffe", "-").split()).strip()


def val(v):
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


# -----------------------
# DESIGN TAB
# -----------------------

with design_tab:
    st.subheader("Design Settings")

    show_title = st.checkbox("Show title", True)
    title_text = st.text_input("Title", "MISSING PERSONS NOTICE")
    subtitle_text = st.text_input("Subtitle", "")
    title_size = st.slider("Title size", 20, 120, 60)
    text_scale = st.slider("Text size", 0.7, 1.5, 1.0)

    show_group_boxes = st.checkbox("Show boxes around grouped people", True)
    show_group_notes = st.checkbox("Show shared group notes", True)

    title_colour = st.color_picker("Title colour", "#111111")
    body_colour = st.color_picker("Text colour", "#000000")
    note_colour = st.color_picker("Small note colour", "#777777")
    group_box_colour = st.color_picker("Group box colour", "#B00020")


# ============================================================
# CSV + IMAGES VERSION
# ============================================================

def csv_is_wide_image(img):
    src_ratio = img.size[0] / img.size[1]
    card_ratio = CSV_CARD_IMG_WIDTH / CSV_CARD_IMG_HEIGHT
    return src_ratio > card_ratio + 0.2


def csv_place_image(poster, img, x, y, card_w):
    src_w, src_h = img.size

    if csv_is_wide_image(img):
        scale = CSV_CARD_IMG_HEIGHT / src_h
        scaled_w = int(src_w * scale)
        scaled_h = CSV_CARD_IMG_HEIGHT
        img_resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

        card = Image.new("RGB", (card_w, CSV_CARD_IMG_HEIGHT), "white")
        paste_x = (card_w - scaled_w) // 2
        card.paste(img_resized, (paste_x, 0))
        poster.paste(card, (x, y))
    else:
        scale = max(card_w / src_w, CSV_CARD_IMG_HEIGHT / src_h)
        scaled_w = int(src_w * scale)
        scaled_h = int(src_h * scale)

        img_resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

        crop_x = (scaled_w - card_w) // 2
        crop_y = (scaled_h - CSV_CARD_IMG_HEIGHT) // 2

        img_cropped = img_resized.crop(
            (crop_x, crop_y, crop_x + card_w, crop_y + CSV_CARD_IMG_HEIGHT)
        )

        poster.paste(img_cropped, (x, y))


def render_csv_poster(df, images_dict, cols):
    title_font = load_font(int(title_size * text_scale))
    name_font = load_font(int(26 * text_scale))
    meta_font = load_font(int(16 * text_scale))

    def measure_text_height(row, card_w, dummy_draw):
        wide = card_w > CSV_CARD_IMG_WIDTH
        h = 8

        if wide:
            h += 20

        name_lines = wrap_text(dummy_draw, val(row["fullname"]), name_font, card_w)
        h += len(name_lines) * 26 + 6

        tag = val(row.get("tag", ""))
        missing = val(row.get("missing_since", ""))
        location = val(row.get("location", ""))
        age = val(row.get("age", ""))
        sex = val(row.get("sex", ""))

        if tag:
            h += 18
        if missing:
            h += 18
        if location:
            h += 18

        age_sex = " | ".join(filter(None, [
            f"Age: {age}" if age else "",
            f"Sex: {sex}" if sex else ""
        ]))

        if age_sex:
            h += 18

        notes = val(row.get("notes", ""))
        if notes:
            note_lines = wrap_text(dummy_draw, notes, meta_font, card_w)
            h += len(note_lines) * 16

        return h

    poster_width = cols * (CSV_CARD_IMG_WIDTH + CSV_PADDING) + CSV_PADDING

    card_widths = []
    for _, row in df.iterrows():
        filename = str(row["filename"]).lower().strip()
        img = images_dict.get(filename)

        if img and csv_is_wide_image(img):
            card_widths.append(CSV_CARD_IMG_WIDTH * 2 + CSV_PADDING)
        else:
            card_widths.append(CSV_CARD_IMG_WIDTH)

    y_offset = 40
    if show_title:
        y_offset += 120

    dummy_img = Image.new("RGB", (poster_width, 100), "white")
    dummy_draw = ImageDraw.Draw(dummy_img)

    row_x = CSV_PADDING
    card_rows = []
    poster_row = 0

    for card_w in card_widths:
        if row_x + card_w > poster_width - CSV_PADDING and row_x > CSV_PADDING:
            row_x = CSV_PADDING
            poster_row += 1

        card_rows.append(poster_row)
        row_x += card_w + CSV_PADDING

    num_poster_rows = poster_row + 1
    row_text_heights = [0] * num_poster_rows

    for i, (_, row) in enumerate(df.iterrows()):
        th = measure_text_height(row, card_widths[i], dummy_draw)
        pr = card_rows[i]
        row_text_heights[pr] = max(row_text_heights[pr], th)

    row_heights = [
        CSV_CARD_IMG_HEIGHT + row_text_heights[r] + CSV_PADDING
        for r in range(num_poster_rows)
    ]

    row_y_starts = []
    cy = y_offset + CSV_PADDING

    for rh in row_heights:
        row_y_starts.append(cy)
        cy += rh

    row_x = CSV_PADDING
    cur_row = 0
    positions = []

    for card_w in card_widths:
        if row_x + card_w > poster_width - CSV_PADDING and row_x > CSV_PADDING:
            row_x = CSV_PADDING
            cur_row += 1

        positions.append((row_x, row_y_starts[cur_row], card_w))
        row_x += card_w + CSV_PADDING

    poster_height = cy + 80
    poster = Image.new("RGB", (poster_width, poster_height), "white")
    draw = ImageDraw.Draw(poster)

    if show_title:
        w = draw.textlength(title_text, font=title_font)
        draw.text(((poster_width - w) / 2, 40), title_text, fill=title_colour, font=title_font)

        if subtitle_text:
            sub_font = load_font(int(28 * text_scale))
            sw = draw.textlength(subtitle_text, font=sub_font)
            draw.text(((poster_width - sw) / 2, 105), subtitle_text, fill=title_colour, font=sub_font)

    for i, (_, row) in enumerate(df.iterrows()):
        x, y, card_w = positions[i]
        filename = str(row["filename"]).lower().strip()

        if filename in images_dict:
            csv_place_image(poster, images_dict[filename], x, y, card_w)

        text_y = y + CSV_CARD_IMG_HEIGHT + 8
        wide = card_w > CSV_CARD_IMG_WIDTH

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

        if wide:
            banner = "— Both photos are of the same person —"
            bw = draw.textlength(banner, font=meta_font)
            bx = x + (card_w - bw) // 2
            draw.text((bx, text_y), banner, fill="#888888", font=meta_font)
            text_y += 20

        for line in wrap_text(draw, val(row["fullname"]), name_font, card_w):
            draw_line(line, name_font, 26)

        text_y += 6

        tag = val(row.get("tag", ""))
        missing = val(row.get("missing_since", ""))
        location = val(row.get("location", ""))
        age = val(row.get("age", ""))
        sex = val(row.get("sex", ""))

        if tag:
            draw_line(f"Tag: {tag}", meta_font, 18)
        if missing:
            draw_line(f"Missing: {missing}", meta_font, 18)
        if location:
            draw_line(f"Location: {location}", meta_font, 18)

        age_sex = " | ".join(filter(None, [
            f"Age: {age}" if age else "",
            f"Sex: {sex}" if sex else ""
        ]))

        if age_sex:
            draw_line(age_sex, meta_font, 18)

        notes = val(row.get("notes", ""))

        if notes:
            for line in wrap_text(draw, notes, meta_font, card_w):
                draw_line(line, meta_font, 16)

    return poster


# ============================================================
# PDF VERSION
# ============================================================

def crop_fill_image(img, size):
    target_w, target_h = size
    src_w, src_h = img.size

    scale = max(target_w / src_w, target_h / src_h)

    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2

    return resized.crop((left, top, left + target_w, top + target_h))


def is_bad_name(line):
    bad = [
        "missing",
        "missing children",
        "how you can help",
        "scan, view",
        "report sighting",
        "police",
        "department",
        "ncmec",
    ]

    l = line.lower().strip()
    return any(b in l for b in bad) or l.startswith("ncic")


def extract_value(line, label):
    return clean_text(
        re.sub(label, "", line, flags=re.IGNORECASE)
        .replace(":", "")
        .strip()
    )


def extract_ncic(segment):
    joined = "\n".join(segment)
    match = re.search(r"NCIC#\s*([A-Z0-9]+)", joined, re.IGNORECASE)

    if match:
        return f"NCIC# {match.group(1).strip()}"

    return ""


def extract_note_text(lines, people):
    stop_phrases = [
        "police",
        "department",
        "how you can help",
        "scan",
        "report sighting",
        "911",
        "1-800",
        "ncmec:",
        "call",
    ]

    known_people = [p["fullname"].lower().strip() for p in people]

    stop_index = len(lines)

    for i, line in enumerate(lines):
        lower = line.lower().strip()
        if any(phrase in lower for phrase in stop_phrases):
            stop_index = i
            break

    start_candidates = []

    for i, line in enumerate(lines[:stop_index]):
        lower = line.lower().strip()

        if lower in ["male", "female"]:
            start_candidates.append(i + 1)

        if re.match(r"^\d+\s+years\s+old$", lower):
            if i + 1 < stop_index and lines[i + 1].lower().strip() in ["male", "female"]:
                start_candidates.append(i + 2)
            else:
                start_candidates.append(i + 1)

    if start_candidates:
        note_start = max(start_candidates)
    else:
        return ""

    note_lines = []

    for line in lines[note_start:stop_index]:
        lower = line.lower().strip()

        skip = (
            not line.strip()
            or lower in ["missing", "missing children", "male", "female"]
            or lower.startswith("ncic")
            or lower.startswith("missing since")
            or lower.startswith("age now")
            or re.match(r"^\d+\s+years\s+old$", lower)
            or any(name == lower for name in known_people)
            or re.match(r"^\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}$", line)
            or ("," in line and len(line.split()) <= 4)
        )

        if skip:
            continue

        note_lines.append(line)

    return clean_text(" ".join(note_lines))


def extract_records_from_pdf(uploaded_file):
    pdf_bytes = uploaded_file.getvalue()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    records = []

    for page_index, page in enumerate(doc):
        text = page.get_text("text")
        lines = [clean_text(l) for l in text.splitlines() if clean_text(l)]

        ncmec_id = ""

        for line in lines:
            m = re.search(r"NCMEC:\s*([0-9]+)", line, re.IGNORECASE)
            if m:
                ncmec_id = m.group(1)

        photo_items = []

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            rects = page.get_image_rects(xref)

            for rect in rects:
                is_person_photo = (
                    rect.x0 < 470
                    and rect.y0 < 520
                    and rect.width > 80
                    and rect.height > 85
                )

                if not is_person_photo:
                    continue

                base = doc.extract_image(xref)
                pil_img = Image.open(BytesIO(base["image"])).convert("RGB")

                photo_items.append({
                    "rect": rect,
                    "image": pil_img,
                })

        photo_items = sorted(photo_items, key=lambda p: (p["rect"].y0, p["rect"].x0))

        missing_indexes = [
            i for i, line in enumerate(lines)
            if line.lower().startswith("missing since")
        ]

        people = []

        for m_i, missing_idx in enumerate(missing_indexes):
            name_idx = None

            for j in range(missing_idx - 1, -1, -1):
                candidate = lines[j]

                if is_bad_name(candidate):
                    continue

                if candidate.lower().startswith(("age now", "location", "sex", "female", "male")):
                    continue

                name_idx = j
                break

            if name_idx is None:
                continue

            next_missing_idx = (
                missing_indexes[m_i + 1]
                if m_i + 1 < len(missing_indexes)
                else len(lines)
            )

            segment = lines[name_idx:next_missing_idx]

            fullname = lines[name_idx]
            missing_since = ""
            location = ""
            age = ""
            sex = ""
            tag = extract_ncic(segment)

            for idx, line in enumerate(segment):
                lower = line.lower()

                if lower.startswith("missing since"):
                    missing_since = extract_value(line, r"Missing Since")

                    if idx + 1 < len(segment):
                        possible_location = segment[idx + 1]
                        if "," in possible_location:
                            location = possible_location

                if lower.startswith("age now"):
                    age = extract_value(line, r"Age Now")

                if lower in ["female", "male"]:
                    sex = line

            people.append({
                "fullname": fullname,
                "tag": tag,
                "missing_since": missing_since,
                "location": location,
                "age": age,
                "sex": sex,
                "line_index": name_idx,
                "images": [],
            })

        shared_note = extract_note_text(lines, people)

        if not people:
            records.append({
                "fullname": uploaded_file.name.replace(".pdf", ""),
                "tag": "",
                "missing_since": "",
                "location": "",
                "age": "",
                "sex": "",
                "notes": shared_note,
                "group_note": "",
                "images": [p["image"] for p in photo_items],
                "group_id": f"solo_{uploaded_file.name}",
                "is_grouped": False,
            })
            continue

        if len(people) == 1:
            people[0]["images"] = [p["image"] for p in photo_items]
        else:
            people = sorted(people, key=lambda p: p["line_index"])

            for idx, photo in enumerate(photo_items):
                if idx < len(people):
                    people[idx]["images"].append(photo["image"])

        is_group = len(people) > 1
        group_id = f"group_{ncmec_id or uploaded_file.name}" if is_group else ""

        for person in people:
            records.append({
                "fullname": person["fullname"],
                "tag": person["tag"],
                "missing_since": person["missing_since"],
                "location": person["location"],
                "age": person["age"],
                "sex": person["sex"],
                "notes": "" if is_group else shared_note,
                "group_note": shared_note if is_group else "",
                "images": person["images"],
                "group_id": group_id if is_group else f"solo_{uploaded_file.name}_{person['fullname']}",
                "is_grouped": is_group,
            })

    return records


def measure_pdf_card_text_height(record, draw, fonts):
    name_font, meta_font, note_font, mini_font = fonts

    h = 8

    if len(record.get("images", [])) >= 2:
        h += 14

    name_lines = wrap_text(draw, val(record.get("fullname", "")), name_font, 260)
    h += len(name_lines) * 21 + 3

    for key in ["tag", "missing_since", "location"]:
        if val(record.get(key, "")):
            h += 13

    if val(record.get("age", "")) or val(record.get("sex", "")):
        h += 13

    notes = val(record.get("notes", ""))

    if notes:
        h += PERSON_NOTE_GAP
        h += len(wrap_text(draw, notes, note_font, 260)) * PERSON_NOTE_LINE_HEIGHT

    return h


def paste_pdf_person_images(poster, record, x, y):
    images = record.get("images", [])

    if len(images) >= 2:
        gap = 4
        half_w = (260 - gap) // 2

        img1 = crop_fill_image(images[0], (half_w, 185))
        img2 = crop_fill_image(images[1], (half_w, 185))

        poster.paste(img1, (x, y))
        poster.paste(img2, (x + half_w + gap, y))

    elif len(images) == 1:
        img = crop_fill_image(images[0], (260, 185))
        poster.paste(img, (x, y))


def render_pdf_poster(records, cards_per_row):
    CARD_WIDTH = 260
    IMAGE_HEIGHT = 185

    title_font = load_font(int(title_size * text_scale))
    name_font = load_font(int(18 * text_scale))
    meta_font = load_font(int(11 * text_scale))
    note_font = load_font(int(10 * text_scale))
    group_note_font = load_font(int(12 * text_scale))
    mini_font = load_font(int(8 * text_scale))

    poster_width = cards_per_row * CARD_WIDTH + (cards_per_row + 1) * PDF_PADDING_X

    dummy_img = Image.new("RGB", (poster_width, 100), "white")
    dummy_draw = ImageDraw.Draw(dummy_img)

    group_map = OrderedDict()

    for i, record in enumerate(records):
        if record.get("is_grouped"):
            group_map.setdefault(record["group_id"], []).append(i)

    positions = {}
    row_for_index = {}

    for i, record in enumerate(records):
        row = i // cards_per_row
        col = i % cards_per_row

        x = PDF_PADDING_X + col * (CARD_WIDTH + PDF_PADDING_X)

        row_for_index[i] = row
        positions[i] = {"x": x, "row": row}

    num_rows = (len(records) + cards_per_row - 1) // cards_per_row

    card_text_heights = [
        measure_pdf_card_text_height(record, dummy_draw, (name_font, meta_font, note_font, mini_font))
        for record in records
    ]

    row_card_heights = [0] * num_rows

    for i, h in enumerate(card_text_heights):
        row = row_for_index[i]
        row_card_heights[row] = max(row_card_heights[row], IMAGE_HEIGHT + h)

    row_extra_group_note = [0] * num_rows

    if show_group_notes:
        for group_id, indexes in group_map.items():
            rows = {}

            for idx in indexes:
                rows.setdefault(row_for_index[idx], []).append(idx)

            final_row = max(rows.keys())
            row_indexes = rows[final_row]

            x1 = min(positions[i]["x"] for i in row_indexes) - GROUP_PAD
            x2 = max(positions[i]["x"] + CARD_WIDTH for i in row_indexes) + GROUP_PAD

            note = val(records[indexes[0]].get("group_note", ""))

            if note:
                note_width = x2 - x1 - 22
                note_lines = wrap_text(dummy_draw, note, group_note_font, note_width)

                row_extra_group_note[final_row] = max(
                    row_extra_group_note[final_row],
                    GROUP_NOTE_GAP + len(note_lines) * GROUP_NOTE_LINE_HEIGHT + GROUP_PAD
                )

    row_heights = [
        row_card_heights[r] + row_extra_group_note[r] + PDF_PADDING_Y
        for r in range(num_rows)
    ]

    row_y = []
    current_y = PDF_TITLE_SPACE if show_title else PDF_PADDING_Y

    for h in row_heights:
        row_y.append(current_y)
        current_y += h

    poster_height = current_y + PDF_PADDING_Y

    poster = Image.new("RGB", (poster_width, poster_height), "white")
    draw = ImageDraw.Draw(poster)

    if show_title:
        title_w = draw.textlength(title_text, font=title_font)
        draw.text(
            ((poster_width - title_w) / 2, 22),
            title_text,
            fill=title_colour,
            font=title_font
        )

    card_bottoms = {}

    for i, record in enumerate(records):
        x = positions[i]["x"]
        y = row_y[row_for_index[i]]

        paste_pdf_person_images(poster, record, x, y)

        text_y = y + IMAGE_HEIGHT + 4

        if len(record.get("images", [])) >= 2:
            mini = "– Both photos are of the same person –"
            mini_w = draw.textlength(mini, font=mini_font)

            draw.text(
                (x + (CARD_WIDTH - mini_w) / 2, text_y),
                mini,
                fill=note_colour,
                font=mini_font
            )

            text_y += 14

        for line in wrap_text(draw, val(record.get("fullname", "")), name_font, CARD_WIDTH):
            line_w = draw.textlength(line, font=name_font)

            draw.text(
                (x + (CARD_WIDTH - line_w) / 2, text_y),
                line,
                fill=body_colour,
                font=name_font
            )

            text_y += 21

        text_y += 3

        tag = val(record.get("tag", ""))
        missing = val(record.get("missing_since", ""))
        location = val(record.get("location", ""))
        age = val(record.get("age", ""))
        sex = val(record.get("sex", ""))

        fields = []

        if tag:
            fields.append(f"Tag: {tag}")
        if missing:
            fields.append(f"Missing: {missing}")
        if location:
            fields.append(f"Location: {location}")

        age_sex = " | ".join(filter(None, [
            f"Age: {age}" if age else "",
            f"Sex: {sex}" if sex else "",
        ]))

        if age_sex:
            fields.append(age_sex)

        for field in fields:
            field_w = draw.textlength(field, font=meta_font)

            draw.text(
                (x + (CARD_WIDTH - field_w) / 2, text_y),
                field,
                fill=body_colour,
                font=meta_font
            )

            text_y += 13

        notes = val(record.get("notes", ""))

        if notes:
            text_y += PERSON_NOTE_GAP

            for line in wrap_text(draw, notes, note_font, CARD_WIDTH):
                line_w = draw.textlength(line, font=note_font)

                draw.text(
                    (x + (CARD_WIDTH - line_w) / 2, text_y),
                    line,
                    fill=body_colour,
                    font=note_font
                )

                text_y += PERSON_NOTE_LINE_HEIGHT

        card_bottoms[i] = text_y

    for group_id, indexes in group_map.items():
        rows = {}

        for idx in indexes:
            rows.setdefault(row_for_index[idx], []).append(idx)

        final_row = max(rows.keys())

        for row, row_indexes in rows.items():
            x1 = min(positions[i]["x"] for i in row_indexes) - GROUP_PAD
            x2 = max(positions[i]["x"] + CARD_WIDTH for i in row_indexes) + GROUP_PAD
            y1 = row_y[row] - GROUP_PAD

            content_bottom = max(card_bottoms[i] for i in row_indexes)
            note_lines = []

            if row == final_row and show_group_notes:
                note = val(records[indexes[0]].get("group_note", ""))

                if note:
                    note_width = x2 - x1 - 22
                    note_lines = wrap_text(draw, note, group_note_font, note_width)

            if note_lines:
                note_y = content_bottom + GROUP_NOTE_GAP
                y2 = note_y + len(note_lines) * GROUP_NOTE_LINE_HEIGHT + GROUP_PAD
            else:
                note_y = content_bottom
                y2 = content_bottom + GROUP_PAD

            if show_group_boxes:
                draw.rectangle([x1, y1, x2, y2], outline=group_box_colour, width=2)

            if note_lines:
                note_x = x1 + 11
                note_width = x2 - x1 - 22

                for line in note_lines:
                    line_w = draw.textlength(line, font=group_note_font)

                    draw.text(
                        (note_x + (note_width - line_w) / 2, note_y),
                        line,
                        fill=body_colour,
                        font=group_note_font
                    )

                    note_y += GROUP_NOTE_LINE_HEIGHT

    return poster


# -----------------------
# CSV TAB
# -----------------------

csv_preview = None

with csv_tab:
    st.subheader("Create from CSV + Images")

    csv_cols = st.slider("Images per row", 3, 12, 8, key="csv_cols")

    csv_file = st.file_uploader("Upload CSV", type=["csv"], key="csv_file")
    image_files = st.file_uploader(
        "Upload Images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="image_files"
    )

    csv_generate = st.button("Generate CSV Poster", key="csv_generate")

    if csv_file and image_files:
        df = pd.read_csv(csv_file)

        images_dict = {
            img.name.lower().strip(): Image.open(img).convert("RGB")
            for img in image_files
        }

        csv_preview = render_csv_poster(df, images_dict, csv_cols)

        st.subheader("Live Preview")
        st.image(csv_preview)

    if csv_generate and csv_preview is not None:
        png_buffer = BytesIO()
        pdf_buffer = BytesIO()

        csv_preview.save(png_buffer, format="PNG")
        png_buffer.seek(0)

        csv_preview.convert("RGB").save(pdf_buffer, format="PDF", resolution=300)
        pdf_buffer.seek(0)

        st.session_state.csv_png = png_buffer
        st.session_state.csv_pdf = pdf_buffer
        st.session_state.csv_generated = True

        st.success("CSV poster generated.")

    if st.session_state.csv_generated:
        st.download_button(
            "⬇️ Download CSV Poster PNG",
            data=st.session_state.csv_png,
            file_name="csv_poster.png",
            mime="image/png"
        )

        st.download_button(
            "⬇️ Download CSV Poster PDF",
            data=st.session_state.csv_pdf,
            file_name="csv_poster.pdf",
            mime="application/pdf"
        )


# -----------------------
# PDF TAB
# -----------------------

pdf_preview = None

with pdf_tab:
    st.subheader("Create from PDFs")

    pdf_cards_per_row = st.slider("People/cards per row", 3, 10, 5, key="pdf_cards_per_row")

    pdf_files = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_files"
    )

    pdf_generate = st.button("Generate PDF Poster", key="pdf_generate")

    records = []

    if pdf_files:
        pdf_files = pdf_files[:40]

        for pdf in pdf_files:
            records.extend(extract_records_from_pdf(pdf))

        st.subheader("Detected Cards")
        st.write(f"{len(records)} people/cards detected from {len(pdf_files)} PDFs.")

        pdf_preview = render_pdf_poster(records, pdf_cards_per_row)

        st.subheader("Live Preview")
        st.image(pdf_preview)

    if pdf_generate and pdf_preview is not None:
        png_buffer = BytesIO()
        pdf_buffer = BytesIO()

        pdf_preview.save(png_buffer, format="PNG")
        png_buffer.seek(0)

        pdf_preview.convert("RGB").save(pdf_buffer, format="PDF", resolution=300)
        pdf_buffer.seek(0)

        st.session_state.pdf_png = png_buffer
        st.session_state.pdf_pdf = pdf_buffer
        st.session_state.pdf_generated = True

        st.success("PDF poster generated.")

    if st.session_state.pdf_generated:
        st.download_button(
            "⬇️ Download PDF Poster PNG",
            data=st.session_state.pdf_png,
            file_name="pdf_poster.png",
            mime="image/png"
        )

        st.download_button(
            "⬇️ Download PDF Poster PDF",
            data=st.session_state.pdf_pdf,
            file_name="pdf_poster.pdf",
            mime="application/pdf"
        )


# -----------------------
# HELP TAB
# -----------------------

with help_tab:
    st.markdown("""
## 📘 How to use this tool

This tool now has two poster creation modes:

### 1. CSV + Images
Use this when you already have structured data and image files.

### 2. PDF Upload
Use this when you have NCMEC-style PDFs and want the system to extract the text and images automatically.

---

## 📄 CSV required fields

Each row represents one person.

Required fields:
- filename → image filename
- fullname → full name
- tag → ID label
- missing_since → last seen date
- location → last known location
- age → age
- sex → gender
- notes → optional extra details

---

## 📄 PDF mode

PDF mode automatically detects:
- Person name
- NCIC number
- Missing since date
- Location
- Age now
- Sex
- Notes
- Person photos

Grouped PDFs are boxed together where relevant.

---

## ⚠️ Important rules

- CSV filenames must match uploaded images exactly
- PDF mode is tuned for NCMEC-style PDFs
- Upload up to 40 PDFs at a time
""")

    st.download_button(
        "Download CSV Template",
        data="""filename,fullname,tag,missing_since,location,age,sex,notes
example.png,Example Name,ID001,2025-01-01,London,12,Male,Blue jacket""",
        file_name="template.csv",
        mime="text/csv"
    )
