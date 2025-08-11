#!/usr/bin/env python
# coding: utf-8

import ROOT
import pandas as pd
import os
import argparse
import re
import glob

def prepare_output_folder(input_path, base_output_dir):
    # Extract the filename
    filename = os.path.basename(input_path)  # e.g., rec_clas_020139.root

    # Extract number using regex
    match = re.search(r'(\d+)(?=\.root$)', filename)
    if not match:
        raise ValueError(f"No numeric identifier found in input file: {filename}")

    run_number = match.group(1)

    # Create full output path
    full_output_dir = os.path.join(base_output_dir, run_number)
    if not os.path.exists(full_output_dir):
        os.makedirs(full_output_dir)

    return full_output_dir

# Argument parsing
parser = argparse.ArgumentParser(description="ROOT histogram processing")
parser.add_argument("--input", required=True, help="Path to the input ROOT file")
parser.add_argument("--output", required=True, help="Output directory for plots and CSVs")
args = parser.parse_args()

# Use these variables in place of hardcoded paths
# Open input file
histFileData = ROOT.TFile.Open(args.input, "READ")

# Prepare structured output folder
output_dir = prepare_output_folder(args.input, args.output)

# Plot styling functions
def setMarginsTitlesSize(h):
    h.GetXaxis().SetTitleSize(0.04)
    h.GetXaxis().SetLabelSize(0.04)
    h.GetXaxis().SetTitleOffset(0.9)
    h.GetYaxis().SetTitleOffset(0.6)
    h.GetYaxis().SetTitleSize(0.07)
    h.GetYaxis().SetLabelSize(0.07)
    h.GetYaxis().SetNdivisions(6)
    h.GetXaxis().SetNdivisions(30)
    ROOT.TGaxis.SetMaxDigits(3)
    ROOT.gStyle.SetTitleFontSize(0.1)
    ROOT.gPad.SetGrid()
    ROOT.gPad.SetMargin(0.1, 0.15, 0.15, 0.12)
    ROOT.gStyle.SetErrorX(0)
    ROOT.gStyle.SetOptStat(0)

def setHistParam1D(h, color, labelX="wire", labelY="events"):
    setMarginsTitlesSize(h)
    h.SetMarkerColor(color)
    h.SetMarkerSize(0.3)
    h.SetMarkerStyle(20)
    h.SetLineColor(color)
    h.SetLineWidth(1)
    h.GetXaxis().SetTitle(labelX)
    h.GetYaxis().SetTitle(labelY)

def setHistParam2D(h, labelX="wire", labelY="layer"):
    setMarginsTitlesSize(h)
    h.GetXaxis().SetNdivisions(10)
    h.GetYaxis().SetNdivisions(10)
    h.GetXaxis().SetTitle(labelX)
    h.GetYaxis().SetTitle(labelY)
    ROOT.gStyle.SetPalette(55)

def readHistS(file, name, out, suffix='S'):
    folder = 'overview/'
    for sec in range(6):
        out.append(file.Get(f'{folder}{name}{suffix}{sec}'))

def readHistSandSL(file, name, out):
    folder = 'overview/'
    for sec in range(6):
        out.append([file.Get(f'{folder}{name}_S{sec}_SL{sl}') for sl in range(6)])

def readSLS(file, name, out):
    folder = 'overview/'
    for sec in range(6):
        out.append([[file.Get(f'{folder}{name}_S{sec}_SL{sl}_L{lay}') for lay in range(6)] for sl in range(6)])

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def fit_clone(func_base, name):
    # Create the new TF1 using the known formula string
    formula = func_base.GetTitle()  # like "pol3"
    f = ROOT.TF1(name, formula, func_base.GetXmin(), func_base.GetXmax())

    # SAFELY copy parameters
    npar = func_base.GetNpar()
    for i in range(npar):
        param = func_base.GetParameter(i)
        f.SetParameter(i, param)
        f.SetParError(i, func_base.GetParError(i))  # optional
        #print(f"Copying param[{i}] = {param}")

    return f


####################################################################

for iSL in range(6):
  out_dir = f'{output_dir}/results/SL{iSL + 1}'
  ensure_dir(out_dir)
  
  # Delete all CSV files in the folder
  for file_path in glob.glob(os.path.join(out_dir, "*.csv")):
      try:
          os.remove(file_path)
          print(f"Deleted old file: {file_path}")
      except OSError as e:
          print(f"Error deleting {file_path}: {e}")

####################################################################

# Load and plot avgWireSummed histograms
aveWireSum = []
readHistS(histFileData, 'avgWireSummed', aveWireSum, suffix='_SL')

canvas = ROOT.TCanvas("c2", "c2", 2500, 1200)
canvas.Divide(3, 2, 0.0001, 0.0001)

