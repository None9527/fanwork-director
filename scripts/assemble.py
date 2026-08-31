#!/usr/bin/env python3
"""剪辑工具：末帧抽取 / 时长质检 / ffmpeg 拼接。依赖系统 ffmpeg/ffprobe。

子命令：
  lastframe <in.mp4> <out.png> [--at SECONDS]   抽取末帧（或指定时刻帧）作下一镜首帧
  qc <storyboard.json> clips/                    逐镜核对实际时长 vs 规划时长（容差±0.5s）
  concat <storyboard.json> <final.mp4>           按 shot 顺序拼接 clips/（统一 24fps 重编码）
"""
import argparse, json, os, subprocess, sys


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[assemble] FAILED: {' '.join(cmd)}\n{r.stderr[:500]}", file=sys.stderr)
        sys.exit(1)
    return r.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", path]).strip()
    return float(out)


def cmd_lastframe(a):
    d = duration(a.infile)
    t = a.at if a.at is not None else max(0.0, d - 0.1)
    run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", a.infile,
         "-frames:v", "1", a.outfile])
    print(json.dumps({"source": a.infile, "extracted_at": round(t, 3),
                      "out": a.outfile, "video_duration": round(d, 2)}, ensure_ascii=False))


def ordered_clips(sb, clipdir):
    clips = []
    for s in sb["shots"]:
        f = s.get("clip_file") or os.path.join(clipdir, f"shot_{s['id']}.mp4")
        clips.append((s["id"], s["duration_s"], f))
    return clips


def cmd_qc(a):
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    bad = 0
    for sid, plan, f in ordered_clips(sb, a.clipdir):
        if not os.path.exists(f):
            print(f"shot {sid}: MISSING {f}"); bad += 1; continue
        act = duration(f)
        flag = "OK " if abs(act - plan) <= 0.5 else "OFF"
        if flag == "OFF":
            bad += 1
        print(f"shot {sid}: planned {plan}s actual {act:.2f}s [{flag}]")
    print(f"QC: {bad} problem(s)")
    sys.exit(1 if bad else 0)


def cmd_concat(a):
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    lst = a.outfile + ".list.txt"
    with open(lst, "w") as fh:
        for sid, _, f in ordered_clips(sb, os.path.dirname(a.outfile) or "."):
            if not os.path.exists(f):
                f = f"clips/shot_{sid}.mp4"
            os.path.exists(f) or sys.exit(f"missing clip shot {sid}")
            fh.write(f"file '{os.path.abspath(f)}'\n")
    # 统一重编码拼接：各段可能来自不同批次，参数未必全等，re-encode 最稳
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-vf", "fps=24,scale='if(gt(iw,ih),trunc(iw/2)*2,trunc(iw/2)*2)':'if(gt(iw,ih),trunc(ih/2)*2,trunc(ih/2)*2)'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", a.outfile])
    os.remove(lst)
    print(json.dumps({"out": a.outfile, "duration": round(duration(a.outfile), 2)},
                     ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("lastframe")
    s1.add_argument("infile"); s1.add_argument("outfile")
    s1.add_argument("--at", type=float, default=None)
    s1.set_defaults(fn=cmd_lastframe)
    s2 = sub.add_parser("qc")
    s2.add_argument("storyboard"); s2.add_argument("clipdir")
    s2.set_defaults(fn=cmd_qc)
    s3 = sub.add_parser("concat")
    s3.add_argument("storyboard"); s3.add_argument("outfile")
    s3.set_defaults(fn=cmd_concat)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
