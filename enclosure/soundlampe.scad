// Soundlampe – retro table lamp with a speaker base
// OpenSCAD, fully parametric. Render one part at a time:
//   openscad -D 'part="base_shell"' -o base_shell.stl soundlampe.scad
// Parts: assembly, base_shell, divider, top_lid, bottom_plate, stem, led_core,
//        core_cap, spider, shade, knob
//
// Base: 2 compartments. Below: electronics (Pi Zero 2 W + DigiAMP+, LED buck).
// Above: sealed ~2.6 l speaker chamber with a 4" full-range driver firing to
// the front and a passive radiator firing to the back, behind vertical grille slats.
// Top: brass or printed stem, LED core wrapped with an SK6812 strip,
// pleated shade printed in vase mode from translucent PLA/PETG.
//
// !!! Check the driver / passive radiator values against your datasheets !!!

part = "assembly";

/* [Base] */
base_d      = 190;   // outer diameter
base_h      = 160;   // total height of the base
wall        = 3.2;
div_z       = 40;    // top of the electronics compartment (divider sits here)
div_t       = 4;
lid_t       = 5;

/* [Driver (front) and passive radiator (back)] */
drv_flange_d = 106;  // outer flange diameter (Dayton ND105-4: check!)
drv_cutout_d = 93;   // baffle cut-out
drv_bolt_d   = 99;   // bolt circle for 4 mounting screws
drv_bolt_hole= 4.2;  // M3 heat-set insert hole (use 5.0 for M4 inserts)
pr_flange_d  = 106;  // passive radiator (Dayton ND105-PR: check!)
pr_cutout_d  = 93;
pr_bolt_d    = 99;
baffle_dist  = 66;   // distance of the baffle's inner face from the centre
baffle_t     = 8;

/* [Grille] */
slot_w     = 3.6;
slot_pitch = 7.5;     // along the circumference
grille_deg = 70;      // angular width of each grille field

/* [Electronics] */
dc_jack_d   = 11;     // panel DC jack (5.5/2.1 mm)
pi_holes    = [[0,0],[58,0],[0,49],[58,49]];   // DigiAMP+/Pi HAT pattern, M2.5
knob_offset = [0, -52];   // encoder position on the lid (front)

/* [Lamp] */
stem_od    = 20;      // fits a 20 mm brass tube, or print the stem part
stem_id    = 13;
stem_len   = 150;
core_d     = 40;      // LED strip wraps around this (126 mm circumference)
core_h     = 60;
shade_bot_d= 210;
shade_top_d= 128;
shade_h    = 155;
shade_z    = 250;     // height of the shade's lower edge above the table
pleats     = 40;
pleat_depth= 4;

$fn = 96;
eps = 0.01;
R  = base_d / 2;
Ri = R - wall;
chamber_bot = div_z + div_t;
chamber_top = base_h - lid_t;
drv_z = (chamber_bot + chamber_top) / 2;
stem_z   = chamber_top + lid_t + 4;           // stem sits 4 mm deep in the lid socket
stem_top = stem_z + stem_len;
spider_z = shade_z + shade_h - 8;
pin_len  = spider_z + 10 - (stem_top + core_h + 3);   // core cap pin reaches through the spider hub

// ------------------------------------------------------------------ helpers
module ring(od, id, h) { difference() { cylinder(d = od, h = h); translate([0,0,-eps]) cylinder(d = id, h = h + 2*eps); } }

// support ledge inside the shell with a 45° underside, printable without supports
module ledge(z, width = 6) {
  rotate_extrude() polygon([[Ri + eps, z - width], [Ri + eps, z], [Ri - width, z]]);
}

// teardrop hole on a vertical wall (prints without supports), axis along Y
module teardrop_y(d, len) {
  rotate([90, 0, 0]) linear_extrude(len, center = true)
    union() { circle(d = d); rotate(45) square(d / 2); }
}

module baffle(side = -1, cut_d, bolt_d) {
  // side = -1 front (-Y), +1 back (+Y)
  difference() {
    intersection() {
      cylinder(r = Ri + eps, h = base_h);
      translate([-R, side < 0 ? -(baffle_dist + baffle_t) : baffle_dist, chamber_bot])
        cube([2*R, baffle_t, chamber_top - chamber_bot]);
    }
    translate([0, side * (baffle_dist + baffle_t/2), drv_z]) teardrop_y(cut_d, baffle_t + 2);
    for (a = [45:90:315])
      translate([cos(a) * bolt_d/2, side * (baffle_dist + baffle_t/2), drv_z + sin(a) * bolt_d/2])
        rotate([90,0,0]) cylinder(d = drv_bolt_hole, h = baffle_t + 2, center = true, $fn = 24);
  }
}

