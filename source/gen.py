"""Generate a Logisim Evolution .circ for an 8-bit single-cycle simple computer.

Every component port is joined by a short wire to a labelled tunnel, so the
connections are exact and readable. Port geometry comes from Logisim itself
(Probe.java), so nothing is guessed.
"""
import os, subprocess, sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
JAR = os.environ.get("LOGISIM_JAR", "logisim-evolution-5.0.0-all.jar")  # path to the Logisim Evolution jar
OUT = sys.argv[1]

LIB = {"Pin": 0, "Tunnel": 0, "Constant": 0, "Clock": 0, "Splitter": 0,
       "AND Gate": 1, "OR Gate": 1, "XOR Gate": 1, "NOT Gate": 1,
       "Multiplexer": 2, "Decoder": 2,
       "Adder": 3, "Comparator": 3, "Shifter": 3,
       "Register": 4, "RAM": 4, "ROM": 4}

# ---------------------------------------------------------------- program
OPS = {"HALT": 0, "MOV": 1, "ADD": 2, "SUB": 3, "AND": 4, "OR": 5, "XOR": 6, "NOT": 7,
       "INC": 8, "JMP": 9, "SHL": 10, "SHR": 11, "LDI": 12, "LD": 13, "ST": 14, "BRZ": 15}

def ins(op, dr=0, sa=0, sb=0, imm=None):
    w = OPS[op] << 12 | dr << 10 | sa << 8
    w |= (imm & 0xFF) if imm is not None else sb << 6
    return w

PROGRAM = [
    ins("LDI", dr=0, imm=5),          # 0  R0 = 5        (counter)
    ins("LDI", dr=1, imm=0),          # 1  R1 = 0        (sum)
    ins("LDI", dr=2, imm=1),          # 2  R2 = 1
    ins("ADD", dr=1, sa=1, sb=0),     # 3  loop: R1 = R1 + R0
    ins("SUB", dr=0, sa=0, sb=2),     # 4  R0 = R0 - 1
    ins("BRZ", sa=0, imm=7),          # 5  if R0 == 0 goto 7
    ins("JMP", imm=3),                # 6  goto loop
    ins("LDI", dr=3, imm=0x10),       # 7  R3 = 16       (address)
    ins("ST", sa=3, sb=1),            # 8  M[R3] = R1
    ins("LD", dr=2, sa=3),            # 9  R2 = M[R3]
    ins("SHL", dr=2, sb=2),           # 10 R2 = R2 << 1
    ins("XOR", dr=0, sa=2, sb=1),     # 11 R0 = R2 xor R1
    ins("HALT"),                      # 12
]

# control word bits: G = bits 0-3 (Cin, S0, S1, S2), H = 4-5, MF 6, MB 7, MD 8, RW 9, MW 10, PL 11, JB 12, HALT 13
RW, MF, MB, MD, MW, PL, JB, HLT = 1 << 9, 1 << 6, 1 << 7, 1 << 8, 1 << 10, 1 << 11, 1 << 12, 1 << 13
def G(s2, s1, s0, cin): return s2 << 3 | s1 << 2 | s0 << 1 | cin
def H(h): return h << 4
CONTROL = {
    "HALT": HLT,
    "MOV": G(0, 0, 0, 0) | RW,
    "ADD": G(0, 0, 1, 0) | RW,
    "SUB": G(0, 1, 0, 1) | RW,
    "AND": G(1, 0, 0, 0) | RW,
    "OR":  G(1, 0, 1, 0) | RW,
    "XOR": G(1, 1, 0, 0) | RW,
    "NOT": G(1, 1, 1, 0) | RW,
    "INC": G(0, 0, 0, 1) | RW,
    "JMP": PL | JB,
    "SHL": H(2) | MF | RW,
    "SHR": H(1) | MF | RW,
    "LDI": MB | MF | RW,
    "LD":  MD | RW,
    "ST":  MW,
    "BRZ": PL,
}
CONTROL_ROM = [CONTROL[name] for name, _ in sorted(OPS.items(), key=lambda kv: kv[1])]

def rom_contents(addr, data, words):
    vals = " ".join(format(w, "x") for w in words)
    return f"addr/data: {addr} {data}\n{vals}\n"

# ---------------------------------------------------------------- components
FONT = "SansSerif plain 12"
comps = []  # dict(f, attrs, conn{port: tunnel}, section, text)

def add(f, attrs, conn, section):
    comps.append(dict(f=f, attrs=attrs, conn=conn, section=section))

