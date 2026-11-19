// Soundlampe v2 – speaker base + lamp, two base designs sharing all other parts.
// Rules: see KONSTRUKTIONSPLAN.md (P1S build volume, no heat-set inserts,
// self-tapping BT3/BT2.6 pan-head screws, no visible screws, bayonet lid,
// flush knob, open shades that continue the sphere without a step).
//
// Render one part at a time:
//   openscad -D 'base="kugel"' -D 'part="body"' -o body.stl soundlampe.scad
// Parts:  body, plinth, plate, lid, knob, stem, led_core, core_cap, spider, shade
// Views:  assembly, exploded, section
//
// !!! Check driver / passive radiator dimensions against your datasheets !!!

part        = "assembly";
step        = 1;            // part = "step": assembly step 1..8 for the building guide
base        = "kugel";      // "kugel" | "zylinder"
shade_style = "laterne";    // "plissee" | "glocke" (on the stem) | "kolben" | "twist" | "laterne" (on the lid)
theme       = "walnuss";

/* [Common base frame] */
top_z     = 44 + 2 * 102 * cos(45);   // 188.25: top of both bases, lid flush with it
plinth_d  = 150;
plinth_h  = 44;
plinth_wall = 3;
plinth_top_t = 4;
wall      = 4;
sph_r     = 102;                      // kugel
cyl_r     = 95;                       // zylinder
cut_h     = sph_r * cos(45);
zc        = plinth_h + cut_h;         // centre height of the speakers and the knob
// speakers sit behind the round wall: inner baffle at y = +-baf_in, the wall in front of it is the grille
baf_in    = base == "kugel" ? 76 : 69;  // flange seat (inside face of the baffle); room for the 106 mm flange
baf_t     = 7;
pilot_depth = 7;                      // pilot hole from 1 mm in front of the baffle: ends 6 mm into it. The corner holes on the 110 mm bolt circle sit near the outer wall, deeper holes broke through (leak)
// BT3 x 10 through ear (about 2 mm) and foam gasket (2 mm) bite about 6 mm into the baffle

/* [Driver (front, -Y) and passive radiator (back, +Y)] */
drv_flange_d = 106;
drv_flange_t = 4.5;
drv_cutout_d = 100;                  // round cutout, 100 mm as measured (data sheet says 93 mm, the cone and frame need more room)
drv_bolt_d   = 110;                   // measured on the driver: 110 mm across the diagonal (holes on the 45 deg diagonals), about 78-80 mm between neighbours
pr_flange_d  = 106;
pr_cutout_d  = 100;
pr_bolt_d    = 110;                   // same pattern as the ND105-4 (measured)

/* [Hole field in the wall (the grille is printed with the body)] */
grille_r  = 44;
hole_d    = 4.2;
hole_pitch = 5.6;

/* [Screws: self-tapping, pan head] */
bt3_pilot   = 2.5;
bt3_clear   = 3.4;
bt26_pilot  = 2.1;
boss_d      = 9;
screw_r     = 62;                     // bolt circle body <-> plinth (4x, 45/135/225/315 deg)
plate_screw_r = 62;                   // plate <-> plinth (3x, 90/210/330 deg, under the feet)

/* [Bayonet lid] */
bore_r    = 62;                       // collar bore below the 45 deg seat
lid_t     = 4;
lug_w     = 12;                       // deg
lock_a    = 40;                       // turn to lock

/* [Knob] */
knob_d    = 30;
knob_h    = 14;
knob_out  = 10;                       // the knob stands 10 mm proud, only about 4 mm sit in the inset
pocket_d  = knob_d + 3;               // shallow inset, 1.5 mm gap round the knob
pocket_depth = knob_h - knob_out + 1; // 1 mm under the knob

/* [Electronics] */
dc_jack_d   = 11;
hat_origin  = [-32.5, -28];
hat_holes   = [[3.5,3.5],[61.5,3.5],[3.5,52.5],[61.5,52.5]];
pi_holes    = hat_holes;
zero_z      = 8;
hat_z       = zero_z + 1.6 + 11;
buck_center = [0, -45];
buck_size   = [43, 21];
buck_holes  = [[-15,-8],[15,-8],[-15,8],[15,8]];

