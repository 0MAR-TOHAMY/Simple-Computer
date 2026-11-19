"""Generate the simple computer as wired blocks (subcircuits) for Logisim Evolution 5.0.0.

Usage: python gen2.py <output.circ>
Each stage is its own subcircuit with real wires inside; the main circuit wires
the blocks together as a classic bus-based datapath. Wires are placed by route.py and
checked for splits and shorts before the file is written.
"""
import os, subprocess, sys
from xml.sax.saxutils import escape
from route import Board, check, GRID, split_wires

HERE = os.path.dirname(os.path.abspath(__file__))
JAR = os.environ.get("LOGISIM_JAR", "logisim-evolution-5.0.0-all.jar")  # path to the Logisim Evolution jar
CP = JAR + ";" + HERE
OUT = sys.argv[1]

LIB = {"Pin": 0, "Tunnel": 0, "Constant": 0, "Clock": 0, "Splitter": 0,
       "AND Gate": 1, "OR Gate": 1, "XOR Gate": 1, "NOT Gate": 1,
       "Multiplexer": 2, "Decoder": 2,
       "Adder": 3, "Comparator": 3, "Shifter": 3,
       "Register": 4, "RAM": 4, "ROM": 4}

# ------------------------------------------------------------------ program and control
OPS = {"HALT": 0, "MOV": 1, "ADD": 2, "SUB": 3, "AND": 4, "OR": 5, "XOR": 6, "NOT": 7,
       "INC": 8, "JMP": 9, "SHL": 10, "SHR": 11, "LDI": 12, "LD": 13, "ST": 14, "BRZ": 15}

def ins(op, dr=0, sa=0, sb=0, imm=None):
    w = OPS[op] << 12 | dr << 10 | sa << 8
    w |= (imm & 0xFF) if imm is not None else sb << 6
    return w

PROGRAM = [
    ins("LDI", dr=0, imm=5), ins("LDI", dr=1, imm=0), ins("LDI", dr=2, imm=1),
    ins("ADD", dr=1, sa=1, sb=0), ins("SUB", dr=0, sa=0, sb=2), ins("BRZ", sa=0, imm=7), ins("JMP", imm=3),
    ins("LDI", dr=3, imm=0x10), ins("ST", sa=3, sb=1), ins("LD", dr=2, sa=3), ins("SHL", dr=2, sb=2),
    ins("XOR", dr=0, sa=2, sb=1), ins("HALT"),
]
RW, MF, MB, MD, MW, PL, JB, HLT = 1 << 9, 1 << 6, 1 << 7, 1 << 8, 1 << 10, 1 << 11, 1 << 12, 1 << 13
def G(s2, s1, s0, cin): return s2 << 3 | s1 << 2 | s0 << 1 | cin
def H(h): return h << 4
CONTROL = {"HALT": HLT, "MOV": G(0, 0, 0, 0) | RW, "ADD": G(0, 0, 1, 0) | RW, "SUB": G(0, 1, 0, 1) | RW,
           "AND": G(1, 0, 0, 0) | RW, "OR": G(1, 0, 1, 0) | RW, "XOR": G(1, 1, 0, 0) | RW, "NOT": G(1, 1, 1, 0) | RW,
           "INC": G(0, 0, 0, 1) | RW, "JMP": PL | JB, "SHL": H(2) | MF | RW, "SHR": H(1) | MF | RW,
           "LDI": MB | MF | RW, "LD": MD | RW, "ST": MW, "BRZ": PL}
CONTROL_ROM = [CONTROL[n] for n, _ in sorted(OPS.items(), key=lambda kv: kv[1])]

def rom(addr, data, words):
    return f"addr/data: {addr} {data}\n" + " ".join(format(w, "x") for w in words) + "\n"

def splitter(incoming, groups):
    a = {"incoming": str(incoming), "fanout": str(len(groups))}
    for gi, bits in enumerate(groups):
        for b in bits:
            a[f"bit{b}"] = str(gi)
    return a