for iS, hist in enumerate(aveWireSum):
    canvas.cd(iS + 1)
    # Force minimum content for bins > 109
    for iXbin in range(110, hist.GetNbinsX() + 1):
        if hist.GetBinContent(iXbin) < 10:
            hist.SetBinContent(iXbin, 10)
    setHistParam1D(hist, color=4)
    hist.SetTitle(f'         Sum All Sec, SupLay {iS + 1}')
    hist.Draw()

ensure_dir(f"{output_dir}/plots")
canvas.Print(f"{output_dir}/plots/avgWireSum.png", 'png')

# Load and plot avgWire histograms for each sector & superlayer
avgWire = []
readHistSandSL(histFileData, 'avgWire', avgWire)

# --- Accuracy thresholds ---
accuracy = 15
minBorder = 1 - accuracy / 100
maxBorder = 1 + 1.2 * accuracy / 100

# --- Polynomial function definitions ---
def GetPol3_value(x, p0, p1, p2, p3):
    return p0 + x * p1 + x * x * p2 + x * x * x * p3

def GetPol1hyperb_value(x, p0, p1, p2):
    return p0 + x * p1 + p2 / x

# --- Fit subranges for each SuperLayer ---
startG1fit = [0, 0, 0, 0, 0, 5]
endG1fit   = [7, 7, 7, 9, 9, 14]
startG2fit = [6, 6, 6, 8, 9, 14]
endG2fit   = [32, 32, 28, 50, 20, 25]
startG3fit = [30, 30, 26, 50, 20, 25]
endG3fit   = [75, 75, 75, 90, 75, 80]
startG4fit = [75, 75, 75, 90, 75, 80]
maxWireFit = 114

# --- Containers ---
histDiff = []
g1_sec, g2_sec, g3_sec, g4_sec = [], [], [], []

# --- Fit and filter wires by SuperLayer ---
for iSL in range(6):
    c2 = ROOT.TCanvas(f"c2_{iSL}", "Canvas", 2500, 1000)
    c2.Divide(4, 2, 0.0001, 0.0001)
    histDiff.append([])

    # Sum histogram and fitting
    histSum = aveWireSum[iSL]
    c2.cd(8)
    setHistParam1D(histSum, 115)
    histSum.SetTitle(f'     avgWire Sum, SupLay {iSL + 1}')

    g1 = ROOT.TF1("g1", "pol3", startG1fit[iSL], endG1fit[iSL])
    g2 = ROOT.TF1("g2", "pol3", startG2fit[iSL], endG2fit[iSL])
    g3 = ROOT.TF1("g3", "pol3", startG3fit[iSL], endG3fit[iSL])
    g4 = ROOT.TF1("g4", "[0] + [1]*x + [2]/x", startG4fit[iSL], maxWireFit)

    histSum.Fit(g1, 'WQR')
    histSum.Fit(g2, 'WQR+')
    histSum.Fit(g3, 'WQR+')
    histSum.Fit(g4, 'WQR+')

    # Per sector fits
    g1_sec.append([]); g2_sec.append([]); g3_sec.append([]); g4_sec.append([])

    histSum.Draw()

    for sec in range(6):
        pad = sec + 1 if sec < 3 else sec + 2
        c2.cd(pad)

        hist = avgWire[sec][iSL]
        fullName = f'fitDiffS{sec}_SL{iSL}'
        hdiff = ROOT.TH1D(fullName, fullName, hist.GetNbinsX(), hist.GetXaxis().GetXmin(), hist.GetXaxis().GetXmax())
        histDiff[-1].append(hdiff)

        setHistParam1D(hist, 4)
        hist.SetTitle(f'          avgWire Sec {sec + 1}, SupLay {iSL + 1}')



        fit_integral = histSum.Integral(startG1fit[iSL], maxWireFit)
        hist_integral = hist.Integral(startG1fit[iSL], maxWireFit)
        norm = hist_integral / fit_integral if fit_integral > 0 else 0

      

        g1f = fit_clone(g1, "g1_sec_SL" + str(iSL) + '_S'+ str(sec))
        g2f = fit_clone(g2, "g2_sec_SL" + str(iSL) + '_S'+ str(sec))
        g3f = fit_clone(g3, "g3_sec_SL" + str(iSL) + '_S'+ str(sec))
        g4f = fit_clone(g4, "g4_sec_SL" + str(iSL) + '_S'+ str(sec))
      


      
        for f in [g1f, g2f, g3f, g4f]:
            for i in range(f.GetNpar()):
                f.SetParameter(i, f.GetParameter(i) * norm)

        g1_sec[-1].append(g1f)
        g2_sec[-1].append(g2f)
        g3_sec[-1].append(g3f)
        g4_sec[-1].append(g4f)
      

        # Loop over bins to filter wires
        for iBin in range(1, hist.GetNbinsX() + 1):
            x = hist.GetBinCenter(iBin)
            y = hist.GetBinContent(iBin)

            if x <= endG1fit[iSL]:
                fit_val = GetPol3_value(x, *[g1f.GetParameter(i) for i in range(4)])
            elif x <= endG2fit[iSL]:
                fit_val = GetPol3_value(x, *[g2f.GetParameter(i) for i in range(4)])
            elif x <= endG3fit[iSL]:
                fit_val = GetPol3_value(x, *[g3f.GetParameter(i) for i in range(4)])
            else:
                fit_val = GetPol1hyperb_value(x, *[g4f.GetParameter(i) for i in range(3)])

            if (minBorder * fit_val < y < maxBorder * fit_val and 15 <= x < 107) or x < 15 or x >= 107:
                histDiff[-1][-1].SetBinContent(iBin, y)

        # Draw
        hist.SetFillColor(2)
        hist.SetAxisRange(0, 115, 'x')
        hist.Draw()
        
        histDiff[-1][-1].SetFillColor(9)
        histDiff[-1][-1].Draw("same")
        
        g1_sec[-1][-1].Draw("same")
        g2_sec[-1][-1].Draw("same")
        g3_sec[-1][-1].Draw("same")
        g4_sec[-1][-1].Draw("same")
        
    ensure_dir(f'{output_dir}/SupLayers')
  
    filename = f"{output_dir}/SupLayers/SLnew{iSL + 1}.png"
    c2.Print(filename)

    #c2.Print(f'{output_dir}/SupLayers/SLnew{iSL + 1}.png')






