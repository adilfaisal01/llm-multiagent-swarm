# Report: SiMa.ai's Palette Neat software stack (Palette SDK, Neat runtime, model-compiler) for their Modalix MLSoC — how does it technically work as a model-to-hardware compiler and runtime? Cover: what the compiler actually emits (MLSoC binary/MPK archive, operator scheduling, MLA tessellation), its precision strategy (INT8/BF16 quantization, calibration, mixed precision, accuracy deltas), the runtime execution model (GStreamer-based pipeline, host vs device orchestration, APIs), supported model/operator coverage, and whether the source is open or proprietary. Ignore funding and valuation.

**Date:** 2026-09-29 09:42:40  
**Wall time:** 383.1s  
**Workers:** 5  
**Models:** kimi-k2.6:cloud, deepseek-v4-pro:cloud, minimax-m3:cloud, gemma4:31b-cloud, glm-5.3-flash:cloud

---

# SiMa.ai Palette Neat: Technical Architecture of the Model-to-Hardware Compiler and Runtime

## Executive Summary

Palette Neat is SiMa.ai's software development toolkit for the Modalix MLSoC, comprising an offline Model Compiler, a C++/Python runtime library, and an agentic development environment. The compiler ingests ONNX models and emits a hardware-optimized `.sima` binary packaged as an MPK archive, with INT8/BF16 quantization claiming under 1% accuracy loss. The runtime executes compiled models through a GStreamer-based pipeline with host/device orchestration. The silicon-specific compiler backend is proprietary and Modalix-locked, while the runtime library and example repositories are publicly available on GitHub.

## Background / Context

The question asks how SiMa.ai's Palette Neat stack technically functions as a model-to-hardware compiler and runtime for the Modalix MLSoC. This matters because edge AI deployment increasingly depends on the quality of the compilation toolchain — how well a vendor's software maps neural networks onto custom silicon determines both developer adoption and real-world inference performance. SiMa.ai positions Palette Neat as a successor to its earlier Palette/MPK toolchain, with an "agentic" frontend that collapses application development complexity [1][4]. Understanding the emission artifacts, precision handling, runtime orchestration, and licensing model is essential for evaluating the platform's technical maturity and developer accessibility.

## Findings

### Compiler Emission and Artifacts

The Model Compiler takes an ONNX model as input and compiles it directly to SiMa.ai's MLSoC binary in a single API call [2]. The output is a hardware-optimized `.sima` binary packaged as an MPK archive (a `.tar.gz` container) [2]. The compiled artifact contains the optimized weights, the operator schedule, and the hardware-specific instruction stream targeting the MLA (Machine Learning Accelerator) [2]. The compiler is invoked through the `afe` Python package in the SDK, which checks compatibility, prepares the graph, quantizes, compiles, and validates accuracy and performance.

The compiler performs **MLA tessellation**, breaking large tensors into smaller tiles that fit within the MLSoC's local SRAM. This is paired with a patented proactive data prefetch mechanism that schedules data movement so the next layer's weights and activations are available in local memory before they are needed. The compiler also handles layer-wise precision mapping and memory layout optimization [2].

### Precision Strategy

The compiler handles quantization from FP32 to INT8 and BF16, with layer-wise precision mapping [2]. SiMa.ai claims a quantization accuracy delta of under 1% for this process. INT16 is also supported as a precision option. The quantization flow includes calibration and validation steps within the compilation pipeline. Mixed precision is achieved through the layer-wise mapping — different layers can be assigned different numerical precisions based on sensitivity analysis during compilation.

### Runtime Execution Model

The Neat Runtime is a C++20 library (`neat`/`pyneat`) for building, validating, and running AI applications [9]. It provides both C++ and Python APIs. For on-device inference, the `ModelExecutor` class provides a simplified execution interface [5]. The runtime executes compiled models through a **GStreamer-based pipeline**, which handles media streaming and processing orchestration between the host CPU and the Modalix device. The host/device split involves the host managing pipeline construction, input/output handling, and application logic, while the device executes the compiled model graph on the MLA.

The Palette Neat stack consists of four components: the **Neat SDK** (containerized development environment), the **Neat Library** (the C++/Python runtime), the **Model Compiler** (ONNX → MLA), and **LLiMa** (the GenAI runtime for large language models) [4]. Everything installs through a single CLI tool, `sima-cli`, with commands such as `sima-cli login` and `sima-cli neat install core@v0.3.0` [13].

### Model and Operator Coverage

The compiler supports ONNX as the primary input format for vision and general models [2]. For generative AI workloads, a separate toolchain path (LLiMa) handles large language model input. The runtime supports computer vision applications including YOLO-based detection, demonstrated on the Modalix DevKit 3.0 [12]. The Palette platform integrates programming of the APUs (application processing units), CVU (computer vision unit), and the MLA [11].

### Open vs. Proprietary Status

The licensing model is split. The **silicon-specific compiler backend** — operator scheduling, MLA memory-layout optimization, and tessellation logic — is **closed-source and Modalix-locked**. However, SiMa.ai maintains public GitHub repositories under the `sima-neat` organization, including the core C++20 library [3][9]. The company describes the environment as "open source, purpose-built" combining an execution library and agent workflow [8]. Example application repositories (such as `sima-vision`) are publicly available [13]. The Palette Neat official release was announced on the SiMa.ai community forum [10].

## Analysis

The worker reports show strong agreement on the core architecture: ONNX input, `.sima` binary/MPK archive output, INT8/BF16 quantization with sub-1% accuracy claims, GStreamer-based runtime, and a split licensing model. No worker contradicted another on these fundamentals.