module grille(side = -1) {
  n = floor((grille_deg * PI * R / 180) / slot_pitch);
  z0 = chamber_bot + 6; z1 = chamber_top - 6;
  for (i = [0 : n - 1]) {
    a = (side < 0 ? -90 : 90) + (i - (n - 1) / 2) * (slot_pitch / (PI * R) * 180);
    rotate([0, 0, a]) translate([R - wall - 1, -slot_w/2, z0])
      hull() {
        cube([wall + 2, slot_w, z1 - z0 - slot_w]);
        translate([0, slot_w/2, z1 - z0 - slot_w/2]) rotate([0,90,0]) cylinder(d = slot_w, h = wall + 2, $fn = 16);
      }
  }
}

// ------------------------------------------------------------------ parts
module base_shell() {
  difference() {
    union() {
      ring(base_d, base_d - 2*wall, base_h);
      ledge(div_z);
      ledge(chamber_top);
      baffle(-1, drv_cutout_d, drv_bolt_d);
      baffle(+1, pr_cutout_d, pr_bolt_d);
      // bosses for the bottom plate
      for (a = [0:90:270]) rotate(a + 45) translate([Ri - 5, 0, 0]) cylinder(d = 11, h = 14, $fn = 32);
      // decorative bands
      for (z = [div_z - 2, base_h - 2]) translate([0,0,z]) ring(base_d + 1.6, base_d - 1, 2);
    }
    grille(-1);
    grille(+1);
    for (a = [0:90:270]) rotate(a + 45) translate([Ri - 5, 0, -eps]) cylinder(d = 4.2, h = 10, $fn = 24);
    // DC jack at the back of the electronics band
    translate([0, R - wall/2, 18]) rotate([90,0,0]) cylinder(d = dc_jack_d, h = wall + 4, center = true);
  }
}

module divider() {
  difference() {
    cylinder(r = Ri - 0.4, h = div_t);
    // speaker cables + LED/encoder conduit, seal with silicone after wiring
    for (p = [[30, 0], [-30, 0]]) translate([p[0], p[1], -eps]) cylinder(d = 5, h = div_t + 1, $fn = 20);
    translate([0, 0, -eps]) cylinder(d = 10, h = div_t + 1);
    // screws into the ledge (heat-set inserts in the ledge)
    for (a = [0:60:300]) rotate(a) translate([Ri - 3.5, 0, -eps]) cylinder(d = 3.4, h = div_t + 1, $fn = 20);
  }
  // stub that the cable tube (conduit) slides over
  ring(9.8, 6, div_t + 6);
}

module top_lid() {
  difference() {
    union() {
      cylinder(r = Ri - 0.4, h = lid_t);
      // overhanging top cap with a soft retro chamfer
      translate([0, 0, lid_t]) cylinder(d1 = base_d + 2, d2 = base_d - 14, h = 8);
      // stem socket
      translate([0, 0, lid_t]) cylinder(d = stem_od + 12, h = 22);
    }
    translate([0, 0, lid_t + 4]) cylinder(d = stem_od + 0.4, h = 40);   // stem socket
    translate([0, 0, -eps]) cylinder(d = 10, h = 60);                 // cable conduit
    translate([knob_offset[0], knob_offset[1], -eps]) cylinder(d = 7.4, h = 40, $fn = 32);  // EC11 bushing
    translate([knob_offset[0], knob_offset[1], -eps]) cylinder(d = 14, h = lid_t + 8 - 1.6, $fn = 32); // thin top skin for the nut
  }
}

// cable tube from the divider up to the lid: keeps the speaker chamber sealed
module conduit() { ring(16, 10, chamber_top - chamber_bot); }

module bottom_plate() {
  difference() {
    union() {
      cylinder(r = Ri - 0.4, h = 3);
      // standoffs for the Pi Zero 2 W + DigiAMP+ stack
      translate([-29, -10, 0]) for (p = pi_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = 8, $fn = 24);
      // standoffs for the 5 V buck converter (mini MP1584 / LM2596 board)
      translate([-20, -60, 0]) for (p = [[0,0],[30,0]]) translate([p[0], p[1], 0]) cylinder(d = 6, h = 6, $fn = 24);
    }
    translate([-29, -10, -eps]) for (p = pi_holes) translate([p[0], p[1], 0]) cylinder(d = 2.6, h = 10, $fn = 16);
    translate([-20, -60, -eps]) for (p = [[0,0],[30,0]]) translate([p[0], p[1], 0]) cylinder(d = 2.6, h = 10, $fn = 16);
    // vent slots
    for (x = [-60:8:60]) translate([x - 1.5, 45, -eps]) cube([3, 30, 4]);
    // screw holes into the shell bosses + recesses for rubber feet
    for (a = [0:90:270]) rotate(a + 45) translate([Ri - 5, 0, -eps]) {
      cylinder(d = 3.4, h = 4, $fn = 20);
    }
    for (a = [0:120:240]) rotate(a) translate([Ri - 22, 0, -eps]) cylinder(d = 12.5, h = 1.2, $fn = 32);
  }
}

module stem() { ring(stem_od, stem_id, stem_len); }

