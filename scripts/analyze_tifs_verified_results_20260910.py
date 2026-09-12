"""Independently validate and summarize the completed verified TIFS experiment.

Read-only with respect to experiments/runners/manuscripts. No PIR execution or
timing experiments. Statistics use five process-run means, never 500 individual
queries as independent experimental replicates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / "manuscripts/tifs/revision_20260910"
DATASETS = [("fuel", "Fuel vectors"), ("polygon-recent", "Polygon recent"),
            ("zksync-sample", "ZKsync sample"), ("polygon-multi", "Polygon multi"),
            ("polygon-broad", "Polygon broad"), ("zksync-broad", "ZKsync broad")]
METHODS = ["first_fit", "hybrid", "activebalance", "nonempty_depth", "flat_active", "pbc_routed"]
LABELS = {"first_fit": "First-fit", "hybrid": "Hybrid", "activebalance": "ActiveBalance",
          "nonempty_depth": "Nonempty-depth", "flat_active": "Flat-active", "pbc_routed": "PBC-routed"}
T975_DF4 = 2.7764451051977987


def readj(path):
    return json.loads(path.read_text(encoding="utf-8"))


def writej(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def writecsv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(values):
    values = list(values)
    assert len(values) == 5
    avg = statistics.mean(values); sd = statistics.stdev(values)
    radius = T975_DF4*sd/math.sqrt(5)
    return {"mean": avg, "sample_sd": sd, "mean_ci95_low": avg-radius,
            "mean_ci95_high": avg+radius, "min_run": min(values), "max_run": max(values)}


def approx(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-8), (a, b)


def defaults(height):
    out = [hashlib.sha256(b"\x02").digest()]
    for _ in range(height): out.append(hashlib.sha256(b"\x01"+out[-1]+out[-1]).digest())
    return out


def value_for(slot, height):
    return hashlib.sha256(b"TIFS-revision-value\x00"+height.to_bytes(2,"big")
                          +slot.to_bytes(max(1,(height+7)//8),"big")).digest()


def proof_root(slot, value, proof):
    current = hashlib.sha256(b"\x00"+value).digest()
    for level, sibling in enumerate(proof):
        current = hashlib.sha256(b"\x01"+(sibling+current if (slot >> level)&1 else current+sibling)).digest()
    return current


def validate_run(run_dir, label, method, rep, paired, layout, environment, expected_summary, global_queries):
    manifest = readj(run_dir/"manifest.json")
    context = readj(run_dir/"client_context.json")
    result = readj(run_dir/"backend_result.json")
    signature = readj(run_dir/"run_signature.json")
    summary = readj(run_dir/"verified_summary.json")
    with (run_dir/"verified_queries.csv").open(encoding="utf-8",newline="") as stream:
        queries = list(csv.DictReader(stream))
    h = manifest["height"]; count = len(paired["slots"]); width = manifest["width"]
    assert count == 100 == manifest["query_samples"] == result["query_samples"] == result["completed_queries"]
    assert len(result["targets"]) == len(queries) == count
    assert context["slots"] == paired["slots"]
    assert context["root"] == layout["root"]
    assert result["gomaxprocs"] == 1 and result["warmup_queries"] == 5
    assert result["record_bytes"] == 32 and result["chunked_queries_per_color"] == 8
    assert signature["manifest_sha256"] == sha(run_dir/"manifest.json")
    assert signature["binary_sha256"] == environment["binary_sha256"]
    assert signature["warmup"] == 5 and signature["gomaxprocs"] == 1
    for key, value in summary.items():
        if key in expected_summary:
            if isinstance(value, (int,float)): approx(value,expected_summary[key])
            else: assert str(value) == expected_summary[key]
    blobs = {name:(run_dir/name).read_bytes() for name in signature["database_sha256"]}
    for name, content in blobs.items(): assert hashlib.sha256(content).hexdigest() == signature["database_sha256"][name]
    subdbs = {sub["color"]:sub for sub in manifest["subdatabases"]}
    assert len(subdbs) == width == len(result["parameters"])
    unique = {}; expected_A = 0; expected_H = 0
    for sub, param in zip(manifest["subdatabases"], result["parameters"]):
        assert sub["color"] == param["color"]
        identity = (sub["database_file"],sub["records"],sub["record_bytes"])
        if identity not in unique:
            unique[identity] = sub
            expected_A += param["matrix_columns_m"]*param["lwe_dimension_n"]*4*8
            expected_H += param["matrix_rows_l"]*param["lwe_dimension_n"]*4*8
    assert expected_A == result["setup"]["public_shared_state_bytes"]
    assert expected_H == result["setup"]["offline_hint_bytes"]
    assert len(unique) == result["unique_database_files"]
    assert sum(max(1,x["records"]) for x in unique.values()) == result["stored_records_with_padding"]
    if method == "flat_active": assert len(unique) == 1
    observed_bytes = set(); roots = 0; tamper_rejections = 0; record_checks = 0
    empty_chain = defaults(h); root = bytes.fromhex(layout["root"])
    for i, (target, actual, query) in enumerate(zip(paired["slots"], result["targets"], queries)):
        assert query == global_queries[label,method,rep,i]
        slot = int(target,16)
        assert i == actual["sample_index"] == int(query["sample_index"])
        assert query["target_slot"] == target and query["valid_root"] == "True"
        assert query["dataset"] == label and query["method"] == method and int(query["repeat"]) == rep
        assert actual["chunk_checks_passed"] and actual["chunk_query_count"] == 8*width
        assert actual["logical_record_queries"] == width
        records = {record["color"]:record for record in actual["recovered_records"]}
        assert len(records) == width and set(records) == set(subdbs)
        decoded = {}
        for color, record in records.items():
            sub = subdbs[color]; idx = sub["query_indices"][i]
            assert record["query_index"] == idx
            decoded[color] = bytes.fromhex(record["record_hex"])
            assert len(decoded[color]) == 32
            assert decoded[color] == blobs[sub["database_file"]][idx*32:(idx+1)*32]
            record_checks += 1
        routing = context["real_color_to_level"][i]
        assert len(set(routing.values())) == len(routing)
        proof = list(empty_chain[:h])
        for color, level in routing.items():
            assert 0 <= level < h
            proof[level] = decoded[int(color)]
        value = value_for(slot,h)
        assert proof_root(slot,value,proof) == root, (label,method,rep,i,"root")
        roots += 1
        assert routing, "These six n>=100 workloads should all have non-default proof records"
        level = next(iter(routing.values())); bad = list(proof)
        bad[level] = bytes([bad[level][0]^1])+bad[level][1:]
        assert proof_root(slot,value,bad) != root
        tamper_rejections += 1
        total_bytes = actual["online_upload_bytes"]+actual["online_download_bytes"]
        assert total_bytes == actual["online_total_bytes"] == int(query["online_bytes"])
        observed_bytes.add(total_bytes)
        approx(query["processing_ms"], float(query["backend_wall_ms"])+float(query["routing_ms"])+float(query["proof_assembly_verify_ms"]))
        for qkey, rkey in [("query_ms","client_query_ms"),("answer_ms","server_answer_ms"),("decode_ms","client_decode_ms"),("backend_wall_ms","backend_wall_ms")]:
            approx(query[qkey],actual[rkey])
        approx(query["routing_ms"],context["routing_ms"][i])
    assert len(observed_bytes) == 1 and observed_bytes.pop() == summary["online_bytes"]
    approx(statistics.mean(float(q["processing_ms"]) for q in queries),summary["processing_mean_ms"])
    enriched = dict(summary)
    for field in ("backend_wall_ms","routing_ms","proof_assembly_verify_ms"):
        enriched[field+"_mean"] = statistics.mean(float(q[field]) for q in queries)
    for field in ("pick_params_ms","make_db_ms","init_ms"):
        enriched[field] = result["setup"][field]
    enriched["unique_database_files"] = result["unique_database_files"]
    return enriched, {"root_checks":roots,"tamper_rejections":tamper_rejections,"record_byte_checks":record_checks}


def pm(avg, sd, digits=2):
    return rf"\({avg:.{digits}f}\pm{sd:.{digits}f}\)"


def make_tables(generated, groups, paired):
    lookup = {(r["dataset"],r["method"]):r for r in groups}
    ratio = {(r["dataset"],r["baseline"]):r for r in paired}
    lines = [r"\begin{table*}[!t]",r"\centering",r"\caption{Verified local proof-retrieval pipeline at height 128. Time is the sum of backend wall time, client routing, and proof assembly/root verification; no network is measured. Each method has five independent process runs of 100 paired targets, after five warmup batches. Ratios are the mean of five paired baseline/ActiveBalance run-mean ratios.}",r"\label{tab:real_backend_summary}",r"\small",r"\setlength{\tabcolsep}{5pt}",r"\begin{tabular}{lrrrrrr}",r"\toprule",r"Workload & AB ms (mean $\pm$ SD) & Depth/AB & Routed/AB & Flat/AB & AB KiB & AB $q$ \\",r"\midrule"]
    for _, label in DATASETS:
        row = lookup[label,"activebalance"]
        ratios = [ratio[label,m]["processing_ratio_mean"] for m in ("nonempty_depth","pbc_routed","flat_active")]
        lines.append(f"{label} & {pm(row['processing_mean_ms_mean'],row['processing_mean_ms_sample_sd'])} & "+" & ".join(rf"${v:.2f}\times$" for v in ratios)+f" & {row['online_bytes']/1024:.2f} & {row['logical_queries']} "+r"\\")
    lines += [r"\bottomrule",r"\end{tabular}",r"\par\smallskip\parbox{\textwidth}{\footnotesize AB denotes ActiveBalance; Depth is Nonempty-depth; Routed is PBC-routed, our three-choice replication control with complete per-proof matching, not the published SealPIR implementation. KiB is per-proof PIR upload plus download under matrix-element accounting. $q$ counts logical 32-byte slots; the runner makes $8q$ scalar SimplePIR calls. All 18\,000 measured proofs passed root verification and a one-digest corruption check. SD is across process-run means, not individual targets.}",r"\end{table*}"]
    (generated/"main_verified_backend_table.tex").write_text("\n".join(lines)+"\n",encoding="utf-8")
    lines = [r"% Six independent table blocks allow pagination without extra packages."]
    for key,label in DATASETS:
        lines += [r"\begin{table}[H]",r"\centering",rf"\caption{{Verified retrieval and setup accounting: {label}, height 128. Times are process-run means $\pm$ sample SD over five runs; each run measures 100 targets.}}",rf"\label{{tab:verified_{key.replace('-','_')}}}",r"\scriptsize",r"\setlength{\tabcolsep}{3pt}",r"\begin{tabular}{lrrrrrrrr}",r"\toprule",r"Method & $q$ & Online KiB & Processing ms & Query ms & Answer ms & Decode ms & Verify ms & Setup wall ms \\",r"\midrule"]
        for method in METHODS:
            r=lookup[label,method]
            line=[LABELS[method],str(r["logical_queries"]),f"{r['online_bytes']/1024:.2f}"]
            for field in ("processing_mean_ms","query_mean_ms","answer_mean_ms","decode_mean_ms","verify_mean_ms","setup_total_wall_ms"):
                line.append(pm(r[field+"_mean"],r[field+"_sample_sd"],3 if field in ("answer_mean_ms","verify_mean_ms") else 2))
            lines.append(" & ".join(line)+r" \\")
        lines += [r"\bottomrule",r"\end{tabular}",r"\par\smallskip",r"\begin{tabular}{lrrrrrrr}",r"\toprule",r"Method & Hint KiB & Shared A KiB & Metadata KiB & Digest KiB & Setup API ms & Parse ms & Runner RSS MiB \\",r"\midrule"]
        for method in METHODS:
            r=lookup[label,method]
            line=[LABELS[method]]+[f"{r[field]/1024:.2f}" for field in ("offline_hint_bytes","public_shared_state_bytes","client_metadata_bytes","server_payload_bytes")]
            line += [pm(r["setup_api_ms_mean"],r["setup_api_ms_sample_sd"]),pm(r["client_directory_parse_ms_mean"],r["client_directory_parse_ms_sample_sd"]),f"{r['runner_peak_rss_bytes_mean']/1048576:.2f}"]
            lines.append(" & ".join(line)+r" \\")
        lines += [r"\bottomrule",r"\end{tabular}",r"\par\smallskip\parbox{\linewidth}{\footnotesize Processing adds backend wall, routing, and proof assembly/root checking; constituent API times do not sum exactly to wall time. Setup wall includes reading record files and PickParams/MakeDB/Init/Setup, but excludes layout construction, metadata publication, and routing preflight. Metadata includes the serialized directory and occupied-slot index. Hint and public A are separate matrix-element sizes, not measured network transfers. RSS is the arithmetic mean of five per-process peaks for the whole combined runner, sampled before output serialization, not client-only memory. Flat-active initializes its repeated database once. Shared A uses uncompressed Init.}",r"\end{table}"]
    (generated/"supp_verified_backend_table.tex").write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--input",type=Path,default=ROOT/"examples/tifs_revision_20260910/verified_backend");parser.add_argument("--generated",type=Path,default=REVISION/"generated");parser.add_argument("--notes",type=Path,default=REVISION/"notes");args=parser.parse_args()
    completion=readj(args.input/"completion.json"); environment=readj(args.input/"environment.json")
    assert completion["completed_process_runs"]==180 and completion["verified_proofs"]==18000 and completion["failed_process_runs"]==[]
    assert completion["repeats"]==5 and completion["samples"]==100 and completion["methods"]==METHODS
    assert completion["requested_datasets"].split(",")==[k for k,_ in DATASETS]
    with (args.input/"run_summary.csv").open(encoding="utf-8",newline="") as stream: raw=list(csv.DictReader(stream))
    expected={(label,m,r) for _,label in DATASETS for m in METHODS for r in range(5)}
    actual={(row["dataset"],row["method"],int(row["repeat"])) for row in raw}
    assert len(raw)==len(actual)==180 and actual==expected
    raw_lookup={(row["dataset"],row["method"],int(row["repeat"])):row for row in raw}
    with (args.input/"query_measurements.csv").open(encoding="utf-8",newline="") as stream:
        global_rows=list(csv.DictReader(stream))
    global_queries={(r["dataset"],r["method"],int(r["repeat"]),int(r["sample_index"])):r for r in global_rows}
    assert len(global_rows)==len(global_queries)==18000
    audited=[];counts=defaultdict(int);caches={};layouts={}
    for key,label in DATASETS:
        dpath=args.input/f"{key}_h128";layout=readj(dpath/"layout_setup.json");layouts[label]=layout
        caches[label]=readj(dpath/"full_cache_reference.json")
        for rep in range(5):
            paired=readj(dpath/f"targets_repeat{rep}.json")
            assert paired["seed"]==2026091000+rep and set(paired["method_order"])==set(METHODS)
            assert len(paired["method_order"])==6 and len(set(paired["slots"]))==100
            for method in METHODS:
                row, checks=validate_run(dpath/method/f"repeat{rep}",label,method,rep,paired,layout,environment,raw_lookup[label,method,rep],global_queries)
                audited.append(row)
                for name,value in checks.items():counts[name]+=value
        print(f"validated {label}: 30 process runs, 3000 proofs",flush=True)
    assert counts["root_checks"]==counts["tamper_rejections"]==18000
    grouped=defaultdict(list)
    for r in audited: grouped[r["dataset"],r["method"]].append(r)
    group_rows=[]
    fixed_fields=["n","N","m","logical_queries","chunk_queries","max_bucket","online_bytes","offline_hint_bytes","public_shared_state_bytes","client_metadata_bytes","directory_plus_hint_bytes","server_payload_bytes","full_cache_bootstrap_bytes","unique_database_files"]
    metric_fields=["processing_mean_ms","processing_p50_ms","processing_p95_ms","backend_wall_ms_mean","routing_ms_mean","query_mean_ms","answer_mean_ms","decode_mean_ms","verify_mean_ms","setup_api_ms","setup_total_wall_ms","pick_params_ms","make_db_ms","init_ms","client_directory_parse_ms","runner_peak_rss_bytes"]
    for _,label in DATASETS:
        for method in METHODS:
            members=grouped[label,method];row={"dataset":label,"height":128,"method":method,"process_runs":5,"targets_per_run":100}
            for field in fixed_fields:
                values={m[field] for m in members};assert len(values)==1,(label,method,field,values)
                row[field]=values.pop()
            for field in metric_fields:
                for suffix,value in summarize(m[field] for m in members).items():row[field+"_"+suffix]=value
            row["layout_build_ms_single_observation"]=sum(layouts[label]["build_timings_ms"].get(method,{}).values()) if method in ("first_fit","hybrid","activebalance") else None
            row["pbc_preflight_ms_single_observation"]=layouts[label]["pbc"]["routing_preflight_ms"] if method=="pbc_routed" else None
            row["hint_plus_directory_over_full_cache"]=row["directory_plus_hint_bytes"]/row["full_cache_bootstrap_bytes"]
            group_rows.append(row)
    lookup={(r["dataset"],r["method"],r["repeat"]):r for r in audited};paired_rows=[];raw_ratios=[]
    for _,label in DATASETS:
        for baseline in METHODS:
            if baseline=="activebalance":continue
            ratios=[lookup[label,baseline,r]["processing_mean_ms"]/lookup[label,"activebalance",r]["processing_mean_ms"] for r in range(5)]
            bytes_ratio=lookup[label,baseline,0]["online_bytes"]/lookup[label,"activebalance",0]["online_bytes"]
            row={"dataset":label,"baseline":baseline,"denominator":"activebalance","communication_ratio":bytes_ratio}
            for suffix,v in summarize(ratios).items():row["processing_ratio_"+suffix]=v
            row["ratio_of_run_means"]=statistics.mean(lookup[label,baseline,r]["processing_mean_ms"] for r in range(5))/statistics.mean(lookup[label,"activebalance",r]["processing_mean_ms"] for r in range(5))
            paired_rows.append(row)
            for rep,value in enumerate(ratios):raw_ratios.append({"dataset":label,"baseline":baseline,"repeat":rep,"processing_baseline_over_ab":value,"communication_baseline_over_ab":bytes_ratio})
    args.generated.mkdir(parents=True,exist_ok=True);args.notes.mkdir(parents=True,exist_ok=True)
    writecsv(args.generated/"verified_backend_summary.csv",group_rows)
    writecsv(args.generated/"verified_backend_paired_ratios.csv",paired_rows)
    writecsv(args.generated/"verified_backend_run_ratios.csv",raw_ratios)
    sources={str(p.relative_to(ROOT)):sha(p) for p in [args.input/"completion.json",args.input/"environment.json",args.input/"run_summary.csv",args.input/"query_measurements.csv",ROOT/"scripts/run_tifs_verified_backend_suite_20260910.py",ROOT/"backend/simplepir/tifs_full_proof_backend.go"]}
    result={"audit_status":"passed","matrix":"6 datasets x 6 methods x 5 independent processes x 100 targets","counts":dict(counts),"paired_targets_checked":True,"message_bytes_invariant_within_fixed_layout":True,"flat_cache_setup_deduplicated":True,"statistics":{"unit":"independent process-run mean","n":5,"sample_sd_ddof":1,"mean_ci95":"two-sided Student t, df=4; descriptive model-based CI with five runs","ratio":"mean over five paired baseline run-mean / AB run-mean ratios; not ratio of grand means","no_query_pseudoreplication":True},"environment":environment,"groups":group_rows,"paired_comparisons":paired_rows,"full_cache_reference":caches,"layout_setup":layouts,"source_sha256":sources}
    writej(args.generated/"verified_backend_summary.json",result)
    make_tables(args.generated,group_rows,paired_rows)
    lines=["# 新增真实证明检索实验：独立审计与结果", "", "审计范围：完成后的 6 工作负载 × 6 方法 × 5 独立进程 × 100 目标。没有重新运行 PIR 或性能实验。", "", f"180 个进程、18,000 个测量目标的矩阵完整，全部目标与同次重复的其他方法配对一致。独立从 backend_result.json 的真实回收记录重组 SMT 证明，18,000 次 root 校验通过，18,000 次单摘要篡改均被拒绝；另核对 {counts['record_byte_checks']:,} 条恢复记录与对应数据库字节相等。所有固定布局的通信字节数不随 target 或重复变化，Flat-active 共享文件只计一次初始化。", "", "本次量纲：processing = 后端逐目标墙钟 + Python 路由 + 证明重组/验根。它是本地各组件测量之和，不是跨进程或网络服务的端到端墙钟。Go runner 的 warmup 是额外 5 次完整查询，不进入正式 100 条记录。", "", "## 配对性能结果", "", "比值是五次配对 run-mean 比值的均值，>1 表示 AB 更快。SD 和 t(df=4) 均值区间的统计单位是五个独立进程，不能把 500 个查询当作 500 次独立重复。区间是小样本、基于模型的描述性区间，不是稳定部署的保证。", "", "| Workload | AB ms mean ± SD | First-fit/AB | Hybrid/AB | Nonempty/AB | Routed/AB | Flat/AB |", "|---|---:|---:|---:|---:|---:|---:|"]
    gm={(r["dataset"],r["method"]):r for r in group_rows};pmat={(r["dataset"],r["baseline"]):r for r in paired_rows}
    for _,label in DATASETS:
        g=gm[label,"activebalance"]
        vals=[pmat[label,m]["processing_ratio_mean"] for m in ("first_fit","hybrid","nonempty_depth","pbc_routed","flat_active")]
        lines.append(f"| {label} | {g['processing_mean_ms_mean']:.3f} ± {g['processing_mean_ms_sample_sd']:.3f} | "+" | ".join(f"{v:.3f}" for v in vals)+" |")
    lines += ["", "## 必须保留的负结果和成本边界", ""]
    slower=[r for r in paired_rows if r["processing_ratio_mean"]<1]
    for r in slower:lines.append(f"- {r['dataset']}：{LABELS[r['baseline']]} / AB = {r['processing_ratio_mean']:.3f}，AB 在该配对均值指标下更慢；比值的 t 均值区间为 [{r['processing_ratio_mean_ci95_low']:.3f}, {r['processing_ratio_mean_ci95_high']:.3f}]。")
    if not slower:lines.append("- 这批样本中没有配对均值比值小于 1 的方法；仍不代表全部输入上的支配性结果。")
    lines += ["", "通信的负结果必须与时延分开描述（比值为 baseline/AB，<1 表示 AB 通信更多）：", "", "| Workload | First-fit/AB bytes | Hybrid/AB bytes | Nonempty/AB bytes | Routed/AB bytes | Flat/AB bytes |", "|---|---:|---:|---:|---:|---:|"]
    for _,label in DATASETS:
        vals=[pmat[label,m]["communication_ratio"] for m in ("first_fit","hybrid","nonempty_depth","pbc_routed","flat_active")]
        lines.append(f"| {label} | "+" | ".join(f"{v:.3f}" for v in vals)+" |")
    lines += ["", "AB 通信量高于 First-fit 的全部六组，也高于 Nonempty-depth 的五组。更小的 max bucket 和更少的逻辑查询槽不保证更少的总通信；本次 SimplePIR 参数选择与分块的非线性总费用是必须保留的实现边界。桶最大值优化不是串行总时延或总通信的优化定理。"]
    lines += ["", "| Workload | AB online KiB | Hint KiB | Public A KiB | Directory+index KiB | Full-cache bootstrap KiB | (Hint+directory)/full-cache |", "|---|---:|---:|---:|---:|---:|---:|"]
    for _,label in DATASETS:
        r=gm[label,"activebalance"]
        values=[r[f]/1024 for f in ("online_bytes","offline_hint_bytes","public_shared_state_bytes","client_metadata_bytes","full_cache_bootstrap_bytes")]
        lines.append(f"| {label} | "+" | ".join(f"{v:.2f}" for v in values)+f" | {r['hint_plus_directory_over_full_cache']:.2f} |")
    lines += ["", "- Full-cache 是一次下载完整 active digests 后本地验证的隐私参照；它有零在线请求，下载时间未测，local p50/p95 来自每个数据集一次最多 1,000 目标的独立参考检查，不能作为五进程配对延迟胜负表。现有样本下 SimplePIR hint 加目录显著大于 full-cache 材料，必须如实报告，不能声称 AB 的总客户端存储小于全量缓存。", "- public_shared_state_bytes 是当前 Init 实际物化的共享 A 矩阵元素空间，与数据库相关的 hint 分开；可压缩 seed 重建属于另外的实现路径。本次没有使用 InitCompressedSeeded，也没有测网络传输，不能把 A/H/metadata 之和称为实测下载量。", "- backend setup wall 包含读记录、参数选择、MakeDB、Init 和 Setup；Setup API 单列。它不包含整个 SMT 构建、AB 预处理、PBC 对所有 occupied targets 的匹配预检、元数据发布。layout_setup.json 只提供单次构建/预检时间，不应与五进程 backend setup 混作同一重复实验。", "- 所有六个 routed three-choice 布局均在公开 setup 中预检全部 occupied targets；这里是作者实现的三选择复制和最大二分匹配控制，不是原版 SealPIR 可执行系统，也不是原论文性能复现。失败/重试事实见下表。", "", "| Workload | PBC public setup attempts | Last failed targets / tested targets | Preflight ms (one observation) |", "|---|---:|---:|---:|"]
    for _,label in DATASETS:
        p=layouts[label]["pbc"];a=p["public_setup_attempts"]
        lines.append(f"| {label} | {len(a)} | {a[-1]['failed_targets']} / {a[-1]['tested_targets']} | {p['routing_preflight_ms']:.3f} |")
    lines += ["", "- RSS 是同一个 Go 进程里 server/client 合并运行的峰值，读取于结果 JSON 序列化之前，不能标为客户端内存，也不包含 Python verifier。", "- 树仍是以实际工作负载坐标和确定性实验值建立的二叉 SMT；不是链原生状态值/原生哈希格式。网络、并发服务、跨 epoch 和恶意服务器隐私组合未实测。", "", "产物：generated/verified_backend_summary.csv/.json、verified_backend_paired_ratios.csv、verified_backend_run_ratios.csv、main_verified_backend_table.tex、supp_verified_backend_table.tex。所有数值表由此脚本从原始记录重建。"]
    (args.notes/"verified_backend_findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"audit":"passed","runs":len(audited),"counts":dict(counts),"summary_rows":len(group_rows),"paired_groups":len(paired_rows)},ensure_ascii=False))


if __name__=="__main__":main()