def splitter(incoming, groups):
    a = {"incoming": str(incoming), "fanout": str(len(groups))}
    for gi, bits in enumerate(groups):
        for b in bits:
            a[f"bit{b}"] = str(gi)
    return a

W8 = "8"
S = "1 Fetch"
add("Clock", {"label": "CLK"}, {0: "CLK"}, S)
add("Register", {"width": W8, "label": "PC"}, {0: "PC", 1: "PC_NEXT", 2: "CLK", 4: "RUN"}, S)
add("Constant", {"width": W8, "value": "0x1"}, {0: "ONE8"}, S)
add("Constant", {"width": "1", "value": "0x0"}, {0: "ZERO1"}, S)
add("Adder", {"width": W8}, {0: "PC", 1: "ONE8", 2: "PC_INC", 3: "ZERO1"}, S)
add("Multiplexer", {"select": "1", "width": W8, "enable": "false"}, {0: "PC_INC", 1: "IMM", 2: "TAKEN", 3: "PC_NEXT"}, S)
add("ROM", {"addrWidth": "8", "dataWidth": "16", "label": "Program",
            "contents": rom_contents(8, 16, PROGRAM)}, {0: "PC", 1: "IR"}, S)
add("Splitter", splitter(16, [range(0, 8), range(8, 10), range(10, 12), range(12, 16)]),
    {0: "IR", 1: "IMM", 2: "SA", 3: "DR", 4: "OP"}, S)
add("Splitter", splitter(8, [range(0, 6), range(6, 8)]), {0: "IMM", 2: "SB"}, S)

S = "2 Control"
add("ROM", {"addrWidth": "4", "dataWidth": "16", "label": "Control",
            "contents": rom_contents(4, 16, CONTROL_ROM)}, {0: "OP", 1: "CW"}, S)
add("Splitter", splitter(16, [range(0, 4), [4, 5], [6], [7], [8], [9], [10], [11], [12], [13], [14, 15]]),
    {0: "CW", 1: "G", 2: "H", 3: "MF", 4: "MB", 5: "MD", 6: "RW", 7: "MW", 8: "PL", 9: "JB", 10: "HALT"}, S)
add("NOT Gate", {"size": "20"}, {0: "RUN", 1: "HALT"}, S)
add("Constant", {"width": W8, "value": "0x0"}, {0: "ZERO8"}, S)
add("Comparator", {"width": W8, "mode": "unsigned"}, {0: "BUS_A", 1: "ZERO8", 3: "A_ZERO"}, S)
add("OR Gate", {"size": "30"}, {0: "JUMP_OK", 1: "JB", 2: "A_ZERO"}, S)
add("AND Gate", {"size": "30"}, {0: "TAKEN", 1: "PL", 2: "JUMP_OK"}, S)

S = "3 Register file"
add("Decoder", {"select": "2", "enable": "false"}, {0: "DST0", 1: "DST1", 2: "DST2", 3: "DST3", 4: "DR"}, S)
for k in range(4):
    add("AND Gate", {"size": "30"}, {0: f"LOAD{k}", 1: f"DST{k}", 2: "RW"}, S)
for k in range(4):
    add("Register", {"width": W8, "label": f"R{k}"}, {0: f"R{k}", 1: "BUS_D", 2: "CLK", 4: f"LOAD{k}"}, S)
add("Multiplexer", {"select": "2", "width": W8, "enable": "false"},
    {0: "R0", 1: "R1", 2: "R2", 3: "R3", 4: "SA", 5: "BUS_A"}, S)
add("Multiplexer", {"select": "2", "width": W8, "enable": "false"},
    {0: "R0", 1: "R1", 2: "R2", 3: "R3", 4: "SB", 5: "REG_B"}, S)
add("Multiplexer", {"select": "1", "width": W8, "enable": "false"}, {0: "REG_B", 1: "IMM", 2: "MB", 3: "BUS_B"}, S)

S = "4 ALU"
add("Splitter", splitter(4, [[0], [1, 2], [3]]), {0: "G", 1: "CI", 2: "S10", 3: "S2"}, S)
add("NOT Gate", {"width": W8, "size": "20"}, {0: "NOT_B", 1: "BUS_B"}, S)
add("Constant", {"width": W8, "value": "0xff"}, {0: "ONES8"}, S)
add("Multiplexer", {"select": "2", "width": W8, "enable": "false"},
    {0: "ZERO8", 1: "BUS_B", 2: "NOT_B", 3: "ONES8", 4: "S10", 5: "Y"}, S)
