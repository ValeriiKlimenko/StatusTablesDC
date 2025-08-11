import os
import sys

def ensure_dir(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)

def generate_hipo_lists(base_path):
    base_path = os.path.abspath(base_path)
    if not os.path.isdir(base_path):
        print(f"❌ Input path does not exist or is not a directory: {base_path}")
        return

    output_dir = os.path.join(os.getcwd(), "run_paths")
    ensure_dir(output_dir)

    for root, _, files in os.walk(base_path):
        # Filter only .hipo files
        hipo_files = [f for f in files if f.endswith(".hipo")]
        if not hipo_files:
            continue  # Skip folders without .hipo files

        abs_paths = [os.path.join(root, f) for f in hipo_files]
        rel_path = os.path.relpath(root, base_path).replace(os.sep, "_")
        if rel_path == ".":
            rel_path = "root"

        output_file = os.path.join(output_dir, f"{rel_path}.txt")
        with open(output_file, "w") as f:
            for path in abs_paths:
                f.write(f"{path}\n")

        print(f"✅ Saved {len(abs_paths)} .hipo paths to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_hipo_file_lists.py <base_input_folder>")
        sys.exit(1)

    input_path = sys.argv[1]
    generate_hipo_lists(input_path)