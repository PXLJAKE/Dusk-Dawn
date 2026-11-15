// Soundlampe "Kugel" – second base design: a sphere band on a slim plinth.
//
// The original cylinder base (soundlampe.scad) stays as it is. This file reuses
// its lamp parts (stem, LED core, core cap, spider, shades, globe seat, knob) and
// only replaces the base:
//
//   plinth          electronics compartment (Pi 3 A+ / Zero 2 W + DigiAMP+, LM2596)
//   sphere_shell    sealed speaker chamber, ~3.1 l gross / ~2.8 l net (cylinder: 2.1 l net)
//   sphere_lid      flat lid with stem socket, sits in the top opening
//   plinth_plate    bottom plate with the board standoffs
//   sphere_conduit  cable tube through the chamber
//
// Render one part at a time:
//   openscad -D 'part="sphere_shell"' -o stl/sphere_shell.stl soundlampe_kugel.scad
// Pictures: part = "kugel_assembly" | "kugel_section", theme = see THEMES below.
//
// The sphere is cut at +-45 deg latitude, so the shell prints upright without
// supports (the lower half leans out by at most 45 deg). Lid and plinth are flat parts.
// Acoustics: a sphere has no parallel walls (fewer standing waves), diffracts
// smoothly and is very stiff for its wall thickness, so it needs no extra ribs.

include <soundlampe.scad>

part  = "kugel_assembly";
theme = "nachtblau";

/* [Sphere base] */
sph_r    = 102;    // outer radius of the sphere
sph_wall = 4;      // 4 mm, print with 100 % perimeters
plinth_d = 150;
plinth_h = 44;     // electronics compartment incl. 4 mm top plate
plinth_wall = 3;
plinth_top_t = 4;
flange_t = 6;      // inner ring at the bottom of the shell, screwed onto the plinth
baffle_in  = 72;   // inner face of the baffles from the centre (driver flange sits here)
baffle_thk = 8;
grille_r   = 44;   // radius of the round hole field in front of each driver
hole_d     = 4;
hole_pitch = 6.5;
knob_dz    = 28;   // encoder height above the sphere centre (right side)

// derived
sph_ri = sph_r - sph_wall;
cut_h  = sph_r * cos(45);              // half height of the band
sph_zc = plinth_h + cut_h;             // sphere centre above the table
band_top = plinth_h + 2 * cut_h;
open_r = sph_r * sin(45);              // outer radius at the cuts
inner_r_at = function(z) sqrt(max(0, sph_ri * sph_ri - (z - sph_zc) * (z - sph_zc)));

// hand the lid height to the lamp parts of soundlampe.scad
// OpenSCAD evaluates an overridden include variable at its original place, so this has to be
// written with numbers: plinth_h + 2 * sph_r * cos(45). Change it together with those two.
base_h = 44 + 2 * 102 * cos(45);       // chamber_top = base_h - lid_t, stem and globe seat follow
// keep the plissee/glocke shade where it was on the cylinder: the base is 28 mm taller,
// so the stem is 28 mm shorter (same overall height). Numbers again, as for base_h.
stem_len = 150 - (44 + 2 * 102 * cos(45) - 160);
buck_center = [0, -50];                // LM2596 moved inwards for the narrower plinth
k_chamber_bot = plinth_h + flange_t;   // top of the bottom flange
k_ledge_r = inner_r_at(chamber_top) - 7;

// ------------------------------------------------------------------ themes
// [sphere, plinth, accent (stem, ring), shade, knob]
function theme_colors(t) =
  t == "walnuss"    ? ["#6b4630", "#3d281c", "#c19a5b", "#f1e4c8", "#e9dcc2"] :
  t == "salbei"     ? ["#8c9c82", "#f1eee6", "#c8a46a", "#fbf6ea", "#f1eee6"] :
  t == "terrakotta" ? ["#b4623f", "#efe6d6", "#c9a063", "#f6ecd9", "#efe6d6"] :
  t == "schwarz"    ? ["#25262a", "#25262a", "#c79b4b", "#efe2c4", "#c79b4b"] :
  t == "creme"      ? ["#ece5d6", "#8a6a4c", "#b8925a", "#fbf3e2", "#8a6a4c"] :
  /* nachtblau */     ["#3c4157", "#2b2f3d", "#b88a3c", "#f3ead8", "#d0c7b3"];
