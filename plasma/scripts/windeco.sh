#!/usr/bin/env bash
# Flat Breeze window decoration tuned to the HaltMono palette. Usage: windeco.sh [kwriteconfig6 --file prefix]
set -euo pipefail
dir=${1:-}
kw() { kwriteconfig6 --file "${dir}$1" --group "$2" --key "$3" "$4"; }
kw breezerc Common ShadowSize ShadowSmall
kw breezerc Common ShadowStrength 160
kw breezerc Common ShadowColor 0,0,0
kw breezerc Windeco TitleAlignment AlignLeft
kw breezerc Windeco ButtonSize ButtonSmall
kw breezerc Windeco DrawBackgroundGradient false
kw breezerc Windeco DrawBorderOnMaximizedWindows false
kw breezerc Windeco OutlineCloseButton false
# The group was renamed in Plasma 6.3 and both names are still read depending on the code path.
for g in org.kde.kdecoration2 org.kde.kdecoration3; do
    kw kwinrc "$g" library org.kde.breeze
    kw kwinrc "$g" theme Breeze
    kw kwinrc "$g" BorderSize Tiny
    kw kwinrc "$g" BorderSizeAuto false
    kw kwinrc "$g" ButtonsOnLeft ""
    kw kwinrc "$g" ButtonsOnRight IAX
done