####################################################################



# Overlay plots and save integrated view per SuperLayer
canvas = ROOT.TCanvas("c2", "c2", 2000, 600)
canvas.Divide(3, 2, 0.0001, 0.0001)
for iSL in range(6):
    canvas.cd(iSL + 1)
    hist = aveWireSum[iSL]
    setHistParam1D(hist, 9)
    hist.SetLineWidth(3)
    hist.SetAxisRange(0, 114, 'x')
    hist.Draw()
  
ensure_dir(f"{output_dir}/plots")
canvas.Print(f"{output_dir}/plots/avgWireInt.png")

# --- Thresholds for layer-level accuracy ---
accuracyLayLow = 42
accuracyLayHigh = 150
accuracyLayLow_Mid = 38

minBorderLay = 1 - accuracyLayLow / 100
minBorderLay_Mid = 1 - accuracyLayLow_Mid / 100
maxBorderLay = 1 + accuracyLayHigh / 100

# --- Load 2D histograms and detailed layer wire distributions ---
layVScomp_SL_L, layVScomp_SL_R = [], []
readHistSandSL(histFileData, 'layVScomp_leftSL', layVScomp_SL_L)
readHistSandSL(histFileData, 'layVScomp_rightSL', layVScomp_SL_R)

layersSLS = []
readSLS(histFileData, 'wireINlayer', layersSLS)

# --- Containers for fits and filtered results ---
g1_lay, g2_lay, g3_lay, g4_lay = [], [], [], []
histDiffSecLay = []

