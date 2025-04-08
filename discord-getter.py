import asyncio
import os
import aiohttp
from jinja2 import Environment, FileSystemLoader
import discord
from discord.ext import commands
import datetime

from linkpreview import Link, LinkPreview, LinkGrabber
import json

from urlextract import URLExtract;
import tldextract

import xxhash

import typer
from pathlib import PurePath, Path
from typing_extensions import Annotated
from typing import Dict, Optional, List

from aiochannel import Channel
from typing import TypedDict

import mimetypes

from tqdm.asyncio import tqdm as tqdmio
from tqdm import tqdm

extractor = URLExtract()
bot = commands.Bot(command_prefix='!')
grabber = LinkGrabber(
    initial_timeout=20,
    maxsize=1048576,
    receive_timeout=10,
    chunk_size=1024,
)

max_per_page = 30
script_dir = os.path.dirname(os.path.abspath(__file__))
env = Environment(loader=FileSystemLoader(script_dir))
template = env.get_template("discord-getter/child.html.jinja")  # Load our template file

excluded_hosts = [
    "tenor.com",
    "discordapp.com",
    "discordapp.net",
    "twitter.com",
    "fxtwitter.com",
    "vxtwitter.com",
    "x.com",
]

BOT_READY_LOCK: asyncio.Lock

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