# ------------------------------------------------------------------ geometry
GEO = {}
def spec(f, attrs):
    return "|".join([f] + [f"{k}={v}" for k, v in attrs.items() if k not in ("label", "contents", "radix")])

def probe(specs):
    need = sorted(set(specs) - set(GEO))
    if not need:
        return
    res = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", CP, "Probe"], input="\n".join(need) + "\n",
                         capture_output=True, text=True, cwd=HERE)
    if res.returncode:
        sys.exit(res.stderr)
    cur = None
    for line in res.stdout.splitlines():
        p = line.split()
        if line.startswith("SPEC "):
            cur = line[5:]
            GEO[cur] = {"ports": {}}
        elif p and p[0] == "bounds":
            GEO[cur]["bounds"] = tuple(map(int, p[1:5]))
        elif p and p[0] == "port":
            GEO[cur]["ports"][int(p[1])] = (int(p[2]), int(p[3]), int(p[4]))

SUBGEO = {}
PORTDUMP = []
EXPORT = {}  # circuit name -> {"bounds":..., "ports": {label: (dx, dy, w)}}

# ------------------------------------------------------------------ circuit model
class Ckt:
    def __init__(self, name, title=None, fill="#ffffff"):
        self.name, self.items, self.texts = name, [], []
        self.title, self.fill = title or name, fill

    def appearance(self):
        """Custom block look: coloured box, title, named ports 30 px apart."""
        ins = [i for i in self.items if i.get("pin") == "in"]
        outs = [i for i in self.items if i.get("pin") == "out"]
        SP, TOP, W = 30, 50, 200
        n = max(len(ins), len(outs))
        H = TOP + (n - 1) * SP + 30
        X0, Y0 = 50, 50
        e = [f'      <rect fill="{self.fill}" height="{H}" rx="8" ry="8" stroke="#3b4252" stroke-width="2" width="{W}" x="{X0}" y="{Y0}"/>',
             f'      <text dominant-baseline="central" font-family="SansSerif" font-size="15" font-weight="bold" text-anchor="middle" x="{X0 + W // 2}" y="{Y0 + 20}">{escape(self.title)}</text>']
        for k, it in enumerate(ins):
            y = Y0 + TOP + k * SP
            px, py = it["at"]
            e.append(f'      <circ-port dir="in" pin="{px},{py}" x="{X0}" y="{y}"/>')
            e.append(f'      <text dominant-baseline="central" font-family="SansSerif" font-size="12" text-anchor="start" x="{X0 + 8}" y="{y}">{escape(it["attrs"]["label"])}</text>')
        for k, it in enumerate(outs):
            y = Y0 + TOP + k * SP
            px, py = it["at"]
            e.append(f'      <circ-port dir="out" pin="{px},{py}" x="{X0 + W}" y="{y}"/>')
            e.append(f'      <text dominant-baseline="central" font-family="SansSerif" font-size="12" text-anchor="end" x="{X0 + W - 8}" y="{y}">{escape(it["attrs"]["label"].replace("_OUT", ""))}</text>')
        e.append(f'      <circ-anchor facing="east" x="{X0}" y="{Y0}"/>')
        return "    <appear>\n" + "\n".join(e) + "\n    </appear>"

    def comp(self, f, attrs, x, y, conn):
        """Place a built-in component so its bounds' top-left sits near (x, y)."""
        self.items.append(dict(kind="std", f=f, attrs=attrs, tl=(x, y), conn=conn))

    def sub(self, name, x, y, conn):
        self.items.append(dict(kind="sub", f=name, attrs={}, tl=(x, y), conn=conn))

    def pin_in(self, label, width, x, y):
        self.items.append(dict(kind="std", f="Pin", attrs={"type": "input", "facing": "east", "width": str(width),
                                                           "label": label}, at=(x, y), conn={0: label}, pin="in"))

    def pin_out(self, label, width, x, y, net=None, radix=None):
        a = {"type": "output", "facing": "west", "width": str(width), "label": label}
        if radix:
            a["radix"] = radix
        self.items.append(dict(kind="std", f="Pin", attrs=a, at=(x, y), conn={0: net or label}, pin="out"))

    def text(self, s, x, y, size=18):
        self.texts.append((s, x, y, size))

    def geometry(self, it):
        if it["kind"] == "sub":
            g = SUBGEO[it["f"]]
            return g["bounds"], {lab: v for lab, v in g["ports"].items()}
        g = GEO[spec(it["f"], it["attrs"])]
        return g["bounds"], g["ports"]

    def build(self):
        probe([spec(i["f"], i["attrs"]) for i in self.items if i["kind"] == "std"])
        placed = []
        xml = []
        for it in self.items:
            (bx, by, bw, bh), ports = self.geometry(it)
            if "at" in it:
                lx, ly = it["at"]
            else:
                lx = round((it["tl"][0] - bx) / GRID) * GRID
                ly = round((it["tl"][1] - by) / GRID) * GRID
            it["loc"] = (lx, ly)
            pl = []
            for key, net in it["conn"].items():
                dx, dy, _w = ports[key]
                pl.append((net, lx + dx, ly + dy, outward(it, (bx, by, bw, bh), (dx, dy))))
            for key, (dx, dy, _w) in ports.items():
                if key not in it["conn"]:  # unused port: keep every wire off it
                    pl.append((f"_unused_{len(placed)}_{key}", lx + dx, ly + dy, None))
            placed.append(((lx + bx, ly + by, bw, bh), pl))
            xml.append(comp_xml(it))
        order = None
        for attempt in range(25):
            board = Board()
            nets = {}
            for body, pl in placed:
                board.add_body(*body)
            for body, pl in placed:
                for net, px, py, d in pl:
                    cell = board.add_port(net, px, py, d)
                    nets.setdefault(net, []).append((cell, d))
            if order is None:
                order = [n for n, t in sorted(nets.items(), key=lambda kv: -len(kv[1])) if len(t) > 1]
            try:
                for net in order:
                    board.route(net, nets[net])
                break
            except RuntimeError as e:
                print(f"  {self.name} try {attempt + 1}: {e}", flush=True)
                bad = str(e).split()[4]
                order.remove(bad)
                order.insert(0, bad)
        else:
            sys.exit(f"{self.name}: routing failed")
        PORTDUMP.extend(f"{self.name}|{n}|{p[0]}|{p[1]}" for n, p in board.ports)
        board.wires = split_wires(board.wires, board.ports)
        problems = check(board.wires, board.ports)
        if problems:
            sys.exit(f"{self.name}: " + "; ".join(problems))
        for _, a, b in board.wires:
            xml.append(f'    <wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>')
        EXPORT[self.name] = {
            "items": [{"f": it["f"], "kind": it["kind"], "loc": list(it["loc"]),
                       "attrs": {k: v for k, v in it["attrs"].items() if k != "contents"},
                       "body": list(body),
                       "ports": [[net, x, y] for net, x, y, d in pl if not net.startswith("_unused")],
                       "conn": {str(k): v for k, v in it["conn"].items()}}
                      for it, (body, pl) in zip(self.items, placed)],
            "wires": [[n, a[0], a[1], b[0], b[1]] for n, a, b in board.wires],
            "texts": [[s, x, y, size] for s, x, y, size in self.texts],
        }
        for s, x, y, size in self.texts:
            xml.append(f'    <comp lib="5" loc="({x},{y})" name="Text">\n{attr("text", s)}\n'
                       f'{attr("font", f"SansSerif bold {size}")}\n{attr("halign", "left")}\n    </comp>')
        print(f"{self.name}: {len(self.items)} parts, {len(nets)} nets, {len(board.wires)} wires, {attempt + 1} tries, ok")
        appear = self.appearance() + "\n" if self.name != "main" else ""
        return (f'  <circuit name="{self.name}">\n    <a name="circuit" val="{self.name}"/>\n' + appear
                + "\n".join(xml) + "\n  </circuit>")


