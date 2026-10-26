"""Rebuild Study.pdf from the current engine, bundled fonts and vector equations.

Run with the project's Python. No GUI, TeX installation or online service is used.
Only documentation, diagrams and a quality report under work/ are written.
"""

import argparse
from functools import partial
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, PageBreak

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.math_engine import PropellerMathEngine, PropellerParameters
from scripts.study_figures import make_figures
from scripts.study_layout import (CHECKED_TEXT, EQUATIONS, WIDTH, Equation, StudyDoc,
                                  paragraph, setup_fonts, styles, table, verify_text_glyphs)


def build_study_pdf(output_path=ROOT / "Study.pdf"):
    setup_fonts()
    CHECKED_TEXT.clear()
    EQUATIONS.clear()
    sheet = styles()
    p = PropellerParameters(254.0, 114.3, 2)
    engine = PropellerMathEngine(p)
    thrust, gf = p.estimate_static_thrust()
    figures = make_figures(ROOT / "scripts" / "diagrams")
    story = []
    page_count = 20
    doc = StudyDoc(output_path, page_count)

    def text(value, style="body"):
        story.append(paragraph(value, sheet[style]))

    def heading(number, title):
        if number > 1:
            story.append(PageBreak())
        item = paragraph(title, sheet["cover"] if number == 1 else sheet["chapter"])
        item.chapter_id = f"chapter-{number}"
        item.chapter_title = title.replace("<br/>", " ")
        story.append(item)

    def section(title):
        text(title, "section")

    def eq(value, size=14):
        story.append(Equation(value, size=size))

    def grid(rows, widths):
        story.append(table(rows, widths, sheet))

    def figure(key, caption, height=None):
        image = Image(str(figures[key]))
        # Resolve lazy image metadata before assigning the final print dimensions.
        natural_width, natural_height = image.imageWidth, image.imageHeight
        image.drawWidth = WIDTH
        image.drawHeight = height or WIDTH * natural_height / natural_width
        story.append(image)
        text(caption, "small")

    def symbol(value):
        return Equation(value, size=12, width=72, boxed=False)

    # Each chapter is deliberately one page; page positions are checked after build.
    heading(1, "Understand your<br/>propeller")
    text("A practical guide to the geometry, airflow and CAD behind Propeller Maker.", "deck")
    text("Start with the physical picture, then follow one blade section from a few numbers to a closed solid. "
         "Every numerical example uses the same 10 × 4.5 inch, two-blade clockwise benchmark as the app.")
    grid([["Diameter", "Pitch", "Blades", "Rotation"],
          ["254.0 mm", "114.3 mm", "2", "Clockwise"]], [125, 125, 90, WIDTH - 340])
    section("Three ideas to keep in mind")
    text("<b>A propeller is a rotating wing.</b> Its sections create aerodynamic forces; their combined axial component is thrust.")
    text("<b>Pitch is a distance.</b> The blade angle changes from root to tip even when geometric pitch is constant.")
    text("<b>A valid CAD solid is a starting point.</b> Geometry checks and a thrust estimate answer different questions. "
         "Neither is a measured performance or structural test.")
    section("Choose your route")
    grid([["If you want to...", "Read"],
          ["Use the app and export a model", '<link href="#chapter-2" color="#1B6C80">Page 2</link>, then pages 12-13'],
          ["Understand the shape without advanced maths", '<link href="#chapter-5" color="#1B6C80">Pages 5-8</link>'],
          ["Follow the equations into 3D", '<link href="#chapter-9" color="#1B6C80">Pages 9-11</link>, then page 16'],
          ["Interpret thrust and prepare for CFD", '<link href="#chapter-14" color="#1B6C80">Pages 14-18</link>'],
          ["Look up a symbol or practise", "Pages 3-4 and 19"]], [WIDTH - 174, 174])
    text("The guide describes the current source code, including its modelling choices and limits. "
         "Equations and symbol cells are vector artwork; body fonts are embedded. References and regeneration instructions are on page 20.", "small")

    heading(2, "From inputs to a STEP file")
    text("You control three physical quantities: diameter, pitch and blade count. The hub, bore, thickness, section shapes and twist are derived automatically.")
    section("1. Set dimensions")
    text("Choose <b>mm</b> or <b>in</b>, enter a diameter and geometric pitch, and select 2-8 blades. "
         "Changing units converts the display; it does not resize the underlying design. Clockwise rotation is fixed.")
    eq(r"1\ \mathrm{in}=25.4\ \mathrm{mm},\qquad P/D=114.3/254=0.450")
    text("Read 10 × 4.5 in as a 10 inch diameter and a 4.5 inch geometric pitch. "
         "The second number is not the hub diameter, blade width or measured distance travelled through air.")
    section("2. Inspect the result")
    text("Select <b>Update preview</b> after changing dimensions. The app can display edited parameters while the previous solid is still visible; "
         "the status message tells you when a preview update is needed. Drag to orbit, right-drag to zoom, or use Isometric, Top, Front and Side.")
    text("<b>Hub dimensions</b> gives the mounting sizes. Expand <b>Engineering details</b> for the pitch ratio, pitch angles, swept area, "
         "thrust estimate and validation details. Expand <b>Blade profiles</b> to see chord and twist distributions.")
    section("3. Export")
    text("Select <b>Export STEP</b>, choose a location, and wait for the exported status. The worker generates or reuses the matching solid, "
         "writes a temporary STEP file, imports it again, validates it, and only then replaces the chosen output.")
    grid([["You receive", "What it contains"],
          [".step / .stp", "The geometric boundary of a connected solid, suitable for import into CAD or meshing tools."],
          ["You do not receive", "A CFD solution, pressure field, material, motor model, torque curve or stress result."]], [105, WIDTH - 105])
    section("Useful input checks")
    text("Diameter and pitch must be finite and positive; the diameter must exceed the minimum 12 mm hub diameter. "
         "A pitch/diameter ratio outside 0.2-2.5 raises a UI warning. That warning is guidance, not an aerodynamic pass/fail test.")
    text("Keep the project folder together: the launchers, local Python environment, source and bundled fonts are used from that folder.", "small")

    heading(3, "Geometry symbols and units")
    text("A symbol is a short label for a quantity. The same letter in a different case can mean something else: uppercase P is pitch; lowercase p is a camber-position fraction.")
    rows = [["Symbol", "Meaning in this guide", "Units"]]
    for name, meaning, units in [
        ("D", "Propeller diameter: the nominal tip-to-tip dimension.", "mm or m"),
        ("R", "Tip radius, measured from the shaft centre; R = D/2.", "mm or m"),
        ("P", "Geometric pitch: ideal screw advance per revolution.", "mm or m"),
        ("B", "Number of blades; the app accepts integers 2-8.", "none"),
        ("r", "Local radius from the shaft axis to one blade station.", "mm or m"),
        (r"\xi", "xi: radius divided by tip radius, r/R.", "none"),
        ("c(r)", "Chord: width of an airfoil section before 3D placement.", "mm or m"),
        (r"\beta(r)", "beta: local geometric pitch angle to the rotation plane.", "rad / deg"),
        ("d_h", "Outer hub diameter; hub radius is d_h/2.", "mm"),
        ("d_b", "Diameter of the open shaft bore through the hub.", "mm"),
        ("H", "Hub thickness along the shaft axis.", "mm"),
        (r"r_{\mathrm{embed}}", "Buried starting radius of the blade, inside the hub.", "mm"),
        (r"z_{\mathrm{extent}}", "Largest absolute axial extent of the buried neck.", "mm"),
        ("A", "Swept disk area, pi times the square of the tip radius.", "m²"),
    ]:
        rows.append([symbol(name), meaning, units])
    grid(rows, [88, WIDTH - 162, 74])
    section("Two conversions that prevent large mistakes")
    eq(r"R_{\mathrm{m}}=R_{\mathrm{mm}}/1000,\qquad A_{\mathrm{m^2}}=A_{\mathrm{mm^2}}\times10^{-6}")
    text("Geometry is stored in millimetres. Aerodynamic force calculations use metres, seconds and kilograms. "
         "Do not put a radius in millimetres into a formula that expects metres.")

    heading(4, "Airfoil and airflow symbols")
    rows = [["Symbol", "Meaning; read the Greek name aloud", "Units"]]
    for name, meaning, units in [
        ("m,p,t", "NACA maximum camber, camber position and thickness ratio.", "fractions"),
        ("u", "Normalized chord position, 0 at leading edge and 1 at trailing edge; called xc in code.", "none"),
        (r"y_c,y_t", "Mean camber ordinate and half-thickness, divided by chord.", "none"),
        (r"\theta_c", "theta-c: local angle of the mean camber line.", "rad"),
        (r"\hat{x},\hat{y}", "Section coordinates divided by chord; x is centred at quarter-chord.", "none"),
        ("X,Y,Z", "Final Cartesian point coordinates; +Z is upstream.", "mm"),
        (r"\Omega", "omega: angular speed; 2 pi times RPM divided by 60.", "rad/s"),
        ("n", "Rotation rate in revolutions per second, not RPM.", "1/s"),
        (r"\phi", "phi: angle of the effective inflow to the rotation plane.", "rad / deg"),
        (r"\alpha", "alpha: angle of attack; geometric pitch angle minus inflow angle.", "rad / deg"),
        (r"\rho", "rho: air density; estimator default is 1.225.", "kg/m³"),
        (r"C_L,C_D", "Section lift and drag coefficients used in the estimator.", "none"),
        (r"F,\sigma", "Tip-loss factor; solidity is total local blade chord / circumference.", "none"),
        ("T,dT", "Total thrust and the small contribution of one radial strip; dr is strip width (metres).", "N"),
        (r"Re,C_T", "Reynolds number and propeller thrust coefficient.", "none"),
        (r"\mu", "mu: dynamic viscosity of air.", "kg/(m s)"),
        (r"V", "Speeds: Vrot is rotational, Veff effective and Vrel relative to a section.", "m/s"),
        (r"\alpha_0", "alpha-zero: the assumed zero-lift angle.", "rad / deg"),
        (r"\vartheta_k", "theta-k: cosine-sampling angle; k is the sample index.", "rad"),
    ]:
        rows.append([symbol(name), meaning, units])
    grid(rows, [88, WIDTH - 162, 74])
    text("Angles inside trigonometric functions use radians. Multiply radians by 180/pi to display degrees. "
         "A hat denotes a normalized coordinate; a subscript identifies a location or quantity. dT is a differential force, not diameter multiplied by thrust.", "small")

    heading(5, "A consistent clockwise convention")
    text("Clockwise depends on which side you look from. This program defines it from the upstream side: "
         "look from <b>+Z toward -Z</b>, as though the shaft points toward your eye.")
    figure("coordinates", "Figure 1. The observer, axes, blade motion and thrust use one convention. The drawing shows directions, not a computed airflow field.")
    section("Follow a blade at the top of the disk")
    text("At the +Y position, a clockwise-moving blade travels toward +X. Its leading edge must therefore lie ahead of its trailing edge in X. "
         "The pitched section also places that leading edge farther upstream in Z.")
    eq(r"X_{\mathrm{LE}}>X_{\mathrm{TE}},\qquad Z_{\mathrm{LE}}>Z_{\mathrm{TE}}")
    text("The upper, suction-side surface is on the +Z side of the section. The engine provides a dedicated orientation check that compares "
         "leading/trailing edges and upper/lower points near quarter-chord at each analytical station. "
         "That standalone check is separate from the app's per-export topology validation.")
    section("Force and flow point in opposite directions")
    text("In the intended operating direction, the propeller accelerates air downstream toward -Z; the reaction thrust on the propeller is toward +Z. "
         "The words upper and lower describe the section's two surfaces; they are not a promise about the world's vertical direction after a blade rotates.")
    section("Why this matters during import")
    text("Keep the same shaft direction and viewing convention in another CAD or CFD tool. A visually plausible model can be assigned the wrong angular-velocity sign. "
         "Always check a point on +Y: does the chosen rotation move it toward +X?")
    text("Geometry orientation does not by itself establish the amount of thrust. That requires a flow calculation or measurement, with matching operating conditions.", "small")

    heading(6, "Pitch is distance. Twist is angle.")
    text("Imagine replacing air with a material in which the blade behaves like a screw without slip. One revolution would advance by P. "
         "Unroll the circular path at radius r: the horizontal distance is its circumference and the vertical distance is the pitch.")
    figure("helix", "Figure 2. Unrolling a helix gives a right triangle. A larger radius makes the base longer while P stays constant.")
    eq(r"\tan\beta=\frac{P}{2\pi r},\qquad \beta(r)=\arctan\left(\frac{P}{2\pi r}\right)")
    text("<b>Read it as:</b> divide the pitch by the circumference, then take the inverse tangent. Use the same length unit for both.")
    grid([["Location", "Radius", "Pitch angle"],
          ["Hub edge, 0.10R", "12.70 mm", f"{p.root_pitch_deg:.2f}°"],
          ["Half span, 0.50R", "63.50 mm", "15.99°"],
          ["Tip, 1.00R", "127.00 mm", f"{p.tip_pitch_deg:.2f}°"]], [WIDTH - 220, 110, 110])
    section("Worked example at half span")
    eq(r"\beta=\arctan\left(\frac{114.3}{2\pi\times63.5}\right)=15.99^{\circ}")
    text("Air is not a solid screw thread, so the actual advance per revolution can differ from P. "
         "Constant geometric pitch also does not guarantee constant angle of attack, because the inflow angle varies with the operating condition.")
    text("Inside the root blend, the code limits pitch angle to 65°. At the benchmark embedded root (8.89 mm), it is 63.96°; "
         "the UI's root-pitch readout refers to the 12.70 mm hub edge, not that buried start.", "small")

    heading(7, "Reading chord and thickness")
    text("The blade's outline and twist are different distributions. Chord describes its width; pitch angle describes its rotation out of the disk plane. "
         "The program prescribes both rather than optimizing them for a chosen motor or mission.")
    figure("distributions", "Figure 3. Actual benchmark distributions from the current engine. The widest nominal section is at half span.")
    grid([["Radius / R", "Chord / D", "Chord at D = 254 mm"],
          ["0.07 (embedded root)", "0.027", "6.858 mm"],
          ["0.22 (transition)", "0.072", "18.288 mm"],
          ["0.50", "0.155", "39.370 mm"],
          ["0.75", "0.115", "29.210 mm"],
          ["0.96", "0.040", "10.160 mm"],
          ["0.99", "0.023", "5.842 mm"],
          ["1.00 (nominal tip section)", "0.015", "3.810 mm"]], [WIDTH - 280, 100, 180])
    text("A shape-preserving cubic interpolator (PCHIP) connects these design anchors [4]. "
         "The transition location is derived from the root proportions; it is 0.22R for this benchmark.")
    section("Thickness ratio is not an absolute thickness")
    text("The embedded root starts at 13% chord, decreases to 12% at the transition, and then tapers to 8.5% at the tip. "
         "Multiply the local chord by the local ratio to estimate maximum section thickness. The exact surface normal geometry sets the detailed value.")
    text("The final CAD tip is rounded to an apex over a short cap region. The nominal chord at 1.00R is a construction section, not a flat exposed 3.810 mm end face.", "small")

    heading(8, "What a NACA section means")
    text("An <b>airfoil</b> is a blade sliced at one radius. A NACA four-digit section combines a curved mean line with a thickness distribution [1]. "
         "The familiar name 4412 means 4% maximum camber, located at 40% chord, and 12% maximum thickness.")
    figure("airfoil", "Figure 4. A 12% benchmark section at the transition. The camber line is the midpoint between the two surfaces; the chord is the straight LE-to-TE reference.")
    grid([["Feature", "What to notice"],
          ["Leading edge (LE)", "The rounded nose meets the incoming relative airflow."],
          ["Trailing edge (TE)", "The two surfaces meet at the closed rear edge."],
          ["Camber line", "Its maximum ordinate is 0.04 times the chord, at u = 0.40."],
          ["Quarter-chord reference", "Subtracting 0.25 from normalized x moves the coordinate origin; it does not change the airfoil shape."]], [125, WIDTH - 125])
    section("The program uses a family of related sections")
    text("The camber parameters stay at m = 0.04 and p = 0.40, while thickness changes along the span. "
         "It is more precise to call the result a NACA 44-series-inspired varying-thickness blade than a constant 4412 section everywhere.")
    section("What camber tells you - and what it does not")
    text("Camber changes the lift curve and zero-lift angle. It can produce lift at zero geometric angle of attack. "
         "It does not guarantee attached flow: Reynolds number, roughness, incidence, transition and operating conditions still matter. "
         "The section geometry alone is not a measured lift/drag polar.")

    heading(9, "Build a section with equations")
    text("All coordinates on this page are divided by the local chord. Let u run from 0 at the nose to 1 at the trailing edge. "
         "The thickness function gives <b>half</b> the distance between the surfaces, measured normal to the camber line.")
    eq(r"y_t=5t\left(0.2969\sqrt{u}-0.1260u-0.3516u^2+0.2843u^3-0.1036u^4\right)", size=13)
    text("The final coefficient is the program's closed-trailing-edge modification. The code explicitly sets the endpoint thickness to zero. "
         "A finite-thickness trailing edge can also form valid CAD when capped appropriately; it is not inherently non-manifold.")
    section("Mean camber: one expression on each side of p")
    text("The prime in y'c means the derivative: the local slope of the mean camber line.", "small")
    eq(r"u<p:\quad y_c=\frac{m}{p^2}(2pu-u^2),\qquad y'_c=\frac{2m}{p^2}(p-u)")
    eq(r"u\geq p:\quad y_c=\frac{m}{(1-p)^2}(1-2p+2pu-u^2)", size=13)
    eq(r"u\geq p:\quad y'_c=\frac{2m}{(1-p)^2}(p-u),\qquad \theta_c=\arctan(y'_c)")
    text("The slope angle tells us how to offset the upper and lower surfaces perpendicular to the curved mean line. "
         "The subtraction of 0.25 below centres the x coordinate at quarter-chord.")
    eq(r"\hat{x}_u=u-y_t\sin\theta_c-0.25,\qquad \hat{y}_u=y_c+y_t\cos\theta_c", size=13)
    eq(r"\hat{x}_l=u+y_t\sin\theta_c-0.25,\qquad \hat{y}_l=y_c-y_t\cos\theta_c", size=13)
    section("Sampling is about resolving curvature")
    eq(r"u_k=\frac{1-\cos\vartheta_k}{2},\qquad 0\leq\vartheta_k\leq\pi")
    text("Cosine spacing puts more points near both ends than uniform chordwise spacing. "
         "With 60 sample points per surface, 15 lie in the first 15% chord. The joined outline contains 118 unique points before an optional repeated closing point.", "small")

    heading(10, "From 2D section to 3D station")
    text("Each section is scaled by chord and pitched at a chosen radius. The <b>production CAD uses planar radial sections</b>: "
         "every point of the unrotated section has the same Y coordinate. The source also contains a cylindrical-wrap helper, but that helper is not the active section-building path.")
    figure("stations", "Figure 5. Selected actual analytical stations before CAD tip remapping. Each closed curve is a rib; the loft fills the surface between ribs.")
    eq(r"x_s=c\hat{x},\qquad y_s=c\hat{y}")
    eq(r"s=-x_s\cos\beta-y_s\sin\beta+\operatorname{sweep}(\xi)")
    eq(r"z_0=-x_s\sin\beta+y_s\cos\beta,\qquad (X,Y,Z)=(s,r,z)")
    text("The minus signs orient the leading edge toward +X and +Z for the chosen CW convention. "
         "A small prescribed tangential sweep changes X. In the buried root region, an axial centring offset changes z from z0 so the section fits between the hub faces.")
    text("Here s is the tangential coordinate, z0 the axial coordinate before centring, and z the final axial coordinate; all three are in millimetres.", "small")
    section("How the radial ribs are chosen")
    text("The default has 22 base stations. Root, hub edge, transition and 0.96R/0.99R/1.00R are explicit anchors. "
         "Additional stations are chosen from cosine-spaced candidates by filling the largest gaps. These are geometry samples, not CFD mesh cells.")
    text("The CAD generator slightly compresses the station Y positions to reserve the terminal cap region. "
         "The analytical distributions and station drawing describe the design before that final cap construction.", "small")

    heading(11, "A hub that contains the root")
    text("The hub is the central mounting body. Its bore must remain open after blades are joined to it. "
         "The current app derives these sizes; it does not offer independent bore or hub controls.")
    figure("hub", "Figure 6. Axial section of the benchmark hub. The open shaft bore runs through its full thickness; the drawing omits small edge chamfers.")
    eq(r"d_h=\max(12\ \mathrm{mm},0.10D),\qquad d_b=0.45d_h")
    eq(r"r_{\mathrm{embed}}=0.70(d_h/2)")
    eq(r"H=\max\left(0.036D,\ 1.15\times2z_{\mathrm{extent}}\right)")
    text("The extent is the largest absolute axial coordinate found while sampling the buried neck from the embedded root to the hub edge. "
         "Twice that extent gives a symmetric envelope; the factor 1.15 adds clearance. The other term keeps a minimum proportional hub thickness.")
    grid([["For the benchmark", "Calculation", "Result"],
          ["Hub diameter", "0.10 × 254", "25.400 mm"],
          ["Bore diameter", "0.45 × 25.4", "11.430 mm"],
          ["Hub thickness", f"max(9.144, {1.15 * 2 * engine.root_axial_extent_mm():.3f})", f"{p.hub_length_mm:.3f} mm"]],
         [160, WIDTH - 265, 105])
    text("The bore is cut <b>after</b> all blade unions. This removes any blade material that would otherwise obstruct the mounting hole. "
         "A rim chamfer and a root fillet are attempted only when the kernel can make a valid result; they are not guaranteed features.", "small")

    heading(12, "How the CAD solid is built")
    text("A boundary representation (B-Rep) stores surfaces, edges, vertices and their connections. "
         "The on-screen triangle mesh is a rendering of that solid; the STEP file stores the CAD representation [5, 6].")
    grid([["Stage", "Construction and reason"],
          ["1. Close each rib", "Fit one spline from TE to LE on the upper surface and one from LE back to TE on the lower. Join the two edges into a valid closed wire."],
          ["2. Reserve the cap", "Compress the base-station radial positions slightly. Reserve 0.008R for the rounded terminal region, rather than leave an exposed flat tip face."],
          ["3. Loft the blade", "Use 22 base wires, five progressively smaller cap wires and a terminal apex. The loft requests degree at most 3 and preserves consistent wire ordering."],
          ["4. Create the hub", "Build a cylinder centred about Z = 0. Try a small rim chamfer, retaining the original hub if finishing fails."],
          ["5. Repeat and fuse", "Rotate copies about Z, then boolean-fuse them to the hub. For B blades the angular spacing is 360/B degrees."],
          ["6. Finish and bore", "Try a root fillet, cut the shaft bore through the joined model, clean the result and validate the final connected solid."]], [105, WIDTH - 105])
    section("Two operations that sound similar")
    text("<b>A loft</b> creates a surface or solid through a series of section wires. <b>A boolean union</b> combines overlapping volumes. "
         "The buried root provides overlap so a blade can connect to the hub; merely touching at a point or edge would not be a reliable volume connection.")
    section("Why the tip has extra wires")
    text("The cap sections shrink with a cosine factor and advance with a sine factor at construction angles of 25°, 45°, 65°, 80° and 88°, "
         "then close at a vertex. This is an ellipsoidal-style loft closure, not a separately attached sphere. "
         "The maximum-degree request is not a proof of global C² continuity across every face or sharp edge.")
    text("For two blades, the copies are 180° apart. Three blades are 120° apart; four are 90° apart. "
         "Changing blade count repeats the prescribed blade rather than designing a new optimum blade for that count.", "small")

    heading(13, "What watertight really checks")
    text("A watertight CAD solid has a closed boundary enclosing positive volume. In this program, validation asks about connectivity and topology, "
         "then repeats the checks after importing the exported STEP file. It does not ask whether the blade will be efficient or strong.")
    grid([["Check", "Plain-language meaning"],
          ["One connected solid", "All blades and the hub belong to a single material volume."],
          ["One closed shell", "The outer boundary encloses the material without an open gap."],
          ["Kernel validity", "Both the shape API and OpenCascade's B-Rep analyzer accept the topology."],
          ["Positive volume", "The result is a material body, not only a surface or wire."],
          ["Edge incidence", "Ordinary boundary edges connect to two faces. A permitted zero-length pole edge is handled separately."],
          ["STEP readback", "The temporary exported file can be reimported and passes the same solid checks."],
          ["Bore and hub audit", "The benchmark verification script additionally probes bore clearance, hub faces, embedded roots and tip compactness."]], [125, WIDTH - 125])
    section("Why the save operation uses a temporary file")
    text("Export is completed beside the destination, checked, and then moved into place with an atomic replacement. "
         "If writing or readback fails, a half-written file should not replace the selected output. "
         "The app serializes CAD work and keeps Tk operations on the main thread.")
    section("A clear division of evidence")
    text("<b>Preview:</b> helps you see shape and orientation. <b>Topology audit:</b> establishes a valid connected geometric boundary. "
         "<b>CFD or experiment:</b> estimates or measures performance. <b>Structural analysis and testing:</b> address loads, materials and failure. "
         "Passing one does not automatically pass the others.")
    text("The extra benchmark audit is available as: <font name='PlexMono'>python verify_geometry.py</font>. "
         "It writes its generated STEP and JSON report under work/ by default.", "small")

    heading(14, "The airflow seen by a blade")
    text("A blade section moves tangentially, while air also moves through the propeller disk. "
         "The section responds to the <b>relative airflow</b>, not simply to the air's speed relative to the room.")
    eq(r"\Omega=\frac{2\pi\,\mathrm{RPM}}{60},\qquad V_{\mathrm{rot}}=\Omega r")
    section("Pitch angle and angle of attack are different")
    eq(r"\alpha=\beta-\phi")
    text("Beta is built into the geometry. Phi describes the effective inflow direction. Alpha is the difference between the chord direction and that inflow. "
         "For example, a 16° pitch angle with 10° inflow gives 6° angle of attack. The 10° is an illustrative operating condition, not a fixed value in the CAD model.")
    section("At the benchmark speed of 6,000 RPM")
    grid([["Quantity", "Calculation", "Result"],
          ["Turns per second", "6,000 / 60", "100 1/s"],
          ["Angular speed", "2 pi × 100", "628.32 rad/s"],
          ["Half-span tangential speed", "628.32 × 0.0635", "39.90 m/s"],
          ["Tip tangential speed", "628.32 × 0.127", "79.80 m/s"]], [180, WIDTH - 285, 105])
    text("The tip travels faster because it covers a larger circumference in the same revolution. "
         "That is one reason blade sections are twisted. The helical-pitch rule supplies a geometric relationship; actual aerodynamic loading still depends on inflow and the section polar.")
    section("Reynolds number explains why scale matters")
    eq(r"Re=\frac{\rho V_{\mathrm{rel}}c}{\mu}")
    text("Reynolds number compares inertial and viscous effects. Here mu is dynamic viscosity in kg/(m s). "
         "Speed and chord change across the blade, so Reynolds number changes too. UIUC experiments document these effects for small propellers [2, 3]. "
         "This app's simple lift/drag law is not a Reynolds-dependent lookup table.")

    heading(15, "How the thrust estimate works")
    text("The app uses a simplified static blade-element/momentum calculation. Think of the disk as narrow radial strips. "
         "For each strip, estimate the local inflow and section force, then add the strips. Static means no imposed forward flight speed.")
    eq(r"\sigma=\frac{Bc}{2\pi r},\qquad \alpha=\beta-\phi")
    text("Solidity sigma is the total blade chord divided by the circumference at that radius. "
         "The code assumes a zero-lift angle of -3.8°, applies a lift-slope factor of 0.95, limits lift, and estimates drag from lift:")
    eq(r"C_L=\mathrm{clip}\!\left[2\pi(0.95)(\alpha-\alpha_0),-0.5,1.35\right]", size=13)
    eq(r"\alpha_0=-3.8^{\circ},\qquad C_D=0.012+0.045C_L^2")
    text("Clip means keep the result within the two stated limits. The tip-loss factor F reduces the idealized loading near the blade ends. "
         "Inflow is updated through a relaxed annular balance:")
    eq(r"4F\sin^2\phi=\sigma(C_L\cos\phi-C_D\sin\phi)")
    text("The implementation samples 60 uniformly spaced radii from the hub edge to 0.995R and performs 30 relaxed inflow updates per radius. "
         "It clips intermediate values for numerical stability; it does not stop on a measured convergence tolerance.")
    eq(r"dT=B\,\frac{1}{2}\rho V_{\mathrm{eff}}^2c(C_L\cos\phi-C_D\sin\phi)\,dr", size=13)
    eq(r"V_{\mathrm{eff}}=\frac{\Omega r}{\cos\phi},\qquad T\approx\sum dT")
    text("<b>Read the force equation:</b> dynamic pressure times chord times strip width gives a force scale; "
         "the bracket projects lift and drag along the shaft; B includes all blades. "
         "The default density is 1.225 kg/m³. Geometry uses millimetres, but this calculation converts lengths to metres.", "small")

    heading(16, "A worked section, end to end")
    text("Take the benchmark section at half span, then locate one point on its upper surface. "
         "This example connects the symbol table, airfoil formula and 3D placement; it is not a new design rule.")
    section("1. Locate the section")
    eq(r"\xi=0.50,\quad r=0.50(127)=63.5\ \mathrm{mm},\quad c=0.155(254)=39.37\ \mathrm{mm}", size=12.5)
    text("At this radius the current engine gives beta = 15.9859° and thickness ratio t = 0.1097075. "
         "The local sweep is 1.906568 mm, and the root-centring correction has already faded to zero.")
    section("2. Evaluate the airfoil at u = 0.40")
    text("This is the maximum-camber position: the camber-line slope is zero, so theta-c is zero. "
         "Substituting into the thickness polynomial and upper-surface formula gives:")
    eq(r"y_c=0.04,\quad y_t=0.05302333,\quad \hat{x}_u=0.40-0.25=0.15", size=13)
    eq(r"\hat{y}_u=0.04+0.05302333=0.09302333")
    section("3. Multiply by the local chord")
    eq(r"x_s=39.37(0.15)=5.9055\ \mathrm{mm}")
    eq(r"y_s=39.37(0.09302333)=3.662329\ \mathrm{mm}")
    section("4. Pitch, sweep and place the point")
    eq(r"X=-5.9055\cos\beta-3.662329\sin\beta+1.906568")
    eq(r"Y=63.5,\qquad Z=-5.9055\sin\beta+3.662329\cos\beta")
    text("<b>Result:</b> upper-surface point (X, Y, Z) = <b>(-4.779171, 63.500000, 1.894326) mm</b>. "
         "The matching lower-surface point at the same u is (-3.629358, 63.500000, -2.119280) mm.")
    text("Do not confuse this point's 4.175057 mm surface separation with the section's maximum thickness. "
         "It is one local chordwise sample. The loft fits the complete closed outline at many radii.", "small")

    heading(17, "Interpret the numbers honestly")
    text("For the default 254 mm / 114.3 mm / two-blade design at 6,000 RPM and the default air density, "
         "the current estimator returns the values below. These are reproducible outputs of its assumed model, not a measured rating.")
    grid([["Readout", "Benchmark value", "Meaning"],
          ["Estimated static thrust", f"{thrust:.4f} N", "Axial force predicted by this estimator."],
          ["Grams-force equivalent", f"{gf:.1f} gf", "A force conversion, not the propeller's mass."],
          ["Pitch / diameter", f"{p.pitch_to_diameter_ratio:.3f}", "A geometry ratio, not efficiency."],
          ["Swept disk area", f"{p.disk_area_m2:.5f} m²", "Area enclosed by the nominal tip radius."]], [160, 115, WIDTH - 275])
    eq(r"1\ \mathrm{gf}=0.00980665\ \mathrm{N},\qquad 6.377726\ \mathrm{N}\approx650.35\ \mathrm{gf}", size=13)
    section("A coefficient helps compare propellers")
    eq(r"C_T=\frac{T}{\rho n^2D^4},\qquad n=\mathrm{RPM}/60")
    ct = thrust / (1.225 * 100 ** 2 * .254 ** 4)
    text(f"With diameter in metres and n = 100 revolutions/s, the estimated static thrust coefficient is {ct:.4f}. "
         "Use the same definition, propeller geometry, rotation speed and test condition when comparing data. "
         "A coefficient computed from an estimate remains an estimate [2].")
    section("What this estimator leaves out")
    text("It has no measured Reynolds-dependent polar table, induced-swirl solution, torque/power prediction, "
         "forward-flight input, motor/ESC model, acoustic model or structural calculation. "
         "Its lift limit is a numerical approximation to stall behaviour, not a complete stall model.")
    text("The 6.38 N result is useful for a first consistency check. The repository does not supply a matched test report proving this exact CAD geometry agrees with UIUC measurements. "
         "UIUC data are a reference for how to test and compare, rather than certification of this generated blade [2, 3].")

    heading(18, "Taking the model into CAD or CFD")
    section("Start by checking scale and axes")
    text("Import the STEP into your downstream tool and measure a known dimension such as the 25.4 mm hub diameter or 11.43 mm bore. "
         "Confirm the shaft axis, upstream +Z direction and intended CW motion. A scale or sign error can overwhelm a sophisticated calculation.")
    section("The solid and the fluid are different regions")
    text("The exported propeller is the <b>solid</b>. A CFD airflow domain is a surrounding fluid volume with the propeller volume removed. "
         "Its outer boundaries, rotating region and mesh must be created in the CFD tool. The app does not export that fluid setup.")
    grid([["Step", "What you decide downstream"],
          ["Operating condition", "Rotation speed, static or forward flow, density, viscosity and reference frame."],
          ["Fluid domain", "Extent of upstream, downstream and lateral regions; demonstrate domain independence rather than assume one universal size."],
          ["Rotor treatment", "A rotating-reference-frame approximation or a transient sliding-mesh setup, depending on the question."],
          ["Mesh", "Resolve the leading edge, closed trailing edge, root, tip and wake; use appropriate wall treatment."],
          ["Evidence", "Check residuals, force history, mass balance, mesh/time-step independence and comparison with relevant data."]], [112, WIDTH - 112])
    section("Compare the quantity you actually calculated")
    text("Integrate pressure and viscous forces on the blade/hub surfaces, then project the result along the chosen shaft direction. "
         "Compare a static CFD condition with the static estimator; do not compare it directly with a forward-flight operating point.")
    section("For manufacturing or structural work")
    text("A STEP shape contains geometry, not a material specification, process tolerance or balance result. "
         "Mounting fit, finite edge thickness, strength, vibration and manufacturing constraints need their own assessment. "
         "The application's topology audit establishes geometry integrity and leaves those separate engineering questions open.")

    heading(19, "Questions, checks and practice")
    for question, answer in [
        ("Why does the blade flatten toward the tip?", "The circumference grows with radius while geometric pitch stays fixed. The ratio P/(2 pi r) decreases, so the helix angle decreases."),
        ("Is the root-pitch readout the angle at the very first rib?", "No. It is evaluated at the hub edge (12.70 mm here). The buried starting rib is at 8.89 mm and has a larger angle."),
        ("Why is the bore not editable?", "It is derived as 45% of hub diameter in the current model. Changing diameter changes the derived mounting sizes; this is not an independent hardware selection."),
        ("Why did changing units not change the preview?", "A correct unit conversion describes the same dimensions. The canonical lengths remain in millimetres."),
        ("Why is an old preview still present after an edit?", "Edits update the readouts first. Use Update preview to rebuild the solid; the caption describes the model currently shown."),
        ("Why can export fail with positive dimensions?", "Positive inputs pass the first checks, but unusual shapes can still fail a loft, union or topology check. Read the error and the project's propeller_error.log; do not treat a partially generated file as a successful export."),
    ]:
        section(question)
        text(answer)
    section("Try these before reading the answers")
    text("<b>A.</b> Convert a 9 inch diameter to mm and find its radius.")
    text("<b>B.</b> At r = 127 mm, double the benchmark pitch and calculate beta.")
    text("<b>C.</b> If beta = 20° and phi = 12°, find alpha.")
    text("<b>D.</b> How far apart are five blades?")
    text("<b>Answers:</b> A: D = 228.6 mm, R = 114.3 mm. B: arctan(228.6/(2 pi × 127)) = 15.99°, "
         "which is not exactly twice the original angle. C: 8°. D: 360/5 = 72°.", "small")

    heading(20, "Sources and a reproducible guide")
    text("The equations and examples were checked against this project's implementation. "
         "The external sources explain the background or APIs; they do not certify the generated propeller.")
    references = [
        ("1. Jacobs, Ward and Pinkerton (1933). NACA Report 460.",
         "The Characteristics of 78 Related Airfoil Sections from Tests in the Variable-Density Wind Tunnel. Background for NACA four-digit shape definitions.",
         "https://ntrs.nasa.gov/citations/19930091108"),
        ("2. UIUC Propeller Data Site.",
         "Wind-tunnel propeller measurements and coefficient definitions. Use a matching geometry and operating condition for any comparison.",
         "https://m-selig.ae.illinois.edu/props/propDB.html"),
        ("3. Brandt and Selig (2011), AIAA 2011-1255.",
         "Propeller Performance Data at Low Reynolds Numbers. Primary experimental context for small-propeller performance.",
         "https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf"),
        ("4. SciPy PchipInterpolator documentation.",
         "The shape-preserving piecewise cubic interpolator used for the prescribed chord anchors.",
         "https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html"),
        ("5. CadQuery import/export documentation.",
         "STEP import and export API reference.",
         "https://cadquery.readthedocs.io/en/latest/importexport.html"),
        ("6. OpenCascade BRepOffsetAPI_ThruSections reference.",
         "Loft construction from ordered wires and vertices; API settings do not alone prove global smoothness.",
         "https://dev.opencascade.org/doc/refman/html/class_b_rep_offset_a_p_i___thru_sections.html"),
    ]
    for title, description, url in references:
        text(f"<b>{title}</b> {description} "
             f'<link href="{url}" color="#1B6C80">Open source</link>', "small")
    section("Find the implementation")
    grid([["Source", "What to inspect"],
          ["core/math_engine.py", "Parameters, profiles, stations, planar placement and static thrust estimator."],
          ["core/cad_generator.py", "Closed wires, cap, hub, boolean operations, validation and atomic STEP export."],
          ["verify_geometry.py", "Round-trip benchmark, bore, hub and distal-tip checks."],
          ["ui/layout.py", "Native controls and disclosures referred to on page 2."]], [175, WIDTH - 175])
    section("Rebuild without opening the app")
    text("venv\\Scripts\\python.exe scripts\\generate_study_pdf.py", "code")
    text("On Unix/macOS use the local environment's Python instead. The script reads the existing engine, "
         "regenerates diagrams and embeds bundled Plex fonts; mathematics is drawn as PDF vector paths. "
         "It uses the project's existing dependencies and does not install fonts or modify application logic.", "small")

    glyphs = verify_text_glyphs()
    doc.build(story, onFirstPage=doc.decorate, onLaterPages=doc.decorate,
              canvasmaker=partial(canvas.Canvas, invariant=1, initialFontName="Plex"))
    actual_pages = max(row["page"] for row in doc.chapter_pages)
    positions_correct = [row["page"] for row in doc.chapter_pages] == list(range(1, page_count + 1))
    report = {**glyphs, "expected_pages": page_count, "chapter_pages": doc.chapter_pages,
              "chapters_on_expected_pages": positions_correct,
              "benchmark": {"diameter_mm": p.diameter_mm, "pitch_mm": p.pitch_mm,
                            "blades": p.num_blades, "hub_height_mm": p.hub_length_mm,
                            "root_pitch_deg": p.root_pitch_deg, "thrust_n": thrust},
              "output": str(Path(output_path).resolve()), "bytes": Path(output_path).stat().st_size}
    report_path = ROOT / "work" / "study-build.report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not positions_correct:
        raise RuntimeError(f"Chapter layout overflow: inspect {report_path}; last heading at page {actual_pages}")
    print(f"Built {output_path}: {page_count} pages; {glyphs['vector_equations_and_symbols']} vector equations/symbols; no missing text glyphs.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "Study.pdf")
    build_study_pdf(parser.parse_args().output)
