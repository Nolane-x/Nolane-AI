#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root with Git LFS installed and authenticated GitHub access.
git lfs install
git lfs track '*.pt' '*.pth' '*.safetensors'
git add .gitattributes checkpoints/*.pt
git commit -m 'weights: publish provenance-bound Nolane checkpoints with Git LFS'
git push origin main