module led_core() {
  // hollow spool, the strip winds around it in a gentle spiral
  difference() {
    union() {
      cylinder(d = core_d, h = core_h);
      cylinder(d = core_d + 6, h = 3);                    // lower flange
      translate([0,0,-12]) cylinder(d = stem_id - 0.3, h = 12);   // spigot into the stem
    }
    translate([0,0,-13]) cylinder(d = 8, h = 16);                    // cable path
    translate([0,0,3]) cylinder(d = core_d - 5, h = core_h);
    translate([0, 0, 6]) for (a = [0:60:300]) rotate(a) translate([core_d/2, 0, 0]) rotate([0,90,0]) cylinder(d = 6, h = 8, center = true, $fn = 16);
  }
}

module core_cap() {
  // closes the core and carries a pin for the shade spider
  difference() {
    union() {
      cylinder(d = core_d + 6, h = 3);
      translate([0,0,-4]) ring(core_d - 5.4, core_d - 9, 4);        // plugs into the core
      translate([0,0,3]) cylinder(d = 10, h = pin_len);
    }
    for (a = [0:45:315]) rotate(a) translate([core_d/2 - 9, 0, -eps]) cylinder(d = 3, h = 4, $fn = 12); // vents
  }
}

// inner shade radius at height z above the shade's lower edge (pleat valleys)
function shade_r(z) = (shade_bot_d + (shade_top_d - shade_bot_d) * z / shade_h) / 2 - pleat_depth;

module spider() {
  ring_z = shade_h - 8;           // where the ring sits inside the shade
  rr = shade_r(ring_z) + 0.8;     // slightly larger: the shade rests on the ring
  hub_h = 10;
  difference() {
    union() {
      cylinder(d = 18, h = hub_h);
      ring(2 * rr, 2 * rr - 8, 4);
      for (a = [0:120:240]) rotate(a) translate([0, -2.5, 0]) cube([rr - 3, 5, 4]);
    }
    translate([0,0,-eps]) cylinder(d = 10.4, h = hub_h + 1);
  }
}

module shade() {
  // pleated cone; slice in vase/spiral mode (single wall, 0.8 mm line width)
  scale_f = shade_top_d / shade_bot_d;
  linear_extrude(height = shade_h, scale = scale_f, $fn = pleats * 4)
    let(n = pleats * 2, ro = shade_bot_d / 2, ri = ro - pleat_depth * 1.0)
      polygon([for (i = [0 : n - 1]) let(a = 360 * i / n, r = (i % 2 == 0) ? ro : ri) [r * cos(a), r * sin(a)]]);
}

module knob() {
  // retro knob with fine knurling for an EC11 encoder (6 mm D shaft)
  difference() {
    union() {
      cylinder(d = 30, h = 14, $fn = 120);
      translate([0,0,14]) cylinder(d1 = 30, d2 = 26, h = 3, $fn = 120);
    }
    for (a = [0:6:354]) rotate(a) translate([15.2, 0, -eps]) cylinder(d = 1.6, h = 14.5, $fn = 8);
    translate([0,0,-eps]) difference() { cylinder(d = 6.2, h = 12, $fn = 32); translate([1.6, -4, -1]) cube([4, 8, 14]); }
    translate([0, 9, 17 - 0.6]) cylinder(d = 2.5, h = 1, $fn = 16);   // dot marker
  }
}

// ------------------------------------------------------------------ assembly
module assembly(with_shade = true) {
  color("#3c4157") base_shell();
  color("#2b2f3d") translate([0,0,div_z]) divider();
  color("#4b5168") translate([0,0,chamber_top]) top_lid();
  color("#2b2f3d") translate([0,0,-3]) bottom_plate();
  color("#1b1d26") translate([0, -(baffle_dist), drv_z]) rotate([90,0,0]) cylinder(d = drv_flange_d, h = 3);
  color("#b88a3c") translate([0,0,stem_z]) stem();
  color("#2b2f3d") translate([0,0,chamber_bot]) conduit();
  color("#e9e3d5") translate([0,0,stem_top]) led_core();
  color("#e9e3d5") translate([0,0,stem_top + core_h]) core_cap();
  color("#d0c7b3") translate([knob_offset[0], knob_offset[1], chamber_top + lid_t + 10]) knob();
  translate([0,0,shade_z]) {
    color("#d9cdb5") translate([0,0,shade_h - 8]) spider();
    if (with_shade) color("#f3ead8", 0.85) shade();
  }
}

// cut open to show the inside (for documentation)
module cutaway() { difference() { assembly(with_shade = false); translate([0, -300, -10]) cube([300, 600, 600]); } }

if (part == "assembly")      assembly();
if (part == "cutaway")       cutaway();
if (part == "base_shell")    base_shell();
if (part == "divider")       divider();
if (part == "top_lid")       top_lid();
if (part == "conduit")       conduit();
if (part == "bottom_plate")  bottom_plate();
if (part == "stem")          stem();
if (part == "led_core")      led_core();
if (part == "core_cap")      core_cap();
if (part == "spider")        spider();
if (part == "shade")         shade();
if (part == "knob")          knob();
