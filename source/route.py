"""Grid wire router for Logisim circuits, plus a connectivity checker.

Logisim rules this respects:
- a wire end (or a component port) that lies anywhere on a wire connects to it;
- two wires that cross in their middles do not connect.
So: other nets may cross a wire only where neither bends or ends, and no net may
run along another net's wire or touch another net's port.
"""
import heapq
from collections import defaultdict

GRID = 10
DIRS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
AXIS = {"E": "H", "W": "H", "N": "V", "S": "V"}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


class Board:
    def __init__(self):
        self.blocked = set()
        self.near = set()
        self.port_net = {}
        self.reserved = {}  # first cell outside each port belongs to that port's net
        self.occ = defaultdict(dict)  # cell -> {net: set of 'H','V','N'}
        self.tree = defaultdict(set)
        self.wires = []  # (net, (x1, y1), (x2, y2)) in px
        self.ports = []  # (net, (x, y)) in px
        self.lo = [10 ** 9, 10 ** 9]
        self.hi = [-10 ** 9, -10 ** 9]

    def _grow(self, cx, cy):
        self.lo = [min(self.lo[0], cx), min(self.lo[1], cy)]
        self.hi = [max(self.hi[0], cx), max(self.hi[1], cy)]

    def add_body(self, x, y, w, h):
        x0, y0 = x // GRID, y // GRID
        x1, y1 = (x + w) // GRID, (y + h) // GRID
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                self.blocked.add((cx, cy))
        for cx in range(x0 - 1, x1 + 2):
            for cy in range(y0 - 1, y1 + 2):
                self.near.add((cx, cy))
        self._grow(x0, y0)
        self._grow(x1, y1)

    def add_port(self, net, x, y, d=None):
        c = (x // GRID, y // GRID)
        if d:
            for k in (1, 2):
                e = (c[0] + DIRS[d][0] * k, c[1] + DIRS[d][1] * k)
                if self.reserved.get(e, net) != net:
                    if k == 1:
                        raise ValueError(f"exit cell {e} wanted by {self.reserved[e]} and {net}")
                    continue
                self.reserved[e] = net
                self.blocked.discard(e)  # some ports sit inside the drawn body (select stubs)
        assert x % GRID == 0 and y % GRID == 0, (net, x, y)
        if c in self.port_net and self.port_net[c] != net:
            raise ValueError(f"two nets on one port point {c}: {self.port_net[c]} {net}")
        self.port_net[c] = net
        self.ports.append((net, (x, y)))
        self._grow(*c)
        return c

    def _free_of_others(self, cell, net):
        return all(n == net for n in self.occ.get(cell, {}))

    def route(self, net, terms, margin=25):
        """terms: list of (cell, outward_dir). Connects them all into one tree."""
        cells = [t[0] for t in terms]
        for c in cells:
            self.blocked.discard(c)
        first = terms[0]
        self.tree[net].add(first[0])
        self.occ[first[0]].setdefault(net, set()).add("N")
        rest = sorted(terms[1:], key=lambda t: abs(t[0][0] - first[0][0]) + abs(t[0][1] - first[0][1]))
        lo = (self.lo[0] - margin, self.lo[1] - margin)
        hi = (self.hi[0] + margin, self.hi[1] + margin)
        all_ports = set(self.port_net)
        for t in rest:
            if t[0] in self.tree[net]:
                continue
            path = self._search(net, t, lo, hi, all_ports)
            if path is None:
                raise RuntimeError(f"could not route net {net} to {t}")
            self._commit(net, path)

    def _search(self, net, term, lo, hi, all_ports):
        start, d0 = term
        tree = self.tree[net]
        txs = [c[0] for c in tree]
        tys = [c[1] for c in tree]
        bx0, bx1, by0, by1 = min(txs), max(txs), min(tys), max(tys)

        def h(c):
            dx = 0 if bx0 <= c[0] <= bx1 else min(abs(c[0] - bx0), abs(c[0] - bx1))
            dy = 0 if by0 <= c[1] <= by1 else min(abs(c[1] - by0), abs(c[1] - by1))
            return dx + dy

        pq = [(h(start), 0, start, None, None)]
        best = {(start, None): 0}
        parent = {}
        pops = 0
        while pq:
            pops += 1
            if pops > 250000:
                return None
            f, g, a, din, _ = heapq.heappop(pq)
            if best.get((a, din), 1e18) < g:
                continue
            for d, (vx, vy) in DIRS.items():
                if din is None and d != d0:
                    continue
                if din is not None and d == OPP[din]:
                    continue
                bend = din is not None and d != din
                if bend and not self._free_of_others(a, net):
                    continue
                b = (a[0] + vx, a[1] + vy)
                if not (lo[0] <= b[0] <= hi[0] and lo[1] <= b[1] <= hi[1]):
                    continue
                if b in tree:
                    if b == start or not self._free_of_others(b, net):
                        continue
                    if b in all_ports and self.port_net[b] != net:
                        continue
                    parent[(b, d)] = (a, din)
                    return self._unwind(parent, (b, d), start)
                if b in self.blocked or b in all_ports:
                    continue
                if self.reserved.get(b, net) != net:
                    continue
                occ = self.occ.get(b, {})
                bad = False
                cross = 0
                for n, s in occ.items():
                    if n == net:
                        continue
                    if "N" in s or AXIS[d] in s:
                        bad = True
                        break
                    cross = 1
                if bad:
                    continue
                cost = 1 + (4 if bend else 0) + (2 if b in self.near else 0) + cross
                ng = g + cost
                key = (b, d)
                if ng < best.get(key, 1e18):
                    best[key] = ng
                    parent[key] = (a, din)
                    heapq.heappush(pq, (ng + h(b), ng, b, d, None))
        return None

    def _unwind(self, parent, key, start):
        cells = []
        while key in parent:
            cells.append(key[0])
            key = parent[key]
        cells.append(start)
        cells.reverse()
        return cells

    def _commit(self, net, cells):
        n = len(cells)
        for i, c in enumerate(cells):
            s = self.occ[c].setdefault(net, set())
            dirs = []
            if i > 0:
                dirs.append("H" if cells[i - 1][1] == c[1] else "V")
            if i < n - 1:
                dirs.append("H" if cells[i + 1][1] == c[1] else "V")
            s.update(dirs)
            if i == 0 or i == n - 1 or len(set(dirs)) > 1:
                s.add("N")
            self.tree[net].add(c)
        # straight runs -> wires
        run_start = 0
        for i in range(1, n):
            last = i == n - 1
            turn = not last and ((cells[i - 1][0] == cells[i][0]) != (cells[i][0] == cells[i + 1][0]))
            if last or turn:
                a, b = cells[run_start], cells[i]
                self.wires.append((net, (a[0] * GRID, a[1] * GRID), (b[0] * GRID, b[1] * GRID)))
                run_start = i


def check(wires, ports):
    """Return list of problems: ports of one net split apart, or different nets joined."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    pts = set(p for _, p in ports)
    for _, a, b in wires:
        pts.add(a)
        pts.add(b)
    for i, (_, a, b) in enumerate(wires):
        wid = ("w", i)
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for p in pts:
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                union(("p", p), wid)
    groups = defaultdict(set)
    for net, p in ports:
        groups[net].add(find(("p", p)))
    problems = []
    owner = {}
    for net, roots in groups.items():
        if len(roots) > 1:
            problems.append(f"net {net} is split into {len(roots)} parts")
        for r in roots:
            if r in owner and owner[r] != net:
                problems.append(f"nets {owner[r]} and {net} are shorted")
            owner[r] = net
    return problems


def split_wires(wires, ports):
    """Logisim joins wires only at end points, so cut each wire where a point of its own net lies inside it."""
    from collections import defaultdict
    pts = defaultdict(set)
    for net, a, b in wires:
        pts[net].add(a)
        pts[net].add(b)
    for net, p in ports:
        pts[net].add(p)
    out = []
    for net, a, b in wires:
        inner = [p for p in pts[net] if p != a and p != b
                 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])]
        chain = sorted([a, b] + inner, key=lambda p: (abs(p[0] - a[0]) + abs(p[1] - a[1])))
        for u, v in zip(chain, chain[1:]):
            out.append((net, u, v))
    return out
