import com.cburch.logisim.circuit.*;
import com.cburch.logisim.data.*;
import com.cburch.logisim.file.*;
import java.io.*;
import java.util.*;

// Reads "circuit|net|x|y" lines; uses Logisim's own wire sets to report shorts and splits.
public class Probe4 {
  public static void main(String[] args) throws Exception {
    LogisimFile lf = new Loader(null).openLogisimFile(new File(args[0]));
    Map<String, List<String[]>> byCirc = new LinkedHashMap<>();
    BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
    for (String l; (l = in.readLine()) != null; ) {
      if (l.isBlank()) continue;
      String[] p = l.split(java.util.regex.Pattern.quote("|"));
      byCirc.computeIfAbsent(p[0], k -> new ArrayList<>()).add(p);
    }
    int problems = 0;
    for (var e : byCirc.entrySet()) {
      Circuit c = lf.getCircuit(e.getKey());
      for (String[] a : e.getValue()) {
        Location la = Location.create(Integer.parseInt(a[2]), Integer.parseInt(a[3]), false);
        Collection<Wire> ws = c.getWires(la);
        if (ws.isEmpty()) continue;
        WireSet set = c.getWireSet(ws.iterator().next());
        for (String[] b : e.getValue()) {
          Location lb = Location.create(Integer.parseInt(b[2]), Integer.parseInt(b[3]), false);
          boolean in2 = set.containsLocation(lb);
          if (in2 && !a[1].equals(b[1])) { System.out.println("SHORT " + e.getKey() + " " + a[1] + " <-> " + b[1] + " at " + lb); problems++; }
          if (!in2 && a[1].equals(b[1]) && !c.getWires(lb).isEmpty()) { System.out.println("SPLIT " + e.getKey() + " " + a[1] + " at " + lb); problems++; }
        }
      }
    }
    System.out.println("problems " + problems);
  }
}
