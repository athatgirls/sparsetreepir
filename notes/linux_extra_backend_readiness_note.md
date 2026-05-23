# Linux extra backend readiness

| category | item | ready | detail |
|---|---|---:|---|
| path | TreePIR artifact | yes | `/home/thighlight/Desktop/paper/sparsetreepir/external/TreePIR-main` |
| path | TreePIR indexing | yes | `/home/thighlight/Desktop/paper/sparsetreepir/external/TreePIR-main/TreePIR-Indexing` |
| path | Spiral checkout | yes | `/home/thighlight/Desktop/paper/sparsetreepir/.tools/spiral` |
| path | YPIR checkout | yes | `/home/thighlight/Desktop/paper/sparsetreepir/.tools/ypir` |
| path | VBPIR checkout | yes | `/home/thighlight/Desktop/paper/sparsetreepir/.tools/vectorized_batchpir` |
| path | SealPIR checkout | yes | `/home/thighlight/Desktop/paper/sparsetreepir/.tools/SealPIR` |
| command | git | yes | `/home/thighlight/.local/bin/git` |
| command | python3 | yes | `/usr/bin/python3` |
| command | java | yes | `/usr/bin/java` |
| command | javac | yes | `/usr/bin/javac` |
| command | cmake | yes | `/usr/bin/cmake` |
| command | g++ | yes | `/usr/bin/g++` |
| command | clang++ | no | `` |
| command | docker | no | `` |
| command | go | yes | `/home/thighlight/.local/bin/go` |
| hardware | AVX-512 for YPIR | no | `required for the current YPIR route; check lscpu flags` |

Interpretation:

- TreePIR indexing is the lightest extra artifact check and should work once Java and `external/TreePIR-main` are present.
- Spiral and VBPIR need backend-specific build steps from the TreePIR/Spiral/VBPIR artifacts.
- YPIR should only be attempted on a machine with AVX-512 support.
- SealPIRplus is a service/orchestrator route and requires heavier SEAL/gRPC/Protobuf setup.