/* [Lamp] */
stem_od   = 20;
stem_id   = 13;
socket_d  = 18;                       // stem socket depth in the lid
stem_long = 140;                      // plissee / glocke (both bases)
stem_short = 95;                      // kolben / twist / laterne (both bases)
core_d    = 40;
core_h    = 60;
shade_wall = 1.2;
flange_in = 60;                       // globe shades: inner radius of the bottom flange

$fn = 96;
eps = 0.01;

// ------------------------------------------------------------------ helpers
module ring(od, id, h) { difference() { cylinder(d = od, h = h); translate([0, 0, -eps]) cylinder(d = id, h = h + 2 * eps); } }
// hole along +Y with a 45 deg roof, so it prints in a vertical wall without supports
module teardrop_y(d, len) {
  rotate([90, 0, 0]) linear_extrude(len, center = true)
    union() { circle(d = d); rotate(45) square(d / 2); }
}
function sph_rz(z) = sqrt(max(0, sph_r * sph_r - (z - zc) * (z - zc)));      // outer sphere radius at height z
function sph_irz(z) = sqrt(max(0, (sph_r - wall) * (sph_r - wall) - (z - zc) * (z - zc)));
edge_bot = sph_rz(top_z - lid_t);     // 74.9: lid edge, bottom
edge_top = sph_rz(top_z);             // 72.1: lid edge, top
edge_shade = sph_rz(top_z - 1.6);    // 73.2: globe shades start here (their flange sits 1.6 mm deep in the lid)

// cubic Hermite spline through knots [z, r, dr/dz]
function _hseg(k, z, i = 0) = (i >= len(k) - 2 || z <= k[i + 1][0]) ? i : _hseg(k, z, i + 1);
function herm(k, z) =
  let(i = _hseg(k, z), a = k[i], b = k[i + 1], h = b[0] - a[0], t = max(0, min(1, (z - a[0]) / h)),
      t2 = t * t, t3 = t2 * t)
  (2 * t3 - 3 * t2 + 1) * a[1] + (t3 - 2 * t2 + t) * h * a[2] + (-2 * t3 + 3 * t2) * b[1] + (t3 - t2) * h * b[2];

// ------------------------------------------------------------------ themes [body, plinth, accent, shade, knob]
function theme_colors(t) =
  t == "walnuss"    ? ["#6b4630", "#3d281c", "#c19a5b", "#f1e4c8", "#e9dcc2"] :
  t == "salbei"     ? ["#8c9c82", "#f1eee6", "#c8a46a", "#fbf6ea", "#f1eee6"] :
  t == "terrakotta" ? ["#b4623f", "#efe6d6", "#c9a063", "#f6ecd9", "#efe6d6"] :
  t == "schwarz"    ? ["#25262a", "#25262a", "#c79b4b", "#efe2c4", "#c79b4b"] :
  t == "creme"      ? ["#ece5d6", "#8a6a4c", "#b8925a", "#fbf3e2", "#8a6a4c"] :
                      ["#3c4157", "#2b2f3d", "#b88a3c", "#f3ead8", "#d0c7b3"];
TC = theme_colors(theme);

// ------------------------------------------------------------------ shades
// [height, knots, ribs, rib depth, twist, on lid?, rib shape ("cos" | "pleat")]
function style(n) =
  n == "plissee" ? [160, [[0, 104, -0.12], [80, 88, -0.24], [160, 60, -0.42]], 44, 4.0, 0, false, "pleat"] :
  n == "glocke"  ? [150, [[0, 106, -0.85], [40, 76, -0.45], [150, 50, -0.08]], 36, 2.2, 0, false, "cos"] :
  n == "kolben"  ? [225, [[0, edge_shade, -1], [16, 64.5, 0], [105, 99, 0], [225, 54, -0.85]], 56, 2.2, 0, true, "cos"] :
  n == "twist"   ? [205, [[0, edge_shade, -1], [14, 66, 0], [100, 84, 0], [205, 70, -0.15]], 40, 3.0, 55, true, "cos"] :
                   [215, [[0, edge_shade, -1], [12, 65.5, 0], [45, 82, 0], [78, 69, 0], [112, 86, 0], [146, 69, 0], [180, 80, 0], [215, 60, -0.7]], 72, 1.6, 0, true, "cos"];
S       = style(shade_style);
S_h     = S[0];
S_k     = S[1];
on_lid  = S[5];
function S_prof(z) = herm(S_k, z);
function shade_r(z) = S_prof(z) - S[3];            // rib valleys (inside)