def outward(it, bounds, port):
    bx, by, bw, bh = bounds
    dx, dy = port
    if it["f"] == "Splitter":
        return "W" if (dx, dy) == (0, 0) else "E"
    d = {"W": abs(dx - bx), "E": abs(bx + bw - dx), "N": abs(dy - by), "S": abs(by + bh - dy)}
    if min(d["W"], d["E"]) <= 2:
        return "W" if d["W"] <= d["E"] else "E"
    return min(d, key=d.get)


def attr(n, v):
    return f'      <a name="{n}" val="{escape(v, {chr(34): "&quot;"})}"/>'


def comp_xml(it):
    lx, ly = it["loc"]
    body = []
    for k, v in it["attrs"].items():
        if k == "contents":
            body.append(f'      <a name="contents">{escape(v)}</a>')
        else:
            body.append(attr(k, v))
    lib = "" if it["kind"] == "sub" else f' lib="{LIB[it["f"]]}"'
    return f'    <comp{lib} loc="({lx},{ly})" name="{it["f"]}">\n' + "\n".join(body) + "\n    </comp>"


# ------------------------------------------------------------------ blocks
W8 = "8"
def mux(sel, w=W8):
    return {"select": str(sel), "width": w, "enable": "false"}

fetch = Ckt("FETCH", "FETCH", "#dbeafe")
fetch.text("FETCH: PC, PC + 1, jump select, program memory", 60, 30)
fetch.pin_in("CLK", 1, 100, 120)
fetch.pin_in("RUN", 1, 100, 180)
fetch.pin_in("TAKEN", 1, 100, 300)
fetch.pin_in("TARGET", 8, 100, 360)
fetch.comp("Multiplexer", mux(1), 260, 300, {0: "PC_INC", 1: "TARGET", 2: "TAKEN", 3: "PC_NEXT"})
fetch.comp("Register", {"width": W8, "label": "PC"}, 400, 90, {0: "PC", 1: "PC_NEXT", 2: "CLK", 4: "RUN"})
fetch.comp("Constant", {"width": W8, "value": "0x1"}, 420, 470, {0: "ONE"})
fetch.comp("Constant", {"width": "1", "value": "0x0"}, 560, 400, {0: "ZERO"})
fetch.comp("Adder", {"width": W8}, 560, 450, {0: "PC", 1: "ONE", 2: "PC_INC", 3: "ZERO"})
fetch.comp("ROM", {"addrWidth": "8", "dataWidth": "16", "label": "Program", "contents": rom(8, 16, PROGRAM)},
           700, 90, {0: "PC", 1: "IR"})
