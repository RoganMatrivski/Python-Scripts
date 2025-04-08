#!/usr/bin/env python3
"""
This script provides a CLI with two subcommands using Typer:
- encode: Converts a string to its hexadecimal representation.
- decode: Converts a hexadecimal string back to its original string.

Usage examples:
    $ python script.py encode "Hello, world!"
    $ python script.py decode "48656c6c6f2c20776f726c6421"
"""

import typer

app = typer.Typer(help="A CLI tool to encode and decode strings using hexadecimal representation.")

def encode_to_hex(input_string: str) -> str:
    """
    Encode a given string into its hexadecimal representation.
    """
    return input_string.encode("utf-8").hex()

def decode_from_hex(hex_string: str) -> str:
    """
    Decode a hexadecimal string back into its original string.

    Raises:
        ValueError: If the input is not a valid hexadecimal string.
    """
    try:
        return bytes.fromhex(hex_string).decode("utf-8")
    except ValueError as error:
        raise ValueError("Invalid hexadecimal input. Please ensure the string is a valid hex-encoded value.") from error

@app.command()
def encode(text: str):
    """
    Encode the given text into a hex string.
    """
    result = encode_to_hex(text)
    typer.echo(f"Encoded: {result}")

@app.command()
def decode(hex: str):
    """
    Decode the given hex string back into text.
    """
    try:
        result = decode_from_hex(hex)
        typer.echo(f"Decoded: {result}")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)

if __name__ == "__main__":
    app()