lamp_stem = on_lid ? stem_short : stem_long;
stem_z    = top_z - socket_d;
stem_top  = stem_z + lamp_stem;
shade_z   = on_lid ? top_z - 1.6 : 262;            // globe shades: flange sits in the lid recess
spider_z  = shade_z + S_h - 8;
pin_len   = on_lid ? 4 : spider_z + 10 - (stem_top + core_h + 3);

// rib depth fades in over the first 22 mm of the globe shades, so the bottom edge is a clean circle
function rib_fade(z) = on_lid ? min(1, z / 22) : 1;
function rib(a, z) = S[6] == "pleat" ? abs(((a * S[2] / 360) % 1) * 2 - 1) : (1 - cos(S[2] * (a + S[4] * z / S_h))) / 2;

module shade_shell(steps = 110) {
  ribs = S[2]; amp = S[3];
  seg = ribs * (S[6] == "pleat" ? 2 : 6);
  ro = function(z, a) S_prof(z) - amp * rib(a, z) * rib_fade(z);
  pts = concat(
    [for (i = [0:steps]) for (j = [0:seg - 1]) let(z = S_h * i / steps, a = 360 * j / seg, r = ro(z, a)) [r * cos(a), r * sin(a), z]],
    [for (i = [0:steps]) for (j = [0:seg - 1]) let(z = S_h * i / steps, a = 360 * j / seg, r = ro(z, a) - shade_wall) [r * cos(a), r * sin(a), z]]);
  N = (steps + 1) * seg;
  P = function(i, j) i * seg + (j % seg);
  Q = function(i, j) N + i * seg + (j % seg);
  polyhedron(pts, concat(
    [for (i = [0:steps - 1]) for (j = [0:seg - 1]) [P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)]],
    [for (i = [0:steps - 1]) for (j = [0:seg - 1]) [Q(i, j), Q(i, j + 1), Q(i + 1, j + 1), Q(i + 1, j)]],
    [for (j = [0:seg - 1]) [P(0, j), P(0, j + 1), Q(0, j + 1), Q(0, j)]],
    [for (j = [0:seg - 1]) [P(steps, j), Q(steps, j), Q(steps, j + 1), P(steps, j + 1)]]), convexity = 8);
}
module shade() {
  shade_shell();
  // globe shades: 1.6 mm flange on the bed, it sits in the lid recess and centres the shade
  if (on_lid) ring(2 * (S_prof(0) - 0.6), 2 * flange_in, 1.6);
}

// ------------------------------------------------------------------ body
module outer_solid() {
  if (base == "kugel")
    intersection() {
      translate([0, 0, zc]) sphere(r = sph_r, $fn = 180);
      translate([-200, -200, plinth_h]) cube([400, 400, top_z - lid_t - plinth_h]);
    }
  else
    difference() {
      translate([0, 0, plinth_h]) cylinder(r = cyl_r, h = top_z - plinth_h, $fn = 180);
      // flush recess for the lid edge (same cone as on the sphere)
      translate([0, 0, top_z - lid_t]) cylinder(r1 = edge_bot + 0.2, r2 = edge_top + 0.2, h = lid_t + eps, $fn = 180);
    }
}
module inner_cavity() {
  if (base == "kugel") translate([0, 0, zc]) sphere(r = sph_r - wall, $fn = 180);
  else translate([0, 0, plinth_h - 1]) cylinder(r = cyl_r - wall, h = top_z, $fn = 180);
}