fetch.pin_out("PC_OUT", 8, 1080, 140, net="PC")
fetch.pin_out("IR", 16, 1080, 220)

dec = Ckt("DECODE_CONTROL", "DECODE + CONTROL", "#fef3c7")
dec.text("DECODE + CONTROL: split the instruction, look up the control word, decide jumps", 60, 30)
dec.pin_in("IR", 16, 100, 140)
dec.pin_in("BUS_A", 8, 100, 700)
dec.comp("Splitter", splitter(16, [range(0, 8), range(8, 10), range(10, 12), range(12, 16)]), 200, 100,
         {0: "IR", 1: "IMM", 2: "SA", 3: "DR", 4: "OP"})
dec.comp("Splitter", splitter(8, [range(0, 6), range(6, 8)]), 380, 180, {0: "IMM", 2: "SB"})
dec.comp("ROM", {"addrWidth": "4", "dataWidth": "16", "label": "Control", "contents": rom(4, 16, CONTROL_ROM)},
         340, 280, {0: "OP", 1: "CW"})
dec.comp("Splitter", splitter(16, [range(0, 4), [4, 5], [6], [7], [8], [9], [10], [11], [12], [13], [14, 15]]),
         700, 230, {0: "CW", 1: "G", 2: "H", 3: "MF", 4: "MB", 5: "MD", 6: "RW", 7: "MW", 8: "PL", 9: "JB", 10: "HALT"})
