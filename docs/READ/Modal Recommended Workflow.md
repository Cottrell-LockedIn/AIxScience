# Modal Recommended Workflow

> This is a non-binding starting guide, not a required procedure. The team should change, reorder, combine or discard it after dataset inspection and discussion. Evidence and team judgment override this note.

## What Modal is for

Modal runs Python functions in managed cloud containers. A function can request CPUs, memory or a GPU. Modal builds the environment, starts containers when work arrives and scales parallel calls.

Inference means using an already trained or pretrained model to turn new images into embeddings, masks, anomaly scores or predictions. In this project, Modal could run inference over many microscopy images or model configurations in parallel.

## Useful starting options

### Local or CPU first

Use local execution for:

- metadata inspection;
- acquisition-QC metrics;
- classical image processing;
- KPI computation;
- statistical aggregation;
- UI development.

This gives a cheap, transparent reference implementation.

### Representative benchmark

Benchmark one representative batch or subset before scaling:

- runtime per image;
- memory use;
- upload and startup overhead;
- estimated full-dataset cost;
- whether GPU output matches local output.

### Bounded model matrix

Register a small matrix, for example:

- handcrafted features;
- one ResNet/PatchCore baseline;
- one DINOv2 challenger;
- one or two preprocessing variants.

Run identical leakage-safe splits and record:

- model and weight revision;
- hardware;
- wall-clock time;
- cost;
- accuracy and false-positive metrics;
- batch-level result.

Stop configurations that do not provide material benefit.

### Parallel inference

Useful Modal features:

- `.map` or `.spawn_map` for parallel image or configuration jobs;
- a Volume for model weights and persistent outputs;
- `@modal.enter()` to load weights once per container;
- explicit timeouts and retry limits;
- deployed functions or an HTTP endpoint if the UI needs remote inference.

Do not place secrets in code or logs.

### Demonstration path

Prefer:

1. local frontend;
2. Modal for measured batch inference;
3. cached local result if Modal or venue internet fails;
4. submitted recording as an additional fallback.

The demo must remain usable without Modal.

## Hardware starting points

Hardware selection is empirical, not a required sequence.

- CPU/local: classical KPIs and statistics.
- L4 or T4: modest frozen feature extraction.
- A10 or L40S: larger image workloads or models if measured need exists.
- H100: only if benchmarking shows a genuine wall-clock advantage.

Modal’s own current inference guidance often recommends L40S as a cost/performance starting point, but this does not prove it is best for this dataset.

## Approximate costs

Published rates as of 3 October 2026 include approximately:

- T4: $0.5904/hour;
- L4: $0.7992/hour;
- A10: $1.1016/hour;
- L40S: $1.9512/hour;
- A100 40 GB: $2.0988/hour;
- H100: $3.9492/hour.

CPU, memory, startup and idle time also contribute. A short experiment can be inexpensive, but repeated uncapped runs can consume credits.

Use:

- a spend limit;
- fixed maximum container counts;
- fixed dataset subsets during development;
- timeouts;
- a per-run cost log;
- stop rules for unproductive configurations.

## ZeroGPU decision

Do not use Hugging Face ZeroGPU as the judge-critical backend.

Current constraints include shared queues, Gradio-only hosting and daily GPU quotas. It may be useful for an optional public showcase after the core demo is stable.

The primary demonstration path is local UI plus Modal inference with cached local fallback.
