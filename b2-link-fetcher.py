from b2sdk.v2 import InMemoryAccountInfo, B2Api
import urllib.parse

import typer
from pathlib import Path
from typing_extensions import Annotated
from typing import Optional

def main(
    key_id: Annotated[str, typer.Option(default=...)],
    key: Annotated[str, typer.Option(default=...)],
    bucket_str: str,
    path: Annotated[Optional[Path], typer.Argument()] = Path()
):
    info = InMemoryAccountInfo()
    b2 = B2Api(info)
    b2.authorize_account("production", key_id, key)

    path_str = "" if not path or str(path) == "." else str(path)

    bucket = b2.get_bucket_by_name(bucket_str)
    files = bucket.ls(path_str, latest_only=True, recursive=True)
    auth = bucket.get_download_authorization(file_name_prefix="", valid_duration_in_seconds=2*24*60*60)

    for f in files:
        file = f[0]

        download_url = b2.get_download_url_for_file_name(bucket_str, file.file_name)
        download_url_with_auth = f"{download_url}?Authorization={auth}"
        # print(f"Download URL: {download_url_with_auth}")
        decoded_file_name = urllib.parse.unquote(file.file_name).replace("()\'", "\'")
        file_directory, file_name = decoded_file_name.rsplit('/', 1)
        # print(f"Directory: {file_directory}, File Name: {file_name}")
        print(f"{download_url_with_auth}\n\tdir={file_directory}\n\tout={file_name}\n")

        # print(file.file_name)

if __name__ == "__main__":
    typer.run(main)