add("NOT Gate", {"size": "20"}, {0: "NOT_S2", 1: "S2"}, S)
add("AND Gate", {"size": "30"}, {0: "CIN", 1: "NOT_S2", 2: "CI"}, S)
add("Adder", {"width": W8}, {0: "BUS_A", 1: "Y", 2: "ARITH", 3: "CIN", 4: "C_FLAG"}, S)
add("AND Gate", {"width": W8, "size": "30"}, {0: "L_AND", 1: "BUS_A", 2: "BUS_B"}, S)
add("OR Gate", {"width": W8, "size": "30"}, {0: "L_OR", 1: "BUS_A", 2: "BUS_B"}, S)
add("XOR Gate", {"width": W8, "size": "30"}, {0: "L_XOR", 1: "BUS_A", 2: "BUS_B"}, S)
add("NOT Gate", {"width": W8, "size": "20"}, {0: "L_NOT", 1: "BUS_A"}, S)
add("Multiplexer", {"select": "2", "width": W8, "enable": "false"},
    {0: "L_AND", 1: "L_OR", 2: "L_XOR", 3: "L_NOT", 4: "S10", 5: "LOGIC"}, S)
add("Multiplexer", {"select": "1", "width": W8, "enable": "false"}, {0: "ARITH", 1: "LOGIC", 2: "S2", 3: "ALU_OUT"}, S)

S = "5 Shifter, MUX F, memory, MUX D"
add("Constant", {"width": "3", "value": "0x1"}, {0: "ONE3"}, S)
add("Shifter", {"width": W8, "shift": "lr"}, {0: "BUS_B", 1: "ONE3", 2: "SHR_OUT"}, S)
add("Shifter", {"width": W8, "shift": "ll"}, {0: "BUS_B", 1: "ONE3", 2: "SHL_OUT"}, S)
add("Multiplexer", {"select": "2", "width": W8, "enable": "false"},
    {0: "BUS_B", 1: "SHR_OUT", 2: "SHL_OUT", 3: "BUS_B", 4: "H", 5: "SHIFT_OUT"}, S)
add("Multiplexer", {"select": "1", "width": W8, "enable": "false"}, {0: "ALU_OUT", 1: "SHIFT_OUT", 2: "MF", 3: "BUS_F"}, S)
add("Constant", {"width": "1", "value": "0x1"}, {0: "ONE1"}, S)
add("RAM", {"addrWidth": "8", "dataWidth": "8", "asyncread": "true", "databus": "bibus", "label": "DataMemory"},
    {0: "BUS_A", 1: "MEM_OUT", 2: "BUS_B", 3: "ONE1", 4: "MW", 5: "CLK"}, S)
add("Multiplexer", {"select": "1", "width": W8, "enable": "false"}, {0: "BUS_F", 1: "MEM_OUT", 2: "MD", 3: "BUS_D"}, S)
add("Comparator", {"width": W8, "mode": "unsigned"}, {0: "BUS_F", 1: "ZERO8", 3: "Z_FLAG"}, S)
add("Splitter", splitter(8, [range(0, 7), [7]]), {0: "BUS_F", 2: "N_FLAG"}, S)

S = "6 Display"
def out_pin(label, tunnel, width, radix):
    add("Pin", {"type": "output", "facing": "west", "width": str(width), "label": label, "radix": radix},
        {0: tunnel}, S)
out_pin("PC", "PC", 8, "10unsigned")
out_pin("IR", "IR", 16, "16")
for k in range(4):
    out_pin(f"R{k}", f"R{k}", 8, "10unsigned")
out_pin("BUS_D", "BUS_D", 8, "10unsigned")
out_pin("Z", "Z_FLAG", 1, "2")
out_pin("N", "N_FLAG", 1, "2")
out_pin("C", "C_FLAG", 1, "2")
out_pin("halt", "HALT", 1, "2")

# ---------------------------------------------------------------- geometry from Logisim
def spec(c):
    parts = [c["f"]] + [f"{k}={v}" for k, v in c["attrs"].items() if k not in ("label", "contents", "radix")]
    return "|".join(parts)

specs = sorted({spec(c) for c in comps})
cp = JAR + ";" + HERE
res = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", cp, "Probe"], input="\n".join(specs) + "\n",
                     capture_output=True, text=True, cwd=HERE)
if res.returncode:
    sys.exit(res.stderr)
