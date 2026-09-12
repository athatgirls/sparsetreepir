// Common serialized proof pipeline. Official VBPIR crypto lives in vendor/.
#include "client.h"
#include "server.h"
#include "utils.h"
#include "rapidjson/document.h"
#include "rapidjson/stringbuffer.h"
#include "rapidjson/writer.h"
#include <openssl/sha.h>
#include <sys/resource.h>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <map>
#include <numeric>
#include <cctype>
#include <cstdlib>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

using Clock = std::chrono::steady_clock;
using Bytes = std::vector<unsigned char>;
using V = rapidjson::Value;
using Alloc = rapidjson::Document::AllocatorType;
Alloc* alloc = nullptr;
constexpr uint64_t NONE = std::numeric_limits<uint64_t>::max();
double ms(Clock::time_point start) { return std::chrono::duration<double,std::milli>(Clock::now()-start).count(); }
void require(bool ok,const std::string& what) { if(!ok) throw std::runtime_error(what); }
void str(V& o,const char* k,const std::string& x) { V key(k,*alloc), value(x.c_str(),x.size(),*alloc); o.AddMember(key,value,*alloc); }
void num(V& o,const char* k,double x) { o.AddMember(V(k,*alloc),V(x),*alloc); }
void integer(V& o,const char* k,uint64_t x) { o.AddMember(V(k,*alloc),V(x),*alloc); }
void boolean(V& o,const char* k,bool x) { o.AddMember(V(k,*alloc),V(x),*alloc); }
void object(V& o,const char* k,V& value) { o.AddMember(V(k,*alloc),value,*alloc); }
V ints(const std::vector<uint64_t>& xs) { V a(rapidjson::kArrayType); for(auto x:xs) a.PushBack(V(x),*alloc); return a; }
Bytes unhex(std::string s) {
    if(s.rfind("0x",0)==0) s=s.substr(2);
    require(!s.empty(),"empty hexadecimal input"); if(s.size()%2) s="0"+s;
    Bytes b; b.reserve(s.size()/2);
    for(size_t i=0;i<s.size();i+=2) { require(std::isxdigit(s[i]) && std::isxdigit(s[i+1]),"invalid hexadecimal input"); b.push_back(std::stoul(s.substr(i,2),nullptr,16)); }
    return b;
}
std::string hex(const Bytes& b) { std::ostringstream out; out<<std::hex<<std::setfill('0'); for(auto x:b) out<<std::setw(2)<<unsigned(x); return out.str(); }
Bytes digest(const Bytes& b) { Bytes r(32); SHA256(b.data(),b.size(),r.data()); return r; }
Bytes root_of(const Bytes& value,const Bytes& slot,const std::vector<Bytes>& proof) {
    Bytes leaf{0}; leaf.insert(leaf.end(),value.begin(),value.end()); auto current=digest(leaf);
    for(size_t level=0;level<proof.size();++level) {
        require(proof[level].size()==32,"bad proof digest length");
        const bool right=(slot[slot.size()-1-level/8]>>(level%8))&1;
        Bytes data{1}; const auto& left=right?proof[level]:current; const auto& r=right?current:proof[level];
        data.insert(data.end(),left.begin(),left.end()); data.insert(data.end(),r.begin(),r.end()); current=digest(data);
    }
    return current;
}
std::string slot_key(const std::string& s,size_t height) { auto b=unhex(s); size_t n=(height+7)/8; require(b.size()<=n,"coordinate too wide"); b.insert(b.begin(),n-b.size(),0); return hex(b); }
void write64(std::string& s,uint64_t x) { for(int i=0;i<8;++i)s.push_back(char((x>>(8*i))&255)); }
uint64_t read64(const std::string& s,size_t& p) { require(p+8<=s.size(),"truncated metadata");uint64_t x=0;for(int i=0;i<8;++i)x|=uint64_t(uint8_t(s[p++]))<<(8*i);return x; }
template<class T> std::string save_seal(const T& x) { std::ostringstream s(std::ios::binary); x.save(s,seal::compr_mode_type::none); return s.str(); }
template<class T> T load_seal(const std::string& data,const seal::SEALContext& ctx) { std::istringstream s(data,std::ios::binary); T x; x.load(ctx,s); require(size_t(s.tellg())==data.size(),"SEAL roundtrip trailing bytes"); return x; }
std::vector<seal::Ciphertext> roundtrip(const std::vector<seal::Ciphertext>& xs,const seal::SEALContext& ctx,uint64_t& payload,uint64_t& framed) {
    // Counts and length fields are an actual binary envelope, not estimates.
    std::string wire; write64(wire,xs.size()); payload=0;
    for(const auto& x:xs) { auto saved=save_seal(x); write64(wire,saved.size()); wire+=saved; payload+=saved.size(); }
    framed=wire.size(); size_t p=0,n=read64(wire,p); std::vector<seal::Ciphertext> out; out.reserve(n);
    for(size_t i=0;i<n;++i) { size_t len=read64(wire,p);require(p+len<=wire.size(),"truncated ciphertext");out.push_back(load_seal<seal::Ciphertext>(wire.substr(p,len),ctx));p+=len; }
    require(p==wire.size(),"trailing envelope bytes");return out;
}
uint64_t peak_rss() { struct rusage r{}; getrusage(RUSAGE_SELF,&r); return uint64_t(r.ru_maxrss)*1024; }