// solid top: 45 deg seat cone that runs straight out to the sphere at top_z - 4 (no flat rim, so the lid
// has no overhanging lip), bayonet collar below it, 45 deg underside
seat_z = top_z - lid_t - (edge_bot - bore_r);     // where the seat cone meets the bore (about T - 16.9)
module top_block() {
  T = top_z;
  rotate_extrude($fn = 180) polygon([[bore_r, T - 20], [bore_r, seat_z], [edge_bot, T - lid_t], [edge_top, T], [130, T], [130, T - 88]]);
}
module bottom_block() {   // flange / floor ring the body is screwed down with
  h = base == "kugel" ? 6 : 4;
  ring(2 * 130, 2 * 56, h + plinth_h);
  for (a = [45:90:315]) rotate(a) translate([screw_r, 0, 0]) cylinder(d = boss_d, h = plinth_h + 12, $fn = 32);
}
module baffles() { for (s = [-1, 1]) translate([-200, s > 0 ? baf_in : -baf_in - baf_t, 0]) cube([400, baf_t, 400]); }
knob_x = base == "kugel" ? sph_r : cyl_r;
module knob_cup() {   // closed cup in the chamber, pointed underneath (45 deg) so only the pocket roof needs tree supports
  translate([knob_x - pocket_depth - 3, 0, zc]) rotate([0, 90, 0]) hull() {
    cylinder(d = pocket_d + 6, h = pocket_depth + 3, $fn = 64);
    translate([(pocket_d + 6) / 2 * sqrt(2) - 0.5, 0, 0]) cylinder(d = 1, h = pocket_depth + 3, $fn = 8);
  }
}
module knob_pocket() {
  translate([knob_x - pocket_depth, 0, zc]) rotate([0, 90, 0]) cylinder(d = pocket_d, h = 30, $fn = 64);
  translate([knob_x - pocket_depth - 4, 0, zc]) rotate([0, 90, 0]) cylinder(d = 7.4, h = 6, $fn = 32);   // EC11 bushing
  translate([knob_x - pocket_depth - 4, 0, zc + 8]) rotate([0, 90, 0]) cylinder(d = 3.2, h = 6, $fn = 16);  // anti-rotation tab
}
module face_cuts(s) {
  cut = s < 0 ? drv_cutout_d : pr_cutout_d;
  bd = s < 0 ? drv_bolt_d : pr_bolt_d;
  // opening in the baffle: exactly round (seals against the foam gasket); the upper arc needs manual tree supports when printing
  translate([0, s * (baf_in + baf_t / 2), zc]) rotate([90, 0, 0]) cylinder(d = cut, h = baf_t + 2, center = true, $fn = 180);
  // pilot holes, screwed from inside the chamber
  for (a = [45:90:315]) translate([cos(a) * bd / 2, s * (baf_in - 1), zc + sin(a) * bd / 2]) rotate([-s * 90, 0, 0]) cylinder(d = bt3_pilot, h = pilot_depth, $fn = 16);
  // room for flange and screw heads where the 45 deg roof of the chamber reaches down: 7 mm straight, then a 45 deg cone
  let(cr = max(drv_flange_d / 2, bd / 2 + 3.6) + 0.75)   // also covers the mounting ears and the screw heads on the bolt circle
  translate([0, s * baf_in, zc]) rotate([s * 90, 0, 0]) { cylinder(r = cr, h = 7 + eps, $fn = 120); translate([0, 0, 7]) cylinder(r1 = cr, r2 = cr - 8, h = 8, $fn = 120); }
  // round hole field in the outer wall, flat-top hexagons: each roof is a 2.4 mm bridge
  hole_field(s);
}
module hole_field(s) render(convexity = 4) {
  for (x = [-grille_r:hole_pitch:grille_r]) for (j = [-9:9]) let(z = j * hole_pitch * 0.866, xx = x + (abs(j) % 2) * hole_pitch / 2)
    if (xx * xx + z * z <= grille_r * grille_r) translate([xx, s * (baf_in + baf_t + 0.5), zc + z]) rotate([-s * 90, 0, 0]) cylinder(d = hole_d / cos(30), h = 40, $fn = 6);
}
module body() {
  difference() {
    union() {
      difference() { outer_solid(); inner_cavity(); }
      intersection() {
        outer_solid();
        union() { top_block(); bottom_block(); baffles(); knob_cup();
        }
      }
    }
    // keep the chamber open below, the plinth closes it; keep the bore open
    translate([0, 0, plinth_h - 1]) cylinder(r = 56, h = 13);
    translate([0, 0, top_z - 21]) cylinder(r = bore_r, h = 30);
    // bayonet entry slots
    for (a = [0:120:240]) rotate(a) rotate_extrude(angle = lug_w + 2, $fn = 120) translate([bore_r - 1, top_z - 25]) square([3.8, 9]);
    rotate_extrude($fn = 180) translate([bore_r - 1, top_z - 24.5]) square([3.6, 4.5]);   // lug track under the collar
    face_cuts(-1); face_cuts(1);
    knob_pocket();
    for (a = [45:90:315]) rotate(a) translate([screw_r, 0, plinth_h - eps]) cylinder(d = bt3_pilot, h = 11, $fn = 16);
  }
}

