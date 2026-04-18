# Discover.Wav Clip Maker

A web app for creating Instagram-ready 9:16 music clips.

## Setup

1. Install ffmpeg
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

2. Install Python dependencies
```bash
pip install -r requirements.txt
```

3. Run the app
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## How to use

1. Click **New clip** to expand the form
2. Choose your source: upload a video file or paste a Google Drive share link
3. Set the start/end timestamps (MM:SS format)
4. Type your hook caption — wrap [artist name] in brackets to highlight in gold
5. Give the output a filename
6. Click **Add to queue** — repeat for as many clips as you want
7. Click **Generate** — clips process one by one
8. Download individually or as a ZIP when done

## Caption format

Wrap any words in `[square brackets]` to render them in gold:

```
Sometimes all you need is a new [Janisht Joshi] song.
```

## Hosting

To share with the team, deploy to [Streamlit Community Cloud](https://streamlit.io/cloud):
1. Push this folder to a GitHub repo
2. Connect the repo on share.streamlit.io
3. Share the link — no installs needed for anyone else