geo, cur = {}, None
for line in res.stdout.splitlines():
    p = line.split()
    if line.startswith("SPEC "):
        cur = line[5:]; geo[cur] = {"ports": {}}
    elif p and p[0] == "bounds":
        geo[cur]["bounds"] = tuple(map(int, p[1:5]))
    elif p and p[0] == "port":
        geo[cur]["ports"][int(p[1])] = (int(p[2]), int(p[3]), int(p[4]))

# ---------------------------------------------------------------- layout
def outward(c, port):
    bx, by, bw, bh = geo[spec(c)]["bounds"]
    dx, dy, _ = geo[spec(c)]["ports"][port]
    if c["f"] == "Splitter":
        return "W" if port == 0 else "E"
    d = {"W": abs(dx - bx), "E": abs(bx + bw - dx), "N": abs(dy - by), "S": abs(by + bh - dy)}
    if min(d["W"], d["E"]) <= 2:
        return "W" if d["W"] <= d["E"] else "E"
    return min(d, key=d.get)

PAD_X, PAD_Y = 170, 70
COL_H = 1500
x0, y0 = 60, 120
cx, cy, colw = x0, y0, 0
placed, texts = [], []
last_section = None
for c in comps:
    bx, by, bw, bh = geo[spec(c)]["bounds"]
    if c["section"] != last_section:
        if last_section is not None:
            cx, cy, colw = cx + colw + 2 * PAD_X, y0, 0
        texts.append((cx + PAD_X, cy - 50, c["section"]))
        last_section = c["section"]
    if cy + bh + PAD_Y > y0 + COL_H:
        cx, cy, colw = cx + colw + 2 * PAD_X, y0, 0
    # top-left of bounds goes to (cx + PAD_X, cy); loc = that - offset
    lx = cx + PAD_X - bx
    ly = cy - by
    lx, ly = (lx + 9) // 10 * 10, (ly + 9) // 10 * 10
    c["loc"] = (lx, ly)
    placed.append(c)
    cy = ly + by + bh + PAD_Y + 20
    colw = max(colw, bw)

# ---------------------------------------------------------------- xml
VEC = {"W": (-1, 0), "E": (1, 0), "N": (0, -1), "S": (0, 1)}
TFACE = {"W": "east", "E": "west", "N": "south", "S": "north"}
lines = []
def a(n, v):
    return f'      <a name="{n}" val="{escape(v, {chr(34): "&quot;"})}"/>'

for c in placed:
    lx, ly = c["loc"]
    body = []
    for k, v in c["attrs"].items():
        if k == "contents":
            body.append(f'      <a name="contents">{escape(v)}</a>')
        else:
            body.append(a(k, v))
    lines.append(f'    <comp lib="{LIB[c["f"]]}" loc="({lx},{ly})" name="{c["f"]}">\n' + "\n".join(body) + "\n    </comp>")
    side_count = {}
    for port, tname in c["conn"].items():
        dx, dy, w = geo[spec(c)]["ports"][port]
        d = outward(c, port)
        n = side_count.get(d, 0); side_count[d] = n + 1
        length = 20 if n % 2 == 0 else 70
        vx, vy = VEC[d]
        px, py = lx + dx, ly + dy
        tx, ty = px + vx * length, py + vy * length
        lines.append(f'    <wire from="({px},{py})" to="({tx},{ty})"/>')
        lines.append(f'    <comp lib="0" loc="({tx},{ty})" name="Tunnel">\n{a("facing", TFACE[d])}\n{a("width", str(w))}\n'
                     f'{a("label", tname)}\n{a("labelfont", FONT)}\n    </comp>')
for (tx, ty, t) in texts:
    lines.append(f'    <comp lib="5" loc="({tx // 10 * 10},{ty // 10 * 10})" name="Text">\n{a("text", t)}\n'
                 f'{a("font", "SansSerif bold 20")}\n{a("halign", "left")}\n    </comp>')

xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="5.0.0" version="1.0">
  This file is intended to be loaded by Logisim-evolution v5.0.0(https://github.com/logisim-evolution/).

  <lib desc="#Wiring" name="0"/>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Plexers" name="2"/>
  <lib desc="#Arithmetic" name="3"/>
  <lib desc="#Memory" name="4"/>
  <lib desc="#Base" name="5"/>
  <main name="main"/>
  <circuit name="main">
    <a name="circuit" val="main"/>
{chr(10).join(lines)}
  </circuit>
</project>
'''
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(xml)
print("components", len(placed), "file", OUT)
print("program", " ".join(format(w, "04x") for w in PROGRAM))
print("control", " ".join(format(w, "04x") for w in CONTROL_ROM))