// ------------------------------------------------------------------ lid (same for both bases and all shades)
module lid() {
  T = top_z;
  difference() {
    union() {
      // flush edge = the missing sphere band, then a 45 deg cone into the seat (prints top up without supports)
      rotate_extrude($fn = 180) polygon([[0, T], [edge_top, T], [edge_bot, T - lid_t], [edge_bot - 0.4, T - lid_t],
                                         [bore_r - 0.4, seat_z - 0.4], [bore_r - 0.4, T - 24], [0, T - 24]]);
      for (a = [0:120:240]) rotate(a + 1) rotate_extrude(angle = lug_w, $fn = 120) translate([bore_r - 1, T - 24]) square([3.2, 3]);  // lugs
    }
    translate([0, 0, T - socket_d]) cylinder(d = stem_od + 0.4, h = socket_d + 1);                  // stem socket
    // recess for the flange of the globe shades
    translate([0, 0, T - 1.6]) ring(2 * (edge_top + 1), 2 * (flange_in - 0.3), 2);
    // LED cable: through the plug, up into the stem; arc slot covers the locking turn
    rotate(180) rotate_extrude(angle = lock_a + 10, $fn = 120) translate([40, T - 25]) square([8, 8]);
    hull() { translate([-44, 0, T - 18]) sphere(d = 7, $fn = 24); translate([0, 0, T - 18]) sphere(d = 7, $fn = 24); }
    // two finger holes to turn the lid
    for (x = [-34, 34]) translate([x, 0, T - 6]) cylinder(d = 14, h = 7, $fn = 48);
  }
}

// ------------------------------------------------------------------ plinth (same for both)
plate_screw_a = [90, 210, 330];
module plinth() {
  pr = plinth_d / 2; pri = pr - plinth_wall;
  difference() {
    union() {
      ring(plinth_d, plinth_d - 2 * plinth_wall, plinth_h);
      translate([0, 0, plinth_h - plinth_top_t]) cylinder(r = pr - eps, h = plinth_top_t);
      for (a = plate_screw_a) rotate(a) translate([plate_screw_r, 0, 3]) cylinder(d = boss_d, h = plinth_h - 3, $fn = 32);
    }
    for (a = [45:90:315]) rotate(a) translate([screw_r, 0, plinth_h - plinth_top_t - eps]) cylinder(d = bt3_clear, h = 10, $fn = 20);
    for (a = plate_screw_a) rotate(a) translate([plate_screw_r, 0, 3 - eps]) cylinder(d = bt3_pilot, h = 14, $fn = 16);
    // cable holes (speakers, encoder, LED), sealed with silicone after wiring
    for (p = [[-22, 34], [22, 34], [-42, 0]]) translate([p[0], p[1], plinth_h - plinth_top_t - eps]) cylinder(d = 6, h = 10, $fn = 24);
    // DC jack and vents at the back
    rotate(120) translate([pri, 0, 21]) rotate([0, 90, 0]) cylinder(d = dc_jack_d, h = 10, center = true, $fn = 32);
    for (i = [-3:3]) if (i != 0) rotate(90 + i * 7) translate([pri, 0, 14]) cube([10, 3, 16], center = true);
  }
}
module plate() {
  pri = plinth_d / 2 - plinth_wall;
  difference() {
    union() {
      cylinder(r = pri - 0.4, h = 3);
      translate(hat_origin) for (p = pi_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = zero_z, $fn = 24);
      translate(buck_center) for (p = buck_holes) translate([p[0], p[1], 0]) cylinder(d = 6, h = 7, $fn = 24);
    }
    translate([hat_origin[0], hat_origin[1], -eps]) for (p = pi_holes) translate([p[0], p[1], 0]) cylinder(d = 2.1, h = 30, $fn = 16);
    translate([buck_center[0], buck_center[1], -eps]) for (p = buck_holes) translate([p[0], p[1], 0]) cylinder(d = bt26_pilot, h = 10, $fn = 16);
    for (a = plate_screw_a) rotate(a) translate([plate_screw_r, 0, -eps]) {
      cylinder(d = bt3_clear, h = 4, $fn = 20);
      cylinder(d = 13, h = 1.2, $fn = 40);              // recess: the rubber foot covers the screw head
    }
  }
}