dec.comp("NOT Gate", {"size": "20"}, 900, 520, {0: "RUN", 1: "HALT"})
dec.comp("Constant", {"width": W8, "value": "0x0"}, 200, 770, {0: "ZERO"})
dec.comp("Comparator", {"width": W8, "mode": "unsigned"}, 340, 690, {0: "BUS_A", 1: "ZERO", 3: "A_IS_ZERO"})
dec.comp("OR Gate", {"size": "30"}, 560, 700, {0: "JUMP_OK", 1: "JB", 2: "A_IS_ZERO"})
dec.comp("AND Gate", {"size": "30"}, 720, 640, {0: "TAKEN", 1: "PL", 2: "JUMP_OK"})
for i, (lab, w) in enumerate([("DR", 2), ("SA", 2), ("SB", 2), ("IMM", 8), ("G", 4), ("H", 2), ("MF", 1), ("MB", 1),
                              ("MD", 1), ("RW", 1), ("MW", 1), ("TAKEN", 1), ("RUN", 1), ("HALT", 1)]):
    dec.pin_out(lab, w, 1180, 100 + i * 50)

reg = Ckt("REGISTER_FILE", "REGISTER FILE", "#dcfce7")
reg.text("REGISTER FILE: destination decoder, load enables, R0-R3, read MUXes A and B", 60, 30)
reg.pin_in("CLK", 1, 100, 100)
reg.pin_in("BUS_D", 8, 100, 160)
reg.pin_in("DR", 2, 100, 400)
reg.pin_in("RW", 1, 100, 470)
reg.pin_in("SA", 2, 100, 760)
reg.pin_in("SB", 2, 100, 820)
reg.comp("Decoder", {"select": "2", "enable": "false"}, 200, 300, {0: "D0", 1: "D1", 2: "D2", 3: "D3", 4: "DR"})
for k in range(4):
    reg.comp("AND Gate", {"size": "30"}, 340, 220 + k * 90, {0: f"LOAD{k}", 1: f"D{k}", 2: "RW"})
for k in range(4):
    reg.comp("Register", {"width": W8, "label": f"R{k}"}, 520, 90 + k * 160,
             {0: f"R{k}", 1: "BUS_D", 2: "CLK", 4: f"LOAD{k}"})
reg.comp("Multiplexer", mux(2), 800, 300, {0: "R0", 1: "R1", 2: "R2", 3: "R3", 4: "SA", 5: "A_DATA"})
reg.comp("Multiplexer", mux(2), 800, 560, {0: "R0", 1: "R1", 2: "R2", 3: "R3", 4: "SB", 5: "B_DATA"})
reg.pin_out("A_DATA", 8, 1060, 330)
reg.pin_out("B_DATA", 8, 1060, 590)
for k in range(4):
    reg.pin_out(f"R{k}_OUT", 8, 1060, 760 + k * 50, net=f"R{k}")

