import com.cburch.logisim.comp.*;
import com.cburch.logisim.data.*;
import com.cburch.logisim.instance.*;
import java.io.*;
import java.util.*;

// Reads lines "Factory|name=value|name=value..." and prints component geometry:
// bounds and each port's offset from the component location, width, direction and tooltip.
public class Probe {
  static List<com.cburch.logisim.tools.Library> LIBS = List.of(
      new com.cburch.logisim.std.wiring.WiringLibrary(), new com.cburch.logisim.std.gates.GatesLibrary(),
      new com.cburch.logisim.std.plexers.PlexersLibrary(), new com.cburch.logisim.std.arith.ArithmeticLibrary(),
      new com.cburch.logisim.std.memory.MemoryLibrary(), new com.cburch.logisim.std.base.BaseLibrary());
  static ComponentFactory factory(String n) throws Exception {
    for (var lib : LIBS) for (var t : lib.getTools())
      if (t instanceof com.cburch.logisim.tools.AddTool at && at.getName().equals(n)) return at.getFactory();
    throw new IllegalArgumentException(n);
  }

  @SuppressWarnings({"unchecked", "rawtypes"})
  static void set(AttributeSet as, String name, String val) {
    for (Attribute a : as.getAttributes()) {
      if (a.getName().equals(name)) { as.setValue(a, a.parse(val)); return; }
    }
    throw new IllegalArgumentException("no attr " + name);
  }

  public static void main(String[] args) throws Exception {
    BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
    String line;
    while ((line = in.readLine()) != null) {
      line = line.trim();
      if (line.isEmpty()) continue;
      String[] parts = line.split("\\|");
      ComponentFactory f = factory(parts[0]);
      AttributeSet as = f.createAttributeSet();
      for (int i = 1; i < parts.length; i++) {
        int e = parts[i].indexOf('=');
        set(as, parts[i].substring(0, e), parts[i].substring(e + 1));
      }
      Location loc = Location.create(1000, 1000, true);
      Component c = f.createComponent(loc, as);
      StringBuilder sb = new StringBuilder();
      sb.append("SPEC ").append(line).append('\n');
      if (args.length > 0) {
        for (Attribute<?> a : as.getAttributes()) {
          Object v = as.getValue(a);
          sb.append("  attr ").append(a.getName()).append(" = ").append(v).append('\n');
        }
      }
      Bounds b = c.getBounds();
      sb.append("  bounds ").append(b.getX() - 1000).append(' ').append(b.getY() - 1000)
          .append(' ').append(b.getWidth()).append(' ').append(b.getHeight()).append('\n');
      List<Port> ports = null;
      if (c instanceof InstanceComponent ic) ports = ic.getInstance().getPorts();
      List<EndData> ends = c.getEnds();
      for (int i = 0; i < ends.size(); i++) {
        EndData ed = ends.get(i);
        String tip = "";
        if (ports != null && i < ports.size()) { String t = ports.get(i).getToolTip(); tip = t == null ? "" : t; }
        sb.append("  port ").append(i).append(' ').append(ed.getLocation().getX() - 1000).append(' ')
            .append(ed.getLocation().getY() - 1000).append(' ').append(ed.getWidth().getWidth()).append(' ')
            .append(ed.isInput() && ed.isOutput() ? "io" : ed.isInput() ? "in" : "out").append(' ').append(tip).append('\n');
      }
      System.out.print(sb);
    }
  }
}