The most significant architectural insight is the **tessellation + prefetch combination**. Breaking tensors into SRAM-sized tiles is standard practice for edge NPUs, but the patented proactive prefetch mechanism suggests SiMa.ai's differentiation lies in scheduling data movement to hide memory latency — a critical bottleneck for edge inference. This is the kind of optimization that is invisible to developers but determines whether real-world throughput approaches theoretical peak.

The **split licensing model** is strategically notable. By open-sourcing the runtime library and examples while keeping the compiler backend proprietary, SiMa.ai lowers the barrier to application development (developers can inspect, modify, and debug the runtime) while protecting the crown-jewel IP that maps models to silicon. This mirrors approaches from other edge AI vendors but is more permissive than fully closed stacks.

A point of ambiguity across reports is the exact relationship between the `.sima` binary and the MPK archive. The evidence suggests the `.sima` binary is the compiled model artifact, and the MPK archive is the packaging container (`.tar.gz`) that wraps it along with metadata. This is consistent with the older Palette/MPK toolchain naming convention that Palette Neat replaces.

The **agentic frontend** is a differentiator worth noting. SiMa.ai describes Palette Neat as "the industry's first agentic AI platform" for edge development [1][20], where an agent workflow assists with model compilation, validation, and deployment. This is a relatively new direction for embedded AI toolchains and may reduce the expertise required to deploy models on Modalix.

## Implications

For **developers**, the open runtime and example repositories reduce integration friction, but the proprietary compiler means debugging below the runtime API boundary requires SiMa.ai support. The single-API-call compilation model [2] is a meaningful simplification compared to multi-stage toolchains.

For **SiMa.ai**, the closed compiler backend protects the MLA's architectural advantages — competitors cannot reverse-engineer the tessellation and scheduling heuristics from public artifacts. The agentic frontend positions the company to capture developer mindshare in the increasingly crowded edge AI NPU market.

For **the broader edge AI ecosystem**, SiMa.ai's approach validates the trend toward ONNX as the de facto interchange format, with vendor-specific compilation happening downstream. The sub-1% accuracy claim, if robust across model types, sets a competitive bar for quantization quality.

## Recommendations / Outlook

**Watch for:** (1) Whether SiMa.ai publishes quantization accuracy benchmarks across a diverse model zoo, not just flagship vision models — the sub-1% claim needs independent verification. (2) Expansion of the open-source surface area — if the compiler backend or at least its IR specification is opened, third-party tooling could emerge. (3) LLiMa's maturity for GenAI workloads, which is a newer and less-documented path than the vision/ONNX flow.

**Key uncertainties:** The exact operator coverage list is not publicly documented in detail; the GStreamer pipeline's host/device split is described at a high level but not architecturally specified; and the calibration methodology for quantization (per-tensor vs. per-channel, calibration dataset requirements) is not disclosed in the available sources. These gaps matter for developers evaluating whether their specific models will compile and run efficiently.

**Outlook:** Palette Neat represents a coherent, modern toolchain that addresses the two hardest problems in edge AI deployment — model-to-silicon compilation and runtime orchestration — with a pragmatic open/proprietary split. Its success will depend less on the architecture described here and more on execution: breadth of operator support, robustness of the quantization pipeline, and whether the agentic workflow genuinely reduces time-to-deployment.

## Sources

[1] sima.ai — Palette product page (Palette Neat agentic environment)
[2] sima.ai — Home page (Palette SDK compiles ONNX directly to MLSoC binary)
[3] github.com — SiMa.ai Palette Neat GitHub organization
[4] developer.sima.ai — Palette Neat software development toolkit documentation
[5] docs.sima.ai — SiMa.ai Developer Guide (ModelExecutor)
[7] developer.sima.ai — For AI Agents onboarding documentation
[8] sima.ai — Palette page (open source execution library and agent workflow)
[9] github.com — sima-neat/core (C++20 library)
[10] community.sima.ai — Palette Neat Official Release announcement
[11] sima.ai — MLSoC Modalix Product Brief (Palette integrates APU, CVU, MLA programming)
[12] pypi.org — Live YOLO computer vision on SiMa Modalix DevKit 3.0
[13] github.com — RizwanMunawar/sima-vision (sima-cli usage examples)
[20] linkedin.com — Palette Neat as agentic AI platform
## Sources

1. https://sima.ai/palette/ — sima.ai (★★★)
4. https://developer.sima.ai/software/getting-started/ — developer.sima.ai (★★★)
2. https://sima.ai/ — sima.ai (★★★)
9. https://github.com/sima-neat/core — github.com (★★)
5. https://docs.sima.ai/ — docs.sima.ai (★★)
13. https://github.com/RizwanMunawar/sima-vision — github.com (★★)
12. https://pypi.org/project/sima-vision/ — pypi.org (★★)
11. https://sima.ai/wp-content/uploads/2024/12/SiMa_MLSoC_Modalix_Product-Brief.pdf — sima.ai (★★)
3. https://github.com/sima-neat — github.com (★★★)
8. https://sima.ai/palette-sdk/ — sima.ai (★★)
10. https://community.sima.ai/t/palette-neat-official-release/1602 — community.sima.ai (★★)
20. https://www.linkedin.com/posts/gohegde_ml-embedded-mlsoc-activity-7472670173846585345-HsRm — linkedin.com (★★)
7. https://developer.sima.ai/agents — developer.sima.ai (★★)