async def get_preview(url):
    mime_type, _ = mimetypes.guess_type(url)

    if mime_type and not mime_type.startswith("text/html"):
        # print(f"Skipping grabber for non-webpage URL: {url} (type: {mime_type})")
        filename = url.split("/")[-1]

        return {
            "url": url,
            "title": filename,
            "description": "",
            "image": url if mime_type.startswith("image/") else ""
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"}) as response:
                if response.status == 200:
                    content = await response.text()
                else:
                    raise Exception(f"Failed to fetch URL {url} with status code {response.status}")
        link = Link(url, content)
        preview = LinkPreview(link, parser="lxml")
    except Exception as e:
        if "404" in str(e):
            tqdm.write(f"404 Not Found: {url}")
            return None

        tqdm.write(f"Error fetching preview for {url}: {e}")
        filename = url.rstrip("/").split("/")[-1]
        tqdm.write(f"Using filename from URL: {filename}")
        return {
            "url": url,
            "title": filename,
            "description": url,
            "image": ""
        }

    return {
        "url": url,
        "title": preview.title,
        "description": preview.description,
        "image": preview.image
    }

def parse_month_year_str(str):
    try:
        return datetime.datetime.strptime(str, "%Y-%m")
    except ValueError:
        print(f"Error parsing date string: {str}")
        return None

def get_month_range(cur_datetime):
    start_of_month = cur_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if cur_datetime.month == 12:
        end_of_month = cur_datetime.replace(year=cur_datetime.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(microseconds=1)
    else:
        end_of_month = cur_datetime.replace(month=cur_datetime.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(microseconds=1)
    return start_of_month, end_of_month

async def write_to_disk(session, url, out_path):
    async with session.get(url) as response:
        if response.status == 200:
            with open(out_path, "wb") as f:
                f.write(await response.read())

class AppClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    channels: List[int]
    token: str
    output_dir: Path
    url_prefix: str
    month_list: List[datetime.datetime]

    def __init__(
        self,
        channels: List[int],
        token: str,
        output_dir: Path,
        url_prefix: str,
        month_list: List[datetime.datetime],
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.channels = channels
        self.token = token
        self.output_dir = output_dir
        self.url_prefix = url_prefix
        self.month_list = month_list

    class FetchResult:
        month: str
        client_name: str
        urls: List[str]

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def setup_hook(self):
        self.bg_task = self.loop.create_task(self.run_task())

    def get_channel(self, id):
        channel = super().get_channel(id)
        if not channel:
            raise ValueError(f"Channel with ID {id} not found.")

        return channel

    def get_channel_fileid(self, id):
        ch = self.get_channel(id)
        srv_name = ch.guild.name
        ch_name = ch.name

        return f"{ch_name}({srv_name})"

    def get_date_outputdir(self, prefix, t_date, id):
        formatted_date = t_date.strftime("%Y%B")
        return os.path.join(prefix, formatted_date, self.get_channel_fileid(id))

    def get_serversinfo_tuple(self, prefix, t_date, channel_id):
        fileid = self.get_channel_fileid(channel_id)
        formatted_date = t_date.strftime("%Y%B")
        return (os.path.join(prefix, formatted_date, fileid), fileid)

    async def fetch_urls(self, channel_id, start, end):
        curr_start = start.replace(tzinfo=None)
        try:
            channel = self.get_channel(channel_id)
        except ValueError as e:
            print(f"Error: {e}")
            return

        while curr_start < end:
            print(f'Fetching messages after {curr_start}')
            messages = channel.history(oldest_first=True, after=curr_start, before=end)

            messages_list = [msg async for msg in messages]
            if not messages_list:
                break

            for message in messages_list:
                curr_start = message.created_at.replace(tzinfo=None)
                content = message.content

                urls = extractor.find_urls(content)

                if not urls:
                    continue

                for url in urls:
                    yield url

        print("Done!")

    async def run_task(self):
        await self.wait_until_ready()

        for month in self.month_list:
            tqdm.write(f'Processing {month}')
            t_range = get_month_range(month)

            srv_list = []
            preview_list = []

            for ch in self.channels:
                tqdm.write(f'Processing {ch}')
                urls = [url async for url in self.fetch_urls(ch, t_range[0], t_range[1])]
                if not urls:
                    continue

                base_dir = self.get_serversinfo_tuple(self.output_dir, month, ch)[0]
                img_dir = os.path.join(base_dir, "img/")
                _url_prefix = self.url_prefix if self.url_prefix else self.output_dir
                chinfo_tuple = self.get_serversinfo_tuple(_url_prefix, month, ch)
                output_dir=chinfo_tuple[0]
                chname=chinfo_tuple[1]

                aiosession = aiohttp.ClientSession(
                    max_line_size=8190 * 8,
                    # fixing exception: Got more than 8190 bytes (15340) when reading Header value is too long
                    max_field_size=8190 * 8,
                )
                previews = []

                semaphore = asyncio.Semaphore(16)  # Limit concurrency to 16 tasks

                async def process_url(url):
                    async with semaphore:
                        parsed = tldextract.extract(url)
                        basename = parsed.registered_domain

                        if basename in excluded_hosts:
                            return  # Skip excluded host

                        if not url.startswith("http"):
                            url = "https://" + url

                        tqdm.write(url)

                        try:
                            preview = await get_preview(url)
                        except Exception as e:
                            tqdm.write(f"ERROR: Error processing URL {url}: {e}\n")
                            return

                        if preview:
                            if preview["image"]:
                                image_url = preview["image"]

                                if not image_url.startswith("http"):
                                    image_url = url + image_url

                                image_filename = xxhash.xxh128_hexdigest(os.path.basename(image_url)) + (
                                    os.path.splitext(image_url)[1] if os.path.splitext(image_url)[1] else ""
                                )
                                image_output_path = os.path.join(img_dir, image_filename)
                                os.makedirs(img_dir, exist_ok=True)

                                try:
                                    await write_to_disk(aiosession, image_url, image_output_path)
                                except Exception as e:
                                    tqdm.write(f"ERROR: Error writing image {image_url} to disk: {e}\n")

                                preview["image"] = os.path.join("img", image_filename)

                            previews.append(preview)

                tasks = [process_url(url) for url in urls]
                await tqdmio.gather(*tasks)

                await asyncio.sleep(1)

                await aiosession.close()

                if not previews:
                    continue

                srv_list.append(chinfo_tuple)
                preview_list.append([output_dir, chname, previews])

            for (output_dir, chname, previews) in preview_list:
                formatted_date = month.strftime("%Y%B")
                base_dir = os.path.join(self.output_dir, formatted_date, chname)

                total_pages = (len(previews) + max_per_page - 1) // max_per_page  # Ceiling division
                for curr_pagenum in range(1, total_pages + 1):
                    start_idx = (curr_pagenum - 1) * max_per_page
                    end_idx = start_idx + max_per_page
                    page_cards = previews[start_idx:end_idx]

                    # Determine previous and next page links
                    prev_page = curr_pagenum - 1 if curr_pagenum > 1 else None
                    next_page = curr_pagenum + 1 if curr_pagenum < total_pages else None

                    total_pagenum = total_pages

                    # Render HTML file
                    output_html = template.render(
                        total_links=len(previews),
                        cards=page_cards,
                        prev_page=prev_page,
                        next_page=next_page,
                        page_num=curr_pagenum,
                        total_pagenum=total_pagenum,

                        server_list=srv_list,
                        current_server=chname
                    )

                    # Save the output file
                    output_filename = f"{base_dir}/page{curr_pagenum}.html" if curr_pagenum > 1 else f"{base_dir}/index.html"
                    print(f"Writing to {output_filename}")
                    os.makedirs(base_dir, exist_ok=True)
                    with open(output_filename, "w", encoding="utf-8") as f:
                        f.write(output_html)

        print("Task done")
        await asyncio.sleep(1)
        await self.close()

@bot.event
async def on_command_error(ctx, command):
    pass

def main(
    channels: Annotated[
        List[int],
        typer.Option(
            "-c",
        )
    ],
    token: Annotated[
        str,
        typer.Argument()
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "-o",
            file_okay=False,
            writable=True,
        )
    ] = Path("./output/"),
    url_prefix: Annotated[
        str,
        typer.Option()
    ] = None,
    month_list: Annotated[
        List[datetime.datetime],
        typer.Argument(
            formats=["%Y-%m"]
        )
    ] = None,
):
    if not month_list:
        month_list = [datetime.datetime.now()]

    for month in month_list:
        print(f"Processing month: {month.strftime('%B %Y')}")

    asyncio.run(async_main(
        channels,
        token,
        output_dir,
        url_prefix,
        month_list,
    ))

async def async_main(
    channels: List[int],
    token: str,
    output_dir: Path,
    url_prefix: str,
    month_list: List[datetime.datetime]
):
    client = AppClient(channels, token, output_dir, url_prefix, month_list)
    await asyncio.gather(client.start(token))
    print("Done")

if __name__ == "__main__":
    typer.run(main)