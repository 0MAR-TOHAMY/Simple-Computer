# Simple Computer

An 8-bit, single-cycle computer, built twice:

- **`simple_computer.circ`**: the circuit in [Logisim Evolution](https://github.com/logisim-evolution/logisim-evolution) 5.0.
- **`web/index.html`**: an interactive web simulator that shows the signals travelling through the same circuit.

## The web simulator

A single static HTML page, with no build step and no dependencies.

- **Overview** of the whole machine, plus an inside view of each part: Fetch, Decode + control, Register file, ALU and Shifter.
- **Signal flow**:
  - Every wire fills from its source to its destination.
  - Each part lights up when its inputs arrive.
  - A MUX passes only the input its select line picks.
- **Values** in binary and decimal (hex for 16-bit signals), side by side.
- **Playback**:
  - Step one instruction, or run the whole program.
  - Pause and continue mid-signal.
  - Speeds from ⅛× to 2×, changeable while running.
- **Try a part alone**: type input and register values, then press *Run this part*.
- **Code editor** with a built-in assembler. Errors are shown per line, and the program is loaded into program memory as *My code*.
- Light and dark themes.

### Run locally

```sh
python -m http.server 5173 --directory web
```

Then open <http://localhost:5173>.

### Deploy

The `web` folder is a static site. On Vercel, import the repository and set **Root Directory** to `web`. Leave the framework preset as *Other*, with no build command.

### Keyboard

| Key | Action |
| --- | --- |
| `→` | step one instruction |
| `Space` | run / pause |
| `R` | reset |
| `S` | next speed |
| `1`–`4` | choose a program |
| `C` | code editor |
| `T` | light / dark |

## Architecture

### Parts

- **Fetch**:
  - PC, program memory (ROM, 256 × 16) and a PC + 1 adder.
  - A MUX chooses the next PC: PC + 1, or the jump target.
- **Decode + control**:
  - Splits the instruction into fields.
  - A control ROM turns the opcode into the control word.
  - Branch logic: `TAKEN = PL · (JB + (A = 0))`.
- **Register file**: four 8-bit registers R0–R3, read MUXes A and B, and a destination decoder with load enables.
- **ALU**:
  - Arithmetic: `G = A + Y + Cin`, with `Y ∈ {0, B, B̄, 1111 1111}`.
  - Logic: AND, OR, XOR, NOT.
  - Flags: C, Z, N.
- **Shifter**: pass, shift right or shift left by one.
- **MUX B** (register or immediate), **MUX F** (ALU or shifter), **MUX D** (result or memory) and a 256 × 8 **data memory**.

### Instruction format (16 bits)

```
| 15..12 | 11..10 | 9..8 | 7..6 | 5..0 |
|   OP   |   DR   |  SA  |  SB  |  --  |
                         |   IMM (7..0)  |
```

### Instruction set

| OP | Instruction | Meaning | Control word |
| --- | --- | --- | --- |
| 0 | `HALT` | stop | `2000` |
| 1 | `MOV Rd, Ra` | Rd ← Ra | `0200` |
| 2 | `ADD Rd, Ra, Rb` | Rd ← Ra + Rb | `0202` |
| 3 | `SUB Rd, Ra, Rb` | Rd ← Ra − Rb | `0205` |
| 4 | `AND Rd, Ra, Rb` | Rd ← Ra ∧ Rb | `0208` |
| 5 | `OR Rd, Ra, Rb` | Rd ← Ra ∨ Rb | `020A` |
| 6 | `XOR Rd, Ra, Rb` | Rd ← Ra ⊕ Rb | `020C` |
| 7 | `NOT Rd, Ra` | Rd ← ¬Ra | `020E` |
| 8 | `INC Rd, Ra` | Rd ← Ra + 1 | `0201` |
| 9 | `JMP n` | PC ← n | `1800` |
| A | `SHL Rd, Rb` | Rd ← Rb << 1 | `0260` |
| B | `SHR Rd, Rb` | Rd ← Rb >> 1 | `0250` |
| C | `LDI Rd, n` | Rd ← n | `02C0` |
| D | `LD Rd, [Ra]` | Rd ← M[Ra] | `0300` |
| E | `ST [Ra], Rb` | M[Ra] ← Rb | `0400` |
| F | `BRZ Ra, n` | if Ra = 0 then PC ← n | `0800` |

### Control word bits

| Bits | Signal | Meaning |
| --- | --- | --- |
| 0–3 | `G` | ALU operation: Cin, S0, S1, S2 |
| 4–5 | `H` | shifter: 0 pass, 1 right, 2 left |
| 6 | `MF` | take the shifter instead of the ALU |
| 7 | `MB` | take the immediate instead of a register |
| 8 | `MD` | take memory instead of the result |
| 9 | `RW` | write a register |
| 10 | `MW` | write memory |
| 11 | `PL` | jump enable |
| 12 | `JB` | jump always |
| 13 | `HALT` | stop |

### Assembly syntax

- One instruction per line.
- Labels end with `:`, and comments start with `;`.
- Numbers can be written as `12`, `0x0C` or `0b1100`.

```asm
        LDI R0, 3
        LDI R1, 1
loop:   SUB R0, R0, R1
        BRZ R0, done
        JMP loop
done:   HALT
```

## The Logisim circuit

1. Open `simple_computer.circ` in Logisim Evolution 5.0.
2. Use the Poke tool, and press `Ctrl + T` to run one instruction. `Ctrl + K` runs continuously.
3. Double-click a block to look inside it.

The program stored in the ROM adds 5 + 4 + 3 + 2 + 1. It writes the sum to memory, reads it back, shifts it and XORs it. It halts at PC = 12 with R0 = 17, R1 = 15, R2 = 30, R3 = 16.

To check it headless:

```sh
java -jar logisim-evolution-5.0.0-all.jar -t table simple_computer.circ
```

### Regenerating the circuit

`source/gen2.py` builds the circuit file. `source/route.py` places the wires and checks for shorts and splits. The Java probes read port positions from Logisim itself, so `Probe.class` must be compiled first.

```sh
LOGISIM_JAR=/path/to/logisim-evolution-5.0.0-all.jar python source/gen2.py simple_computer.circ
```

`source/simple_computer_tunnels_v1.circ` is an earlier version that uses tunnels instead of wires.

## Project layout

```
simple_computer.circ     Logisim circuit
web/index.html           web simulator
source/                  circuit generator, wire router and Logisim probes
```
