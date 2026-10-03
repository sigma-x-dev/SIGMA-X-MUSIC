import os
import asyncio
import aiohttp
from youtube_search import YoutubeSearch


API_URL = "https://api.shrutibots.site"
API_KEY = "ShrutiBotsfj3PpULm1Nj9D8Cb54ht"
API_TYPE = "audio"
API_FORMAT = "mp3"

DOWNLOAD_TIMEOUT = int(
    os.environ.get("DOWNLOAD_TIMEOUT", "300")
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def search_youtube(query: str):
    """YouTube pe search karta hai aur pehla result deta hai."""
    loop = asyncio.get_event_loop()

    def _search():
        results = YoutubeSearch(
            query,
            max_results=1
        ).to_dict()

        return results[0] if results else None

    return await loop.run_in_executor(None, _search)


async def search_track(query: str):
    """YouTube search result ko bot ke required format me convert karta hai."""
    result = await search_youtube(query)

    if not result:
        return None

    thumbnails = result.get("thumbnails") or []
    video_id = result.get("id")

    return {
        "id": video_id,
        "title": result.get("title", "Unknown"),
        "duration": result.get("duration", ""),
        "thumbnail": thumbnails[0] if thumbnails else None,
        "channel": (
            result.get("channel")
            or result.get("uploader")
            or ""
        ),
        "url": (
            f"https://www.youtube.com/watch?v={video_id}"
            if video_id
            else None
        ),
    }


class DownloadError(Exception):
    """Shruti API se audio download nahi ho paya."""


def _video_id(video: str) -> str:
    """YouTube URL ya video ID se sirf video ID nikalta hai."""
    video = (video or "").strip()

    if not video:
        return ""

    if "youtu.be/" in video:
        video = video.split("youtu.be/", 1)[1]

    elif "v=" in video:
        video = video.split("v=", 1)[1]

    elif "/shorts/" in video:
        video = video.split("/shorts/", 1)[1]

    elif "/embed/" in video:
        video = video.split("/embed/", 1)[1]

    for separator in ("?", "&", "/", "#"):
        video = video.split(separator, 1)[0]

    return video


async def get_stream_url(video: str) -> str:
    """
    Shruti API se YouTube audio download karta hai
    aur local MP3 file ka path return karta hai.
    """

    video_id = _video_id(video)

    if not video_id:
        raise DownloadError("Video ID nahi mila.")

    if not API_KEY:
        raise DownloadError(
            "SHRUTI_API_KEY Render Environment me set nahi hai."
        )

    file_path = os.path.join(
        DOWNLOAD_DIR,
        f"{video_id}.{API_FORMAT}"
    )

    # Pehle se downloaded file available hai
    if (
        os.path.exists(file_path)
        and os.path.getsize(file_path) > 0
    ):
        return file_path

    params = {
        "url": video_id,
        "type": API_TYPE,
        "api_key": API_KEY,
    }

    timeout = aiohttp.ClientTimeout(
        total=DOWNLOAD_TIMEOUT,
        sock_read=DOWNLOAD_TIMEOUT,
    )

    temp_path = f"{file_path}.part"

    try:
        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                f"{API_URL}/download",
                params=params,
            ) as resp:

                if resp.status != 200:
                    error_text = await resp.text(
                        errors="ignore"
                    )

                    raise DownloadError(
                        f"Shruti API error {resp.status}: "
                        f"{error_text[:200]}"
                    )

                with open(temp_path, "wb") as audio_file:
                    async for chunk in resp.content.iter_chunked(
                        131072
                    ):
                        audio_file.write(chunk)

        if not os.path.exists(temp_path):
            raise DownloadError(
                "Audio file create nahi hui."
            )

        if os.path.getsize(temp_path) <= 0:
            raise DownloadError(
                "Shruti API se empty audio file mili."
            )

        # Download complete hone ke baad final file banegi
        os.replace(temp_path, file_path)

        return file_path

    except asyncio.TimeoutError:
        if os.path.exists(temp_path):
            os.remove(temp_path)

        raise DownloadError(
            f"Download timeout — "
            f"{DOWNLOAD_TIMEOUT} seconds ke baad."
        )

    except aiohttp.ClientError as error:
        if os.path.exists(temp_path):
            os.remove(temp_path)

        raise DownloadError(
            f"Shruti API connection error: {error}"
        )

    except DownloadError:
        if os.path.exists(temp_path):
            os.remove(temp_path)

        raise

    except Exception as error:
        if os.path.exists(temp_path):
            os.remove(temp_path)

        raise DownloadError(
            f"Audio download failed: {error}"
        )


async def get_related_track(
    title: str,
    exclude_id: str = None
):
    """
    Autoplay ke liye related YouTube track search karta hai.
    """

    loop = asyncio.get_event_loop()

    base = (
        (title or "")
        .split("|")[0]
        .split("(")[0]
        .strip()
    )

    if not base:
        return None

    def _search():
        try:
            return YoutubeSearch(
                f"{base} song",
                max_results=8
            ).to_dict()

        except Exception:
            return []

    results = await loop.run_in_executor(
        None,
        _search
    )

    for result in results or []:
        video_id = result.get("id")

        if not video_id:
            continue

        if video_id == exclude_id:
            continue

        thumbnails = result.get("thumbnails") or []

        return {
            "id": video_id,
            "title": result.get(
                "title",
                "Unknown"
            ),
            "duration": result.get(
                "duration",
                ""
            ),
            "thumbnail": (
                thumbnails[0]
                if thumbnails
                else None
            ),
            "channel": (
                result.get("channel")
                or result.get("uploader")
                or ""
            ),
            "url": (
                f"https://www.youtube.com/watch?v={video_id}"
            ),
        }

    return None