struct Interval { uint64_t left,right,level,record; };
struct Target { std::string id,slot; Bytes value; std::vector<Interval> expected; };
Interval interval(const V& v) { return {v["left"].GetUint64(),v["right"].GetUint64(),v["level"].GetUint64(),v["record"].GetUint64()}; }
// Laminar index shared by all targets, built once from public intervals.
struct Forest {
    std::vector<Interval> nodes;
    std::vector<std::vector<size_t>> children;
    std::vector<size_t> roots;
    explicit Forest(std::vector<Interval> x):nodes(std::move(x)),children(nodes.size()) {
        std::vector<size_t> order(nodes.size()),stack; std::iota(order.begin(),order.end(),0);
        std::sort(order.begin(),order.end(),[&](size_t a,size_t b){ return nodes[a].left!=nodes[b].left?nodes[a].left<nodes[b].left:nodes[a].right>nodes[b].right; });
        for(auto i:order) {
            while(!stack.empty() && nodes[i].left>nodes[stack.back()].right) stack.pop_back();
            if(stack.empty()) roots.push_back(i);
            else { auto p=stack.back();require(nodes[i].right<=nodes[p].right,"non-laminar intervals");require(nodes[i].left!=nodes[p].left || nodes[i].right!=nodes[p].right,"duplicate interval");children[p].push_back(i); }
            stack.push_back(i);
        }
    }
    std::vector<Interval> stab(uint64_t rank) const {
        std::vector<Interval> out; const auto* list=&roots;
        while(!list->empty()) { auto it=std::upper_bound(list->begin(),list->end(),rank,[&](uint64_t r,size_t i){return r<nodes[i].left;}); if(it==list->begin())break;--it;auto idx=*it;if(rank>nodes[idx].right)break;out.push_back(nodes[idx]);list=&children[idx]; }
        return out;
    }
};

// Official PBC recursive cuckoo insertion; only state reset/RNG seeding differ.
bool cuckoo_insert(uint64_t key,size_t attempt,std::unordered_map<uint64_t,std::vector<size_t>> candidates,std::unordered_map<uint64_t,uint64_t>& owner) {
    if(attempt>500) throw std::invalid_argument("official PBC cuckoo routing failed after 500 attempts");
    for(auto b:candidates[key]) if(owner.find(b)==owner.end()){owner[b]=key;return true;}
    auto options=candidates[key];auto chosen=options[std::rand()%options.size()];auto old=owner[chosen];owner[chosen]=key;
    cuckoo_insert(old,attempt+1,candidates,owner);return true;
}
std::vector<uint64_t> cuckoo(const std::vector<uint64_t>& batch,size_t bucket_count,unsigned seed) {
    std::vector<uint64_t> table; table.assign(bucket_count,NONE); // reset, unlike upstream resize reuse.
    std::unordered_map<uint64_t,std::vector<size_t>> candidates;
    for(auto r:batch) candidates[r]=utils::get_candidate_buckets(r,3,bucket_count);
    std::unordered_map<uint64_t,uint64_t> owner; std::srand(seed);
    for(const auto& kv:candidates)cuckoo_insert(kv.first,0,candidates,owner);
    for(const auto& kv:owner)table[kv.first]=kv.second;
    require(owner.size()==batch.size(),"cuckoo lost a requested record");return table;
}