TC = theme_colors(theme);

// ------------------------------------------------------------------ parts
module k_band() {   // the sphere cut to the band between the two 45 deg latitudes
  intersection() {
    translate([0, 0, sph_zc]) sphere(r = sph_r, $fn = 160);
    translate([-sph_r, -sph_r, plinth_h]) cube([2 * sph_r, 2 * sph_r, 2 * cut_h]);
  }
}

module k_hole_field(side) {   // side -1 front (-Y), +1 back (+Y); stops before the baffle
  for (iz = [-8:8]) for (ix = [-8:8]) {
    x = ix * hole_pitch + (abs(iz) % 2 ? hole_pitch / 2 : 0);
    z = iz * hole_pitch * 0.866;
    if (x * x + z * z <= grille_r * grille_r)
      translate([x, side * (baffle_in + baffle_thk + 2), sph_zc + z]) rotate([side * -90, 0, 0])
        rotate(30) cylinder(d = hole_d / cos(30), h = 40, $fn = 6);   // hexagonal holes bridge cleanly
  }
}

module k_baffle(side, cut_d, bolt_d) {
  y0 = side < 0 ? -(baffle_in + baffle_thk) : baffle_in;
  difference() {
    intersection() {
      translate([0, 0, sph_zc]) sphere(r = sph_ri + 0.5, $fn = 120);
      translate([-sph_r, y0, k_chamber_bot]) cube([2 * sph_r, baffle_thk, chamber_top - k_chamber_bot]);
    }
    translate([0, side * (baffle_in + baffle_thk / 2), sph_zc]) teardrop_y(cut_d, baffle_thk + 2);
    for (a = [45:90:315])
      translate([cos(a) * bolt_d / 2, side * (baffle_in + baffle_thk / 2), sph_zc + sin(a) * bolt_d / 2])
        rotate([90, 0, 0]) cylinder(d = drv_bolt_hole, h = baffle_thk + 2, center = true, $fn = 24);
  }
}

module sphere_shell() {
  kx = sqrt(sph_r * sph_r - knob_dz * knob_dz);    // sphere surface at the knob height
  difference() {
    union() {
      difference() {
        k_band();
        translate([0, 0, sph_zc]) sphere(r = sph_ri, $fn = 160);
      }
      // bottom flange: printed on the bed, screwed onto the plinth from below
      intersection() {
        translate([0, 0, plinth_h]) ring(2 * open_r, 2 * (open_r - 16), flange_t);
        translate([0, 0, sph_zc]) sphere(r = sph_r - 0.1, $fn = 160);
      }
      // lid ledge with a 45 deg underside
      intersection() {
        translate([0, 0, sph_zc]) sphere(r = sph_r - 0.1, $fn = 160);
        rotate_extrude($fn = 160) polygon([[k_ledge_r, chamber_top], [sph_r, chamber_top], [sph_r, chamber_top - (sph_r - k_ledge_r)]]);
      }
      k_baffle(-1, drv_cutout_d, drv_bolt_d);
      k_baffle(+1, pr_cutout_d, pr_bolt_d);
    }
    k_hole_field(-1);
    k_hole_field(+1);
    // 45 deg chamfer on the inner top edge, the lid plug sits in it
    translate([0, 0, band_top - 3]) cylinder(r1 = inner_r_at(band_top), r2 = inner_r_at(band_top) + 3, h = 3 + eps, $fn = 160);
    // encoder: flat seat outside, 7.4 mm bushing hole
    translate([kx - 2, 0, sph_zc + knob_dz]) rotate([0, 90, 0]) cylinder(d = 18, h = 20, $fn = 48);
    translate([kx - 12, 0, sph_zc + knob_dz]) rotate([0, 90, 0]) cylinder(d = 7.4, h = 20, $fn = 32);
    // M3 heat-set inserts: 4 in the flange (from below), 4 in the lid ledge (from above)
    for (a = [45:90:315]) rotate(a) translate([open_r - 8, 0, plinth_h - eps]) cylinder(d = 4.2, h = flange_t - 1, $fn = 24);
    for (a = [0:90:270]) rotate(a) translate([k_ledge_r + 3.5, 0, chamber_top - 6]) cylinder(d = 4.2, h = 6 + eps, $fn = 24);
  }
}

