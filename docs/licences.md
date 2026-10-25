# Dependency licences

Recorded per the definition of done. Update when a dependency is added.

| Component | Used in | Licence |
| --- | --- | --- |
| Moodle 4.5 | Plugins, staging | GPL-3.0-or-later (plugins are GPL-3.0-or-later too) |
| FastAPI, Starlette, Pydantic, pydantic-settings | Service | MIT |
| Uvicorn, httpx | Service | BSD-3-Clause |
| asyncpg | Service | Apache-2.0 |
| redis-py | Service | MIT |
| React, Vite, Vitest | Dashboards, SDK tests | MIT |
| TypeScript | SDK, dashboards | Apache-2.0 |
| ESLint, typescript-eslint | Lint | MIT |
| PostgreSQL | Staging | PostgreSQL Licence |
| Redis 7 | Staging | BSD-3-Clause |
| SeaweedFS | Staging object store | Apache-2.0 |
| OpenCV (opencv-python-headless) | Analysis worker | Apache-2.0 |
| NumPy | Analysis worker | BSD-3-Clause |
| boto3 / botocore | Object store client | Apache-2.0 |
| Playwright | Staging browser tests | Apache-2.0 |
| YuNet face detector `face_detection_yunet_2023mar.onnx` (sha256 8f2383e4…) | Analysis worker | MIT (OpenCV Model Zoo) |
| SFace face recogniser `face_recognition_sface_2021dec.onnx` (sha256 0ba9fbfa…) | Analysis worker | Apache-2.0 (OpenCV Model Zoo) |

**Residual risk recorded for Gate C:** the SFace and YuNet weight files are published under permissive licences, but the face datasets they were trained on (public academic face datasets) carry their own research-oriented terms. OUK legal should accept or reject this before production. Rejected alternatives: InsightFace ArcFace weights (non-commercial only); TensorFlow-based DeepFace models (same dataset question, plus about 1 GB of runtime).
