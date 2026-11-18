#!/bin/bash
# Exportiert alle Teile aus ../soundlampe.scad als ASCII-STL nach $1 (Standard: ./stl_roh).
# Danach: python3 stl_binaer.py <zielordner> <stl_roh>/*.stl  und  python3 pakete_bauen.py <binärordner>
set -e
OUT=$(realpath -m "${1:-stl_roh}"); mkdir -p "$OUT"; cd "$(dirname "$0")/.."
job() { read n b s p <<< "$1"; openscad -D "base=\"$b\"" -D "shade_style=\"$s\"" -D "part=\"$p\"" -o "$OUT/$n.stl" soundlampe.scad; }
export -f job; export OUT
{
  echo "body_kugel kugel laterne body"; echo "body_zylinder zylinder laterne body"
  for p in plinth plate lid knob led_core; do echo "$p kugel laterne $p"; done
  for s in plissee glocke kolben twist laterne; do echo "shade_$s kugel $s shade"; echo "stem_$s kugel $s stem"; echo "core_cap_$s kugel $s core_cap"; done
  echo "spider_plissee kugel plissee spider"; echo "spider_glocke kugel glocke spider"
} | xargs -P"$(nproc)" -I{} bash -c 'job "{}"'
