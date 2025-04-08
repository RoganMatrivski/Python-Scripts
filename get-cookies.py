import requests

import typer
from pathlib import PurePath, Path
from typing_extensions import Annotated
from typing import Dict, Optional, List

session_key = "PHPSESSID"
login_payload = {
    "ahd_username": "",
    "ahd_password": "",
    "Submit": "",
}
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
}

def print_cookies(cookies):
    for cookie in cookies:
        expiry = cookie.expires if cookie.expires is not None else "Session"
        print(f"{cookie.name}\t{expiry}\t{cookie.value}")

def main(
    file: Annotated[
        Path,
        typer.Argument()
    ] = None,
    base_url: Annotated[
        str,
        typer.Option("-b", "--base-url")
    ] = None,
    username: Annotated[
        str,
        typer.Option("-u", "--username")
    ] = None,
    password: Annotated[
        str,
        typer.Option("-p", "--passsword")
    ] = None
):
    login_url = f"{base_url}/login"
    profile_url = f"{base_url}/my-profile"

    is_file_valid = False
    if file:
        file_path = Path(file)
        if not file_path.exists():
            raise FileNotFoundError(f"The file {file} does not exist.")
        if not file_path.is_file():
            raise ValueError(f"The path {file} is not a file.")

        with file_path.open("r") as f:
            lines = f.readlines()
            if len(lines) < 1 or not lines[0].startswith("# Netscape HTTP Cookie File"):
                raise ValueError(f"The file {file} is not a valid Netscape cookie file.")
        is_file_valid = True

    session = requests.Session()

    if username:
        login_payload["ahd_username"] = username
    if password:
        login_payload["ahd_password"] = password

    login_response = session.post(login_url, data=login_payload, headers=headers, allow_redirects=False)
    login_response.raise_for_status()

    if login_response.status_code != 302 and login_response.headers.get("Location") != profile_url:
        raise ValueError("Login did not redirect as expected. Status code: " + str(login_response.status_code))

    my_session_cookie = None

    # Iterate over the cookies
    for cookie in session.cookies:
        if cookie.name == session_key:
            my_session_cookie = cookie
            break

    if my_session_cookie:
        # If there's no explicit expiration, mark it as a session cookie.
        expiry = my_session_cookie.expires if my_session_cookie.expires is not None else "Session"
        name = my_session_cookie.name
        value = my_session_cookie.value

        if is_file_valid:
            import http.cookiejar

            # Load existing cookies from the file
            cookie_jar = http.cookiejar.MozillaCookieJar(file)
            cookie_jar.load(ignore_discard=True, ignore_expires=True)

            # Update the cookie if it matches the same name and host
            for existing_cookie in cookie_jar:
                if existing_cookie.name == name and existing_cookie.domain == my_session_cookie.domain:
                    existing_cookie.expires = my_session_cookie.expires
                    existing_cookie.value = my_session_cookie.value
                    break
                else:
                    # Add the new cookie if no match is found
                    cookie_jar.set_cookie(http.cookiejar.Cookie(
                        version=0,
                        name=name,
                        value=value,
                        port=None,
                        port_specified=False,
                        domain=my_session_cookie.domain,
                        domain_specified=True,
                        domain_initial_dot=my_session_cookie.domain.startswith('.'),
                        path=my_session_cookie.path,
                        path_specified=True,
                        secure=my_session_cookie.secure,
                        expires=my_session_cookie.expires,
                        discard=False,
                        comment=None,
                        comment_url=None,
                        rest={},
                        rfc2109=False
                    ))

            # Save the updated cookies back to the file
            cookie_jar.save(ignore_discard=True, ignore_expires=True)
            print("Updated cookie to file")

        print(f"{expiry}\t {name}\t {value}")
    else:
        raise KeyError(f"Cookie {session_key} not found")

if __name__ == "__main__":
    typer.run(main)