// ------------------------------------------------------------------ knob, lamp parts
module knob() {   // knurled wheel with a 1 mm chamfer, stands knob_out proud of the inset
  difference() {
    union() { cylinder(d = knob_d, h = knob_h - 1, $fn = 120); translate([0, 0, knob_h - 1]) cylinder(d1 = knob_d, d2 = knob_d - 2, h = 1, $fn = 120); }
    for (a = [0:6:354]) rotate(a) translate([knob_d / 2 + 0.2, 0, -eps]) cylinder(d = 1.6, h = knob_h - 1.5, $fn = 8);
    translate([0, 0, -eps]) difference() { cylinder(d = 6.2, h = 12, $fn = 32); translate([1.6, -4, -1]) cube([4, 8, 14]); }
    translate([0, 9, knob_h - 0.6]) cylinder(d = 2.5, h = 2, $fn = 16);
  }
}
module stem() { ring(stem_od, stem_id, lamp_stem); }
module led_core() {
  difference() {
    union() {
      cylinder(d = core_d, h = core_h);
      cylinder(d1 = core_d, d2 = core_d + 6, h = 3);                 // 45 deg collar: printed upside down, no overhang
      translate([0, 0, -12]) cylinder(d = stem_id - 0.3, h = 12);
      translate([0, 0, core_h]) ring(core_d - 2.4, core_d - 5, 1.5);     // centring lip for the cap
    }
    translate([0, 0, -13]) cylinder(d = 8, h = 16);
    translate([0, 0, 3]) cylinder(d = core_d - 5, h = core_h);
    translate([0, 0, 6]) for (a = [0:60:300]) rotate(a) translate([core_d / 2, 0, 0]) rotate([0, 90, 0]) cylinder(d = 6, h = 8, center = true, $fn = 16);
  }
}
module core_cap() {
  difference() {
    union() {
      cylinder(d = core_d + 6, h = 3);
      translate([0, 0, 3]) cylinder(d = 10, h = pin_len);
    }
    translate([0, 0, -eps]) ring(core_d - 2, core_d - 5.4, 1.7);         // groove for the lip of the core
    for (a = [0:45:315]) rotate(a) translate([core_d / 2 - 9, 0, -eps]) cylinder(d = 3, h = 4, $fn = 12);
  }
}
module spider() {
  rr = shade_r(S_h - 8) + 0.8; hub_h = 10;
  difference() {
    union() {
      cylinder(d = 18, h = hub_h);
      ring(2 * rr, 2 * rr - 8, 4);
      for (a = [0:120:240]) rotate(a) translate([0, -2.5, 0]) cube([rr - 3, 5, 4]);
    }
    translate([0, 0, -eps]) cylinder(d = 10.4, h = hub_h + 1);
  }
}

// ------------------------------------------------------------------ dummies (pictures only)
module dummy_driver() color("#202231") { cylinder(d = drv_flange_d, h = 3); translate([0, 0, -30]) cylinder(d1 = 40, d2 = drv_cutout_d - 4, h = 30); translate([0, 0, -64]) cylinder(d = 62, h = 34); }
module dummy_pr() { color("#202231") cylinder(d = pr_flange_d, h = 3); color("#6d7282") translate([0, 0, -3]) cylinder(d = 80, h = 3); }
module dummy_electronics() {
  translate([hat_origin[0], hat_origin[1], 0]) {
    color("#1f7a3c") translate([0, 0, zero_z]) cube([65, 56, 1.6]);
    color("#2a4b8d") translate([0, 0, hat_z]) cube([65, 56.5, 1.6]);
    color("#111") translate([8, 8, hat_z + 1.6]) cube([14, 14, 10]);
    color("#111") translate([40, 8, hat_z + 1.6]) cube([14, 14, 10]);
    color("#2f8a4f") translate([0, 40, hat_z + 1.6]) cube([10, 16, 9]);
  }
  translate([buck_center[0] - buck_size[0] / 2, buck_center[1] - buck_size[1] / 2, 7]) {
    color("#2a4b8d") cube([buck_size[0], buck_size[1], 1.6]);
    color("#333") translate([14, 3, 1.6]) cube([13, 13, 7]);
  }
}
module dummy_encoder() color("#3b3f48") translate([knob_x - pocket_depth - 3, 0, zc]) rotate([0, -90, 0]) { translate([0, 0, 3]) cube([13, 12.5, 6], center = true); translate([0, 0, -6]) cylinder(d = 7, h = 6, $fn = 24); }
module led_strip_spiral(turns = 4, pitch = 13, w = 10) {
  steps = 160; r = core_d / 2 + 0.6;
  for (i = [0:steps - 1]) let(a0 = i * 360 * turns / steps, a1 = (i + 1) * 360 * turns / steps)
    hull() for (a = [a0, a1]) rotate(a) translate([r, 0, 6 + a / 360 * pitch]) cube([0.6, 0.6, w], center = true);
}

