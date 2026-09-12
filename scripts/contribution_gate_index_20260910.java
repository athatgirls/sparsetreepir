// Calls the unchanged official fast index on every leaf; no coloring rewrite.
import java.util.*;
public class contribution_gate_index_20260910 {
    public static void main(String[] args) {
        byte h=Byte.parseByte(args[0]);
        System.out.println("target_slot\tcolor\tposition\tswapped_node");
        for(long j=1;j<=(1L<<h);j++) {
            SubIndices sb=new SubIndices(h,j);
            List<NumColor> c=sb.balancedColorSequence(h);Collections.sort(c);
            LinkedHashMap<Character,Integer> index=sb.mapIndices(sb.Path(),c);
            long[] path=sb.PathID();int i=0;
            for(Map.Entry<Character,Integer> e:index.entrySet())
                System.out.println((j-1)+"\t"+e.getKey()+"\t"+e.getValue()+"\t"+path[i++]);
        }
    }
}
