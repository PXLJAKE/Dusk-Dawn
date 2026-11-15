// Soundlampe – retro table lamp with a speaker base
// OpenSCAD, fully parametric. Render one part at a time:
//   openscad -D 'part="base_shell"' -o base_shell.stl soundlampe.scad
// Parts: assembly, base_shell, divider, top_lid, bottom_plate, stem, led_core,
//        core_cap, spider, shade, knob
//
// Base: 2 compartments. Below: electronics (Pi 3 A+ or Pi Zero 2 W + DigiAMP+, LED buck).
// Above: sealed ~2.1 l (net) speaker chamber with a 4" full-range driver firing to
// the front and a passive radiator firing to the back, behind vertical grille slats.
// Top: brass or printed stem, LED core wrapped with an SK6812 strip,
// pleated shade printed in vase mode from translucent PLA/PETG.
//
// !!! Check the driver / passive radiator values against your datasheets !!!

part = "assembly";

/* [Base] */
base_d      = 190;   // outer diameter
base_h      = 160;   // total height of the base
wall        = 4.0;   // 4 mm solid wall (print with 100 % infill = all perimeters)
div_z       = 40;    // top of the electronics compartment (divider sits here)
div_t       = 4;
lid_t       = 5;

/* [Driver (front) and passive radiator (back)] */
drv_flange_d = 106;  // outer flange diameter (ND105-4: 105 mm, cut-out 93 mm, depth 67 mm per datasheet)
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
hat_origin  = [-32.5, -28];   // lower left corner of the DigiAMP+ (65 x 56.5 mm HAT)
hat_holes   = [[3.5,3.5],[61.5,3.5],[3.5,52.5],[61.5,52.5]];  // M2.5
zero_holes  = [[3.5,29.5],[61.5,29.5],[3.5,52.5],[61.5,52.5]]; // Pi Zero below the HAT, header rows aligned
pi_model    = "3a";   // "3a" = Raspberry Pi 3 Model A+ (same 65 x 56 footprint as the HAT), "zero2" = Pi Zero 2 W
pi_holes    = pi_model == "3a" ? hat_holes : zero_holes;
zero_z      = 8;      // Pi board height above the plate bottom (5 mm air under the board for the SD slot and header pins)
hat_z       = zero_z + 1.6 + 11;   // DigiAMP+ height (Pi + 11 mm M2.5 spacers)
buck_center = [0, -58];            // LM2596 step-down module (approx. 43 x 21 mm)
buck_size   = [43, 21];
buck_holes  = [[-15,-8],[15,-8],[-15,8],[15,8]];  // 4 domes: fits both diagonals of the usual 30 x 16 mm hole pattern
knob_offset = [0, -52];   // encoder position on the lid (front), used when knob_pos = "top"
knob_pos    = "side";     // "side": knob in the right side wall (works with every shade), "top": on the lid
knob_side_a = 0;          // angle of the side knob (0 = right side, seen from the front)
brace_angles = [20, 40, 140, 160, 200, 220, 320, 340];  // vertical stiffening ribs in the chamber
conduit_pos = [45, 0];    // cable tube beside the speakers (the ND105-4 is 67 mm deep, its magnet reaches the centre)

