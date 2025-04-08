import sys
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

import typer
from typing_extensions import Annotated

def get_page_links(soup):
    return [link.get('href') for link in soup.find_all('a') if link.get('href').startswith("page") and link.get('href').endswith(".html")]

def get_video_links(soup, starts_with: str):
    video_links = [link.get('href') for link in soup.find_all('a') if link.get('href').startswith(starts_with)]
    return [urlparse(link)._replace(query=None).geturl() for link in video_links]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def main(base_url: str, reverse: Annotated[bool, typer.Option()] = False):
    parsed_url = urlparse(base_url)
    base_hostname = parsed_url.netloc
    fetch_url_base = f"https://{base_hostname}/video/"

    video_links = []

    print(f"// URL: {base_url}\n")
    eprint("// Fetching...")
    response = requests.get(base_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    links = get_video_links(soup, fetch_url_base)

    page_links = get_page_links(soup)
    page_nums = [int(link.strip("page").strip(".html")) for link in page_links]
    max_page_num = max(page_nums, default=0)

    video_links += links

    for page_num in range(2, max_page_num + 1):
        eprint(f"// Fetching page {page_num}...")
        response = requests.get(f"{base_url}/page{page_num}.html")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        video_links += get_video_links(soup, fetch_url_base)

    if reverse:
        video_links.reverse()

    for link in video_links:
        print(link)

if __name__ == "__main__":
    typer.run(main)