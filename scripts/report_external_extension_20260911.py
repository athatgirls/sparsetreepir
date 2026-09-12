"""Publication figures and a concise evidence report for verified external runs."""
from pathlib import Path
import json
import math
import statistics
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_external_extension_20260911'
OUT = BASE / 'analysis'
LABELS = {'ab': 'SparseTreePIR (AB)', 'pbc': 'VBPIR-PBC', 'treepir': 'Official TreePIR CSA'}
COLORS = {'ab': '#0072B2', 'pbc': '#D55E00', 'treepir': '#009E73'}
MARKERS = {'ab': 'o', 'pbc': 's', 'treepir': '^'}


def main():
    evidence = json.loads((OUT / 'results.json').read_text(encoding='utf8'))
    verified = json.loads((OUT / 'INDEPENDENT_VERIFICATION.json').read_text(encoding='utf8'))
    rows = evidence['aggregates']
    by = {(r['case'], r['method']): r for r in rows}
    snapshots = {p.parent.name: json.loads(p.read_text(encoding='utf8')) for p in (BASE / 'inputs').glob('*/snapshot_summary.json')}
    figures = OUT / 'figures'
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.labelsize': 9,
                         'legend.fontsize': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    uniform = sorted({r['case'] for r in rows if r['case'].startswith('uniform_')}, key=lambda c: snapshots[c]['n'])
    panels = [('serialized_proof_wall_ms', 1, 'Verified proof processing (ms)'),
              ('online_framed_bytes', 1024, 'Online serialized traffic (KiB)'),
              ('ntt_coefficient_payload_bytes', 1024**2, 'Encoded database coefficients (MiB)')]
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.0))
    for ax, (key, unit, ylabel) in zip(axes, panels):
        for method in ['ab', 'pbc']:
            rr = [by[c, method] for c in uniform if (c, method) in by]
            ax.errorbar([r['n'] for r in rr], [r[key + '_mean'] / unit for r in rr],
                        yerr=[(r[key + '_sd'] or 0) / unit for r in rr], label=LABELS[method],
                        color=COLORS[method], marker=MARKERS[method], linewidth=1.4, capsize=3)
        ax.set_xscale('log')
        ax.set_xlabel('Occupied leaves')
        ax.set_ylabel(ylabel)
        ax.grid(alpha=.22)
        if key == 'online_framed_bytes':
            ax.set_ylim(bottom=0)
            if all(by[c, 'ab'][key + '_mean'] == by[c, 'pbc'][key + '_mean'] for c in uniform):
                ax.text(.5, .42, 'AB and PBC coincide', transform=ax.transAxes,
                        ha='center', va='center', fontsize=9, color='#444444')
        elif key == 'ntt_coefficient_payload_bytes':
            ax.set_ylim(bottom=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(.5, 1.01))
    fig.tight_layout(rect=(0, 0, 1, .90))
    for ext in ['pdf', 'png']:
        fig.savefig(figures / f'external_scaling.{ext}', dpi=240, bbox_inches='tight')
    plt.close(fig)
    structure = [c for c in ['uniform_n10000', 'prefix64_n10000', 'cluster90_n10000'] if (c, 'ab') in by and (c, 'pbc') in by]
    names = {'uniform_n10000': 'Uniform', 'prefix64_n10000': 'Shared 64-bit prefix', 'cluster90_n10000': '90% prefix cluster'}
    fig, axes = plt.subplots(1, 2, figsize=(8.3, 3.0))
    for ax, (key, unit, ylabel) in zip(axes, [panels[0], panels[2]]):
        for offset, method in [(-.16, 'ab'), (.16, 'pbc')]:
            rr = [by[c, method] for c in structure]
            ax.bar([i + offset for i in range(len(rr))], [r[key + '_mean'] / unit for r in rr],
                   yerr=[(r[key + '_sd'] or 0) / unit for r in rr], width=.3,
                   color=COLORS[method], label=LABELS[method], capsize=3)
        ax.set_xticks(range(len(structure)), [names[c] for c in structure], fontsize=8)
        ax.set_ylabel(ylabel)
        ax.grid(axis='y', alpha=.22)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(.5, 1.01))
    fig.tight_layout(rect=(0, 0, 1, .90))
    for ext in ['pdf', 'png']:
        fig.savefig(figures / f'external_structure.{ext}', dpi=240, bbox_inches='tight')
    plt.close(fig)

    def ms(r, key='serialized_proof_wall_ms'):
        return f"{r[key + '_mean']:.2f} ± {r[key + '_sd']:.2f}"

    lines = ['# 稀疏证明批量检索：新增外部实验', '',
             f"已完成 {verified['process_results_verified']} 个独立进程、{verified['measured_proofs_verified']} 份计量证明；连同预热共 {verified['proofs_including_warmups_verified']} 份证明均通过独立认证根验证及篡改、错误坐标、错误值检查。每组使用 3 个进程，每进程 2 次预热和 10 个配对目标。下文误差为进程均值的样本标准差。", '',
             '比较的是**一份证明中的多个非默认节点**。双方使用相同树、32 字节记录、目标与根，默认节点由客户端恢复。共用官方 VBPIR 的 Client、Server 和 PirParams 核心；PBC 保留三哈希和 cuckoo 路由，AB 使用原 Hungarian 构造。实际执行了查询及回答的无压缩序列化、反序列化、恢复和验根。', '',
             '**计量范围：本地完整证明处理流程，无网络。** 在线列为真实构造和解析的密文帧字节。初始化列为已序列化的状态载荷，未称 TCP bootstrap。NTT 列只计编码数据库的系数载荷，不能替代服务器总内存；角色合并的进程峰值内存另存原始表。', '',
             '## 1. 有效叶子规模', '',
             '| 有效叶子 | 方法 | 证明处理 / ms | 在线 / KiB | 原始记录存储 / MiB | NTT 系数 / MiB |',
             '| ---: | --- | ---: | ---: | ---: | ---: |']
    for c in uniform:
        for m in ['ab', 'pbc']:
            r = by[c, m]
            lines.append(f"| {r['n']:,} | {LABELS[m]} | {ms(r)} | {r['online_framed_bytes_mean']/1024:.2f} | {r['replicated_record_payload_bytes_mean']/1024**2:.3f} | {r['ntt_coefficient_payload_bytes_mean']/1024**2:.2f} |")
    large_ab, large_pbc = by['uniform_n100000', 'ab'], by['uniform_n100000', 'pbc']
    large_comparison = next(c for c in evidence['comparisons'] if c['case'] == 'uniform_n100000' and c['comparator'] == 'pbc')
    reduction = 100 * (1 - large_ab['serialized_proof_wall_ms_mean'] / large_pbc['serialized_proof_wall_ms_mean'])
    lines += ['', f"在 100,000 个均匀哈希键的实例上，AB 将平均证明处理时间从 {large_pbc['serialized_proof_wall_ms_mean']:.2f} ms 降至 {large_ab['serialized_proof_wall_ms_mean']:.2f} ms，减少 {reduction:.1f}%；编码数据库系数载荷由 {large_pbc['ntt_coefficient_payload_bytes_mean']/1024**2:g} MiB 降为 {large_ab['ntt_coefficient_payload_bytes_mean']/1024**2:g} MiB。配对时间差（PBC−AB）的描述性 95% t 区间为 [{large_comparison['difference_ci95_low_ms']:.2f}, {large_comparison['difference_ci95_high_ms']:.2f}] ms。1,000 和 10,000 叶子的对应区间均跨过零，未确立延迟优势。三种均匀规模下双方在线字节数完全相同。", '',
              '![规模实验](figures/external_scaling.png)', '',
              'PBC 将每条记录存入三个候选桶，AB 每条仅存一次；这项原始存储差异由布局决定。后端编码存储、在线通信与延迟还受向量化分组及矩阵取整影响，应分别以表中的实测结果判断。', '',
              '## 2. 初始化与缓存参照', '',
              '| 有效叶子 | 方法 | 适配器初始化 / ms | 序列化初始化载荷 / MiB | 共同完整缓存载荷 / MiB |',
              '| ---: | --- | ---: | ---: | ---: |']
    for c in uniform:
        for m in ['ab', 'pbc']:
            r = by[c, m]
            full = r['active_digest_payload_bytes_mean'] + r['common_metadata_payload_bytes_mean']
            lines.append(f"| {r['n']:,} | {LABELS[m]} | {ms(r, 'persistent_setup_wall_ms')} | {r['setup_serialized_payload_bytes_mean']/1024**2:.3f} | {full/1024**2:.3f} |")
    lines += ['', '初始化包括输入解析、公开目录处理、PBC 分桶、服务端预处理、客户端密钥及其序列化往返；AB/CSA 离线布局构造另计，不能据此单列断言总初始化更快。完整缓存参照包含同一份公共元数据与全部有效摘要，不含 PIR 密钥或桶映射。这是固定快照载荷参照，未计量缓存网络服务延迟。', '',
              '在全部三个均匀快照上，PIR 序列化初始化载荷已大于完整缓存载荷。因此，这些结果支持相对通用 PBC 的布局和计算收益，不能支持固定快照下相对完整缓存的总通信优势。', '',
              'AB 原构造的单次输入生成记录：' + '；'.join(f"{snapshots[c]['n']:,} 叶子共 {snapshots[c]['build_layout_wall_s']:.2f} s（其中着色 {snapshots[c]['build_layout_stages_ms']['coloring']/1000:.2f} s）" for c in uniform) + '。这些是一次构造的观察值，不能与三进程均值混为同一统计量。', '',
              '## 3. 稀疏结构与完整树对照', '',
              '| 结构，10,000 叶子 | m | AB / ms | PBC / ms | AB / PBC 最大桶 |',
              '| --- | ---: | ---: | ---: | ---: |']
    for c in structure:
        ab, pbc = by[c, 'ab'], by[c, 'pbc']
        lines.append(f"| {names[c]} | {ab['m']} | {ms(ab)} | {ms(pbc)} | {ab['max_bucket']} / {pbc['max_bucket']} |")
    lines += ['', '![结构实验](figures/external_structure.png)', '',
              '| 完整树高度 | 方法 | 最大桶 | 证明处理 / ms | 在线 / KiB |',
              '| ---: | --- | ---: | ---: | ---: |']
    for c in ['complete_h10', 'complete_h14']:
        for m in ['ab', 'treepir', 'pbc']:
            if (c, m) in by:
                r = by[c, m]
                lines.append(f"| {snapshots[c]['height']} | {LABELS[m]} | {r['max_bucket']} | {ms(r)} | {r['online_framed_bytes_mean']/1024:.2f} |")
    lines += ['', 'TreePIR 保留官方 Java CSA 桶分配和原始桶内位置，SubCSA 已在全部完整树目标上核对。此处使用共同的在线目录适配器；它检验官方布局与 AB 在同一后端上的差别，**不代表官方快速索引或其零目录客户端状态的完整系统评估**。', '',
              '## 4. 结论边界与来源', '',
              '本轮可检验稀疏证明结构对真实 VBPIR 检索和存储的影响。每种结构/规模仅一个固定快照、固定密码参数与本地执行，不能推出所有部署的优势；三个进程给出的区间仅反映本机重复运行的不确定性。配对差值的 95% t 区间、分阶段时间及合并进程 RSS 见 CSV。', '',
              'Respire 已额外通过一个 64 条、32 字节记录的真实 query–answer–extract 功能检查；尚未完成同一 SMT 证明和完整计量，因此不纳入以上性能表。', '',
              '- [Vectorized Batch PIR 原论文实现](https://github.com/mhmughees/vectorized_batchpir)',
              '- [本轮实际采用的 TreePIR 仓库 VBPIR_PBC 源码](https://github.com/PIR-PIXR/TreePIR/tree/930063c5aefc441244abb4890fdf35383f3aa956/VBPIR_PBC)',
              '- [TreePIR Appendix J：已有稀疏树讨论](https://arxiv.org/html/2205.05211v5#A10)',
              '- [Respire 官方源码](https://github.com/AMACB/respire/tree/fd20d38e9e94c0298ab21af2f7699a23729eef67)',
              '', '完整协议、源码固定、适配内容与原始日志在实验包中保留。环境正文列 CPU、Ubuntu、GCC、SEAL、OpenSSL 版本；原始环境记录保持原样。', '']
    (OUT / '新增外部实验报告.md').write_text('\n'.join(lines), encoding='utf8')
    print(json.dumps({'report': str(OUT / '新增外部实验报告.md'), 'figures': [str(p) for p in figures.iterdir()]}))


if __name__ == '__main__':
    main()