// ------------------------------------------------------------------ placed parts
module place_body()   color(TC[0]) render(convexity = 6) body();   // render(): the hole field is too big for the preview CSG
module place_plinth() color(TC[1]) plinth();
module place_plate()  color(TC[1]) plate();
module place_lid()    color(TC[0]) rotate(lock_a) lid();
module place_knob()   color(TC[4]) translate([knob_x + knob_out - knob_h, 0, zc]) rotate([0, 90, 0]) knob();
module place_lamp(with_shade = true) {
  color(TC[2]) translate([0, 0, stem_z]) stem();
  color("#e9e3d5") translate([0, 0, stem_top]) { led_core(); translate([0, 0, core_h]) core_cap(); }
  if (!on_lid) color(TC[3]) translate([0, 0, spider_z]) spider();
  if (with_shade) color(TC[3], 0.92) translate([0, 0, shade_z]) shade();
}
module assembly(with_shade = true) {
  place_plinth(); place_plate(); place_body(); place_lid(); place_knob();
  place_lamp(with_shade);
}
module section() {
  difference() {
    union() { assembly(with_shade = true);
      drivers_in();
      dummy_electronics(); dummy_encoder(); }
    translate([0, -300, -10]) cube([300, 600, 700]);
  }
}
// side section through the knob axis (x-z plane): knob pocket, lid bayonet and the lid/shade transition
module section_knob() {
  difference() {
    union() { assembly(with_shade = true); dummy_encoder(); }
    translate([-300, -600, -10]) cube([600, 600, 700]);
  }
}
// exploded view in assembly order: plinth+plate below, body, grilles out front/back, knob out right, lid, stem, core, shade
module exploded(e = 1) {
  translate([0, 0, -70 * e]) { place_plinth(); translate([0, 0, -60 * e]) { place_plate(); dummy_electronics(); } }
  place_body();
  // speakers are mounted from inside: shown beside the body, they go in through the open bottom
  translate([-215 * e, 0, 0]) { drivers_in(); speaker_screws(30); }
  guide([-215 * e + 60, 0, zc], [-70, 0, zc]);
  translate([45 * e, 0, 0]) place_knob();
  translate([0, 0, 55 * e]) place_lid();
  translate([0, 0, 110 * e]) place_lamp(false);
  if (on_lid) color(TC[3], 0.92) translate([0, 0, shade_z + 230 * e]) shade();
  else { color(TC[3]) translate([0, 0, spider_z + 125 * e]) spider(); color(TC[3], 0.92) translate([0, 0, shade_z + 150 * e]) shade(); }
  // screws with red lines to their holes
  for (a = [45:90:315]) let(p = [cos(a) * screw_r, sin(a) * screw_r, plinth_h])
    { translate(p + [0, 0, -70 * e - plinth_top_t - 6]) rotate([180, 0, 0]) screw(10); guide(p + [0, 0, -70 * e - 6], p); }
  for (a = plate_screw_a) let(p = [cos(a) * plate_screw_r, sin(a) * plate_screw_r, 0])
    { translate(p + [0, 0, -130 * e - 25]) rotate([180, 0, 0]) screw(10); guide(p + [0, 0, -130 * e - 25], p + [0, 0, -70 * e]); }
}
// building guide: one picture per step, earlier parts in place, the new parts pulled out along red lines
module drivers_in(e = 0) {
  translate([0, -baf_in + 3 + e, zc]) rotate([90, 0, 0]) dummy_driver();
  translate([0, baf_in - 3 - e, zc]) rotate([-90, 0, 0]) dummy_pr();
}
// pan heads sit on the flange inside the chamber, the screws point outwards into the baffle
module speaker_screws(e) for (s = [-1, 1]) for (a = [45:90:315]) let(bd = s < 0 ? drv_bolt_d : pr_bolt_d, p = [cos(a) * bd / 2, s * (baf_in - drv_flange_t), zc + sin(a) * bd / 2])
  { translate(p - [0, s * e, 0]) rotate([s * 90, 0, 0]) screw(10); if (e > 0) guide(p - [0, s * 2, 0], p - [0, s * (e - 3), 0]); }
