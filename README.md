# Wire Hit Analysis Workflow (Step-By-Step)

This repository contains tools to process CLAS12 HIPO files and generate wire hit histograms and status tables.

---

## 0. Loading Modules

module use /scigroup/cvmfs/hallb/clas12/sw/modulefiles

module load clas12root

module load root

## 1. Generate File Lists (`generate_file_lists.py`)

This script recursively scans a directory and creates `.txt` files listing all `.hipo` files for each subfolder (assumed to represent one run).

###

python generate_file_lists.py /path/to/data


## 2. Create ROOT Files (HIPO_to_HIST.C)
This ROOT macro reads each .txt file and processes the listed .hipo files, creating histograms for wire distributions.

module use /scigroup/cvmfs/hallb/clas12/sw/modulefiles
module load clas12root

clas12root -q -b HIPO_to_HIST.C'("/your/run_paths", "/your/output_dir")'

Example:
clas12root -q -b HIPO_to_HIST.C'("/u/home/valerii/DC_status_tables/run_paths","/lustre24/expphy/volatile/clas12/valerii/DC_stat/")'

Change the path to match where generate_file_lists.py was run.

## 3. Generate Preliminary CSVs with Bad Wires # (GetStatus.py)
After ROOT files are created, run the analysis script to extract wire status data.

python--/path/to/file.root --output /path/to/output_dir

example:
python3 GetStatus.py --input "/lustre24/expphy/volatile/clas12/valerii/DC_stat/rec_clas_020139.root" --output "/lustre24/expphy/volatile/clas12/valerii/DC_stat/"


## 4. Generate Status Tables (GetTable.py)

python GetTable.py --base-dir "/lustre24/expphy/volatile/clas12/valerii/DC_stat/020139/results/" --out-dir "/lustre24/expphy/volatile/clas12/valerii/DC_stat/020139/"


## 5. Make presentation:


python CreatePDF.py --base-dir "/lustre24/expphy/volatile/clas12/valerii/DC_stat/020139/results/" --output "/lustre24/expphy/volatile/clas12/valerii/DC_stat/020139/wire_distrib.pdf"
