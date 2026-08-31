#!/usr/bin/env python3
"""MiniMax H3 视频生成 API 客户端（stdlib-only）。

端点（Global 版，CN 版把 base 换成 https://api.minimaxi.com）：
  创建   POST {base}/v2/video_generation
  查询   GET  {base}/v2/query/video_generation/{task_id}
  下载   GET  {base}/v1/files/retrieve_content?file_id={fid}

认证：Authorization: Bearer $MINIMAX_API_KEY

请求体（以官方文档 v2-create 为准）：
  {
    "model": "MiniMax-H3" | "MiniMax-H3-Max",
    "content": [
      {"type": "text", "text": <prompt>},
      {"type": "image_url", "image_url": {"url": <url-or-data-uri>},
       "role": "first_frame" | "last_frame" | "reference_image"},
      ...
    ],
    "duration": <4-15 int 秒>,
    "resolution": "768P" | "2K" 等,
    "ratio": "16:9" | "adaptive"
  }

注意（官方文档已实锤，2026-08）：
  resolution ∈ {480P, 768P, 2K}；duration ∈ 4..15；
  ratio ∈ {adaptive,21:9,16:9,4:3,1:1,3:4,9:16}，纯文本模式必传且不能 adaptive，
  图生视频由输入图自动判定（勿传）；role ∈ {first_frame,last_frame,reference_image,
  reference_video,reference_audio}；status ∈ {Preparing,Queueing,Processing,Success,Fail}；
  下载 GET /v1/files/retrieve_content?file_id=。
  唯一待首次真实调用验证：本地图以 base64 data URI 直传是否被接受——若拒绝，
  先 POST /v1/files/upload 或换公网 URL。--dry-run 可打印完整请求体。

子命令：
  create   --prompt-file prompts/shot_01.md --duration 6 [--resolution 768P]
           [--ratio 16:9] [--first-frame a.png] [--last-frame b.png]
           [--reference c.jpg]... [--model MiniMax-H3] [--dry-run]
  wait     --task-id T [--out clips/shot_01.mp4] [--timeout 900]
  run      create+wait 一步到位，输出 JSON 摘要（供流水线循环调用）
  shot     --storyboard storyboard.json --shot 01 [--dry-run]
           分镜驱动：自动取 duration/mode/first_frame（PREV_LAST 解析为
           refs/shot_XX_first.png）/char_refs（仅 Ref2VA 模式挂 reference_image）/
           prompt 正文（取 --- 分隔线之后）。含图模式不传 ratio（官方文档：
           图生视频时宽高比由输入图决定，ratio 恒为 adaptive）。
"""
import argparse, base64, json, mimetypes, os, sys, time, urllib.request, urllib.error

BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimax.io").rstrip("/")
KEY = os.environ.get("MINIMAX_API_KEY", "")


def die(msg, code=1):
    print(f"[h3api] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


ALLOW_MISSING = False  # dry-run 时允许引用尚不存在的图（输出 <missing:path> 占位）


def img_to_uri(path):
    if path.startswith(("http://", "https://")):
        return path
    if not os.path.exists(path):
        if ALLOW_MISSING:
            return f"<missing:{path}>"
        die(f"image not found: {path}")
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:{mime};base64,{b64}"


def api(method, url, body=None, raw=False):
    if not KEY and "/v1/" not in url and "/v2/" in url:
        die("MINIMAX_API_KEY not set — use --dry-run for offline plan output", 3)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {KEY}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = r.read()
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code} {url}\n{e.read().decode(errors='replace')[:800]}", 4)
    except urllib.error.URLError as e:
        die(f"network error {url}: {e.reason}", 4)
    return payload if raw else json.loads(payload.decode())


def build_body(a):
    prompt = open(a.prompt_file, encoding="utf-8").read().strip()
    content = [{"type": "text", "text": prompt}]
    for p in a.first_frame or []:
        content.append({"type": "image_url", "image_url": {"url": img_to_uri(p)},
                        "role": "first_frame"})
    for p in a.last_frame or []:
        content.append({"type": "image_url", "image_url": {"url": img_to_uri(p)},
                        "role": "last_frame"})
    for p in a.reference or []:
        content.append({"type": "image_url", "image_url": {"url": img_to_uri(p)},
                        "role": "reference_image"})
    body = {"model": a.model, "content": content, "duration": a.duration}
    if a.resolution:
        body["resolution"] = a.resolution
    if a.ratio:
        body["ratio"] = a.ratio
    return body


