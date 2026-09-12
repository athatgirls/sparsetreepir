# Third-party source and notices

The following notices apply to the corresponding bundled components. No additional repository-wide license is declared for project-owned code in this release.

| Component | Pinned source / version | Notice in this release |
|---|---|---|
| SimplePIR | `ahenzinger/simplepir`, commit `e9020b03bf2872c75b8954e749e32408b5db87ed` | `examples/tifs_simplepir_extension_20260911/backend/upstream/simplepir/LICENSE`; earlier core copy under `.tools/simplepir/simplepir-main/LICENSE` |
| TreePIR / distributed VBPIR components | `PIR-PIXR/TreePIR`, commit `930063c5aefc441244abb4890fdf35383f3aa956` | `examples/tifs_external_extension_20260911/native_adapter/vendor/UPSTREAM_LICENSE`; original notices accompany the retained source copies |
| Gson | 2.10.1 JAR used by the official CSA control | `licenses/GSON-2.10.1-LICENSE.txt`, Apache License 2.0; obtained from the [official release tag](https://github.com/google/gson/blob/gson-parent-2.10.1/LICENSE) |
| RapidJSON | Included headers identify version 1.1.0 | `licenses/RAPIDJSON-1.1.0-LICENSE.txt`, including the upstream component notices; obtained from the [official release tag](https://github.com/Tencent/rapidjson/blob/v1.1.0/license.txt) |

Original copyright and license comments in source/header files are retained. Machine paths originating in pinned third-party sources are historical upstream examples, not publication-author information.

Microsoft SEAL 4.3.2 is a build dependency fetched by the optional build helper at commit `e3476fad1d5bb5e5222c51a551b5a4d7e2cb4f91`; its source and notices remain in the user's separate build directory. OpenSSL, Go, compiler, Python, NumPy, and Matplotlib are external dependencies rather than redistributed installations.
