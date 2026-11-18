// Pictures for the step-by-step assembly guide (docs/pdf/montage.html).
// Each step is an exploded view: parts float above their place, screws and
// heat-set inserts are drawn in grey/brass with a red line showing where they go.
//
//   openscad -D 'step="k1"' -o ../docs/pdf/img/montage/k1.png --colorscheme=Tomorrow montage.scad
//
// Steps k1..k8 are the sphere base (soundlampe_kugel.scad), z1/z3 the cylinder differences.

include <soundlampe_v1_kugel.scad>

part  = "none";
step  = "k1";
theme = "walnuss";

SCREW = "#8d939b";
BRASS = "#c9a14a";
GUIDE = "#d6402f";

// ---------------------------------------------------------------- helpers
// screw pointing along -Z from its head at the origin
module screw(len, head = 5.5, cs = false) {
  color(SCREW) {
    if (cs) translate([0, 0, -1.7]) cylinder(d1 = 3, d2 = 6, h = 1.7, $fn = 24);
    else cylinder(d = head, h = 3, $fn = 24);
    translate([0, 0, -len]) cylinder(d = 3, h = len, $fn = 16);
  }
}
module insert() { color(BRASS) difference() { cylinder(d = 4.8, h = 5, $fn = 24); translate([0, 0, -1]) cylinder(d = 2.6, h = 7, $fn = 16); } }
module guide(a, b) { color(GUIDE) hull() { translate(a) sphere(d = 1.2, $fn = 8); translate(b) sphere(d = 1.2, $fn = 8); } }
// part exploded along a direction: draws the part moved by v and a guide from the moved to the real place
module along(v, p = [0, 0, 0]) { translate(v) children(); guide(p, p + v); }

module cut_front() { difference() { children(); translate([0, -300, -50]) cube([300, 300, 900]); } }   // open a quarter

// ---------------------------------------------------------------- pieces
module shell_c()  color(TC[0]) sphere_shell();
module plinth_c() color(TC[1]) plinth();
module plate_c()  color(TC[1]) plinth_plate();
module lid_c()    color(TC[0]) sphere_lid();
module driver_c() color("#202231") { cylinder(d = drv_flange_d, h = 3); cylinder(d1 = drv_cutout_d - 4, d2 = 40, h = 30); translate([0, 0, 30]) cylinder(d = 62, h = 34); }
module pr_c() { color("#202231") cylinder(d = pr_flange_d, h = 3); color("#6d7282") translate([0, 0, 3]) cylinder(d = 80, h = 3); }

kx = sqrt(sph_r * sph_r - knob_dz * knob_dz);

