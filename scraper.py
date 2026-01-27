import asyncio

import cloudinary
import cloudinary.uploader
from playwright.async_api import async_playwright

cloudinary.config(
    cloud_name="dnssyb7hu",
    api_key="546611568773363",
    api_secret="VIwYmkPKwCMrqIBI18ickdChUK4"
)

class YouTubeScraper:
    async def upload_to_cloudinary(self, url):
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: cloudinary.uploader.upload(url, folder="yt_thumbnails")
        )
        return result.get("secure_url", "")

    async def get_x(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("ytd-playlist-video-renderer", timeout=60000)

            course_name = await page.evaluate("""
                document.getElementsByTagName('yt-dynamic-sizing-formatted-string')[0]?.innerText?.trim()
            """)

            video_count_and_date = await page.evaluate("""
                document.getElementsByTagName('ytd-playlist-byline-renderer')[0]?.innerText?.trim()
            """)

            number_of_videos = ""
            last_updated = ""
            if video_count_and_date:
                if "last" in video_count_and_date.lower():
                    last_update = video_count_and_date.lower().split("last")
                    number_of_videos = last_update[0].strip()
                    last_updated = "Last " + last_update[1].strip() if len(last_update) > 1 else ""
                else:
                    number_of_videos = video_count_and_date

            video_discription = await page.evaluate("""
                document.getElementsByTagName('ytd-text-inline-expander')[0]?.innerText?.trim()
            """)

            main_length = await page.evaluate(
                "document.getElementsByTagName('ytd-playlist-video-renderer').length"
            )

            all_data = []
            upload_tasks = []

            for i in range(main_length):
                await page.evaluate(f"""
                    window.scrollTo(
                        0,
                        document.getElementsByTagName("ytd-playlist-video-renderer")[{i}].offsetTop
                        - window.innerHeight / 2
                    )
                """)

                data = await page.evaluate(f"""
                    (() => {{
                        const el = document.getElementsByTagName("ytd-playlist-video-renderer")[{i}];
                        if (!el) return null;

                        const duration = el.getElementsByTagName("badge-shape")[0];
                        const img = el.getElementsByTagName("yt-image")[0]?.getElementsByTagName("img")[0];
                        const index = el.getElementsByTagName("yt-formatted-string")[0];
                        const titleEl = el.getElementsByTagName("h3")[0];
                        const linkEl = titleEl?.getElementsByTagName("a")[0];

                        const imgSrc = img?.src || "";

                        return {{
                            index: index?.innerText || "",
                            title: titleEl?.innerText || "",
                            duration: duration?.innerText || "",
                            link: linkEl?.href || "",
                            img: imgSrc,
                            img2: imgSrc.split(".jpg")[0] + ".jpg"
                        }};
                    }})()
                """)

                if data and data["img2"]:
                    all_data.append(data)
                    upload_tasks.append(self.upload_to_cloudinary(data["img2"]))

            cloudinary_links = await asyncio.gather(*upload_tasks)

            for i in range(len(all_data)):
                all_data[i]["247_link"] = cloudinary_links[i]

            await browser.close()

            return {
                "playlist_name": course_name,
                "playlist_discription": video_discription,
                "number_of_video": number_of_videos,
                "last_updated_on": last_updated,
                "data": all_data
            }