/* [Lamp] */
shade_style = "plissee";  // "plissee" | "glocke" (on the stem) | "kolben" | "twist" | "laterne" (sit directly on the base)
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
knob_side_z = chamber_top - 18;
stem_z   = chamber_top + lid_t + 4;           // stem sits 4 mm deep in the lid socket

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
      // vertical ribs stiffen the curved wall so it does not resonate
      for (a = brace_angles) rotate(a) translate([Ri - 6, -1.5, chamber_bot]) cube([6 + eps, 3, chamber_top - chamber_bot]);
    }
    if (knob_pos == "side") {
      rotate(knob_side_a) translate([R - wall - 1, 0, knob_side_z]) rotate([0, 90, 0]) cylinder(d = 7.4, h = wall + 2, $fn = 32);
      rotate(knob_side_a) translate([R - 1.2, 0, knob_side_z]) rotate([0, 90, 0]) cylinder(d = 16, h = 5, $fn = 48);  // flat seat for the nut
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
    translate([conduit_pos[0], conduit_pos[1], -eps]) cylinder(d = 10, h = div_t + 1);
    // screws into the ledge (heat-set inserts in the ledge)
    for (a = [0:60:300]) rotate(a) translate([Ri - 3.5, 0, -eps]) cylinder(d = 3.4, h = div_t + 1, $fn = 20);
    // notches so the divider slides past the stiffening ribs
    for (a = brace_angles) rotate(a) translate([Ri - 7, -2, -eps]) cube([8, 4, div_t + 1]);
  }
  // stub that the cable tube (conduit) slides over
  translate(conduit_pos) ring(9.8, 6, div_t + 6);
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
    // cable path: conduit (off-centre) -> horizontal channel inside the lid -> stem socket
    translate([conduit_pos[0], conduit_pos[1], -eps]) cylinder(d = 8, h = lid_t + 2.5 + eps);
    hull() for (p = [[0, 0], conduit_pos]) translate([p[0], p[1], lid_t + 2.5]) sphere(d = 6, $fn = 24);
    if (knob_pos == "top") {
      translate([knob_offset[0], knob_offset[1], -eps]) cylinder(d = 7.4, h = 40, $fn = 32);  // EC11 bushing
      translate([knob_offset[0], knob_offset[1], -eps]) cylinder(d = 14, h = lid_t + 8 - 1.6, $fn = 32); // thin top skin for the nut
    }
    // screw holes for the globe seat (globe shades)
    if (on_base) for (a = [0:120:240]) rotate(a + 30) translate([seat_d/2 - 5, 0, lid_t + 8 - 6]) cylinder(d = 4.2, h = 7, $fn = 20);
  }
}

// cable tube from the divider up to the lid: keeps the speaker chamber sealed
module conduit() { ring(16, 10, chamber_top - chamber_bot); }

