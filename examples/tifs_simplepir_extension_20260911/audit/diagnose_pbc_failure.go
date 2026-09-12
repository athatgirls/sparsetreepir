// Offline diagnostic only: replay the frozen Go routing RNG and inspect the
// resulting fixed bipartite graph. It does not import or invoke any PIR code.
package main

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "math/rand"
    "os"
    "path/filepath"
    "runtime"
    "sort"
    "strconv"
)

type Obj = map[string]interface{}
type Interval struct {Left int `json:"left"`;Right int `json:"right"`;Level int `json:"level"`;Record int `json:"record"`}
type Need struct {Record int `json:"record"`;Level int `json:"level"`}
type Target struct {ID interface{} `json:"id"`;Slot string `json:"slot_hex"`;Needed []Need `json:"needed"`}
type Input struct {
    Mode string `json:"mode"`; Seed int64 `json:"seed"`
    Slots []string `json:"occupied_slots_hex"`; Intervals []Interval `json:"record_intervals"`
    Buckets [][]int `json:"buckets"`; Candidates [][]int `json:"hash_candidates"`; Targets []Target `json:"targets"`
    PIR struct{Batch int `json:"batch_size"`} `json:"pir"`
}
type Pick struct {Bucket int `json:"bucket"`;Position int `json:"position"`;Record int `json:"record"`;Real bool `json:"real"`;Level int `json:"level"`}
type Row struct {ID string `json:"target_id"`;Slot string `json:"slot_hex"`;Picks []Pick `json:"recovered_by_bucket"`}
type Result struct {Status string `json:"status"`;Error string `json:"error"`;Warmups []Row `json:"warmups"`;Queries []Row `json:"queries"`}
func require(ok bool,s string){if !ok{panic(s)}}
func must(e error){if e!=nil{panic(e)}}
func read(path string,dst interface{})[]byte {b,e:=os.ReadFile(path);must(e);must(json.Unmarshal(b,dst));return b}
func hashFile(path string)string {b,e:=os.ReadFile(path);must(e);h:=sha256.Sum256(b);return hex.EncodeToString(h[:])}

// On a laminar interval forest, containing intervals sorted outer-to-inner are
// exactly the frozen driver's stabbing traversal. Filtering every interval is a
// separate slow implementation and is deliberately outside any benchmark.
func needed(in *Input,target Target) []Interval {
    rank:=sort.SearchStrings(in.Slots,target.Slot)
    require(rank<len(in.Slots)&&in.Slots[rank]==target.Slot,"unknown target coordinate")
    out:=[]Interval{}
    for _,x:=range in.Intervals {if x.Left<=rank&&rank<=x.Right {out=append(out,x)}}
    sort.Slice(out,func(i,j int)bool{if out[i].Left!=out[j].Left{return out[i].Left<out[j].Left};return out[i].Right>out[j].Right})
    for i:=1;i<len(out);i++ {require(out[i-1].Left<=out[i].Left&&out[i].Right<=out[i-1].Right,"non-laminar containing intervals")}
    actual:=map[Need]bool{};for _,x:=range out {actual[Need{x.Record,x.Level}]=true}
    require(len(actual)==len(target.Needed),"public interval route width disagrees with expected need")
    for _,n:=range target.Needed {require(actual[n],"public interval route disagrees with expected need")}
    return out
}