alu = Ckt("ALU", "ALU", "#fce7f3")
alu.text("ALU: G = A + Y + Cin (arithmetic) or AND/OR/XOR/NOT (logic), S2 picks", 60, 30)
alu.pin_in("A", 8, 100, 120)
alu.pin_in("B", 8, 100, 300)
alu.pin_in("G", 4, 100, 620)
alu.comp("Splitter", splitter(4, [[0], [1, 2], [3]]), 180, 590, {0: "G", 1: "CI", 2: "S1S0", 3: "S2"})
alu.comp("Constant", {"width": W8, "value": "0x0"}, 230, 210, {0: "ZERO"})
alu.comp("NOT Gate", {"width": W8, "size": "20"}, 240, 340, {0: "NOT_B", 1: "B"})
alu.comp("Constant", {"width": W8, "value": "0xff"}, 230, 420, {0: "ONES"})
alu.comp("Multiplexer", mux(2), 400, 260, {0: "ZERO", 1: "B", 2: "NOT_B", 3: "ONES", 4: "S1S0", 5: "Y"})
alu.comp("NOT Gate", {"size": "20"}, 330, 690, {0: "NOT_S2", 1: "S2"})
alu.comp("AND Gate", {"size": "30"}, 440, 640, {0: "CIN", 1: "NOT_S2", 2: "CI"})
alu.comp("Adder", {"width": W8}, 580, 160, {0: "A", 1: "Y", 2: "ARITH", 3: "CIN", 4: "C"})
alu.comp("AND Gate", {"width": W8, "size": "30"}, 420, 800, {0: "L_AND", 1: "A", 2: "B"})
alu.comp("OR Gate", {"width": W8, "size": "30"}, 420, 880, {0: "L_OR", 1: "A", 2: "B"})
alu.comp("XOR Gate", {"width": W8, "size": "30"}, 420, 960, {0: "L_XOR", 1: "A", 2: "B"})
alu.comp("NOT Gate", {"width": W8, "size": "20"}, 430, 1050, {0: "L_NOT", 1: "A"})
alu.comp("Multiplexer", mux(2), 600, 880, {0: "L_AND", 1: "L_OR", 2: "L_XOR", 3: "L_NOT", 4: "S1S0", 5: "LOGIC"})
alu.comp("Multiplexer", mux(1), 760, 420, {0: "ARITH", 1: "LOGIC", 2: "S2", 3: "F"})
alu.comp("Constant", {"width": W8, "value": "0x0"}, 820, 580, {0: "ZERO"})
alu.comp("Comparator", {"width": W8, "mode": "unsigned"}, 900, 520, {0: "F", 1: "ZERO", 3: "Z"})
alu.comp("Splitter", splitter(8, [range(0, 7), [7]]), 900, 640, {0: "F", 2: "N"})
alu.pin_out("F", 8, 1140, 440)
alu.pin_out("C", 1, 1140, 500)
alu.pin_out("Z", 1, 1140, 560)
alu.pin_out("N", 1, 1140, 620)

shf = Ckt("SHIFTER", "SHIFTER", "#ede9fe")
shf.text("SHIFTER: H = 00 pass, 01 shift right, 10 shift left", 60, 30)
shf.pin_in("B", 8, 100, 120)
shf.pin_in("H", 2, 100, 360)
shf.comp("Constant", {"width": "3", "value": "0x1"}, 180, 260, {0: "ONE"})
shf.comp("Shifter", {"width": W8, "shift": "lr"}, 300, 150, {0: "B", 1: "ONE", 2: "SHR"})
shf.comp("Shifter", {"width": W8, "shift": "ll"}, 300, 250, {0: "B", 1: "ONE", 2: "SHL"})
shf.comp("Multiplexer", mux(2), 480, 140, {0: "B", 1: "SHR", 2: "SHL", 3: "B", 4: "H", 5: "OUT"})
shf.pin_out("OUT", 8, 640, 170)

BLOCKS = [fetch, dec, reg, alu, shf]

# ------------------------------------------------------------------ pass 1: blocks only, then read block geometry
block_xml = [b.build() for b in BLOCKS]

