#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


SL_DIR_RE = re.compile(r"^SL(\d+)$")
SEC_FILE_RE = re.compile(r"^sec(\d+)\.(png|jpg|jpeg)$", re.IGNORECASE)


def natural_key_dir(p: Path):
    m = SL_DIR_RE.match(p.name)
    return (int(m.group(1)) if m else 10**9, p.name.lower())


def natural_key_file(p: Path):
    m = SEC_FILE_RE.match(p.name)
    return (int(m.group(1)) if m else 10**9, p.name.lower())


def collect_images(base_dir: Path):
    """
    Return a list of tuples (folder_name, image_path) sorted by SL#, then sec#.
    """
    images = []
    for sl_dir in sorted([d for d in base_dir.iterdir() if d.is_dir() and SL_DIR_RE.match(d.name)],
                         key=natural_key_dir):
        for img in sorted([p for p in sl_dir.iterdir() if p.is_file() and SEC_FILE_RE.match(p.name)],
                          key=natural_key_file):
            images.append((sl_dir.name, img))
    return images


def make_pdf(images, output_pdf: Path):
    if not images:
        raise SystemExit("No matching images found. Expected SL*/sec*.png under the base directory.")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(output_pdf) as pdf:
        for folder_name, img_path in images:
            # Load image
            with Image.open(img_path) as im:
                # Create a page
                fig = plt.figure(figsize=(8.5, 11), dpi=150)
                ax = fig.add_subplot(111)
                ax.imshow(im)
                ax.axis("off")

                # Title with folder and file name
                title = f"{folder_name} / {img_path.name}"
                ax.set_title(title, pad=16)

                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Create a PDF with one image per page from SL*/sec*.png layout."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path.cwd(),
        help="Base directory containing SL*/sec*.png (default: current directory).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("combined_plots.pdf"),
        help="Output PDF file path (default: combined_plots.pdf).",
    )
    args = parser.parse_args()

    images = collect_images(args.base_dir)
    make_pdf(images, args.output)
    print(f"✅ Wrote {len(images)} pages to {args.output.resolve()}")


if __name__ == "__main__":
    main()