module sphere_lid() {
  lid_r = inner_r_at(band_top) - 0.4;
  difference() {
    union() {
      cylinder(r = lid_r, h = lid_t - 3);                                   // plug in the top opening,
      translate([0, 0, lid_t - 3]) cylinder(r1 = lid_r, r2 = lid_r + 3, h = 3); // 45 deg into the chamfered rim
      // cap: wide enough for the globe seat of every shade (twist is the widest),
      // 45 deg underside so the lid prints flat without supports
      cap_r = on_base ? max(lid_r + 4, seat_d / 2 + 3) : lid_r + 4;
      rotate_extrude($fn = 160) polygon([[0, lid_t], [lid_r + 3, lid_t], [cap_r, lid_t + cap_r - lid_r - 3],
        [cap_r, lid_t + 6.5], [cap_r - 1.5, lid_t + 8], [0, lid_t + 8]]);
      translate([0, 0, lid_t]) cylinder(d = stem_od + 12, h = 22);          // stem socket
    }
    translate([0, 0, lid_t + 4]) cylinder(d = stem_od + 0.4, h = 40);
    // cable path: conduit -> channel in the lid -> stem
    translate([conduit_pos[0], conduit_pos[1], -eps]) cylinder(d = 8, h = lid_t + 2.5 + eps);
    hull() for (p = [[0, 0], conduit_pos]) translate([p[0], p[1], lid_t + 2.5]) sphere(d = 6, $fn = 24);
    // countersunk screws into the ledge
    for (a = [0:90:270]) rotate(a) translate([k_ledge_r + 3.5, 0, -eps]) {
      cylinder(d = 3.4, h = 20, $fn = 20);
      translate([0, 0, lid_t + 8 - 1.8]) cylinder(d1 = 3.4, d2 = 6.8, h = 1.8 + 2 * eps, $fn = 24);
    }
    // globe seat screws (globe shades)
    for (a = [0:120:240]) rotate(a + 30) translate([seat_d / 2 - 5, 0, lid_t + 8 - 6]) cylinder(d = 4.2, h = 7, $fn = 20);
  }
}

module sphere_conduit() { ring(16, 10, chamber_top - k_chamber_bot + 0.0); }

// plinth: printed upside down (top plate on the bed)
module plinth() {
  pr = plinth_d / 2;
  pri = pr - plinth_wall;
  difference() {
    union() {
      ring(plinth_d, plinth_d - 2 * plinth_wall, plinth_h);
      translate([0, 0, plinth_h - plinth_top_t]) cylinder(r = pr - eps, h = plinth_top_t);
      // bosses for the bottom plate
      for (a = [0:90:270]) rotate(a) translate([pri - 4, 0, 0]) cylinder(d = 10, h = plinth_h, $fn = 32);
      translate(conduit_pos) translate([0, 0, plinth_h]) ring(9.8, 6, 6);   // stub for the conduit
    }
    // screws up into the shell flange (heads inside the plinth)
    for (a = [45:90:315]) rotate(a) translate([open_r - 8, 0, plinth_h - plinth_top_t - eps]) cylinder(d = 3.4, h = 10, $fn = 20);
    // speaker cables and conduit, sealed with silicone after wiring
    for (p = [[30, 0], [-30, 0]]) translate([p[0], p[1], plinth_h - plinth_top_t - eps]) cylinder(d = 5, h = 10, $fn = 20);
    translate([conduit_pos[0], conduit_pos[1], plinth_h - plinth_top_t - eps]) cylinder(d = 6, h = 20);
    // bottom plate inserts
    for (a = [0:90:270]) rotate(a) translate([pri - 4, 0, -eps]) cylinder(d = 4.2, h = 8, $fn = 24);
    // DC jack at the back, vent slots at the back
    translate([0, pr - plinth_wall / 2, 20]) rotate([90, 0, 0]) cylinder(d = dc_jack_d, h = plinth_wall + 4, center = true);
    for (i = [-3:3]) if (i != 0) rotate(i * 9) translate([0, pr - plinth_wall / 2, 12]) cube([3, plinth_wall + 4, 18], center = true);
  }
}

