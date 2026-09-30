#!/usr/bin/env python3
"""
本地视频内容提取 — 提取视频里讲了什么

用法：
  python3 video_content_extractor.py <视频文件路径>
  python3 video_content_extractor.py <文件夹路径>   # 批量处理

依赖：
  brew install ffmpeg
  pip install openai-whisper Pillow
"""

import sys
import json
import subprocess
import tempfile
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "video_analysis"
OUTPUT_DIR.mkdir(exist_ok=True)


def extract_audio(video_path: str) -> str:
    """从视频提取音频 → mp3，无音轨返回空字符串"""
    audio_path = str(Path(tempfile.gettempdir()) / f"audio_{int(time.time())}.mp3")

    # First check if video has audio stream
    probe = subprocess.run(
        ["ffmpeg", "-i", video_path], capture_output=True, text=True, timeout=10,
    )
    if "Audio:" not in probe.stderr:
        return ""  # No audio track

    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
         "-q:a", "2", audio_path, "-y"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return ""  # Silent failure for audio
    return audio_path


def transcribe_audio(audio_path: str) -> str:
    """音频转文字 (whisper)"""
    import whisper
    model = whisper.load_model("base")  # tiny/base/small/medium/large
    result = model.transcribe(audio_path, language="zh")
    return result["text"]


def extract_subtitle_text(video_path: str) -> str:
    """用 OCR 提取视频画面中的文字（每秒抽一帧）"""
    import subprocess
    import os

    frame_dir = Path(tempfile.gettempdir()) / f"frames_{int(time.time())}"
    frame_dir.mkdir(exist_ok=True)

    # 每秒抽一帧，最多30帧
    subprocess.run(
        ["ffmpeg", "-i", video_path, "-vf", "fps=1", "-frames:v", "30",
         f"{frame_dir}/frame_%03d.png", "-y"],
        capture_output=True, timeout=30,
    )

    texts = []
    for frame in sorted(frame_dir.glob("*.png")):
        try:
            from app.services.ocr_mac import ocr_image
            text = ocr_image(str(frame))
            if text.strip():
                texts.append(text.strip())
        except Exception:
            pass

    # Cleanup
    import shutil
    shutil.rmtree(frame_dir, ignore_errors=True)

    return "\n".join(texts)


def get_video_info(video_path: str) -> dict:
    """获取视频基本信息"""
    result = subprocess.run(
        ["ffmpeg", "-i", video_path],
        capture_output=True, text=True, timeout=10,
    )
    stderr = result.stderr
    info = {"file": video_path, "size_mb": round(Path(video_path).stat().st_size / 1024 / 1024, 1)}

    import re
    m = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", stderr)
    if m:
        info["duration_seconds"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.search(r"(\d+x\d+)", stderr)
    if m:
        info["resolution"] = m.group(1)

    return info


def analyze_video(video_path: str) -> dict:
    """完整分析一条视频"""
    print(f"\n分析: {Path(video_path).name}")

    result = get_video_info(video_path)
    print(f"  时长: {result.get('duration_seconds', '?')}s  "
          f"分辨率: {result.get('resolution', '?')}")

    # 音频 → 文字
    try:
        print("  提取音频...")
        audio = extract_audio(video_path)
        print("  语音转文字...")
        text = transcribe_audio(audio)
        result["speech_text"] = text
        print(f"  语音: {text[:100]}...")
        Path(audio).unlink(missing_ok=True)
    except Exception as e:
        print(f"  语音提取失败: {e}")
        result["speech_text"] = ""

    # 画面 → OCR
    try:
        print("  提取画面文字...")
        ocr_text = extract_subtitle_text(video_path)
        if ocr_text:
            result["ocr_text"] = ocr_text[:500]
            print(f"  画面文字: {ocr_text[:100]}...")
    except Exception as e:
        print(f"  OCR失败: {e}")

    return result


# ═══ Main ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 video_content_extractor.py <视频文件>")
        print("  python3 video_content_extractor.py <文件夹>  # 批量")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_dir():
        videos = list(target.glob("*.mp4")) + list(target.glob("*.mov")) + list(target.glob("*.avi"))
        print(f"找到 {len(videos)} 个视频")
    elif target.is_file():
        videos = [target]
    else:
        print(f"文件不存在: {target}")
        sys.exit(1)

    results = []
    for v in videos:
        try:
            r = analyze_video(str(v))
            results.append(r)
        except Exception as e:
            print(f"  ❌ {v.name}: {e}")

    # Save
    out = OUTPUT_DIR / f"analysis_{int(time.time())}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n已保存: {out}")
    print(f"共分析 {len(results)} 条视频")
