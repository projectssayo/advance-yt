from fastapi import FastAPI
from playwright.sync_api import sync_playwright
import uvicorn
import os

app = FastAPI(title="YouTube Playlist Scraper", version="1.0")

def get_x(url):
    """Scrape YouTube playlist data"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Changed to True for deployment
        page = browser.new_page()
        page.goto(url)
        page.wait_for_selector("ytd-playlist-video-renderer", state="visible", timeout=10000)
        
        all_data = []
        main_length = page.evaluate("""
            document.getElementsByTagName('ytd-playlist-video-renderer').length
        """)
        print(f"Number of videos in playlist: {main_length}")

        for i in range(main_length):
            page.evaluate(f"""
                window.scrollTo(
                    0,
                    document.getElementsByTagName("ytd-playlist-video-renderer")[{i}].offsetTop
                    - window.innerHeight / 2
                )
            """)

            data = page.evaluate(f"""
                (() => {{
                    const el = document.getElementsByTagName("ytd-playlist-video-renderer")[{i}];
                    if (!el) return null;

                    const duration = el.getElementsByTagName("badge-shape")[0];
                    const img = el.getElementsByTagName("yt-image")[0]?.getElementsByTagName("img")[0];
                    const index = el.getElementsByTagName("yt-formatted-string")[0];
                    const titleEl = el.getElementsByTagName("h3")[0];
                    const linkEl = titleEl?.getElementsByTagName("a")[0];

                    return {{
                        index: index?.innerText || "",
                        title: titleEl?.innerText || "",
                        duration: duration?.innerText || "",
                        link: linkEl?.href || "",
                        img: img?.src || "",
                    }};
                }})()
            """)

            if data:
                all_data.append(data)

        browser.close()
        return {"data": all_data}

@app.get("/")
def home():
    return {"message": "YouTube Playlist Scraper API", "status": "online"}

@app.get("/info")
def info():
    return {
        "ask": "GET https://your-app.onrender.com/scrape?url=YOUR_YOUTUBE_PLAYLIST_URL",
        "example": "https://your-app.onrender.com/scrape?url=https://www.youtube.com/playlist?list=PLGjplNEQ1it_oTvuLRNqXfz_v_0pq6unW"
    }

@app.get("/scrape")
def scrape(url: str):
    """Scrape YouTube playlist"""
    try:
        result = get_x(url)
        return result
    except Exception as e:
        return {"error": str(e)}