module bottom_plate() {
  difference() {
    union() {
      cylinder(r = Ri - 0.4, h = 3);
      // Pi Zero 2 W on short standoffs; the DigiAMP+ sits on 11 mm spacers above it
      // (shared header-side holes) and on two tall standoffs on the other side
      translate(hat_origin) {
        for (p = pi_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = zero_z, $fn = 24);
        // Pi Zero: two tall standoffs carry the free side of the HAT. Pi 3A+: the HAT sits on 4 spacers.
        if (pi_model != "3a") for (p = [hat_holes[0], hat_holes[1]]) translate([p[0], p[1], 0]) cylinder(d = 6, h = hat_z, $fn = 24);
      }
      // standoffs for the LM2596 5 V step-down module
      translate(buck_center) for (p = buck_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = 7, $fn = 24);
    }
    translate([hat_origin[0], hat_origin[1], -eps]) for (p = concat(pi_holes, hat_holes)) translate([p[0], p[1], 0]) cylinder(d = 2.6, h = 30, $fn = 16);
    translate([buck_center[0], buck_center[1], -eps]) for (p = buck_holes) translate([p[0], p[1], 0]) cylinder(d = 2.6, h = 10, $fn = 16);
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

// ------------------------------------------------------------------ shades
// style table: [height, profile(t) -> radius, ribs, rib depth, twist (deg), sits on base?]
function style(name) =
  name == "glocke" ? [150, function(t) 52 + 52 * pow(1 - t, 1.8), 36, 2.0, 0, false] :
  name == "kolben" ? [230, function(t) 58 + 44 * sin(180 * pow(t, 0.85)), 56, 2.2, 0, true] :
  name == "twist"  ? [210, function(t) 76 + 10 * sin(180 * t), 40, 3.0, 50, true] :
  name == "laterne"? [215, function(t) 58 + 16 * sin(180 * t) + 13 * pow(sin(540 * t), 2), 72, 1.6, 0, true] :
  /* plissee */      [shade_h, function(t) (shade_bot_d + (shade_top_d - shade_bot_d) * t) / 2, pleats, pleat_depth, 0, false];

S          = style(shade_style);
S_h        = S[0];
S_prof     = S[1];
on_base    = S[5];
seat_d     = 2 * S_prof(0) - 2 * S[3] - 1.0;   // globe seat fits inside the globe's lower opening
short_stem = 60;                               // stem inside a globe shade
lamp_stem_len = on_base ? short_stem : stem_len;
lamp_shade_z  = on_base ? chamber_top + lid_t + 8 : shade_z;
stem_top = stem_z + lamp_stem_len;
spider_z = lamp_shade_z + S_h - 8;
pin_len  = on_base ? 4 : spider_z + 10 - (stem_top + core_h + 3);   // core cap pin reaches through the spider hub

// inner radius (rib valleys) at height z above the shade's lower edge
function shade_r(z) = S_prof(z / S_h) - S[3];

// ribbed body of revolution as a polyhedron (solid; print in vase mode)
module ribbed(h, prof, ribs, amp, twist = 0, steps = 90) {
  seg = ribs * 8;
  pts = [for (i = [0:steps]) for (j = [0:seg - 1])
           let(t = i / steps, a = 360 * j / seg, r = prof(t) - amp / 2 + amp / 2 * cos(ribs * (a + twist * t)))
             [r * cos(a), r * sin(a), t * h]];
  P = function(i, j) i * seg + (j % seg);
  faces = concat(
    [for (i = [0:steps - 1]) for (j = [0:seg - 1]) [P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)]],
    [[for (j = [0:seg - 1]) P(0, j)]],
    [[for (j = [seg - 1:-1:0]) P(steps, j)]]);
  polyhedron(pts, faces, convexity = 6);
}

module spider() {
  ring_z = S_h - 8;               // where the ring sits inside the shade
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

// ring screwed onto the lid; globe shades slip over it
module globe_seat() {
  difference() {
    union() {
      ring(seat_d, seat_d - 8, 12);
      ring(seat_d + 14, seat_d - 8, 2);          // flange the globe stands on
    }
    for (a = [0:120:240]) rotate(a + 30) translate([seat_d/2 - 5 + 0, 0, -eps]) cylinder(d = 3.4, h = 20, $fn = 20);
  }
}

module shade() {
  if (shade_style == "plissee") {
    // pleated cone
    scale_f = shade_top_d / shade_bot_d;
    linear_extrude(height = shade_h, scale = scale_f, $fn = pleats * 4)
      let(n = pleats * 2, ro = shade_bot_d / 2, ri = ro - pleat_depth * 1.0)
        polygon([for (i = [0 : n - 1]) let(a = 360 * i / n, r = (i % 2 == 0) ? ro : ri) [r * cos(a), r * sin(a)]]);
  } else {
    ribbed(S[0], S[1], S[2], S[3], S[4]);
  }
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

// ------------------------------------------------------------------ dummy components (renders only)
module dummy_driver() {   // in the -Y baffle, cone facing out
  color("#202231") translate([0, -baffle_dist, drv_z]) rotate([-90,0,0]) {
    cylinder(d = drv_flange_d, h = 3);
    cylinder(d1 = drv_cutout_d - 4, d2 = 40, h = 30);
    translate([0,0,30]) cylinder(d = 62, h = 34);   // ND105-4: 67 mm overall depth
  }
  color("#5a5f6e") translate([0, -baffle_dist - 2, drv_z]) rotate([90,0,0]) cylinder(d1 = 84, d2 = 30, h = 14);
  color("#8d92a3") translate([0, -baffle_dist - 14, drv_z]) rotate([90,0,0]) sphere(d = 30);
}
module dummy_pr() {
  color("#202231") translate([0, baffle_dist, drv_z]) rotate([90,0,0]) {
    cylinder(d = pr_flange_d, h = 3);
    difference() { cylinder(d1 = pr_cutout_d - 4, d2 = 60, h = 28); translate([0,0,-1]) cylinder(d1 = pr_cutout_d - 10, d2 = 52, h = 30); }
  }
  color("#6d7282") translate([0, baffle_dist + 1, drv_z]) rotate([-90,0,0]) cylinder(d = 80, h = 3);
}
module dummy_electronics() {
  translate([hat_origin[0], hat_origin[1], 0]) {
    if (pi_model == "3a") {
      color("#1f7a3c") translate([0, 0, zero_z]) cube([65, 56, 1.6]);                // Pi 3 Model A+
      color("#bbb") translate([-1, 18, zero_z + 1.6]) cube([17, 14, 8]);              // USB-A
      color("#999") translate([20, 18, zero_z + 1.6]) cube([14, 14, 2]);              // SoC
    } else
      color("#1f7a3c") translate([0, 26, zero_z]) cube([65, 30, 1.6]);               // Pi Zero 2 W
    color("#222") translate([3.5 + 29 - 25.4, 26 + 30 - 5, zero_z + 1.6]) cube([51, 5, 9]); // header
    color("#2a4b8d") translate([0, 0, hat_z]) cube([65, 56.5, 1.6]);                 // DigiAMP+
    color("#111") translate([8, 8, hat_z + 1.6]) cube([14, 14, 10]);                 // inductors/caps
    color("#111") translate([40, 8, hat_z + 1.6]) cube([14, 14, 10]);
    color("#2f8a4f") translate([0, 40, hat_z + 1.6]) cube([10, 16, 9]);               // terminals
  }
  translate([buck_center[0] - buck_size[0]/2, buck_center[1] - buck_size[1]/2, 7]) {  // LM2596 module
    color("#2a4b8d") cube([buck_size[0], buck_size[1], 1.6]);
    color("#333") translate([14, 3, 1.6]) cube([13, 13, 7]);                         // inductor
    color("#3b6fd8") translate([30, 3, 1.6]) cube([9, 5, 10]);                       // trim pot
    color("#111") translate([4, 4, 1.6]) cylinder(d = 8, h = 11, $fn = 24);           // electrolytic caps
  }
  color("#7a7f8f") translate([0, R - wall - 8, 18]) rotate([-90,0,0]) cylinder(d = 10, h = 12); // DC jack
}
module dummy_leds() {
  color("#fff3c4") translate([0,0,stem_top + 5]) for (i = [0:29])
    let(a = i * 360 / 7.5, z = i * 1.6) translate([0,0,z]) rotate(a) translate([core_d/2 + 0.8, 0, 0]) cube([1.6, 5, 5], center = true);
}

// ------------------------------------------------------------------ assembly
module assembly(with_shade = true, with_parts = true) {
  color("#3c4157") base_shell();
  color("#2b2f3d") translate([0,0,div_z]) divider();
  color("#4b5168") translate([0,0,chamber_top]) top_lid();
  color("#2b2f3d") translate([0,0,-3]) bottom_plate();
  if (with_parts) { dummy_driver(); dummy_pr(); dummy_electronics(); dummy_leds(); }
  color("#b88a3c") translate([0,0,stem_z]) ring(stem_od, stem_id, lamp_stem_len);
  color("#2b2f3d") translate([conduit_pos[0], conduit_pos[1], chamber_bot]) conduit();
  color("#e9e3d5") translate([0,0,stem_top]) led_core();
  color("#e9e3d5") translate([0,0,stem_top + core_h]) core_cap();
  knob_placed();
  if (on_base) color("#d9cdb5") translate([0,0,chamber_top + lid_t + 8]) globe_seat();
  translate([0,0,lamp_shade_z]) {
    if (!on_base) color("#d9cdb5") translate([0,0,S_h - 8]) spider();
    if (with_shade) color("#f3ead8", 0.85) shade();
  }
}

module knob_placed() {
  if (knob_pos == "side")
    color("#d0c7b3") rotate(knob_side_a) translate([R + 3, 0, knob_side_z]) rotate([0, 90, 0]) knob();
  else
    color("#d0c7b3") translate([knob_offset[0], knob_offset[1], chamber_top + lid_t + 10]) knob();
}

// cut open to show the inside (for documentation)
module cutaway() { difference() { assembly(with_shade = false); translate([0, -300, -10]) cube([300, 600, 600]); } }

// ------------------------------------------------------------------ detail views for the docs
module led_strip_spiral(turns = 4, pitch = 15, w = 10) {
  n = 30;                                   // 30 LEDs on 0.5 m
  steps = 160;
  r = core_d / 2 + 0.6;
  for (i = [0 : steps - 1]) let(a0 = i * 360 * turns / steps, a1 = (i + 1) * 360 * turns / steps)
    hull() for (a = [a0, a1]) rotate(a) translate([r, 0, 6 + a / 360 * pitch]) cube([0.6, 0.6, w], center = true);
  for (k = [0 : n - 1]) let(a = k * 360 * turns / n)
    color("#fff2b8") rotate(a) translate([r + 0.9, 0, 6 + a / 360 * pitch]) cube([1.6, 5, 5], center = true);
}
module led_detail() {
  color("#e9e2d2") led_core();
  color("#f4f4f4") led_strip_spiral();
  color("#d8cfbd") translate([0, 0, core_h + 25]) core_cap();
  color("#b88a3e") translate([0, 0, -60]) ring(stem_od, stem_id, 45);
  // cable: 3 wires leaving the strip start into the core and down the stem
  for (i = [0:2]) color(["#e8862a", "#222", "#2f6fd0"][i]) translate([-2 + i * 2, 0, -58]) cylinder(d = 1.6, h = 66, $fn = 8);
}
module perfboard_dummy() {
  translate([-78, -35, 3]) {
    color("#c9e3c4") cube([30, 70, 1.6]);
    color("#232a40") translate([8, 20, 1.6]) cube([7.6, 19, 5]);          // 74AHCT125
    color("#222") translate([20, 10, 1.6]) cylinder(d = 8, h = 12, $fn = 24); // 1000 uF
    color("#d9b46c") translate([16, 48, 1.6]) cube([8, 2.4, 2.4]);       // 330 R
    color("#2f8a4f") translate([4, 58, 1.6]) cube([22, 8, 10]);          // screw terminals
  }
}
module electronics_detail() {
  color("#3a4361") bottom_plate();
  dummy_electronics();
  perfboard_dummy();
}
if (part == "led_detail")         led_detail();
if (part == "electronics_detail") electronics_detail();

if (part == "assembly")      assembly();
if (part == "cutaway")       cutaway();

// ------------------------------------------------------------------ documentation views
module section_side()   { difference() { assembly(with_shade = false); translate([0, -300, -100]) cube([300, 600, 700]); } }
module section_front()  { difference() { assembly(with_shade = false); translate([-300, 0, -100]) cube([600, 300, 700]); } }
module section_top(z)   { difference() { assembly(with_shade = false); translate([-300, -300, z]) cube([600, 600, 420]); } }
module exploded() {
  color("#3c4157") base_shell();
  dummy_driver(); dummy_pr();
  color("#2b2f3d") translate([0,0,-60]) bottom_plate();
  translate([0,0,-57]) dummy_electronics();
  color("#2b2f3d") translate([0,0,div_z]) divider();
  color("#2b2f3d") translate([conduit_pos[0], conduit_pos[1], chamber_bot]) conduit();
  color("#4b5168") translate([0,0,chamber_top + 70]) top_lid();
  translate([40, 0, 0]) knob_placed();
  color("#b88a3c") translate([0,0,stem_z + 110]) ring(stem_od, stem_id, lamp_stem_len);
  translate([0,0,150]) { color("#e9e3d5") translate([0,0,stem_top]) led_core(); dummy_leds(); }
  color("#e9e3d5") translate([0,0,stem_top + core_h + 175]) core_cap();
  translate([0,0,lamp_shade_z + 230]) {
    if (!on_base) color("#d9cdb5") translate([0,0,S_h - 8 - 40]) spider();
    color("#f3ead8", 0.8) translate([0,0,40]) shade();
  }
}
if (part == "section_side")  section_side();
if (part == "section_front") section_front();
if (part == "section_chamber") section_top(drv_z);
if (part == "section_electronics") section_top(div_z - 6);
if (part == "exploded")      exploded();
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
if (part == "globe_seat")    globe_seat();
if (part == "stem_short")    ring(stem_od, stem_id, short_stem);
if (part == "knob")          knob();
