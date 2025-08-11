#!/usr/bin/env python3
"""
Build bad-wire tables by superlayer, total them, and export CCDB-friendly files.

Assumes the following input layout under --base-dir (default: current dir):
  SL1/BWsec1.csv ... SL1/BWsec6.csv
  SL2/BWsec1.csv ... SL2/BWsec6.csv
  ...
  SL6/BWsec1.csv ... SL6/BWsec6.csv

Outputs (under --out-dir, default: current dir):
  BW_SL1.dat ... BW_SL6.dat
  BW_total.dat
  BW_only_ccdb.dat
Optionally (with --make-grid) builds BW_ccdb.dat merged with full sector/layer/component grid.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd
import ROOT



SECTIONS = range(1, 7)       # 1..6
SUPERLAYERS = range(1, 7)    # 1..6
N_LAYERS = 36
N_COMPONENTS = 112


def read_section_files(sl_dir: Path) -> list[pd.DataFrame]:
    """Read BWsec{1..6}.csv from a superlayer directory, skipping missing files."""
    dfs = []
    for sec in SECTIONS:
        f = sl_dir / f"BWsec{sec}.csv"
        if not f.exists():
            print(f"[WARN] Skipping missing file: {f}")
            continue
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"[ERROR] Could not read {f}: {e}")
    return dfs


def normalize_wire_column(df: pd.DataFrame) -> pd.DataFrame:
    """Downcast 'Wire' column to int if it exists."""
    if "Wire" in df.columns:
        df = df.copy()
        df["Wire"] = pd.to_numeric(df["Wire"], errors="coerce").astype("Int64")
    return df


def build_superlayer_outputs(base_dir: Path, out_dir: Path) -> tuple[int, int]:
    """
    For each superlayer SLk, read BWsec1..6.csv, concat, write BW_SLk.dat.
    Returns (total_rows_written, running_count_sum_for_debug)
    """
    total_rows = 0
    running_sum = 0

    out_dir.mkdir(parents=True, exist_ok=True)

    for sl in SUPERLAYERS:
        sl_dir = base_dir / f"SL{sl}"
        dfs = read_section_files(sl_dir)
        # Count rows per section like original code
        num_bw = sum(df.shape[0] for df in dfs)
        # Concatenate
        result = pd.concat(dfs, axis=0, ignore_index=True)
        result = normalize_wire_column(result)

        out_file = out_dir / f"BW_SL{sl}.dat"
        result.to_csv(out_file, index=False)

        print(f"[SL{sl}] rows={result.shape[0]} (sum-of-sections={num_bw}) -> {out_file}")
        total_rows += result.shape[0]
        running_sum += num_bw

    return total_rows, running_sum


def build_total(out_dir: Path) -> pd.DataFrame:
    """Concat BW_SL1..6.dat -> BW_total.dat; return the total DataFrame."""
    per_sl_files = [out_dir / f"BW_SL{sl}.dat" for sl in SUPERLAYERS]
    for f in per_sl_files:
        if not f.exists():
            raise FileNotFoundError(f"Expected file not found: {f}")

    dfs = [pd.read_csv(f) for f in per_sl_files]
    df_total = pd.concat(dfs, axis=0, ignore_index=True)
    (out_dir / "BW_total.dat").write_text(df_total.to_csv(index=False))
    print(f"[TOTAL] rows={df_total.shape[0]} -> {out_dir / 'BW_total.dat'}")
    return df_total


def to_ccdb_only_bw(df_total: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """
    Convert BW_total.dat to CCDB-only format:
    columns -> ['sector','layer','component','status']
    where layer = Lay + (SuperLayer-1)*6, status = 112
    """
    df = df_total.copy()

    # Ensure expected columns exist then rename to a consistent schema
    # Your original code used: ['SuperLayer','sector','Lay','component']
    expected = {"Super Layer", "Sector", "Layer", "Wire"}
    if not expected.issubset(df.columns):
        raise ValueError(f"Expected columns {expected}, got {set(df.columns)}")

    df = df.rename(columns={"Super Layer": "SuperLayer", "Sector": "sector",
                            "Layer": "Lay", "Wire": "component"})

    df["layer"] = df["Lay"] + (df["SuperLayer"] - 1) * 6
    df["status"] = 112
    df = df.sort_values(["sector", "layer", "component"], ignore_index=True)
    df_ccdb = df[["sector", "layer", "component", "status"]]

    out_file = out_dir / "BW_only_ccdb.dat"
    df_ccdb.to_csv(out_file, index=False)
    print(f"[CCDB only] rows={df_ccdb.shape[0]} -> {out_file}")
    return df_ccdb.astype("int32")


def full_grid(out_dir: Path, n_sec=6, n_lay=N_LAYERS, n_comp=N_COMPONENTS) -> pd.DataFrame:
    """Build the full sector/layer/component grid with status0=0."""
    sec = pd.Series(
        sum(([s] * (n_lay * n_comp) for s in range(1, n_sec + 1)), [])
    )

    lay = pd.Series(list(range(1, n_lay + 1)) * n_sec * n_comp)
    comp = pd.Series(list(range(1, n_comp + 1)) * (n_lay * n_sec))
    df = pd.DataFrame({"sector": sec, "layer": lay.astype(int), "component": comp.astype(int)})
    df["status0"] = 0
  
    out_file = out_dir / "BW_empty.dat"
    df.to_csv(out_file, sep=" ", index=False)
  
    return df


def make_grid_merge(df_ccdb_only: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """
    Merge BW_only_ccdb with full grid (sector,layer,component),
    filling missing with 0; write BW_ccdb.dat (space-separated).
    """
    df_grid = full_grid(out_dir)
    bw = df_ccdb_only.rename(columns={"status": "status1"})

    merged = pd.merge(df_grid, bw,  how='left', left_on=["sector","layer", 'component'], right_on = ["sector","layer", 'component'])
    merged = merged.fillna(0)
  
    merged["status"] = (merged["status0"] + merged["status1"]).astype("int32")

    out_file = out_dir / "BW_ccdb.dat"
    merged[["sector", "layer", "component", "status"]].to_csv(out_file, sep=" ", index=False)
    print(f"[Grid merge] rows={merged.shape[0]} -> {out_file}")
    return merged


def parse_args() -> argparse.Namespace:
  
    p = argparse.ArgumentParser(description="Assemble bad-wire tables and CCDB exports.")
    p.add_argument("--base-dir", type=Path, default=Path("."), help="Directory containing SL1..SL6 subfolders.")
    p.add_argument("--out-dir", type=Path, default=Path("."), help="Directory to write outputs.")
    p.add_argument("--make-grid", default=True, action="store_true", help="Also generate BW_ccdb.dat merged with full grid.")
    p.add_argument("--draw-grid", default=True, action="store_true", help="Draw 2x3 grid (one pad per sector).")
    p.add_argument("--plot-out", type=Path, default=None, help="Output image filename for the 2x3 plot.")

    return p.parse_args()


############## Drawing: #####################



def set_margins_titles_size(h):
    h.GetXaxis().SetTitleSize(0.12)
    h.GetXaxis().SetLabelSize(0.07)
    h.GetYaxis().SetTitleOffset(0.3)
    h.GetXaxis().SetTitleOffset(0.5)
    h.GetYaxis().SetTitleSize(0.12)
    h.GetYaxis().SetLabelSize(0.06)
    h.GetYaxis().SetNdivisions(10)
    h.GetXaxis().SetNdivisions(20)
    ROOT.TGaxis.SetMaxDigits(3)
    ROOT.gStyle.SetTitleFontSize(0.1)
    ROOT.gPad.SetGrid()
    ROOT.gPad.SetMargin(0.15, 0.0, 0.15, 0.12)
    ROOT.gStyle.SetOptStat(0)


def set_hist_param_2d(h, labelX="wire", labelY="layer"):
    set_margins_titles_size(h)
    h.GetXaxis().SetTitle(labelX)
    h.GetYaxis().SetTitle(labelY)


def read_ccdb_table(path: Path) -> pd.DataFrame:
    """
    Read a CCDB-style table (sector, layer, component, status).
    Auto-detect separator (comma or space).
    Keeps only rows with status != 0.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    df = pd.read_csv(path, sep=None, engine="python")
    expected = {"sector", "layer", "component", "status"}
    if not expected.issubset(df.columns):
        raise ValueError(f"{path} missing required columns {expected}, got {set(df.columns)}")
    df = df[df["status"] != 0].copy()
    # Ensure integer types
    for col in ["sector", "layer", "component", "status"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df.dropna(subset=["sector", "layer", "component"]).reset_index(drop=True)


def draw_grid_2x3(
    file1: Path,
    file2: Path | None,
    out_png: Path,
    title: str | None = None,
    n_components: int = 112,
    n_layers: int = 36,
):
    # Batch mode if no display
    ROOT.gROOT.SetBatch(True)

    df1 = read_ccdb_table(file1)
    df2 = read_ccdb_table(file2) if file2 else None

    # Prepare one TH2D per sector
    hists = []
    for sec in range(1, 7):
        h = ROOT.TH2D(f"h_sec_{sec}", f"Sector {sec}", n_components + 1, 0.5, n_components + 1.5,
                      n_layers + 1, 0.5, n_layers + 1.5)
        hists.append(h)

    # Fill: file1 -> weight 1, file2 -> weight 2 (so overlaps reach 3)
    color = 1
    if (df2 is None):
      color = 3
    for _, r in df1.iterrows():
        s, lay, comp = int(r["sector"]), int(r["layer"]), int(r["component"])
        if 1 <= s <= 6:
            hists[s - 1].Fill(comp, lay, color)

    if df2 is not None:
        for _, r in df2.iterrows():
            s, lay, comp = int(r["sector"]), int(r["layer"]), int(r["component"])
            if 1 <= s <= 6:
                hists[s - 1].Fill(comp, lay, 2)

    # Canvas
    c = ROOT.TCanvas("c_bw", "Bad-wire occupancy", 1400, 900)
    c.Divide(2, 3, 0.0001, 0.0001)

    ROOT.gStyle.SetPalette(55)  # nice continuous palette

    for i in range(6):
        c.cd(i + 1)
        h = hists[i]
        # Styling
        set_hist_param_2d(h, labelX="wire", labelY="layer")
        if title:
            h.SetTitle(f"{title} — Sector {i+1}")
        else:
            h.SetTitle(f"Sector {i+1}")
        h.SetMinimum(0.)
        h.SetMaximum(3.)  # 1 for file1, 2 for file2, overlap = 3
        h.Draw("COL")

    # Save
    out_png = out_png.with_suffix(out_png.suffix or ".png")
    c.Print(str(out_png))
    print(f"[PLOT] saved -> {out_png}")

#########################################################################




def main() -> int:
    args = parse_args()

    try:
        total_rows, running_sum = build_superlayer_outputs(args.base_dir, args.out_dir)
        df_total = build_total(args.out_dir)
        # Match the original debug print comparing totals
        print(f"[CHECK] total_rows_written={total_rows} running_sum={running_sum}")

        df_ccdb_only = to_ccdb_only_bw(df_total, args.out_dir)

        if args.make_grid:
            _ = make_grid_merge(df_ccdb_only, args.out_dir)

        # ---- 2x3 plotting (optional) ----
        
        if args.draw_grid:
            import ROOT  # ensure ROOT is imported when plotting is requested
            ccdb_file = args.out_dir / "BW_only_ccdb.dat"
            if not ccdb_file.exists():
                raise FileNotFoundError(f"Cannot draw: missing {ccdb_file}")

            # default output name if none provided
            plot_out = args.plot_out if args.plot_out is not None else (args.out_dir / "bw_plot_grid.png")

            # call your 2x3 plotting helper (already copied into this file)
            draw_grid_2x3(ccdb_file, None, plot_out)
            print(f"[PLOT] 2x3 grid saved -> {plot_out}")

          

        print("[DONE]")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