// ---------------------------------------------------------------- steps
// k1: heat-set inserts in the shell (flange 4, lid ledge 4, baffles 8), plinth bosses 4
module k1() {
  cut_front() shell_c();
  for (a = [45:90:315]) rotate(a) translate([open_r - 8, 0, plinth_h]) along([0, 0, -30]) rotate([180, 0, 0]) insert();
  for (a = [0:90:270]) rotate(a) translate([k_ledge_r + 3.5, 0, chamber_top]) along([0, 0, 30]) translate([0, 0, -5]) insert();
  for (side = [-1, 1]) for (a = [45:90:315]) let(bd = side < 0 ? drv_bolt_d : pr_bolt_d)
    translate([cos(a) * bd / 2, side * baffle_in, sph_zc + sin(a) * bd / 2]) along([0, -side * 25, 0]) rotate([side * 90, 0, 0]) insert();
}
// k1b: plinth bosses (from below)
module k1b() {
  pri = plinth_d / 2 - plinth_wall;
  plinth_c();
  for (a = [0:90:270]) rotate(a) translate([pri - 4, 0, 0]) along([0, 0, -30]) rotate([180, 0, 0]) translate([0, 0, -5]) insert();
}
// k2: driver front, passive radiator back, 4 + 4 screws M3x10 from inside
module k2() {
  cut_front() shell_c();
  translate([0, -baffle_in, sph_zc]) along([0, 45, 0]) rotate([-90, 0, 0]) driver_c();
  translate([0, baffle_in, sph_zc]) along([0, -45, 0]) rotate([90, 0, 0]) pr_c();
  for (a = [45:90:315]) {
    translate([cos(a) * drv_bolt_d / 2, -baffle_in + 3, sph_zc + sin(a) * drv_bolt_d / 2]) along([0, 70, 0]) rotate([90, 0, 0]) screw(10);
    translate([cos(a) * pr_bolt_d / 2, baffle_in - 3, sph_zc + sin(a) * pr_bolt_d / 2]) along([0, -70, 0]) rotate([-90, 0, 0]) screw(10);
  }
}
// k3: conduit into the plinth pocket, shell onto the plinth, 4x M3x8 from inside the plinth
module k3() {
  plinth_c();
  translate([conduit_pos[0], conduit_pos[1], plinth_h - 1.5]) along([0, 0, 60]) color(TC[1]) sphere_conduit();
  translate([0, 0, 120]) cut_front() shell_c();
  guide([0, -open_r, plinth_h], [0, -open_r, plinth_h + 120]);
  for (a = [45:90:315]) rotate(a) translate([open_r - 8, 0, plinth_h - plinth_top_t]) along([0, 0, -40]) rotate([180, 0, 0]) screw(8);
}
// k4: encoder through the side hole, nut outside, knob on; wadding in
module k4() {
  shell_c(); plinth_c();
  color("#3b3f48") translate([kx - 14, 0, sph_zc + knob_dz]) along([-30, 0, 0]) rotate([0, 90, 0]) { cube([12.5, 13, 6], center = true); translate([0, 0, 3]) cylinder(d = 7, h = 10, $fn = 24); }
  color(SCREW) translate([kx - 2, 0, sph_zc + knob_dz]) along([30, 0, 0]) rotate([0, 90, 0]) cylinder(d = 12, h = 2, $fn = 6);
  color(TC[4]) translate([kx + 1, 0, sph_zc + knob_dz]) along([60, 0, 0]) rotate([0, 90, 0]) knob();
}
// k5: lid onto the ledge, 4x M3x16 countersunk
module k5() {
  shell_c(); plinth_c();
  translate([0, 0, chamber_top]) along([0, 0, 70]) lid_c();
  for (a = [0:90:270]) rotate(a) translate([k_ledge_r + 3.5, 0, chamber_top + lid_t + 8]) along([0, 0, 120]) screw(16, cs = true);
}
// k6: electronics on the bottom plate, plate into the plinth (4x M3x8), rubber feet
module k6() {
  pri = plinth_d / 2 - plinth_wall;
  translate([0, 0, 90]) { plinth_c(); }
  plate_c();
  translate([0, 0, 0]) dummy_electronics();
  for (a = [0:90:270]) rotate(a) translate([pri - 4, 0, 0]) along([0, 0, -40]) rotate([180, 0, 0]) translate([0, 0, 0]) screw(8);
  guide([0, -pri, 3], [0, -pri, 90]);
}
// k7: stem into the lid socket, LED core on the stem, core cap
module k7() {
  shell_c(); plinth_c(); color(TC[0]) translate([0, 0, chamber_top]) sphere_lid();
  color(TC[2]) translate([0, 0, stem_z]) along([0, 0, 30]) ring(stem_od, stem_id, lamp_stem_len);
  color("#e9e3d5") translate([0, 0, stem_top]) along([0, 0, 70]) led_core();
  color("#ffe9a8") translate([0, 0, stem_top + 70]) led_strip_spiral();
  color("#e9e3d5") translate([0, 0, stem_top + core_h]) along([0, 0, 110]) core_cap();
}
// k8: shade. plissee/glocke: spider on the core cap pin, shade over it.
//     kolben/twist/laterne: globe seat with 3x M3x8 on the lid, shade over it.
module k8() {
  shell_c(); plinth_c(); color(TC[0]) translate([0, 0, chamber_top]) sphere_lid();
  color(TC[2]) translate([0, 0, stem_z]) ring(stem_od, stem_id, lamp_stem_len);
  color("#e9e3d5") translate([0, 0, stem_top]) { led_core(); translate([0, 0, core_h]) core_cap(); }
  if (on_base) {
    sz = chamber_top + lid_t + 8;
    color(TC[2]) translate([0, 0, sz]) along([0, 0, 40]) globe_seat();
    for (a = [0:120:240]) rotate(a + 30) translate([seat_d / 2 - 5, 0, sz + 4]) along([0, 0, 75]) screw(8);
    color(TC[3], 0.55) translate([0, 0, lamp_shade_z]) along([0, 0, 190]) shade();
  } else {
    color(TC[3]) translate([0, 0, lamp_shade_z + S_h - 8]) along([0, 0, 60]) spider();
    color(TC[3], 0.55) translate([0, 0, lamp_shade_z]) along([0, 0, 150]) shade();
  }
}

if (step == "k1")  k1();
if (step == "k1b") k1b();
if (step == "k2")  k2();
if (step == "k3")  k3();
if (step == "k4")  k4();
if (step == "k5")  k5();
if (step == "k6")  k6();
if (step == "k7")  k7();
if (step == "k8")  k8();