int run(const std::string& input,const std::string& output,size_t warmup) {
    rapidjson::Document report;report.SetObject();alloc=&report.GetAllocator();
    V setup(rapidjson::kObjectType),parameters(rapidjson::kObjectType),queries(rapidjson::kArrayType),warmups(rapidjson::kArrayType);
    auto flush=[&](){rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer>w(b);report.Accept(w);std::ofstream f(output);require(bool(f),"cannot write output");f<<b.GetString()<<"\n";};
    try {
        auto setup_start=Clock::now();std::ifstream f(input);require(bool(f),"cannot open input");std::string text((std::istreambuf_iterator<char>(f)),{});
        rapidjson::Document in;in.Parse(text.c_str());require(!in.HasParseError()&&in.IsObject(),"invalid input JSON");
        std::string mode=in["mode"].GetString();require(mode=="ab"||mode=="pbc"||mode=="treepir","mode must be ab, treepir, or pbc");
        size_t height=in["height"].GetUint64(),seed=in.HasMember("seed")?in["seed"].GetUint64():20260911;
        require(height>0 && height<=4096,"unsupported height");
        auto root=unhex(in["root_hex"].GetString());require(root.size()==32,"bad root");
        RawDB records;for(const auto& v:in["records"].GetArray()){records.push_back(unhex(v.GetString()));require(records.back().size()==32,"record must contain 32 bytes");}
        std::vector<Bytes> defaults;for(const auto& v:in["default_hashes"].GetArray()){defaults.push_back(unhex(v.GetString()));require(defaults.back().size()==32,"bad default hash");}require(defaults.size()==height,"default_hashes must cover original levels");
        std::vector<std::string> slots;for(const auto& v:in["occupied_slots_hex"].GetArray())slots.push_back(slot_key(v.GetString(),height));require(std::is_sorted(slots.begin(),slots.end()),"occupied slots must be sorted");require(std::adjacent_find(slots.begin(),slots.end())==slots.end(),"duplicate occupied slots");
        std::vector<Interval> all;std::set<uint64_t> seen;
        for(const auto& v:in["record_intervals"].GetArray()){auto x=interval(v);require(x.record<records.size()&&x.left<=x.right&&x.right<slots.size()&&x.level<height,"bad public interval");require(seen.insert(x.record).second,"duplicate record id");all.push_back(x);}require(all.size()==records.size(),"one public interval per record required");
        Forest forest(all);
        std::vector<Target> targets;size_t ti=0;
        for(const auto& t:in["targets"].GetArray()){Target x;x.id=t.HasMember("id")?(t["id"].IsString()?t["id"].GetString():std::to_string(t["id"].GetUint64())):std::to_string(ti);x.slot=slot_key(t["slot_hex"].GetString(),height);x.value=unhex(t["value_hex"].GetString());if(t.HasMember("needed"))for(const auto& n:t["needed"].GetArray())x.expected.push_back({0,0,n["level"].GetUint64(),n["record"].GetUint64()});targets.push_back(x);++ti;}require(!targets.empty(),"no targets");
        const auto& pi=in["pir"];size_t degree=pi["poly_degree"].GetUint64(),first=pi["first_dimension"].GetUint64(),batch_size=pi["batch_size"].GetUint64();
        require(batch_size>=2 && batch_size<=records.size(),"adapter requires 2<=batch_size<=N");
        std::vector<int> coeff;for(const auto& b:pi["coeff_bits"].GetArray())coeff.push_back(b.GetInt());
        seal::EncryptionParameters enc(seal::scheme_type::bfv);enc.set_poly_modulus_degree(degree);enc.set_coeff_modulus(seal::CoeffModulus::Create(degree,coeff));enc.set_plain_modulus(seal::PlainModulus::Batching(degree,pi["plain_bits"].GetInt()));
        seal::SEALContext context(enc,true,seal::sec_level_type::tc128);require(context.parameters_set(),std::string("SEAL tc128 context invalid: ")+context.parameter_error_message());
        size_t bucket_count=mode=="pbc"?size_t(std::ceil(1.5*batch_size)):in["buckets"].Size();
        require(mode=="pbc"||bucket_count==batch_size,"structured bucket count must equal batch size");require(bucket_count<=degree/first,"unsupported multi-vectorized-group layout");
        std::vector<std::vector<uint64_t>> bucket_ids(bucket_count);std::vector<std::vector<Interval>> bucket_intervals(bucket_count);std::vector<std::unordered_map<uint64_t,uint64_t>> structured_positions(bucket_count);
        std::unordered_map<std::string,uint64_t> pbcmap;
        if(mode=="pbc"){
            require(bucket_count>=3,"PBC needs three distinct candidate buckets");
            for(uint64_t r=0;r<records.size();++r)for(auto b:utils::get_candidate_buckets(r,3,bucket_count)){pbcmap[std::to_string(r)+"_"+std::to_string(b)]=bucket_ids[b].size();bucket_ids[b].push_back(r);}
        }else{
            require(in["bucket_intervals"].Size()==bucket_count,"structured interval count");
            std::set<uint64_t> assigned;
            for(size_t b=0;b<bucket_count;++b){for(const auto& r:in["buckets"][b].GetArray()){auto id=r.GetUint64();require(id<records.size()&&assigned.insert(id).second,"AB duplicate/bad record");bucket_ids[b].push_back(id);}
                for(const auto& v:in["bucket_intervals"][b].GetArray())bucket_intervals[b].push_back(interval(v));require(bucket_intervals[b].size()==bucket_ids[b].size(),"AB row mismatch");
                for(size_t j=0;j<bucket_ids[b].size();++j){require(bucket_intervals[b][j].record==bucket_ids[b][j],"structured index alignment");structured_positions[b][bucket_ids[b][j]]=j;}
                std::sort(bucket_intervals[b].begin(),bucket_intervals[b].end(),[](const Interval& a,const Interval& c){return a.left<c.left;});
                for(size_t j=1;j<bucket_intervals[b].size();++j)require(bucket_intervals[b][j-1].right<bucket_intervals[b][j].left,"structured intervals must be disjoint");}
            require(assigned.size()==records.size(),"AB must partition all records");
        }
        size_t capacity=0,total_records=0;std::vector<uint64_t> loads;
        for(const auto& b:bucket_ids){capacity=std::max(capacity,b.size());total_records+=b.size();loads.push_back(b.size());}
        require(capacity>0,"empty layout");
        // Serialize public map and metadata with explicit little-endian fields.
        std::string mapwire;write64(mapwire,bucket_count);
        for(size_t b=0;b<bucket_count;++b){write64(mapwire,bucket_ids[b].size());for(size_t j=0;j<bucket_ids[b].size();++j){write64(mapwire,bucket_ids[b][j]);write64(mapwire,j);}}
        std::string metadata;write64(metadata,height);metadata.append(reinterpret_cast<const char*>(root.data()),root.size());for(const auto& d:defaults)metadata.append(reinterpret_cast<const char*>(d.data()),d.size());write64(metadata,slots.size());for(const auto& s:slots){auto b=unhex(s);metadata.append(reinterpret_cast<const char*>(b.data()),b.size());}write64(metadata,all.size());for(const auto& x:all){write64(metadata,x.left);write64(metadata,x.right);write64(metadata,x.level);write64(metadata,x.record);}
        // Reconstruct client bucket maps from the serialized public map.
        size_t mp=0;require(read64(mapwire,mp)==bucket_count,"map roundtrip");std::vector<std::vector<uint64_t>> client_bucket_ids(bucket_count);std::unordered_map<std::string,uint64_t> client_pbcmap;
        for(size_t b=0;b<bucket_count;++b){size_t n=read64(mapwire,mp);for(size_t j=0;j<n;++j){auto r=read64(mapwire,mp);require(read64(mapwire,mp)==j,"bad public map order");client_bucket_ids[b].push_back(r);if(mode=="pbc")client_pbcmap[std::to_string(r)+"_"+std::to_string(b)]=j;}}require(mp==mapwire.size(),"map trailing bytes");
        RawDB dummy;std::vector<RawDB> buckets(bucket_count);for(size_t b=0;b<bucket_count;++b){for(auto r:bucket_ids[b])buckets[b].push_back(records[r]);while(buckets[b].size()<capacity)buckets[b].push_back(Bytes(32,1));}
        PirParams params(capacity,32,bucket_count,enc,first);
        auto init=Clock::now();Server server(params,buckets);num(setup,"server_preprocess_ms",ms(init));
        init=Clock::now();Client client(params);num(setup,"client_keygen_ms",ms(init));
        init=Clock::now();auto keys=client.get_public_keys();auto gal=save_seal(keys.first),relin=save_seal(keys.second);auto received_gal=load_seal<seal::GaloisKeys>(gal,context);auto received_relin=load_seal<seal::RelinKeys>(relin,context);server.set_client_keys(0,{received_gal,received_relin});num(setup,"public_key_roundtrip_ms",ms(init));
        integer(setup,"galois_key_payload_bytes",gal.size());integer(setup,"relin_key_payload_bytes",relin.size());integer(setup,"public_key_framed_bytes",gal.size()+relin.size()+16);
        integer(setup,"public_map_payload_bytes",mapwire.size());integer(setup,"common_metadata_payload_bytes",metadata.size());auto eps=save_seal(enc);integer(setup,"encryption_parameters_payload_bytes",eps.size());
        integer(setup,"setup_client_to_server_payload_bytes",gal.size()+relin.size());integer(setup,"setup_server_to_client_payload_bytes",mapwire.size()+metadata.size()+eps.size());
        integer(setup,"active_digest_payload_bytes",records.size()*32);integer(setup,"replicated_record_payload_bytes",total_records*32);integer(setup,"max_padded_bucket_payload_bytes",bucket_count*capacity*32);integer(setup,"backend_rounded_raw_payload_bytes",server.audit_raw_padded_bytes());integer(setup,"ntt_coefficient_payload_bytes",server.audit_ntt_coefficient_bytes());integer(setup,"ntt_plaintexts",server.audit_ntt_plaintext_count());
        integer(setup,"encoded_db_bytes",server.audit_ntt_coefficient_bytes());
        num(setup,"persistent_setup_wall_ms",ms(setup_start));integer(setup,"combined_peak_rss_after_setup_bytes",peak_rss());
        str(parameters,"mode",mode);integer(parameters,"height",height);integer(parameters,"records",records.size());integer(parameters,"batch_size_m",batch_size);integer(parameters,"bucket_count",bucket_count);integer(parameters,"max_bucket_records",capacity);auto lv=ints(loads);object(parameters,"bucket_loads",lv);integer(parameters,"poly_degree",degree);integer(parameters,"plain_modulus",enc.plain_modulus().value());integer(parameters,"plain_bits",pi["plain_bits"].GetUint64());integer(parameters,"first_dimension",first);str(parameters,"security_level","tc128");boolean(parameters,"context_parameters_valid",context.parameters_set());integer(parameters,"record_bytes",32);str(parameters,"compression","none");integer(parameters,"experiment_seed",seed);integer(parameters,"pbc_hash_functions",mode=="pbc"?3:0);integer(parameters,"cuckoo_max_attempts",500);std::vector<uint64_t> dims;for(auto x:params.get_dimensions())dims.push_back(x);auto dv=ints(dims);object(parameters,"pir_dimensions",dv);integer(parameters,"rounded_entries_per_bucket",params.get_rounded_num_entries());
        std::mt19937_64 rng(seed);
        auto query_one=[&](const Target& target,size_t ordinal,bool is_warmup){
            V row(rapidjson::kObjectType);str(row,"target_id",target.id);str(row,"slot_hex",target.slot);boolean(row,"warmup",is_warmup);auto pipeline=Clock::now(),part=pipeline;
            auto sit=std::lower_bound(slots.begin(),slots.end(),target.slot);require(sit!=slots.end()&&*sit==target.slot,"target not occupied");uint64_t rank=sit-slots.begin();
            std::vector<uint64_t> positions(bucket_count,NONE),selected(bucket_count,NONE);std::vector<int64_t> restore(bucket_count,-1);std::vector<Interval> needed;
            if(mode!="pbc"){
                for(size_t b=0;b<bucket_count;++b){const auto& rows=bucket_intervals[b];auto it=std::upper_bound(rows.begin(),rows.end(),rank,[](uint64_t r,const Interval& i){return r<i.left;});if(it!=rows.begin()){--it;if(rank<=it->right){positions[b]=structured_positions[b].at(it->record);selected[b]=it->record;restore[b]=it->level;needed.push_back(*it);}}if(positions[b]==NONE){require(!client_bucket_ids[b].empty(),"empty structured bucket");positions[b]=rng()%client_bucket_ids[b].size();selected[b]=client_bucket_ids[b][positions[b]];}}
            }else{
                needed=forest.stab(rank);require(needed.size()<=batch_size,"proof wider than m");std::vector<uint64_t> padded;std::set<uint64_t> ids;std::unordered_map<uint64_t,uint64_t> levels;for(const auto& x:needed){padded.push_back(x.record);ids.insert(x.record);levels[x.record]=x.level;}
                while(padded.size()<batch_size){auto r=rng()%records.size();if(ids.insert(r).second)padded.push_back(r);}
                selected=cuckoo(padded,bucket_count,unsigned(seed+ordinal));
                for(size_t b=0;b<bucket_count;++b)if(selected[b]!=NONE){auto found=client_pbcmap.find(std::to_string(selected[b])+"_"+std::to_string(b));require(found!=client_pbcmap.end(),"missing PBC map entry");positions[b]=found->second;auto level=levels.find(selected[b]);if(level!=levels.end())restore[b]=level->second;}
            }
            num(row,"route_ms",ms(part));integer(row,"real_records",needed.size());integer(row,"dummy_logical_slots",bucket_count-needed.size());
            part=Clock::now();auto query=client.gen_query(positions);num(row,"query_ms",ms(part));
            uint64_t qp=0,qf=0,ap=0,af=0;part=Clock::now();auto loaded_query=roundtrip(query,context,qp,qf);num(row,"query_roundtrip_ms",ms(part));
            part=Clock::now();std::vector<PIRResponseList> grouped_responses{server.generate_response(0,loaded_query)};auto response=server.merge_responses_chunks_buckets(grouped_responses,0);num(row,"answer_ms",ms(part));
            part=Clock::now();auto loaded_answer=roundtrip(response,context,ap,af);num(row,"answer_roundtrip_ms",ms(part));
            part=Clock::now();auto decoded=client.decode_responses(loaded_answer);num(row,"decode_ms",ms(part));require(decoded.size()==bucket_count,"decoded bucket count mismatch");
            part=Clock::now();auto proof=defaults;std::set<uint64_t> levels;
            for(size_t b=0;b<bucket_count;++b)if(restore[b]>=0){require(size_t(restore[b])<height&&levels.insert(restore[b]).second,"invalid/duplicate original proof level");require(decoded[b].size()==32,"decoded entry not 32 bytes");proof[restore[b]]=decoded[b];}
            auto computed=root_of(target.value,unhex(target.slot),proof);bool valid=computed==root;num(row,"proof_verify_ms",ms(part));num(row,"serialized_proof_wall_ms",ms(pipeline));require(valid,"reconstructed root mismatch");
            // Independent oracle checks are outside the timed proof pipeline.
            for(size_t b=0;b<bucket_count;++b)if(restore[b]>=0)require(decoded[b]==records[selected[b]],"real digest differs from publisher oracle");
            if(!target.expected.empty()){std::set<std::pair<uint64_t,uint64_t>> actual,expected;for(const auto& x:needed)actual.insert({x.record,x.level});for(const auto& x:target.expected)expected.insert({x.record,x.level});require(actual==expected,"online route differs from independent expected needed set");}
            bool flip=false,wrong_bits=false,wrong_value=false;if(!levels.empty()){auto bad=proof;bad[*levels.begin()][0]^=1;flip=root_of(target.value,unhex(target.slot),bad)!=root;}auto bs=unhex(target.slot);bs.back()^=1;wrong_bits=root_of(target.value,bs,proof)!=root;auto bv=target.value;require(!bv.empty(),"empty target value");bv[0]^=1;wrong_value=root_of(bv,unhex(target.slot),proof)!=root;
            require(flip&&wrong_bits&&wrong_value,"negative root check failed");boolean(row,"valid_root",true);boolean(row,"bitflip_rejected",flip);boolean(row,"wrong_coordinate_rejected",wrong_bits);boolean(row,"wrong_value_rejected",wrong_value);str(row,"computed_root_hex",hex(computed));
            boolean(row,"corruption_rejected",flip);V recovered(rapidjson::kArrayType);for(size_t b=0;b<bucket_count;++b){V item(rapidjson::kObjectType);integer(item,"bucket",b);integer(item,"position",positions[b]);integer(item,"record",selected[b]);str(item,"record_hex",hex(decoded[b]));boolean(item,"real",restore[b]>=0);if(restore[b]>=0)integer(item,"level",restore[b]);recovered.PushBack(item,*alloc);}object(row,"recovered_by_bucket",recovered);
            integer(row,"query_ciphertext_payload_bytes",qp);integer(row,"query_framed_bytes",qf);integer(row,"answer_ciphertext_payload_bytes",ap);integer(row,"answer_framed_bytes",af);integer(row,"online_framed_bytes",qf+af);integer(row,"query_ciphertexts",query.size());integer(row,"answer_ciphertexts",response.size());
            V proofhex(rapidjson::kArrayType);for(const auto& d:proof){auto h=hex(d);proofhex.PushBack(V(h.c_str(),*alloc),*alloc);}object(row,"proof_bottom_up_hex",proofhex);auto pos=ints(positions);object(row,"positions_by_bucket",pos);
            if(is_warmup)warmups.PushBack(row,*alloc);else queries.PushBack(row,*alloc);
        };
        for(size_t w=0;w<warmup;++w)query_one(targets[w%targets.size()],w,true);
        for(size_t t=0;t<targets.size();++t)query_one(targets[t],warmup+t,false);
        integer(setup,"combined_peak_rss_final_bytes",peak_rss());str(report,"status","passed");integer(report,"proofs_verified",targets.size());integer(report,"warmup_proofs_verified",warmup);
        str(report,"scope","Persistent same-process serialized proof pipeline; no network. Timed path includes local routing, query, uncompressed SEAL save/load envelopes, answer, decode, original-level/default reconstruction and trusted-root verification. Publisher digest and expected-route checks are untimed. RSS combines client/server, retained input, metadata and validation output; coefficient payload excludes allocator overhead.");
        str(report,"routing_provenance","Official VBPIR_PBC utils three-candidate hash and recursive cuckoo insertion; fixed experiment rand seed, per-query assign/reset, no global rehash or failed-target replacement. AB/TreePIR route from sorted public interval views retaining original bucket positions. TreePIR mode preserves official CSA bucket order but uses this adapter's directory routing, not official fast indexing. SEAL encryption randomness unchanged.");
        object(report,"setup",setup);object(report,"parameters",parameters);object(report,"queries",queries);object(report,"warmups",warmups);flush();return 0;
    }catch(const std::exception& e){str(report,"status","failed");str(report,"error",e.what());integer(report,"combined_peak_rss_bytes",peak_rss());object(report,"setup",setup);object(report,"parameters",parameters);object(report,"queries",queries);object(report,"warmups",warmups);flush();std::cerr<<e.what()<<"\n";return 2;}
}
int main(int argc,char**argv){if(argc!=4){std::cerr<<"usage: serialized_proof_bench INPUT_JSON OUTPUT_JSON WARMUP_COUNT\n";return 2;}setenv("OMP_NUM_THREADS","1",1);struct rlimit limit{10ULL*1024*1024*1024,10ULL*1024*1024*1024};setrlimit(RLIMIT_AS,&limit);std::ostringstream quiet;auto old=std::cout.rdbuf(quiet.rdbuf());int rc=run(argv[1],argv[2],std::stoul(argv[3]));std::cout.rdbuf(old);return rc;}