# --- Main filtering loop ---
for iSL in range(6):
    g1_lay.append([]); g2_lay.append([]); g3_lay.append([]); g4_lay.append([])
    histDiffSecLay.append([])

    for sec in range(6):
        c2 = ROOT.TCanvas("c2", "c2", 1900, 600)
        c2.Divide(4, 2, 0.0001, 0.0001)
        c2.Draw()

        g1_lay[iSL].append([]); g2_lay[iSL].append([]); g3_lay[iSL].append([]); g4_lay[iSL].append([])
        histDiffSecLay[iSL].append([])

        for lay in range(6):
            h = layersSLS[sec][iSL][lay]
            c2.cd(lay + 1)
            setHistParam1D(h, 4)
            h.SetTitle(f'Wires, S {sec + 1}, SupLay {iSL + 1}, Abs. Lay {iSL * 6 + lay + 1}')

            diff_name = f'histDiffSecLaySL{iSL}S{sec}_lay{lay}'
            h_diff = ROOT.TH1D(diff_name, diff_name, h.GetNbinsX(), h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax())
            histDiffSecLay[iSL][sec].append(h_diff)

            # Normalize to sector-level fits
            sectorInt = avgWire[sec][iSL].Integral(startG1fit[iSL], maxWireFit)
            layInt = h.Integral(startG1fit[iSL], maxWireFit)
            norm = layInt / sectorInt if sectorInt > 0 else 0

            g1 = fit_clone(g1_sec[iSL][sec], "g1")
            g2 = fit_clone(g2_sec[iSL][sec], "g2")
            g3 = fit_clone(g3_sec[iSL][sec], "g3")
            g4 = fit_clone(g4_sec[iSL][sec], "g4")

            for f in [g1, g2, g3, g4]:
                for i in range(f.GetNpar()):
                    f.SetParameter(i, f.GetParameter(i) * norm)

            g1_lay[iSL][sec].append(g1)
            g2_lay[iSL][sec].append(g2)
            g3_lay[iSL][sec].append(g3)
            g4_lay[iSL][sec].append(g4)

            # Bin-by-bin filtering
            prev1, prev2 = 0, 0
            for iBin in range(1, h.GetNbinsX() + 1):
                x = h.GetBinCenter(iBin)
                y = h.GetBinContent(iBin)

                # Select function by wire range
                fit_val = 0
                if x <= startG2fit[iSL]:
                    fit_val = GetPol3_value(x, *[g1.GetParameter(i) for i in range(4)])
                elif x <= startG3fit[iSL]:
                    fit_val = GetPol3_value(x, *[g2.GetParameter(i) for i in range(4)])
                elif x <= startG4fit[iSL]:
                    fit_val = GetPol3_value(x, *[g3.GetParameter(i) for i in range(4)])
                else:
                    fit_val = GetPol1hyperb_value(x, *[g4.GetParameter(i) for i in range(3)])

                keep = (

                    ( iBin < 12 and y < maxBorderLay * fit_val and y > minBorderLay * fit_val ) or iBin < 4 or iBin > 105
                   or ( iBin >= 12 and iBin < 75 and y < 2.0 * maxBorderLay * fit_val and y >  minBorderLay_Mid * fit_val)
                   or ( iBin >= 75 and iBin < 100 and y < (2.0 * maxBorderLay * fit_val  or iBin > 98) and y > 1.0 * minBorderLay * fit_val  )
                   or ( iBin >= 100 and y < 2.0 * maxBorderLay * fit_val and y > 0.6 * minBorderLay * fit_val )
                )

                if keep:
                    h_diff.SetBinContent(iBin, y)

                # Spike suppression: drop neighbors if they are inconsistent
                if 12 < iBin < 90:
                    cur = h_diff.GetBinContent(iBin)
                    pr1 = h_diff.GetBinContent(iBin - 1)
                    pr2 = h_diff.GetBinContent(iBin - 2)
                    if (
                        cur > 1 and pr1 > 1 and pr2 > 1 and
                        abs(cur - fit_val) / fit_val < 0.2 and
                        abs(pr1 - prev1) / prev1 > 0.25 and
                        abs(pr1 - cur) / pr1 > 0.25 and
                        abs(pr1 - pr2) / pr2 > 0.25 and
                        abs(pr2 - prev2) / prev2 < 0.2
                    ):
                        h_diff.SetBinContent(iBin - 1, 0)

                prev2, prev1 = prev1, fit_val

            # Plot
            h.SetFillColor(2)
            h.SetAxisRange(0, 114, 'x')
            h.Draw()
            h_diff.SetFillColor(9)
            h_diff.Draw("same")
            g1.Draw("same")
            g2.Draw("same")
            g3.Draw("same")
            g4.Draw("same")

        # LayVSComp 2D Plots
        for idx, side in enumerate([layVScomp_SL_L, layVScomp_SL_R], start=7):
            c2.cd(idx)
            h2d = side[sec][iSL]
            setHistParam2D(h2d)
            h2d.SetTitle(f'S{sec + 1}')
            if side is layVScomp_SL_R:
                ROOT.gPad.SetLogz()
            h2d.Draw("COLZ")

        out_dir = f'{output_dir}/results/SL{iSL + 1}'
        ensure_dir(out_dir)
        c2.Print(f'{out_dir}/sec{sec + 1}.png', "png")

    # Export filtered wires to CSV by sector
    for sec in range(6):
        SL_vals, Layer_vals, Sector_vals, Wire_vals = [], [], [], []
        for lay in range(6):
            h = histDiffSecLay[iSL][sec][lay]
            for iXbin in range(5, h.GetNbinsX() + 1):
                wire = h.GetBinCenter(iXbin)
                val = h.GetBinContent(iXbin)
                if val <= 1 and 5 < wire < 106:
                    SL_vals.append(iSL + 1)
                    Layer_vals.append(lay + 1)
                    Sector_vals.append(sec + 1)
                    Wire_vals.append(wire)

        if SL_vals:
            df = pd.DataFrame({
                "Super Layer": SL_vals,
                "Sector": Sector_vals,
                "Layer": Layer_vals,
                "Wire": Wire_vals
            })
            out_dir = f'{output_dir}/results/SL{iSL + 1}'
            ensure_dir(out_dir)
            df.to_csv(f'{out_dir}/BWsec{sec + 1}.csv', index=False)