def write(path, circuits, main_name):
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="5.0.0" version="1.0">
  This file is intended to be loaded by Logisim-evolution v5.0.0(https://github.com/logisim-evolution/).

  <lib desc="#Wiring" name="0"/>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Plexers" name="2"/>
  <lib desc="#Arithmetic" name="3"/>
  <lib desc="#Memory" name="4"/>
  <lib desc="#Base" name="5"/>
  <main name="{main_name}"/>
{chr(10).join(circuits)}
</project>
'''
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(xml)

# Block geometry follows directly from appearance(): anchor = top-left of the box.
for blk in BLOCKS:
    ins = [i for i in blk.items if i.get("pin") == "in"]
    outs = [i for i in blk.items if i.get("pin") == "out"]
    n = max(len(ins), len(outs))
    H = 50 + (n - 1) * 30 + 30
    ports = {}
    for k, it in enumerate(ins):
        ports[it["attrs"]["label"]] = (0, 50 + k * 30, int(it["attrs"]["width"]))
    for k, it in enumerate(outs):
        ports[it["attrs"]["label"]] = (200, 50 + k * 30, int(it["attrs"]["width"]))
    SUBGEO[blk.name] = {"bounds": (0, 0, 200, H), "ports": ports}
for name, g in SUBGEO.items():
    print(name, g["bounds"], {k: v[:2] for k, v in g["ports"].items()})

# ------------------------------------------------------------------ main: the computer
m = Ckt("main")
m.text("SIMPLE COMPUTER (8-bit, single-cycle)", 60, 30, 24)
m.text("Ctrl+T = one clock = one instruction.  Double-click a block to look inside.", 60, 70, 14)
m.comp("Clock", {"label": "CLK"}, 80, 140, {0: "CLK"})
m.sub("FETCH", 260, 160, {"CLK": "CLK", "RUN": "RUN", "TAKEN": "TAKEN", "TARGET": "IMM", "PC_OUT": "PC", "IR": "IR"})
m.sub("DECODE_CONTROL", 260, 520, {"IR": "IR", "BUS_A": "BUS_A", "DR": "DR", "SA": "SA", "SB": "SB", "IMM": "IMM",
                                    "G": "G", "H": "H", "MF": "MF", "MB": "MB", "MD": "MD", "RW": "RW", "MW": "MW",
                                    "TAKEN": "TAKEN", "RUN": "RUN", "HALT": "HALT"})
m.sub("REGISTER_FILE", 760, 300, {"CLK": "CLK", "BUS_D": "BUS_D", "DR": "DR", "RW": "RW", "SA": "SA", "SB": "SB",
                                   "A_DATA": "BUS_A", "B_DATA": "REG_B", "R0_OUT": "R0", "R1_OUT": "R1", "R2_OUT": "R2", "R3_OUT": "R3"})
m.comp("Multiplexer", mux(1), 1160, 560, {0: "REG_B", 1: "IMM", 2: "MB", 3: "BUS_B"})
m.sub("ALU", 1400, 300, {"A": "BUS_A", "B": "BUS_B", "G": "G", "F": "ALU_OUT", "C": "C", "Z": "Z", "N": "N"})
m.sub("SHIFTER", 1400, 640, {"B": "BUS_B", "H": "H", "OUT": "SHIFT_OUT"})
m.comp("Multiplexer", mux(1), 1720, 420, {0: "ALU_OUT", 1: "SHIFT_OUT", 2: "MF", 3: "BUS_F"})
m.comp("Constant", {"width": "1", "value": "0x1"}, 1700, 840, {0: "ONE"})
m.comp("RAM", {"addrWidth": "8", "dataWidth": "8", "asyncread": "true", "databus": "bibus", "label": "DataMemory"},
       1820, 760, {0: "BUS_A", 1: "MEM_OUT", 2: "BUS_B", 3: "ONE", 4: "MW", 5: "CLK"})
m.comp("Multiplexer", mux(1), 2220, 480, {0: "BUS_F", 1: "MEM_OUT", 2: "MD", 3: "BUS_D"})
m.text("MUX B (immediate)", 1120, 540, 13)
m.text("MUX F", 1700, 400, 13)
m.text("MUX D", 2200, 460, 13)
PX = 2480
for i, (lab, net, w, rad) in enumerate([("PC", "PC", 8, "10unsigned"), ("IR", "IR", 16, "16"),
                                        ("R0", "R0", 8, "10unsigned"), ("R1", "R1", 8, "10unsigned"),
                                        ("R2", "R2", 8, "10unsigned"), ("R3", "R3", 8, "10unsigned"),
                                        ("BUS_D", "BUS_D", 8, "10unsigned"), ("Z", "Z", 1, "2"), ("N", "N", 1, "2"),
                                        ("C", "C", 1, "2"), ("halt", "HALT", 1, "2")]):
    m.pin_out(lab, w, PX, 140 + i * 70, net=net, radix=rad)
m.text("OUTPUTS", PX, 100, 16)

main_xml = m.build()
write(OUT, [main_xml] + block_xml, "main")
print("wrote", OUT)
open(os.path.join(HERE, "ports.txt"), "w").write("\n".join(PORTDUMP) + "\n")
import json
with open(os.path.join(HERE, "layout.json"), "w", encoding="utf-8") as fh:
    json.dump(EXPORT, fh, separators=(",", ":"))
