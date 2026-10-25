#!/bin/sh
# Download the pinned face models and verify their sha256. Licences: YuNet MIT, SFace Apache-2.0
# (OpenCV Model Zoo). Used by `make models` and the Docker build.
set -eu
dir="${1:-models}"
mkdir -p "$dir"
fetch() {
    repo="$1"; file="$2"; sum="$3"
    if [ ! -f "$dir/$file" ]; then
        curl -fsSL -o "$dir/$file" "https://huggingface.co/opencv/$repo/resolve/main/$file"
    fi
    echo "$sum  $dir/$file" | sha256sum -c - 2>/dev/null || echo "$sum  $dir/$file" | shasum -a 256 -c -
}
fetch face_detection_yunet face_detection_yunet_2023mar.onnx 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4
fetch face_recognition_sface face_recognition_sface_2021dec.onnx 0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79