func replay(in *Input,target Target,ordinal int) Obj {
    rng:=rand.New(rand.NewSource(in.Seed+int64(ordinal)))
    ns:=needed(in,target);batch:=[]int{};seen:=map[int]bool{};levels:=map[int]int{}
    for _,x:=range ns {batch=append(batch,x.Record);seen[x.Record]=true;levels[x.Record]=x.Level}
    paddingDraws:=[]Obj{}
    for len(batch)<in.PIR.Batch {
        r:=rng.Intn(len(in.Intervals));accepted:=!seen[r]
        paddingDraws=append(paddingDraws,Obj{"record":r,"accepted":accepted})
        if accepted {seen[r]=true;batch=append(batch,r)}
    }
    owner:=make([]int,len(in.Buckets));for i:=range owner {owner[i]=-1}
    trace:=[]Obj{};failureRecord,failureDepth:=-1,-1;maxDepth:=0
    var insert func(int,int)bool
    insert=func(key,attempt int)bool {
        if attempt>500 {failureRecord=key;failureDepth=attempt;return false}
        if attempt>maxDepth {maxDepth=attempt}
        for _,b:=range in.Candidates[key] {if owner[b]<0 {owner[b]=key;trace=append(trace,Obj{"action":"place_empty","record":key,"depth":attempt,"bucket":b});return true}}
        b:=in.Candidates[key][rng.Intn(len(in.Candidates[key]))];old:=owner[b];owner[b]=key
        trace=append(trace,Obj{"action":"evict","record":key,"depth":attempt,"bucket":b,"displaced_record":old})
        return insert(old,attempt+1)
    }
    success:=true;failedInsertion:=-1
    for i,r:=range batch {if !insert(r,0) {success=false;failedInsertion=i;break}}
    chosen:=[]Pick{}
    if success {
        for b,r:=range owner {
            p:=Pick{Bucket:b,Record:r,Level:-1}
            if r<0 {
                if len(in.Buckets[b])>0 {p.Position=rng.Intn(len(in.Buckets[b]));p.Record=in.Buckets[b][p.Position]}
            } else {
                p.Position=-1;for j,id:=range in.Buckets[b] {if id==r {p.Position=j;break}};require(p.Position>=0,"missing PBC map position")
                if l,ok:=levels[r];ok {p.Level=l;p.Real=true}
            }
            chosen=append(chosen,p)
        }
    }
    nodes:=[]Obj{}
    for _,r:=range batch {x:=Obj{"record":r,"candidate_buckets":in.Candidates[r],"real":false};if l,ok:=levels[r];ok {x["real"]=true;x["level"]=l};nodes=append(nodes,x)}
    return Obj{"target_id":fmt.Sprint(target.ID),"slot_hex":target.Slot,"ordinal":ordinal,"effective_rng_seed":in.Seed+int64(ordinal),"public_needed_intervals_outer_to_inner":ns,"padded_records_in_insertion_order":batch,"padding_draws":paddingDraws,"graph_left_nodes":nodes,"cuckoo_succeeded":success,"failed_insertion_index":failedInsertion,"failure_record":failureRecord,"failure_depth":failureDepth,"max_processed_depth":maxDepth,"cuckoo_trace":trace,"owner_at_termination":owner,"replayed_picks":chosen}
}

func matching(batch []int,candidates [][]int,bucketCount int) Obj {
    owner:=make([]int,bucketCount);for i:=range owner {owner[i]=-1}
    var augment func(int,[]bool)bool
    augment=func(r int,visited []bool)bool {
        for _,b:=range candidates[r] {
            if visited[b] {continue};visited[b]=true
            if owner[b]<0||augment(owner[b],visited) {owner[b]=r;return true}
        }
        return false
    }
    cardinality:=0;for _,r:=range batch {if augment(r,make([]bool,bucketCount)){cardinality++}}
    matched:=map[int]int{};certificate:=[]Obj{}
    for b,r:=range owner {if r>=0 {matched[r]=b;certificate=append(certificate,Obj{"record":r,"bucket":b})}}
    out:=Obj{"left_count":len(batch),"right_count":bucketCount,"maximum_matching_cardinality":cardinality,"complete_matching_exists":cardinality==len(batch),"matching_certificate":certificate,"algorithm":"Exact augmenting-path maximum bipartite matching with fresh right-vertex visited set for each left insertion"}
    if cardinality==len(batch) {return out}
    // Alternating reachability from unmatched left nodes produces a Hall witness.
    reachL:=map[int]bool{};reachR:=map[int]bool{};queue:=[]int{}
    for _,r:=range batch {if _,ok:=matched[r];!ok {reachL[r]=true;queue=append(queue,r)}}
    for head:=0;head<len(queue);head++ {
        r:=queue[head]
        for _,b:=range candidates[r] {reachR[b]=true;require(owner[b]>=0,"augmenting path remained after maximum matching");if !reachL[owner[b]] {reachL[owner[b]]=true;queue=append(queue,owner[b])}}
    }
    left:=[]int{};right:=[]int{}
    for r:=range reachL {left=append(left,r)};for b:=range reachR {right=append(right,b)};sort.Ints(left);sort.Ints(right)
    require(len(left)>len(right),"invalid Hall deficiency witness")
    witness:=[]Obj{};union:=map[int]bool{}
    for _,r:=range left {witness=append(witness,Obj{"record":r,"candidates":candidates[r]});for _,b:=range candidates[r] {union[b]=true}}
    require(len(union)==len(right),"Hall witness neighbor union mismatch")
    out["hall_witness"]=Obj{"records":left,"neighbor_buckets":right,"record_count":len(left),"neighbor_count":len(right),"deficiency":len(left)-len(right),"adjacency":witness,"check":"Every candidate of every listed record is in the listed neighbor union; record_count > neighbor_count proves that no complete assignment exists."}
    return out
}

