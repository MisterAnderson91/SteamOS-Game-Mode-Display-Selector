#!/bin/bash
source venv/bin/activate
python3 -m PyInstaller DisplaySelector.spec
cp -r dist/DisplaySelector/* DisplaySelector.AppDir/usr/bin/
./appimagetool-x86_64.AppImage DisplaySelector.AppDir
