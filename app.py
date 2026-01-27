import os
import uvicorn
from fastapi import FastAPI
from scraper import YouTubeScraper

app = FastAPI()
scraper = YouTubeScraper()

@app.get("/")
async def home():
    return {"message": "YouTube Playlist Scraper"}

@app.get("/scrape")
async def scrape_playlist(url: str):
    return await scraper.get_x(url)

@app.get("/info")
async def info():
    return {
        "usage": "/scrape?url=https://www.youtube.com/playlist?list=XXXX"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