func main(){
    require(len(os.Args)==5,"usage: go run diagnose_pbc_failure.go INPUT_JSON FAILED_RESULT_JSON COMMAND_JSON OUTPUT_JSON")
    inFile,resultFile,commandFile,outFile:=os.Args[1],os.Args[2],os.Args[3],os.Args[4]
    var in Input;var result Result;var cmd struct{Argv []string `json:"argv"`};read(inFile,&in);read(resultFile,&result);read(commandFile,&cmd)
    require(in.Mode=="pbc"&&result.Status=="failed","this diagnostic requires a failed PBC result")
    require(len(cmd.Argv)==4,"unexpected original command")
    wantedWarmups,e:=strconv.Atoi(cmd.Argv[3]);must(e)
    binaryFile:=cmd.Argv[0];driverFile:=filepath.Join(filepath.Dir(filepath.Dir(binaryFile)),"main.go")
    paths:=[]string{inFile,resultFile,commandFile,binaryFile,driverFile};before:=map[string]string{};for _,p:=range paths {before[p]=hashFile(p)}
    checked:=[]Obj{}
    check:=func(row Row,target Target,ordinal int){
        diag:=replay(&in,target,ordinal);require(diag["cuckoo_succeeded"].(bool),"completed request failed replay")
        picks:=diag["replayed_picks"].([]Pick);require(row.ID==fmt.Sprint(target.ID)&&row.Slot==target.Slot,"completed request identity mismatch")
        require(len(picks)==len(row.Picks),"completed bucket count mismatch")
        for i,p:=range picks {q:=row.Picks[i];require(p.Bucket==q.Bucket&&p.Position==q.Position&&p.Record==q.Record&&p.Real==q.Real,"replayed bucket/index/record differs from saved native result");if p.Real {require(p.Level==q.Level,"replayed original level mismatch")}}
        checked=append(checked,Obj{"target_id":row.ID,"ordinal":ordinal,"all_bucket_records_and_positions_match_saved_result":true})
    }
    for w,row:=range result.Warmups {check(row,in.Targets[w%len(in.Targets)],w)}
    for i,row:=range result.Queries {check(row,in.Targets[i],wantedWarmups+i)}
    stage:="measured";targetIndex:=len(result.Queries);ordinal:=wantedWarmups+targetIndex
    if len(result.Warmups)<wantedWarmups {stage="warmup";ordinal=len(result.Warmups);targetIndex=ordinal%len(in.Targets)}
    require(targetIndex<len(in.Targets),"no failed target remains")
    failed:=replay(&in,in.Targets[targetIndex],ordinal)
    require(!failed["cuckoo_succeeded"].(bool)&&failed["failure_depth"].(int)==501,"original routing failure did not reproduce")
    batch:=failed["padded_records_in_insertion_order"].([]int);ns:=failed["public_needed_intervals_outer_to_inner"].([]Interval);real:=[]int{};for _,x:=range ns {real=append(real,x.Record)}
    graph:=matching(batch,in.Candidates,len(in.Buckets));realGraph:=matching(real,in.Candidates,len(in.Buckets))
    classification:="fixed candidate graph has no complete matching"
    if graph["complete_matching_exists"].(bool) {classification="bounded random-eviction heuristic failed despite a complete matching"}
    for _,p:=range paths {require(before[p]==hashFile(p),"frozen artifact changed during diagnostic")}
    out:=Obj{"scope":"Offline route-only diagnosis of the one preserved failed process; no PIR initialization, cryptography, benchmark, seed change, target change or candidate regeneration.","classification":classification,"go_version":runtime.Version(),"case":"prefix64_n10000","method":"pbc","repeat":0,"original_status":result.Status,"original_error":result.Error,"completed_warmups":len(result.Warmups),"completed_measured_requests":len(result.Queries),"failed_stage":stage,"failed_target_zero_based_index":targetIndex,"failed_target_one_based_number":targetIndex+1,"failure_replay":failed,"padded_batch_matching":graph,"real_needed_only_matching":realGraph,"successful_prefix_replay_checks":checked,"frozen_artifact_sha256":before,"frozen_artifacts_unchanged":true,"interpretation_boundary":"A maximum-matching diagnostic does not retroactively replace or repair the failed experimental request; any successful completion times remain conditioned on success and the original failure must be retained."}
    b,e:=json.MarshalIndent(out,"","  ");must(e);must(os.WriteFile(outFile,append(b,'\n'),0644))
    fmt.Printf("classification=%s; stage=%s; target=%v; ordinal=%d; matching=%v/%d\n",classification,stage,failed["target_id"],ordinal,graph["maximum_matching_cardinality"],len(batch))
}
