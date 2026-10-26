# Verified toolchain inventory — version probes only

Slither **0.11.6** and all **30** compiler versions actually required by the frozen plans are provisioned in ignored `data/derived/security_toolchain_v1/`. Artifact checksums, installed versions and full Solidity build identifiers pass verification. The original seven integrity/invocation tests and seven additional verifier-hardening tests pass. No contract was compiled, no Slither analysis ran and no external score was produced. This closes executable-inventory preparation only; semantic sign-off and successful compilation/analysis coverage remain unestablished.

The compiler plan contains 2,689 source rows: 682 training and 1,968 external files have candidate versions, totalling 2,650 planned rows and 3,900 ordered candidate slots. The remaining 39 rows remain unavailable. The initial five dominant releases are insufficient for exact-pragma files; the installed union is:

| Series | Required installed releases |
|---|---|
| 0.4 | 0.4.19, 0.4.21, 0.4.24, 0.4.25, 0.4.26 |
| 0.5 | 0.5.0, 0.5.2, 0.5.8, 0.5.17 |
| 0.6 | 0.6.0, 0.6.9, 0.6.10, 0.6.11, 0.6.12 |
| 0.7 | 0.7.0, 0.7.4, 0.7.5, 0.7.6 |
| 0.8 | 0.8.0, 0.8.4, 0.8.5, 0.8.6, 0.8.7, 0.8.8, 0.8.9, 0.8.10, 0.8.11, 0.8.12, 0.8.13, 0.8.26 |

`compiler_plans.csv` remains unchanged, including each file's ordered candidate list; its SHA256 is `e6db64c3b1061ab86944b412c73743ba897cbbc710b77963398ca746a2fb5e38`. No historical catalog, main environment or frozen protocol was changed.

## Artifact authority and verification

The [official Solidity installation documentation](https://docs.soliditylang.org/en/latest/installing-solidity.html#static-binaries) identifies `solc-bin` and describes verification using each platform's `list.json` SHA256 values. The primary `binaries.soliditylang.org` URL returned HTTP 403 in this runtime. The documented [official repository](https://github.com/argotorg/solc-bin) was used instead, pinned to commit `c04c6cdc827bbdcc7bd65689fa76b63a238b223f`.

The downloaded [linux-amd64 list](https://raw.githubusercontent.com/argotorg/solc-bin/c04c6cdc827bbdcc7bd65689fa76b63a238b223f/linux-amd64/list.json) has SHA256 `b44c1d0e598ed0bcbf4ee49c86c5ae85b63718c1591689b02d12d7a11d45a2ac`. Every release is selected through `releases[version]`, matched to its release build record, downloaded by an immutable commit URL, and checked against the official SHA256 before execution permission is set. The full output of `--version`, including commit identity, is recorded and checked against `longVersion`. Official Keccak values are recorded but not independently calculated; SHA256 is the integrity check performed.

The [official PyPI release](https://pypi.org/project/slither-analyzer/0.11.6/) supplies the Slither wheel. Its SHA256 is `01f809198d3f171e2d768569c0054c96af5736614e183c64f42c9b51636c33c1`. All 47 wheels, including Slither and 46 dependencies, were downloaded from explicit public PyPI, checked against their version-specific official PyPI JSON metadata, then installed offline with `--require-hashes`. `pip check` reports no broken requirements. PyPI reports Trusted Publishing for Slither; this task did not independently verify Sigstore attestations and does not claim a package security audit.

The environment is Linux x86_64, Python 3.12.14, with system site-packages disabled. The dependency lock is platform-specific. The venv bootstrap pip version, 25.0.1, is recorded in `installed_freeze.txt` separately from the 47 runtime dependency wheels. The interpreter binary hash is recorded in `slither_inventory.json`.

## Inventory and execution boundaries

- `manifest.json`: planner/code hashes, artifact metadata hashes and explicit non-readiness flags.
- `solc_download_plan.json` and `solc_inventory.json`: official metadata snapshot identity, all 30 download URLs, artifact SHA256/size and actual version-probe outputs.
- `required_version_inventory.csv`: per-version candidate counts by cohort and full-build identity checks.
- `python_artifacts.json`: all 47 wheel URLs, filenames, hashes, versions and official metadata URLs/hashes.
- `requirements.lock` and `installed_freeze.txt`: exact runtime dependency artifacts and complete installed distribution versions.
- `slither_inventory.json`: executable/interpreter identity, isolated environment and `pip check`/version output.

Compiler paths are `data/derived/security_toolchain_v1/solc/solc-VERSION`. Slither is `data/derived/security_toolchain_v1/python_env/bin/slither`. Future explicitly authorized integration must pass the selected compiler's absolute path; ambient `solc`, PATH order and `solc-select` state are not verified selection mechanisms. The installed `solc-select` dependency was not used to choose or download compilers.

The only invocations of solc and Slither were `[binary, '--version']`, with standard input disabled. Source pragmas alone do not establish compatibility of imports or build settings; installed candidates do not establish actual compiler or detector success. The 39 unavailable plan rows and all external review/scoring gates remain unchanged.

## Reproduction and checks

The saved lock supports exact dependency downloads on the recorded platform:

```bash
python -m pip download --only-binary=:all: --require-hashes --index-url https://pypi.org/simple --dest data/derived/security_toolchain_v1/wheelhouse -r papers/security_evaluation/revision1/external_protocol/toolchain_v1/requirements.lock
python papers/security_evaluation/revision1/external_protocol/toolchain_v1/provision_toolchain.py slither
python papers/security_evaluation/revision1/external_protocol/toolchain_v1/verify_toolchain_v2.py
python -m pytest -q papers/security_evaluation/revision1/external_protocol/toolchain_v1/test_toolchain.py
```

For an exact compiler reinstall, use the immutable URLs and expected SHA256 values in `solc_download_plan.json`. The initial `provision_toolchain.py solc` command resolves the official repository head and creates a new download plan, so a later invocation is a new metadata observation and must not overwrite this frozen inventory record. Existing binaries may be checked without running them using `verify_toolchain_v2.py`; this emits JSON to stdout and changes no files. An explicit `--receipt NEW_PATH` creates a separate new receipt and refuses an existing path. Python installation performs environment administration; it does not execute contract analysis.

## Verifier amendment v2

The original `verify_toolchain.py` was an inventory/receipt generator despite its read-only docstring, and its assertions could be disabled with optimized Python. It remains byte-identical as a historical execution source; do not use it for current revalidation. The original `manifest.json` and provisioner are also unchanged. `amendment_v2/source_snapshot_v1/` preserves all three original files and `legacy_baseline.json` records their hashes.

`verify_toolchain_v2.py` uses explicit exceptions, imports no assertion-based verifier helpers and is checked under `python -O`. Its validation is read-only; optional receipt creation is an explicit, separate exclusive-create operation. No compiler or Slither is executed by either new verification mode. See `amendment_v2/AMENDMENT.md` and the separately dated v2 receipt for source/test provenance.
