"""
Discover.Wav Clip Maker — Streamlit App
Run: streamlit run app.py
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Discover.Wav Clip Maker",
    page_icon="🎬",
    layout="centered",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Page background */
.stApp {
    background: #0a0a0a;
    color: #f0ece4;
}

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Title */
.wav-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    color: #f0ece4;
    letter-spacing: -0.5px;
    margin-bottom: 0;
}
.wav-subtitle {
    font-size: 0.85rem;
    color: #666;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 2rem;
}

/* Queue cards */
.clip-card {
    background: #141414;
    border: 1px solid #222;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
}
.clip-card-title {
    font-size: 0.8rem;
    color: #ffc400;
    font-weight: 500;
    letter-spacing: 0.5px;
    margin-bottom: 0.25rem;
}
.clip-card-meta {
    font-size: 0.85rem;
    color: #888;
}
.clip-card-banner {
    font-size: 0.9rem;
    color: #f0ece4;
    margin-top: 0.2rem;
}

/* Status badges */
.badge-waiting  { color: #555; }
.badge-processing { color: #ffc400; }
.badge-done     { color: #4ade80; }
.badge-error    { color: #f87171; }

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #141414 !important;
    border: 1px solid #2a2a2a !important;
    color: #f0ece4 !important;
    border-radius: 8px !important;
}
.stSelectbox > div > div {
    background: #141414 !important;
    border: 1px solid #2a2a2a !important;
    color: #f0ece4 !important;
}

/* Buttons */
.stButton > button {
    background: #ffc400;
    color: #0a0a0a;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    padding: 0.5rem 1.5rem;
    transition: opacity 0.15s;
}
.stButton > button:hover { opacity: 0.85; }

/* Section divider */
.section-label {
    font-size: 0.7rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #444;
    margin: 1.5rem 0 0.75rem;
}

/* Banner preview label */
.preview-label {
    font-size: 0.7rem;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ── Visual config (matches clip maker) ───────────────────────────────────────
FRAME_W       = 1080
FRAME_H       = 1920
VIDEO_INSET   = 30
CORNER_RADIUS = 36
FONT_SIZE     = 34
LINE_SPACING  = 1.35
TEXT_GAP      = 10
TEXT_COLOR    = (255, 255, 255)
GOLD_COLOR    = (255, 196, 0)
BG_COLOR      = (0, 0, 0)

# ── Helpers ───────────────────────────────────────────────────────────────────

def to_sec(t: str) -> float:
    s = 0.0
    for p in t.strip().split(":"): s = s * 60 + float(p)
    return s


def run_cmd(cmd: str):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-600:])
    return r


def parse_banner(text: str):
    tokens = []
    for chunk in re.split(r"(\[[^\]]+\])", text):
        if chunk.startswith("[") and chunk.endswith("]"):
            for w in chunk[1:-1].split(): tokens.append((w, True))
        else:
            for w in chunk.split(): tokens.append((w, False))
    return tokens


def find_font(size: int):
    from PIL import ImageFont
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_banner_image(text: str, width: int = 500) -> "PIL.Image":
    """Render a cropped banner preview image (just the text region)."""
    from PIL import Image, ImageDraw
    vid_size = FRAME_W - 2 * VIDEO_INSET
    vid_y    = (FRAME_H - vid_size) // 2

    img  = Image.new("RGB", (FRAME_W, FRAME_H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    font = find_font(FONT_SIZE)
    tokens = parse_banner(text)
    max_w  = int(FRAME_W * 0.84)
    sp_w   = draw.textlength(" ", font=font)
    line_h = FONT_SIZE * LINE_SPACING
    lines, cur, cur_w = [], [], 0.0
    for word, gold in tokens:
        ww = draw.textlength(word, font=font)
        if cur and cur_w + sp_w + ww > max_w:
            lines.append(cur); cur, cur_w = [(word, gold)], ww
        else:
            if cur: cur_w += sp_w
            cur.append((word, gold)); cur_w += ww
    if cur: lines.append(cur)
    y = vid_y - len(lines) * line_h - TEXT_GAP
    for line in lines:
        lw = sum(draw.textlength(w, font=font) for w, _ in line) + sp_w * (len(line)-1)
        x = (FRAME_W - lw) / 2.0
        for i, (word, gold) in enumerate(line):
            draw.text((x, y), word, font=font, fill=GOLD_COLOR if gold else TEXT_COLOR)
            x += draw.textlength(word, font=font) + (sp_w if i < len(line)-1 else 0)
        y += line_h

    # Crop to just the banner area + a bit of black below
    top    = max(0, int(vid_y - len(lines) * line_h - TEXT_GAP - 40))
    bottom = vid_y + 60
    cropped = img.crop((0, top, FRAME_W, bottom))
    scale   = width / FRAME_W
    new_h   = int(cropped.height * scale)
    return cropped.resize((width, new_h))


def make_banner_png(text: str, out_path: str):
    from PIL import Image, ImageDraw
    vid_size = FRAME_W - 2 * VIDEO_INSET
    vid_y    = (FRAME_H - vid_size) // 2
    img  = Image.new("RGB", (FRAME_W, FRAME_H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    font = find_font(FONT_SIZE)
    tokens = parse_banner(text)
    max_w  = int(FRAME_W * 0.84)
    sp_w   = draw.textlength(" ", font=font)
    line_h = FONT_SIZE * LINE_SPACING
    lines, cur, cur_w = [], [], 0.0
    for word, gold in tokens:
        ww = draw.textlength(word, font=font)
        if cur and cur_w + sp_w + ww > max_w:
            lines.append(cur); cur, cur_w = [(word, gold)], ww
        else:
            if cur: cur_w += sp_w
            cur.append((word, gold)); cur_w += ww
    if cur: lines.append(cur)
    y = vid_y - len(lines) * line_h - TEXT_GAP
    for line in lines:
        lw = sum(draw.textlength(w, font=font) for w, _ in line) + sp_w * (len(line)-1)
        x = (FRAME_W - lw) / 2.0
        for i, (word, gold) in enumerate(line):
            draw.text((x, y), word, font=font, fill=GOLD_COLOR if gold else TEXT_COLOR)
            x += draw.textlength(word, font=font) + (sp_w if i < len(line)-1 else 0)
        y += line_h
    img.save(out_path)


def make_mask_png(size: int, out_path: str):
    from PIL import Image, ImageDraw
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,size-1,size-1], radius=CORNER_RADIUS, fill=255)
    mask.save(out_path)


def download_drive_file(drive_url: str, dest: str):
    """Download a file from a Google Drive share link using gdown."""
    try:
        import gdown
    except ImportError:
        subprocess.run("pip install gdown -q", shell=True)
        import gdown
    result = gdown.download(url=drive_url, output=dest, quiet=False, fuzzy=True)
    if not result or not os.path.exists(dest) or os.path.getsize(dest) == 0:
        raise RuntimeError(
            "Could not download from Google Drive. "
            "Make sure the file is shared as 'Anyone with the link can view' and try again."
        )


def process_clip(src_path: str, start: str, end: str, banner: str, out_path: str, on_step=None):
    vid_size = FRAME_W - 2 * VIDEO_INSET
    vid_x    = VIDEO_INSET
    vid_y    = (FRAME_H - vid_size) // 2

    with tempfile.TemporaryDirectory() as tmp:
        trimmed    = os.path.join(tmp, "clip.mp4")
        banner_png = os.path.join(tmp, "banner.png")
        mask_png   = os.path.join(tmp, "mask.png")

        dur = to_sec(end) - to_sec(start)
        run_cmd(
            f'ffmpeg -y -loglevel error '
            f'-ss {to_sec(start):.3f} -i "{src_path}" '
            f'-t {dur:.3f} -c:v libx264 -c:a aac "{trimmed}"'
        )
        if on_step: on_step("Rendering banner…")

        make_banner_png(banner, banner_png)
        make_mask_png(vid_size, mask_png)
        if on_step: on_step("Compositing…")

        fc = (
            f"[1:v]crop=min(iw\\,ih):min(iw\\,ih),scale={vid_size}:{vid_size}[vid];"
            f"[vid][2:v]alphamerge[masked];"
            f"[0:v][masked]overlay={vid_x}:{vid_y}[out]"
        )
        run_cmd(
            f'ffmpeg -y -loglevel error '
            f'-loop 1 -i "{banner_png}" -i "{trimmed}" -i "{mask_png}" '
            f'-filter_complex "{fc}" '
            f'-map "[out]" -map 1:a '
            f'-c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k '
            f'-shortest "{out_path}"'
        )


# ── Session state init ────────────────────────────────────────────────────────
if "queue" not in st.session_state:
    st.session_state.queue = []
if "source_cache" not in st.session_state:
    st.session_state.source_cache = {}
if "results" not in st.session_state:
    st.session_state.results = {}
if "auto_generate" not in st.session_state:
    st.session_state.auto_generate = False
if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None
if "auto_output_name" not in st.session_state:
    st.session_state.auto_output_name = ""


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="wav-title">Discover.Wav</div>', unsafe_allow_html=True)
st.markdown('<div class="wav-subtitle">Clip Maker</div>', unsafe_allow_html=True)


# ── Add clip form ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Add a clip</div>', unsafe_allow_html=True)

with st.expander("＋  New clip", expanded=len(st.session_state.queue) == 0):
    source_type = st.radio(
        "Source video",
        ["Upload from device", "Google Drive link"],
        horizontal=True,
        label_visibility="collapsed",
    )

    uploaded_file = None
    drive_url     = None

    if source_type == "Upload from device":
        uploaded_file = st.file_uploader(
            "Video file", type=["mp4", "mov", "mkv"],
            label_visibility="collapsed"
        )
        if uploaded_file and uploaded_file.name != st.session_state.last_uploaded_name:
            st.session_state.last_uploaded_name = uploaded_file.name
            st.session_state.auto_output_name = Path(uploaded_file.name).stem + "_clip.mp4"
    else:
        drive_url = st.text_input(
            "Google Drive share link",
            placeholder="https://drive.google.com/file/d/...",
            label_visibility="collapsed",
        )

    col1, col2 = st.columns(2)
    with col1:
        start = st.text_input("Start time", placeholder="0:47", value="")
    with col2:
        end = st.text_input("End time", placeholder="0:58", value="")

    output_name = st.text_input(
        "Output filename",
        value=st.session_state.auto_output_name,
    )

    banner = st.text_input(
        "Caption  —  wrap [highlighted words] in brackets for gold",
        placeholder='This one [hits different] — you need to hear it',
        value="",
    )

    # Live banner preview
    if banner.strip():
        st.markdown('<div class="preview-label">Caption preview</div>', unsafe_allow_html=True)
        try:
            preview_img = render_banner_image(banner, width=480)
            st.image(preview_img, use_container_width=False)
        except Exception as e:
            st.caption(f"Preview unavailable: {e}")

    single_mode = len(st.session_state.queue) == 0
    if single_mode:
        col_add, col_gen = st.columns(2)
        with col_add:
            add_clicked = st.button("Add to queue", use_container_width=True)
        with col_gen:
            gen_clicked = st.button("🎬  Generate", use_container_width=True)
    else:
        add_clicked = st.button("Add to queue", use_container_width=True)
        gen_clicked = False

    form_clicked = add_clicked or gen_clicked

    if form_clicked:
        errors = []
        if source_type == "Upload from device" and not uploaded_file:
            errors.append("Please upload a video file.")
        if source_type == "Google Drive link" and not drive_url:
            errors.append("Please paste a Google Drive link.")
        if not start or not end:
            errors.append("Start and end times are required.")
        if not banner.strip():
            errors.append("Caption is required.")
        if not output_name.strip():
            errors.append("Output filename is required.")
        else:
            if not output_name.endswith(".mp4"):
                output_name += ".mp4"

        if not errors:
            try:
                to_sec(start)
                to_sec(end)
            except (ValueError, AttributeError):
                errors.append("Please use MM:SS format, e.g. 0:47")

        if errors:
            for e in errors:
                st.error(e)
        else:
            clip_id = f"clip_{int(time.time() * 1000)}"
            entry = {
                "id":          clip_id,
                "source_type": source_type,
                "drive_url":   drive_url,
                "filename":    uploaded_file.name if uploaded_file else (drive_url or ""),
                "file_bytes":  uploaded_file.read() if uploaded_file else None,
                "start":       start,
                "end":         end,
                "banner":      banner,
                "output":      output_name,
                "status":      "waiting",
                "error":       None,
            }
            st.session_state.queue.append(entry)
            if gen_clicked:
                st.session_state.auto_generate = True
            st.rerun()


# ── Queue ─────────────────────────────────────────────────────────────────────
if st.session_state.queue:
    st.markdown('<div class="section-label">Queue</div>', unsafe_allow_html=True)

    for i, clip in enumerate(st.session_state.queue):
        status_html = {
            "waiting":    '<span class="badge-waiting">● Waiting</span>',
            "processing": '<span class="badge-processing">● Processing…</span>',
            "done":       '<span class="badge-done">✓ Done</span>',
            "error":      '<span class="badge-error">✗ Error</span>',
        }.get(clip["status"], "")

        src_label = Path(clip["filename"]).name if clip["filename"] else "unknown"

        st.markdown(f"""
        <div class="clip-card">
            <div class="clip-card-title">📁 {src_label} &nbsp;&nbsp; {clip['start']} → {clip['end']} &nbsp;&nbsp; {status_html}</div>
            <div class="clip-card-meta">→ {clip['output']}</div>
            {'<div style="color:#f87171;font-size:0.8rem;margin-top:0.3rem">'+clip["error"]+'</div>' if clip.get("error") else ''}
        </div>
        """, unsafe_allow_html=True)

        if clip["status"] in ("waiting", "error"):
            try:
                banner_img = render_banner_image(clip["banner"], width=400)
                st.image(banner_img, use_container_width=False)
            except Exception:
                pass

        col_dl, col_rm = st.columns([5, 1])

        # Download button if done
        if clip["status"] == "done" and clip["id"] in st.session_state.results:
            with col_dl:
                st.download_button(
                    f"⬇ {clip['output']}",
                    data=st.session_state.results[clip["id"]],
                    file_name=clip["output"],
                    mime="video/mp4",
                    key=f"dl_{clip['id']}",
                    use_container_width=True,
                )

        # Remove button
        with col_rm:
            if st.button("✕", key=f"rm_{clip['id']}", help="Remove"):
                st.session_state.queue = [c for c in st.session_state.queue if c["id"] != clip["id"]]
                st.rerun()

    # ── Generate button ───────────────────────────────────────────────────────
    waiting = [c for c in st.session_state.queue if c["status"] == "waiting"]
    done    = [c for c in st.session_state.queue if c["status"] == "done"]

    st.markdown("")
    auto_gen = st.session_state.auto_generate
    if auto_gen:
        st.session_state.auto_generate = False

    run_generation = False
    if waiting:
        if auto_gen:
            run_generation = True
        elif st.button(f"🎬  Generate {len(waiting)} clip{'s' if len(waiting)>1 else ''}", use_container_width=True):
            run_generation = True

    if run_generation:
        drive_keys = {c["filename"] for c in waiting if c["source_type"] == "Google Drive link"}
        total_steps = len(drive_keys) + len(waiting)
        step = 0

        progress = st.progress(0, text="Starting…")

        with tempfile.TemporaryDirectory() as tmp:

            source_paths = {}
            for clip in waiting:
                key = clip["filename"]
                if key in source_paths:
                    continue

                if clip["source_type"] == "Upload from device":
                    dest = os.path.join(tmp, f"src_{key}")
                    with open(dest, "wb") as f:
                        f.write(clip["file_bytes"])
                    source_paths[key] = dest

                else:  # Google Drive
                    dest = os.path.join(tmp, f"src_{Path(key).name or 'video.mp4'}")
                    progress.progress(step / total_steps, text=f"Downloading source from Google Drive…")
                    try:
                        download_drive_file(clip["drive_url"], dest)
                        source_paths[key] = dest
                    except Exception as e:
                        for c in waiting:
                            if c["filename"] == key:
                                c["status"] = "error"
                                c["error"]  = f"Drive download failed: {e}"
                    step += 1
                    progress.progress(step / total_steps, text="Source downloaded.")

            for i, clip in enumerate(waiting):
                src = source_paths.get(clip["filename"])
                if not src or not os.path.exists(src):
                    clip["status"] = "error"
                    clip["error"]  = "Source file unavailable."
                    step += 1
                    progress.progress(step / total_steps)
                    continue

                clip["status"] = "processing"
                out_path = os.path.join(tmp, clip["output"])
                label = f"Clip {i+1}/{len(waiting)}: {clip['output']}"
                progress.progress(step / total_steps, text=f"Trimming {label}…")

                # 3 sub-steps per clip: trim (done above) → banner → composite
                SUB = 3
                sub = [1]  # trim already started; callback fires at sub-steps 2 and 3
                def on_step(text, _sub=sub, _step=step, _label=label):
                    _sub[0] += 1
                    progress.progress((_step + _sub[0] / SUB) / total_steps, text=f"{text} {_label}…")

                try:
                    process_clip(src, clip["start"], clip["end"], clip["banner"], out_path, on_step=on_step)
                    with open(out_path, "rb") as f:
                        st.session_state.results[clip["id"]] = f.read()
                    clip["status"] = "done"
                    clip["error"]  = None
                except Exception as e:
                    clip["status"] = "error"
                    clip["error"]  = str(e)[:200]

                step += 1
                progress.progress(step / total_steps)

        progress.progress(1.0, text="Done!")
        st.rerun()

    # ── Download all as ZIP ───────────────────────────────────────────────────
    if done and len(done) > 1:
        st.markdown("")
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for clip in done:
                if clip["id"] in st.session_state.results:
                    zf.writestr(clip["output"], st.session_state.results[clip["id"]])
        st.download_button(
            f"⬇  Download all {len(done)} clips as ZIP",
            data=zip_buf.getvalue(),
            file_name="firstwave_clips.zip",
            mime="application/zip",
            use_container_width=True,
        )

    # ── Clear queue ───────────────────────────────────────────────────────────
    if st.button("Clear queue", use_container_width=False):
        st.session_state.queue   = []
        st.session_state.results = {}
        st.rerun()

else:
    st.markdown("""
    <div style="text-align:center;padding:3rem 0;color:#333;font-size:0.9rem">
        Add your first clip above to get started.
    </div>
    """, unsafe_allow_html=True)
