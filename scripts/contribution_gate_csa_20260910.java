// Calls the unchanged official CSA; only serializes its ordered output for audit.
import java.util.*;
public class contribution_gate_csa_20260910 {
    public static void main(String[] args) {
        byte h=Byte.parseByte(args[0]);
        ColorSplittingAlgorithm csa=new ColorSplittingAlgorithm();
        List<NumColor> c=csa.balancedColorSequence(h); Collections.sort(c);
        NodesSet[] buckets=csa.ColorSplitting(h,c);
        System.out.println("color\tposition\tswapped_node");
        for(NodesSet bucket:buckets) {
            int[] ids=bucket.getAddNodes();
            for(int i=0;i<ids.length;i++)System.out.println(bucket.getColorSet()+"\t"+i+"\t"+ids[i]);
        }
    }
}
