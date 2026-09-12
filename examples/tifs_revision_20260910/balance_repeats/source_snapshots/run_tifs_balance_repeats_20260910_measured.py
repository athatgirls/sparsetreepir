"""Sequential independent-process repeats, reusing disclosed screening run 1."""
from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

import run_tifs_balance_study_20260910 as study

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples/tifs_revision_20260910/balance_repeats"
MANUSCRIPT = ROOT / "manuscripts/tifs/revision_20260910"


def memory(handle):
    if os.name != "nt":
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                "PagefileUsage", "PeakPagefileUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if psapi.GetProcessMemoryInfo(wintypes.HANDLE(int(handle)), ctypes.byref(counters), counters.cb):
        return int(counters.PeakWorkingSetSize)
    return None


def configs():
    originals = [c for c in study.configurations("real") if c["algorithm"] in ("ab-hungarian", "ab-sorted")]
    originals += [c for c in study.configurations("refinement") if c["n"] == 100000 and c["distribution"] == "uniform"]
    result = []
    for original in originals:
        for repeat in (1, 2, 3):
            config = dict(original)
            config.update(repeat=repeat, id=original["id"].rsplit("_r", 1)[0] + f"_r{repeat}")
            result.append(config)
    return result


def execute(timeout=120):
    OUT.mkdir(parents=True, exist_ok=True)
    plan = configs()
    study.write_json(OUT / "plan.json", dict(configurations=plan, sequential=True,
                    timeout_s=timeout, repeat_1="Existing independent screening process, copied with original result SHA-256 and provenance.",
                    repeat_2_and_3="New independent processes after the main PIR benchmark completed."))
    source_paths = [Path(__file__), Path(study.__file__), ROOT / "scripts/run_height_sparsity_profile_balance_experiment.py",
                    ROOT / "scripts/run_sparse_smt_pir_backend_experiment.py", ROOT / "scripts/generate_full_sparse_smt_example.py"]
    source_paths += sorted({ROOT / c["source"] for c in plan if "source" in c})
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    study.write_json(OUT / "source_manifest.json", source_hashes)
    cpu = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"],
                         capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    study.write_json(OUT / "environment.json", dict(platform=platform.platform(), python=sys.version, host=platform.node(),
                    processor=platform.processor(), cpu_cim=cpu.stdout.strip(), cpu_cim_exit=cpu.returncode,
                    cpu_affinity="not pinned", isolation="No other planned heavy benchmark during fresh repeats; ordinary workstation activity not disabled.",
                    memory="Windows WorkingSet/PeakWorkingSet includes interpreter/imports; parent also samples high-water every 0.5 s for new repeats.",
                    timing="coloring_s excludes separately measured checkpoint validation and file IO; subprocess_wall_s includes all startup/output costs."))
    for config in plan:
        directory = OUT / "runs" / config["id"]
        if (directory / "result.json").exists():
            print("SKIP " + config["id"], flush=True)
            continue
        directory.mkdir(parents=True, exist_ok=True)
        study.write_json(directory / "config.json", config)
        if config["repeat"] == 1:
            old = study.OUT / "runs" / config["id"]
            assert (old / "result.json").exists(), old
            for name in ("checkpoint.json", "round_history.json", "stdout.txt", "stderr.txt"):
                if (old / name).exists():
                    shutil.copyfile(old / name, directory / name)
            result = json.loads((old / "result.json").read_text(encoding="utf-8"))
            result.update(measurement_origin="screening_run_reused_as_repeat_1", reused_from=str(old.relative_to(ROOT)),
                          archived_original_result_sha256=hashlib.sha256((old / "result.json").read_bytes()).hexdigest())
            study.write_json(directory / "result.json", result)
            print("REUSED " + config["id"], flush=True)
            continue
        start = time.monotonic()
        sampled_peak = None
        status = "complete"
        with (directory / "stdout.txt").open("w", encoding="utf-8") as stdout, (directory / "stderr.txt").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen([sys.executable, str(Path(study.__file__).resolve()), "--worker", str(directory / "config.json")],
                        cwd=ROOT, stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            while process.poll() is None:
                current = memory(process._handle) if os.name == "nt" else None
                if current is not None:
                    sampled_peak = max(sampled_peak or 0, current)
                if time.monotonic() - start >= timeout:
                    process.kill()
                    process.wait()
                    status = "timeout"
                    break
                try:
                    process.wait(timeout=min(0.5, max(0.01, timeout - (time.monotonic() - start))))
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode and status != "timeout":
                status = "failed"
        result_path = directory / "result.json"
        checkpoint = directory / "checkpoint.json"
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        elif checkpoint.exists():
            result = json.loads(checkpoint.read_text(encoding="utf-8"))
        else:
            result = dict(config)
        result.update(status=status, subprocess_wall_s=time.monotonic() - start, timeout_limit_s=timeout,
                      exit_code=process.returncode, measurement_origin="fresh_repeat_after_PIR_benchmark",
                      external_observed_peak_rss_bytes=sampled_peak,
                      external_peak_scope="OS process high-water sampled every 0.5s while alive; final subsecond interval may not be sampled.",
                      source_hashes=source_hashes,
                      last_completed_checkpoint_only=status != "complete")
        study.write_json(result_path, result)
        print(f"{status.upper()} {config['id']} wall={result['subprocess_wall_s']:.2f}s passes={result.get('actual_passes')} U/B={result.get('U_over_B')}", flush=True)
        summarize()
    summarize()


def stat(values):
    return dict(n=len(values), mean=statistics.mean(values), sample_sd=statistics.stdev(values) if len(values) > 1 else None,
                minimum=min(values), maximum=max(values)) if values else None


def summarize():
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT / "runs").glob("*/result.json"))]
    if not rows:
        return
    fields = sorted(set().union(*(r.keys() for r in rows)))
    with (OUT / "per_run.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)
    groups = {}
    for row in rows:
        key = (row.get("label", "uniform100k"), row["algorithm"])
        groups.setdefault(key, []).append(row)
    summaries = []
    for (label, algorithm), chosen in sorted(groups.items()):
        chosen.sort(key=lambda r: r["repeat"])
        complete = [r for r in chosen if r["status"] == "complete"]
        peaks = [max(r.get("peak_rss_bytes") or 0, r.get("external_observed_peak_rss_bytes") or 0) / 2 ** 20 for r in chosen]
        summary = dict(label=label, algorithm=algorithm, attempts=len(chosen), completed=len(complete),
                       censored=sum(r["status"] == "timeout" for r in chosen), failed=sum(r["status"] == "failed" for r in chosen),
                       coloring_s_complete_only=stat([r["coloring_s"] for r in complete]),
                       subprocess_s_complete_only=stat([r["subprocess_wall_s"] for r in complete]),
                       observed_peak_RSS_MiB=stat(peaks), completed_scan_rounds=[r.get("actual_passes") for r in chosen],
                       accepted_moves=[r.get("actual_moves") for r in chosen], endpoint_max_buckets=[r.get("max_bucket") for r in chosen],
                       endpoint_U_over_B=[r.get("U_over_B") for r in chosen],
                       validity=[r.get("valid") for r in chosen],
                       equal_quality_completed_runs=len({tuple(sorted(r["loads"])) for r in complete}) <= 1,
                       same_key_hash=len({r.get("key_sha256") for r in chosen}) == 1,
                       timeout_limits=[r["timeout_limit_s"] for r in chosen if r["status"] == "timeout"],
                       individual_statuses=[r["status"] for r in chosen])
        assert all(v is True for v in summary["validity"]), summary
        assert summary["same_key_hash"], summary
        summaries.append(summary)
    study.write_json(OUT / "summary.json", dict(total=len(rows), complete=sum(r["status"] == "complete" for r in rows),
                    censored=sum(r["status"] == "timeout" for r in rows), groups=summaries,
                    statistical_scope="Three independent process executions of the same deterministic layout per full group; repeat 1 explicitly reused. sample SD, no claimed CI; censored rows never averaged as completed times."))
    if len(rows) == 42:
        write_findings(summaries)


def write_findings(summaries):
    groups = {(r["label"], r["algorithm"]): r for r in summaries}
    order = [("fuel", "Fuel vectors"), ("polygon-recent", "Polygon recent"), ("zksync-sample", "ZKsync sample"),
             ("polygon-multi", "Polygon multi"), ("polygon-broad", "Polygon broad"), ("zksync-broad", "ZKsync broad")]
    def ms(statistic):
        return f"{statistic['mean']:.4f} +/- {statistic['sample_sd']:.4f}"
    def texstat(statistic, digits=3):
        return r"\(" + f"{statistic['mean']:.{digits}f}\\pm{statistic['sample_sd']:.{digits}f}" + r"\)"
    lines = ["# ActiveBalance 独立进程稳定性重复（2026-09-10）", "",
             "共42次独立进程测量：六个固定真实key workload × 原Hungarian/反向排序 × 3次，以及100k uniform × 两种算法 × 3次。每组第1次明确复用此前筛查阶段的独立进程结果；第2/3次在主要PIR基准结束后重新执行，所有性能子进程串行。每组输入seed/key哈希保持一致，历史结果未修改。", "",
             "结果目录：`examples/tifs_revision_20260910/balance_repeats/`，含逐次result/checkpoint/round_history/stdout/stderr、source_manifest和environment。原始来源路径和result SHA-256记录在复用行。", "",
             "## 六个真实workload", "", "各算法最多20次扫描，完成指完成请求的算法过程（可能达到上限），不自动表示整个负载向量局部收敛。coloring秒为算法时间，排除单独计量的checkpoint校验和写文件；并非PIR在线耗时，也不包含提取器构建。表内为均值±样本标准差，n=3。", "",
             "| Workload | Old max | Sort max | Old 秒 | Sort 秒 | mean时间比 | Old观察peak RSS MiB | Sort观察peak RSS MiB |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    table = [r"\begin{table}[H]", r"\centering", r"\caption{Independent-process stability of the count-only ActiveBalance implementations on six fixed height-128 key workloads. Old uses Hungarian assignment; Sort uses reverse pairing. Each has a 20-scan cap.}", r"\label{tab:supp_balance_repeats}", r"\footnotesize", r"\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{lrrrrrr}", r"\toprule", r"Workload & Old max & Sort max & Old s & Sort s & Old MiB & Sort MiB \\", r"\midrule"]
    for label, display in order:
        old, new = groups[label, "ab-hungarian"], groups[label, "ab-sorted"]
        oldtime, newtime = old["coloring_s_complete_only"], new["coloring_s_complete_only"]
        oldmax, newmax = old["endpoint_max_buckets"][0], new["endpoint_max_buckets"][0]
        ratio = oldtime["mean"] / newtime["mean"]
        lines.append(f"| {display} | {oldmax} | {newmax} | {ms(oldtime)} | {ms(newtime)} | {ratio:.2f} | {ms(old['observed_peak_RSS_MiB'])} | {ms(new['observed_peak_RSS_MiB'])} |")
        table.append(f"{display} & {oldmax} & {newmax} & {texstat(oldtime)} & {texstat(newtime)} & {texstat(old['observed_peak_RSS_MiB'], 1)} & {texstat(new['observed_peak_RSS_MiB'], 1)} " + r"\\")
    table += [r"\bottomrule", r"\end{tabular}", r"\par\smallskip\parbox{\linewidth}{\footnotesize Entries are mean $\pm$ sample SD across three independent process executions; the earlier screening execution is explicitly reused as repetition 1, with two new repetitions. Maxima count records. Coloring time excludes separately timed checkpoint validation and file I/O, and is not PIR latency. MiB measures observed process peak working set including the interpreter and imports. All completed repeats preserve the same input key hash and produce valid colorings with identical within-method load signatures. The six-workload PIR benchmark uses Old layouts; Sort is a separate construction study.}", r"\end{table}", ""]
    old, new = groups["uniform100k", "ab-hungarian"], groups["uniform100k", "ab-sorted"]
    lines += ["", "## 100k：完成值和删失值分开", "",
              f"排序AB完成 {new['completed']}/3 次，coloring时间 {ms(new['coloring_s_complete_only'])} 秒；含启动/提取/输出的进程墙钟 {ms(new['subprocess_s_complete_only'])} 秒。每次完成扫描轮数 {new['completed_scan_rounds']}，终点最大桶 {new['endpoint_max_buckets']}，U/B={new['endpoint_U_over_B']}。", "",
              f"原AB完成 {old['completed']}/3 次，{old['censored']}/3 次在120秒上限右删失；最后完成扫描轮数 {old['completed_scan_rounds']}、最后有效U/B={old['endpoint_U_over_B']}。这些是被中止前的中间状态，不是20轮的质量。没有把120秒平均成算法完成时间，也没有用它计算一个精确speedup。", "",
              f"排序观察peak RSS为 {ms(new['observed_peak_RSS_MiB'])} MiB；原版为 {ms(old['observed_peak_RSS_MiB'])} MiB。原版删失执行的RSS仅是被停止前的可观察高水位，不能称完整20轮的峰值。", "",
              "## 有效性和限制", "", "每组key哈希一致；全部保存的完整/部分checkpoint通过同色interval不相交验证。每算法完成的重复产生相同降序负载签名。不同算法的平局路径仍可能不同，不能由六个真实workload最终最大桶一致推断任意输入/轮数都等价。", "",
              "Windows过程WorkingSet/PeakWorkingSet包含Python和imports；新重复由父进程每0.5秒采样OS高水位，同时保留worker checkpoint测量。复用第1次没有外部采样，明确保留原观察口径。未固定CPU affinity，也未禁用一般工作站活动；无并发计划中的重基准。三个重复给出过程噪声的样本SD，不代表不同snapshot或独立target分布的不确定性。", "",
              "最重要的可用结论：排序法减少当前实现的构造计算，但没有改变width；100k确实执行完整20轮而不是hybrid代替。PIR通信/在线延迟的增益仍须用独立backend实验支持。"]
    table += [r"\begin{table}[H]", r"\centering", r"\caption{Three-process repetition at 100\,000 uniform occupied coordinates and height 128, with a 20-scan target and a 120-s process limit. Censored runs are not treated as completed timings.}", r"\label{tab:supp_balance_repeats_scale}", r"\footnotesize", r"\setlength{\tabcolsep}{4pt}", r"\begin{tabular}{lcccl}", r"\toprule", r"Method & Complete & Coloring s & Finished scans & Endpoint $U/B$ \\", r"\midrule",
              "Old / Hungarian & " + f"{old['completed']}/3" + r" & censored at 120 s & " + ",".join(map(str, old["completed_scan_rounds"])) + " & " + ",".join(f"{x:.4f}" for x in old["endpoint_U_over_B"]) + r" \\",
              "Sort / reverse pairing & " + f"{new['completed']}/3" + " & " + texstat(new["coloring_s_complete_only"]) + " & " + ",".join(map(str, new["completed_scan_rounds"])) + " & " + ",".join(f"{x:.4f}" for x in new["endpoint_U_over_B"]) + r" \\",
              r"\bottomrule", r"\end{tabular}", r"\par\smallskip\parbox{\linewidth}{\footnotesize Old endpoints are the last validated partial states before timeout, not 20-scan results. The 120-s bound covers the complete process, including imports, extraction, checkpoint validation, and output; it is not a completed coloring time. The Sort timing is mean $\pm$ sample SD for three completed executions. Repetition 1 is reused from the screening stage.}", r"\end{table}", ""]
    (MANUSCRIPT / "notes/balance_repeats_findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (MANUSCRIPT / "generated/supp_balance_repeats_table.tex").write_text("\n".join(table), encoding="utf-8")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    summarize() if args.summarize else execute(args.timeout)