module cut_open() difference() { children(); translate([0, -300, -10]) cube([300, 600, 700]); }
module base_screws(e) for (a = [45:90:315]) let(p = [cos(a) * screw_r, sin(a) * screw_r, plinth_h])
  { translate(p + [0, 0, -plinth_top_t - 6 - e]) rotate([180, 0, 0]) screw(10); if (e > 0) guide(p + [0, 0, -plinth_top_t - 6 - e], p); }
module plate_screws(e) for (a = plate_screw_a) let(p = [cos(a) * plate_screw_r, sin(a) * plate_screw_r, 0])
  { translate(p + [0, 0, -e]) rotate([180, 0, 0]) screw(10); if (e > 0) guide(p + [0, 0, -e], p + [0, 0, 20]); }
module step_view(n) {
  if (n == 1) { cut_open() place_body(); drivers_in(28); speaker_screws(40); }
  if (n == 2) { place_body(); dummy_encoder(); translate([60, 0, 0]) place_knob(); guide([knob_x - 2, 0, zc], [knob_x + 45, 0, zc]); }
  if (n == 3) { place_body(); place_knob(); translate([0, 0, -70]) { place_plinth(); base_screws(40); } }
  if (n == 4) { place_plate(); dummy_electronics();
                for (p = [buck_holes[0], buck_holes[3]]) translate([buck_center[0] + p[0], buck_center[1] + p[1], 40]) screw(6); }
  if (n == 5) { assembly_base(); translate([0, 0, -70]) { place_plate(); dummy_electronics(); plate_screws(40); } }
  if (n == 6) { assembly_base(); place_plate(); translate([0, 0, 70]) color(TC[0]) lid(); guide([0, 0, top_z + 2], [0, 0, top_z + 50]); }
  if (n == 7) { assembly_base(); place_plate(); place_lid();
                translate([0, 0, 40]) color(TC[2]) translate([0, 0, stem_z]) stem();
                translate([0, 0, 80]) color("#e9e3d5") translate([0, 0, stem_top]) { led_core(); led_strip_spiral(); }
                translate([0, 0, 120]) color("#e9e3d5") translate([0, 0, stem_top + core_h]) core_cap();
                guide([0, 0, top_z + 2], [0, 0, stem_top + 200]); }
  if (n == 8) { assembly(with_shade = false);
                if (!on_lid) { translate([0, 0, 90]) color(TC[3]) translate([0, 0, spider_z]) spider(); translate([0, 0, 170]) color(TC[3], 0.92) translate([0, 0, shade_z]) shade(); }
                else translate([0, 0, 200]) color(TC[3], 0.92) translate([0, 0, shade_z]) shade();
                guide([0, 0, stem_top + core_h + 5], [0, 0, shade_z + 160]); }
}
module assembly_base() { place_plinth(); place_body(); place_knob(); }

// screw pointing along -Z from its pan head at the origin
module screw(len) color("#8d939b") { cylinder(d = 5.6, h = 2.2, $fn = 24); translate([0, 0, -len]) cylinder(d = 3, h = len, $fn = 16); }
module guide(a, b) color("#d6402f") hull() { translate(a) sphere(d = 1.2, $fn = 8); translate(b) sphere(d = 1.2, $fn = 8); }

// ------------------------------------------------------------------ output
if (part == "assembly") assembly();
if (part == "exploded") exploded();
if (part == "section")  section();
if (part == "section_knob") section_knob();
if (part == "step")     step_view(step);
if (part == "body")     rotate([0, 0, 0]) translate([0, 0, -plinth_h]) body();
if (part == "plinth")   translate([0, 0, plinth_h]) rotate([180, 0, 0]) plinth();   // top on the bed
if (part == "plate")    plate();
if (part == "lid")      translate([0, 0, -(top_z - 24)]) lid();
if (part == "knob")     knob();                                                    // back on the bed, dome up
if (part == "stem")     stem();
if (part == "led_core") translate([0, 0, core_h + 1.5]) rotate([180, 0, 0]) led_core();   // upside down, lip on the bed
if (part == "core_cap") core_cap();
if (part == "spider")   spider();
if (part == "shade")    shade();
