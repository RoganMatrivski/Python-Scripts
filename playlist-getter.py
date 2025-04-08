import sys
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

base_hostname = None
fetch_url_base = None

def get_page_links(soup):
    return [link.get('href') for link in soup.find_all('a') if link.get('href').startswith("page") and link.get('href').endswith(".html")]

def get_video_links(soup):
    if not fetch_url_base:
        raise Exception("Hostname not defined")

    video_links = [link.get('href') for link in soup.find_all('a') if link.get('href').startswith(fetch_url_base)]
    return [urlparse(link)._replace(query=None).geturl() for link in video_links]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def main(base_url):
    global base_hostname, fetch_url_base

    parsed_url = urlparse(base_url)
    base_hostname = parsed_url.netloc
    fetch_url_base = f"https://{base_hostname}/video/"

    print()

    video_links = []

    print(f"// URL: {base_url}\n")
    eprint("// Fetching...")
    response = requests.get(base_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    links = get_video_links(soup)
    page_links = get_page_links(soup)
    page_nums = [int(link.strip("page").strip(".html")) for link in page_links]
    max_page_num = max(page_nums, default=0)

    if max_page_num == 0:
        return links

    video_links += links

    for page_num in range(2, max_page_num + 1):
        eprint(f"// Fetching page {page_num}...")
        response = requests.get(f"{base_url}/page{page_num}.html")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        video_links += get_video_links(soup)

    return video_links

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python playlist-getter.py <base_url>")
        sys.exit(1)
    list = main(sys.argv[1])

    # list.reverse()
    for link in list:
        print(link)