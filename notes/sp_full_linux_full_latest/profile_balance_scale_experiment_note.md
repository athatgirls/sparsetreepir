# Profile Balance Scale Experiment

```text
=== Profile-Balanced Scale Experiment ===
heights=[64, 128, 256]
occupied_counts=[100, 1000]
distributions=['uniform', 'clustered', 'adversarial']
trials_per_setting=3
initial_rounds=120
refine_rounds=20

[occupied_count=100]
height=64, occupied=100, dist=uniform: active_nodes=198.0, m=9.00, hybrid_max=25.67, profile_max=22.00, reduction=14.3%, hybrid_gap=12.33, profile_gap=0.00, runtime_ms=216.9, valid_rate=100.0%
height=64, occupied=100, dist=clustered: active_nodes=198.0, m=10.00, hybrid_max=22.67, profile_max=20.00, reduction=11.8%, hybrid_gap=12.33, profile_gap=1.00, runtime_ms=349.5, valid_rate=100.0%
height=64, occupied=100, dist=adversarial: active_nodes=198.0, m=12.00, hybrid_max=65.00, profile_max=24.00, reduction=63.1%, hybrid_gap=64.00, profile_gap=16.00, runtime_ms=431.3, valid_rate=100.0%
height=128, occupied=100, dist=uniform: active_nodes=198.0, m=9.33, hybrid_max=25.00, profile_max=21.33, reduction=14.7%, hybrid_gap=11.00, profile_gap=0.33, runtime_ms=322.7, valid_rate=100.0%
height=128, occupied=100, dist=clustered: active_nodes=198.0, m=10.33, hybrid_max=22.00, profile_max=19.33, reduction=12.1%, hybrid_gap=8.67, profile_gap=0.67, runtime_ms=404.9, valid_rate=100.0%
height=128, occupied=100, dist=adversarial: active_nodes=198.0, m=12.00, hybrid_max=65.00, profile_max=24.00, reduction=63.1%, hybrid_gap=64.00, profile_gap=16.00, runtime_ms=432.8, valid_rate=100.0%
height=256, occupied=100, dist=uniform: active_nodes=198.0, m=8.67, hybrid_max=28.33, profile_max=23.00, reduction=18.8%, hybrid_gap=15.67, profile_gap=0.33, runtime_ms=185.5, valid_rate=100.0%
height=256, occupied=100, dist=clustered: active_nodes=198.0, m=10.33, hybrid_max=22.67, profile_max=19.33, reduction=14.7%, hybrid_gap=11.33, profile_gap=0.67, runtime_ms=392.6, valid_rate=100.0%
height=256, occupied=100, dist=adversarial: active_nodes=198.0, m=12.00, hybrid_max=65.00, profile_max=24.00, reduction=63.1%, hybrid_gap=64.00, profile_gap=16.00, runtime_ms=432.1, valid_rate=100.0%

[occupied_count=1000]
height=64, occupied=1000, dist=uniform: active_nodes=1998.0, m=14.00, hybrid_max=168.67, profile_max=143.67, reduction=14.8%, hybrid_gap=81.00, profile_gap=1.00, runtime_ms=6419.6, valid_rate=100.0%
height=64, occupied=1000, dist=clustered: active_nodes=1998.0, m=14.33, hybrid_max=167.67, profile_max=140.67, reduction=16.1%, hybrid_gap=81.67, profile_gap=10.33, runtime_ms=6131.4, valid_rate=100.0%
height=64, occupied=1000, dist=adversarial: active_nodes=1998.0, m=18.00, hybrid_max=522.00, profile_max=160.00, reduction=69.3%, hybrid_gap=520.00, profile_gap=125.00, runtime_ms=7686.5, valid_rate=100.0%
height=128, occupied=1000, dist=uniform: active_nodes=1998.0, m=13.67, hybrid_max=173.33, profile_max=146.67, reduction=15.4%, hybrid_gap=89.33, profile_gap=1.00, runtime_ms=5547.4, valid_rate=100.0%
height=128, occupied=1000, dist=clustered: active_nodes=1998.0, m=14.00, hybrid_max=167.67, profile_max=143.67, reduction=14.3%, hybrid_gap=91.33, profile_gap=6.67, runtime_ms=5504.1, valid_rate=100.0%
height=128, occupied=1000, dist=adversarial: active_nodes=1998.0, m=18.00, hybrid_max=522.00, profile_max=160.00, reduction=69.3%, hybrid_gap=520.00, profile_gap=125.00, runtime_ms=7672.9, valid_rate=100.0%
height=256, occupied=1000, dist=uniform: active_nodes=1998.0, m=13.33, hybrid_max=182.00, profile_max=150.33, reduction=17.4%, hybrid_gap=84.67, profile_gap=1.00, runtime_ms=5306.0, valid_rate=100.0%
height=256, occupied=1000, dist=clustered: active_nodes=1998.0, m=14.67, hybrid_max=149.67, profile_max=138.67, reduction=7.3%, hybrid_gap=73.00, profile_gap=23.00, runtime_ms=6303.8, valid_rate=100.0%
height=256, occupied=1000, dist=adversarial: active_nodes=1998.0, m=18.00, hybrid_max=522.00, profile_max=160.00, reduction=69.3%, hybrid_gap=520.00, profile_gap=125.00, runtime_ms=7692.9, valid_rate=100.0%

latex_table_rows:
64 & uniform & 198.0 & 9.00 & 25.67 & 22.00 & 14.3\% & 0.00 & 216.9 \\
64 & clustered & 198.0 & 10.00 & 22.67 & 20.00 & 11.8\% & 1.00 & 349.5 \\
64 & adversarial & 198.0 & 12.00 & 65.00 & 24.00 & 63.1\% & 16.00 & 431.3 \\
128 & uniform & 198.0 & 9.33 & 25.00 & 21.33 & 14.7\% & 0.33 & 322.7 \\
128 & clustered & 198.0 & 10.33 & 22.00 & 19.33 & 12.1\% & 0.67 & 404.9 \\
128 & adversarial & 198.0 & 12.00 & 65.00 & 24.00 & 63.1\% & 16.00 & 432.8 \\
256 & uniform & 198.0 & 8.67 & 28.33 & 23.00 & 18.8\% & 0.33 & 185.5 \\
256 & clustered & 198.0 & 10.33 & 22.67 & 19.33 & 14.7\% & 0.67 & 392.6 \\
256 & adversarial & 198.0 & 12.00 & 65.00 & 24.00 & 63.1\% & 16.00 & 432.1 \\
```
