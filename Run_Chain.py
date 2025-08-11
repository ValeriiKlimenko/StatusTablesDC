import subprocess
from pathlib import Path

# Folder containing your .root files
input_folder = Path("/lustre24/expphy/volatile/clas12/valerii/DC_stat")



#################### STEP 3 from README ####################

# Get all .root files in the folder
root_files = sorted(input_folder.glob("*.root"))

for root_file in root_files:
    cmd = [
        "python3",
        "GetStatus.py",
        "--input", str(root_file),
        "--output", str(input_folder)
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

#################### STEP 4 from README ####################

# Find all */results/ folders
base_path = Path("/lustre24/expphy/volatile/clas12/valerii/DC_stat")
results_dirs = sorted(base_path.glob("*/results/"))

for results_dir in results_dirs:
    # The parent folder (e.g., 020139) will be used for --out-dir
    parent_dir = results_dir.parent

    cmd = [
        "python",
        "GetTable.py",
        "--base-dir", str(results_dir),
        "--out-dir", str(parent_dir)
    ]
    print("Running:", " ".join(cmd))


#################### STEP 5 from README ####################

# Find all */results/ folders
results_dirs = sorted(base_path.glob("*/results/"))

for results_dir in results_dirs:
    # The parent folder (e.g., 020139) will be used to build the output file path
    parent_dir = results_dir.parent
    output_pdf = parent_dir / "wire_distrib.pdf"

    cmd = [
        "python",
        "CreatePDF.py",
        "--base-dir", str(results_dir),
        "--output", str(output_pdf)
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)