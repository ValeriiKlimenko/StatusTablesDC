#include <bitset>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>

#include <TApplication.h>
#include <TBenchmark.h>
#include <TCanvas.h>
#include <TChain.h>
#include <TDatabasePDG.h>
#include <TFile.h>
#include <TH1.h>
#include <TH1F.h>
#include <TH2.h>
#include <TH2F.h>
#include <TROOT.h>
#include <TSystem.h>
#include <TTree.h>
#include <TLorentzVector.h>
#include <TVector3.h>
#include <HipoChain.h>

#include "clas12reader.h"
#include "clas12databases.h"
#include "HipoChain.h"

using namespace std;
namespace fs = std::filesystem;

const size_t nSec = 6;
const size_t nSuperLayer = 6;
const size_t nLayerINsupLay = 6;
const size_t nWire = 115;
const size_t nLayers = 39;
const float wireMin = -0.5, wireMax = 114.5;
const float wireMin_left = -0.5, wireMax_left = 40.5;
const float wireMin_right = 37.5, wireMax_right = 114.5;
const float layerMin = -0.5, layerMax = 38.5;

void processHipoAndAnalyze(const TString& inputListFile, const TString& outputFolder) {
    fs::create_directories(outputFolder.Data());

    ifstream chainIn(inputListFile.Data());
    TString firstFile;
    chainIn >> firstFile;

    TString baseName = gSystem->BaseName(firstFile);
    Ssiz_t evioIndex = baseName.Index(".evio");
    if (evioIndex != kNPOS) {
        baseName.Remove(evioIndex);
    }
    baseName += ".root";
    TString outPath = outputFolder + "/" + baseName;
    TFile outFile(outPath, "recreate");

    // Histograms
    TH1F *avgWire[nSec][nSuperLayer];
    TH1F *wireINlayer[nSec][nSuperLayer][nLayerINsupLay];
    TH1F *avgWireSummed[nSuperLayer];
    TH2F *layVScomp_left[nSec], *layVScomp_right[nSec];
    TH2F *layVScomp_leftSL[nSec][nSuperLayer], *layVScomp_rightSL[nSec][nSuperLayer];
    TH2F *layVScomp_oneSupLay[nSec][nSuperLayer];

    for (size_t iSec = 0; iSec < nSec; iSec++) {
        layVScomp_left[iSec]  = new TH2F(Form("layVScomp_left_S%zu", iSec), "", 41, wireMin_left, wireMax_left, nLayers, layerMin, layerMax);
        layVScomp_right[iSec] = new TH2F(Form("layVScomp_right_S%zu", iSec), "", 77, wireMin_right, wireMax_right, nLayers, layerMin, layerMax);

        for (size_t iSupLay = 0; iSupLay < nSuperLayer; iSupLay++) {
            avgWire[iSec][iSupLay] = new TH1F(Form("avgWire_S%zu_SL%zu", iSec, iSupLay), "", nWire, wireMin, wireMax);
            layVScomp_leftSL[iSec][iSupLay]  = new TH2F(Form("layVScomp_leftSL_S%zu_SL%zu", iSec, iSupLay), "", 41, wireMin_left, wireMax_left, 8, iSupLay * 6 - 0.5, iSupLay * 6 + 6.5);
            layVScomp_rightSL[iSec][iSupLay] = new TH2F(Form("layVScomp_rightSL_S%zu_SL%zu", iSec, iSupLay), "", 77, wireMin_right, wireMax_right, 8, iSupLay * 6 - 0.5, iSupLay * 6 + 6.5);
            layVScomp_oneSupLay[iSec][iSupLay] = new TH2F(Form("layVScomp_oneSupLay_S%zu_SL%zu", iSec, iSupLay), "", 77, wireMin_right, wireMax_right, 8, iSupLay * 6 - 0.5, iSupLay * 6 + 6.5);

            for (size_t iLay = 0; iLay < nLayerINsupLay; iLay++) {
                wireINlayer[iSec][iSupLay][iLay] = new TH1F(Form("wireINlayer_S%zu_SL%zu_L%zu", iSec, iSupLay, iLay), "", nWire, wireMin, wireMax);
            }
        }
    }
    for (size_t iSupLay = 0; iSupLay < nSuperLayer; iSupLay++) {
        avgWireSummed[iSupLay] = new TH1F(Form("avgWireSummed_SL%zu", iSupLay), "", nWire, wireMin, wireMax);
    }

    // Load HIPO files
    HipoChain chain;
    chainIn.clear(); chainIn.seekg(0);
    TString nextFile;
    while (chainIn >> nextFile) {
        chain.Add(nextFile);
    }

    auto config_c12 = chain.GetC12Reader();
    auto idx_HBS = config_c12->addBank("TimeBasedTrkg::TBSegments");
    auto hbs_Sec = config_c12->getBankOrder(idx_HBS, "sector");
    auto hbs_SupLay = config_c12->getBankOrder(idx_HBS, "superlayer");
    auto hbs_AvgWire = config_c12->getBankOrder(idx_HBS, "avgWire");

    auto idx_TBH = config_c12->addBank("TimeBasedTrkg::TBHits");
    auto tdc_Sec = config_c12->getBankOrder(idx_TBH, "sector");
    auto tdc_Lay = config_c12->getBankOrder(idx_TBH, "layer");
    auto tdc_SupLay = config_c12->getBankOrder(idx_TBH, "superlayer");
    auto tdc_Comp = config_c12->getBankOrder(idx_TBH, "wire");

    auto& c12 = chain.C12ref();

    // Main loop
    while (chain.Next()) {
        for (int itdc = 0; itdc < c12->getBank(idx_TBH)->getRows(); ++itdc) {
            int sec = c12->getBank(idx_TBH)->getInt(tdc_Sec, itdc) - 1;
            int lay = c12->getBank(idx_TBH)->getInt(tdc_Lay, itdc) - 1;
            int supLay = c12->getBank(idx_TBH)->getInt(tdc_SupLay, itdc) - 1;
            int wire = c12->getBank(idx_TBH)->getInt(tdc_Comp, itdc);

            layVScomp_left[sec]->Fill(wire, supLay * 6 + lay + 1);
            layVScomp_right[sec]->Fill(wire, supLay * 6 + lay + 1);
            layVScomp_leftSL[sec][supLay]->Fill(wire, supLay * 6 + lay + 1);
            layVScomp_rightSL[sec][supLay]->Fill(wire, supLay * 6 + lay + 1);
            wireINlayer[sec][supLay][lay]->Fill(wire);
            layVScomp_oneSupLay[sec][supLay]->Fill(wire, supLay * 6 + lay + 1);
        }

        for (int ihbs = 0; ihbs < c12->getBank(idx_HBS)->getRows(); ++ihbs) {
            int sec = c12->getBank(idx_HBS)->getInt(hbs_Sec, ihbs) - 1;
            int supLay = c12->getBank(idx_HBS)->getInt(hbs_SupLay, ihbs) - 1;
            float avgWireVal = c12->getBank(idx_HBS)->getFloat(hbs_AvgWire, ihbs);
        
            avgWireSummed[supLay]->Fill(avgWireVal);
            avgWire[sec][supLay]->Fill(avgWireVal);
        }
    }

    // Write histos
    outFile.cd();
    outFile.mkdir("overview");
    outFile.cd("overview");
    for (size_t iSec = 0; iSec < nSec; iSec++) {
        layVScomp_left[iSec]->Write();
        layVScomp_right[iSec]->Write();
        for (size_t iSupLay = 0; iSupLay < nSuperLayer; iSupLay++) {
            avgWire[iSec][iSupLay]->Write();
            layVScomp_oneSupLay[iSec][iSupLay]->Write();
            layVScomp_leftSL[iSec][iSupLay]->Write();
            layVScomp_rightSL[iSec][iSupLay]->Write();
            for (size_t iLay = 0; iLay < nLayerINsupLay; iLay++) {
                wireINlayer[iSec][iSupLay][iLay]->Write();
            }
        }
    }
    for (size_t iSupLay = 0; iSupLay < nSuperLayer; iSupLay++) {
        avgWireSummed[iSupLay]->Write();
    }

    outFile.Close();
    cout << "✅ All done. Output saved to: " << outPath << endl;
}

void HIPO_to_HIST(const TString& inputFolder, const TString& outputFolder) {
    if (!fs::is_directory(inputFolder.Data())) {
        std::cerr << "❌ Invalid input folder: " << inputFolder << endl;
        return;
    }

    for (const auto& entry : fs::directory_iterator(inputFolder.Data())) {
        TString path = entry.path().string();
        if (entry.is_regular_file() && path.EndsWith(".txt")) {
            cout << "📄 Processing: " << path << endl;
            processHipoAndAnalyze(path, outputFolder);
        }
    }

    cout << "✅ All files processed and saved to: " << outputFolder << endl;
}
