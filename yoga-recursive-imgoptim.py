import os
from pathlib import Path
# Removed unused import
import typer
from tqdm import tqdm
from yoga.image import optimize
import asyncio
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from PIL import Image

app = typer.Typer()

def optimize_images_recursive(input_dir: Path, output_dir: Path):
    """
    Optimize images recursively while preserving directory structure.

    Args:
        input_dir (Path): Source directory containing images.
        output_dir (Path): Destination directory for optimized images.
    """
    if not input_dir.is_dir():
        typer.echo(f"Error: {input_dir} is not a valid directory.")
        raise typer.Exit(code=1)

    all_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            all_files.append(Path(root) / file)

    def process_file(source_file: Path):
        relative_path = source_file.parent.relative_to(input_dir)
        target_dir = output_dir / relative_path
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / source_file.name
        if target_file.exists():
            try:
                # Check if the file is not truncated or corrupted
                if target_file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    try:
                        with Image.open(target_file) as img:
                            img.verify()  # Verify that the file is not corrupted
                    except Exception as e:
                        tqdm.write(f"Corrupted or invalid file detected, reprocessing: {target_file}. Error: {e}")
                        target_file.unlink()  # Remove the corrupted file
                        raise
                    tqdm.write(f"Skipping already optimized file: {target_file}")
                    return
            except Exception as e:
                tqdm.write(f"Corrupted or invalid file detected, reprocessing: {target_file}. Error: {e}")

        if source_file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            tqdm.write(f"Optimizing: {source_file} -> {target_file}")
            original_size = source_file.stat().st_size
            try:
                optimize(str(source_file), str(target_file), options={
                    "resize": [512, 512],                # "orig"|[width,height]
                    "png_slow_optimization": True,  # True|False
                })
                optimized_size = target_file.stat().st_size
                size_diff = original_size - optimized_size
                tqdm.write(f"Size reduced by {size_diff / 1024:.2f} KB ({(size_diff / original_size) * 100:.2f}%)")
            except Exception as e:
                tqdm.write(f"Optimization failed for {source_file}. Error: {e}. Copying original file instead.")
                target_file.write_bytes(source_file.read_bytes())

        else:
            tqdm.write(f"Skipping non-image file: {source_file}")
            target_file.write_bytes(source_file.read_bytes())

    async def process_files_concurrently():
        cpu_count = multiprocessing.cpu_count()
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor, process_file, source_file)
                for source_file in all_files
            ]
            with tqdm(total=len(all_files), desc="Processing images") as pbar:
                for f in asyncio.as_completed(tasks):
                    await f
                    pbar.update(1)

    asyncio.run(process_files_concurrently())

@app.command()
def main(
    input_dir: Path = typer.Argument(..., help="Path to the input directory."),
    output_dir: Path = typer.Argument(..., help="Path to the output directory."),
):
    """
    Optimize images recursively while preserving directory structure.
    """
    optimize_images_recursive(input_dir, output_dir)

if __name__ == "__main__":
    app()