module plinth_plate() {
  pri = plinth_d / 2 - plinth_wall;
  difference() {
    union() {
      cylinder(r = pri - 0.4, h = 3);
      translate(hat_origin) for (p = pi_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = zero_z, $fn = 24);
      translate(hat_origin) if (pi_model != "3a") for (p = [hat_holes[0], hat_holes[1]]) translate([p[0], p[1], 0]) cylinder(d = 6, h = hat_z, $fn = 24);
      translate(buck_center) for (p = buck_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = 7, $fn = 24);
    }
    translate([hat_origin[0], hat_origin[1], -eps]) for (p = concat(pi_holes, hat_holes)) translate([p[0], p[1], 0]) cylinder(d = 2.6, h = 30, $fn = 16);
    translate([buck_center[0], buck_center[1], -eps]) for (p = buck_holes) translate([p[0], p[1], 0]) cylinder(d = 2.6, h = 10, $fn = 16);
    for (a = [0:90:270]) rotate(a) translate([pri - 4, 0, -eps]) cylinder(d = 3.4, h = 4, $fn = 20);
    for (a = [0:120:240]) rotate(a + 60) translate([pri - 18, 0, -eps]) cylinder(d = 12.5, h = 1.2, $fn = 32);   // rubber feet
  }
}

// ------------------------------------------------------------------ assembly / pictures
module k_dummy_speakers() {
  color("#202231") translate([0, -baffle_in, sph_zc]) rotate([-90, 0, 0]) {
    cylinder(d = drv_flange_d, h = 3);
    cylinder(d1 = drv_cutout_d - 4, d2 = 40, h = 30);
    translate([0, 0, 30]) cylinder(d = 62, h = 34);
  }
  color("#202231") translate([0, baffle_in, sph_zc]) rotate([90, 0, 0]) cylinder(d = pr_flange_d, h = 3);
  color("#6d7282") translate([0, baffle_in + 1, sph_zc]) rotate([-90, 0, 0]) cylinder(d = 80, h = 3);
}

module kugel_assembly(with_shade = true, with_parts = false) {
  kx = sqrt(sph_r * sph_r - knob_dz * knob_dz);
  color(TC[1]) plinth();
  color(TC[1]) translate([0, 0, -3]) plinth_plate();
  color(TC[0]) sphere_shell();
  color(TC[2]) translate([0, 0, plinth_h - 3]) ring(plinth_d + 2, plinth_d - 1, 3);   // accent ring
  color(TC[0]) translate([0, 0, chamber_top]) sphere_lid();
  color(TC[1]) translate([conduit_pos[0], conduit_pos[1], k_chamber_bot]) sphere_conduit();
  if (with_parts) { k_dummy_speakers(); translate([0, 0, -3]) dummy_electronics(); }
  color(TC[4]) translate([kx + 1, 0, sph_zc + knob_dz]) rotate([0, 90, 0]) knob();
  color(TC[2]) translate([0, 0, stem_z]) ring(stem_od, stem_id, lamp_stem_len);
  color("#e9e3d5") translate([0, 0, stem_top]) led_core();
  color("#e9e3d5") translate([0, 0, stem_top + core_h]) core_cap();
  if (on_base) color(TC[3]) translate([0, 0, chamber_top + lid_t + 8]) globe_seat();
  translate([0, 0, lamp_shade_z]) {
    if (!on_base) color(TC[3]) translate([0, 0, S_h - 8]) spider();
    if (with_shade) color(TC[3], 0.88) shade();
  }
}

module kugel_section() {
  difference() {
    kugel_assembly(with_shade = false, with_parts = true);
    translate([0, -300, -10]) cube([300, 600, 700]);
    translate([-300, plinth_d / 2 + 1, -10]) cube([600, 100, plinth_h + 5]);   // dummy DC jack of the cylinder base
  }
}

if (part == "kugel_assembly") kugel_assembly();
if (part == "kugel_section")  kugel_section();
if (part == "sphere_shell")   sphere_shell();
if (part == "sphere_lid")     sphere_lid();
if (part == "sphere_conduit") sphere_conduit();
if (part == "plinth")         rotate([180, 0, 0]) plinth();   // print orientation
if (part == "plinth_plate")   plinth_plate();