def cmd_create(a):
    body = build_body(a)
    if a.dry_run:
        slim = json.loads(json.dumps(body))  # 脱敏 data URI
        for it in slim["content"]:
            u = it.get("image_url", {}).get("url", "")
            if u.startswith("data:"):
                it["image_url"]["url"] = u[:40] + f"...<{len(u)}B base64>"
        print(json.dumps({"endpoint": f"POST {BASE}/v2/video_generation",
                          "api_key_set": bool(KEY), "request": slim},
                         ensure_ascii=False, indent=2))
        return
    resp = api("POST", f"{BASE}/v2/video_generation", body)
    tid = extract(resp, "task_id") or die(f"no task_id in resp: {json.dumps(resp)[:500]}")
    print(json.dumps({"task_id": tid, "raw": resp}, ensure_ascii=False))


def extract(obj, key):
    """深度搜索 JSON 里第一个 key 的值（不同端点返回层级不一）。"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = extract(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = extract(v, key)
            if r is not None:
                return r
    return None


def cmd_wait(a):
    url = f"{BASE}/v2/query/video_generation/{a.task_id}"
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        resp = api("GET", url)
        status = (extract(resp, "status") or "").lower()
        fid = extract(resp, "file_id")
        if status == "success":
            break
        if status == "fail":
            die(f"task failed: {json.dumps(resp, ensure_ascii=False)[:800]}", 5)
        if status not in ("preparing", "queueing", "processing", ""):
            print(f"[h3api] WARN unknown status '{status}', keep polling", file=sys.stderr)
        time.sleep(a.interval)
    else:
        die(f"timeout after {a.timeout}s; task_id={a.task_id} 可稍后重试 wait", 6)
    if not a.out:
        print(json.dumps(resp, ensure_ascii=False)); return
    if not fid:
        die(f"success but no file_id: {json.dumps(resp)[:500]}")
    dl = api("GET", f"{BASE}/v1/files/retrieve_content?file_id={fid}", raw=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "wb").write(dl)
    print(json.dumps({"out": a.out, "bytes": len(dl), "file_id": fid}, ensure_ascii=False))


def cmd_run(a):
    body = build_body(a)
    if a.dry_run:
        slim = json.loads(json.dumps(body))
        for it in slim["content"]:
            u = it.get("image_url", {}).get("url", "")
            if u.startswith("data:"):
                it["image_url"]["url"] = u[:40] + f"...<{len(u)}B base64>"
        print(json.dumps({"endpoint": f"POST {BASE}/v2/video_generation",
                          "request": slim,
                          "then": f"GET {BASE}/v2/query/video_generation/<task_id>",
                          "out": a.out}, ensure_ascii=False, indent=2))
        return
    resp = api("POST", f"{BASE}/v2/video_generation", body)
    tid = extract(resp, "task_id") or die(f"no task_id: {json.dumps(resp)[:500]}")
    a.task_id, a.timeout, a.interval = tid, a.timeout, a.interval
    cmd_wait(a)


def prompt_body(path):
    """取 prompt 文件 --- 分隔线之后的正文（SKILL.md Phase 4 约定格式）。"""
    text = open(path, encoding="utf-8").read()
    if "\n---\n" in text:
        text = text.split("\n---\n", 1)[1]
    return text.strip()


def slim_body(body):
    s = json.loads(json.dumps(body))
    for it in s["content"]:
        u = it.get("image_url", {}).get("url", "")
        if u.startswith("data:"):
            it["image_url"]["url"] = u[:40] + f"...<{len(u)}B base64>"
    return s


def cmd_shot(a):
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    shot = next((s for s in sb["shots"] if s["id"] == a.shot), None)
    if not shot:
        die(f"shot {a.shot} not found in {a.storyboard}")
    root = os.path.dirname(os.path.abspath(a.storyboard)) or "."

    def resolve(p):
        if not p:
            return None
        if p == "PREV_LAST":
            p = f"refs/shot_{a.shot}_first.png"
        return p if p.startswith("http") else os.path.join(root, p)

    if not (4 <= shot["duration_s"] <= 15):
        die(f"shot {a.shot} duration {shot['duration_s']}s violates H3 4-15s")
    content = [{"type": "text", "text": prompt_body(os.path.join(root, shot["prompt_file"]))}]
    mode = shot.get("mode", "I2VA")
    if mode == "Ref2VA":
        for r in shot.get("char_refs", []):
            content.append({"type": "image_url", "image_url": {"url": img_to_uri(resolve(r))},
                            "role": "reference_image"})
    else:
        ff = resolve(shot.get("first_frame"))
        lf = resolve(shot.get("last_frame")) if shot.get("last_frame") not in (None, "AUTO_EXTRACT") else None
        if ff:
            content.append({"type": "image_url", "image_url": {"url": img_to_uri(ff)}, "role": "first_frame"})
        if lf:
            content.append({"type": "image_url", "image_url": {"url": img_to_uri(lf)}, "role": "last_frame"})
    body = {"model": a.model, "content": content, "duration": shot["duration_s"]}
    if a.resolution:
        body["resolution"] = a.resolution
    if not any(c["type"] == "image_url" for c in content):  # 纯文本模式才需要 ratio
        body["ratio"] = a.ratio or sb.get("aspect_ratio", "16:9")
    out = resolve(shot.get("clip_file") or f"clips/shot_{a.shot}.mp4")
    if a.dry_run:
        print(json.dumps({"endpoint": f"POST {BASE}/v2/video_generation",
                          "api_key_set": bool(KEY), "shot": a.shot, "mode": mode,
                          "request": slim_body(body), "out": out},
                         ensure_ascii=False, indent=2))
        return
    resp = api("POST", f"{BASE}/v2/video_generation", body)
    tid = extract(resp, "task_id") or die(f"no task_id: {json.dumps(resp)[:500]}")
    cmd_wait(argparse.Namespace(task_id=tid, out=out, timeout=a.timeout, interval=a.interval))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_gen(sp):
        sp.add_argument("--prompt-file", required=True)
        sp.add_argument("--duration", type=int, required=True, help="4-15 秒")
        sp.add_argument("--first-frame", action="append")
        sp.add_argument("--last-frame", action="append")
        sp.add_argument("--reference", action="append")
        sp.add_argument("--model", default="MiniMax-H3")
        sp.add_argument("--resolution", default=None)
        sp.add_argument("--ratio", default=None)
        sp.add_argument("--dry-run", action="store_true")

    s1 = sub.add_parser("create"); add_gen(s1); s1.set_defaults(fn=cmd_create)
    s2 = sub.add_parser("wait")
    s2.add_argument("--task-id", required=True)
    s2.add_argument("--out")
    s2.add_argument("--timeout", type=int, default=900)
    s2.add_argument("--interval", type=float, default=10)
    s2.set_defaults(fn=cmd_wait)
    s3 = sub.add_parser("run"); add_gen(s3)
    s3.add_argument("--out", required=True)
    s3.add_argument("--timeout", type=int, default=900)
    s3.add_argument("--interval", type=float, default=10)
    s3.set_defaults(fn=cmd_run)
    s4 = sub.add_parser("shot")
    s4.add_argument("--storyboard", required=True)
    s4.add_argument("--shot", required=True, help="shot id，如 01")
    s4.add_argument("--model", default="MiniMax-H3")
    s4.add_argument("--resolution", default=None, help="默认不传（768p 短边）；2K 需 H3-Regenerate 另走端点")
    s4.add_argument("--ratio", default=None)
    s4.add_argument("--timeout", type=int, default=900)
    s4.add_argument("--interval", type=float, default=10)
    s4.add_argument("--dry-run", action="store_true")
    s4.set_defaults(fn=cmd_shot)

    a = p.parse_args()
    global ALLOW_MISSING
    if getattr(a, "dry_run", False):
        ALLOW_MISSING = True
    if a.cmd in ("create", "run") and not (4 <= a.duration <= 15):
        die(f"duration must be 4-15s (H3 constraint), got {a.duration}")
    a.fn(a)


if __name__ == "__main__":
    main()
