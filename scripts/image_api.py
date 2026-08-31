#!/usr/bin/env python3
"""图像编辑/生成适配器：角色参考图 + edit prompt → 关键帧图。

Providers（env FANWORK_IMAGE_PROVIDER，默认自动探测）：
  minimax     MiniMax 平台 /v1/image_generation（与 H3 同 key：MINIMAX_API_KEY）
  none        占位：输出将要执行的完整请求（JSON），exit code 2，绝不假装成功

用法：
  python3 image_api.py --prompt-file refs/shot_01.prompt.txt \
      --ref images/150_妖王_黑熊精.jpg [--ref 更多角色图] --out refs/shot_01_first.png \
      [--size 1536x864] [--dry-run]

注意：image-01 的请求/响应字段以官方文档 /docs/api-reference/video-image-generation
一类页面为准；本适配器首次真实调用时如报 schema 错误，按文档调整 build_request()。
"""
import argparse, base64, json, mimetypes, os, sys, urllib.request, urllib.error

PROVIDER = os.environ.get("FANWORK_IMAGE_PROVIDER", "")
BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimax.io").rstrip("/")
KEY = os.environ.get("MINIMAX_API_KEY", "")
if not PROVIDER:
    PROVIDER = "minimax" if KEY else "none"


def die(msg, code=1):
    print(f"[image_api] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def build_request(prompt, refs, size):
    if PROVIDER == "minimax":
        # MiniMax image_generation：prompt + 可选参考图列表。字段以文档为准。
        req = {"model": os.environ.get("FANWORK_IMAGE_MODEL", "image-01"),
               "prompt": prompt, "n": 1, "aspect_ratio": "16:9"}
        if size:
            req["resolution"] = size  # 或 "width/height"，按文档
        if refs:
            req["reference_images"] = [data_uri(r) for r in refs]
        return ("POST", f"{BASE}/v1/image_generation", req)
    return None


def extract_image(resp):
    """从响应里找第一张图的 url 或 base64（层级容错）。"""
    def walk(o):
        if isinstance(o, dict):
            for k in ("url", "image_url", "file_id"):
                if k in o and isinstance(o[k], str) and o[k]:
                    return ("url", o[k])
            if "b64_json" in o:
                return ("b64", o["b64_json"])
            for v in o.values():
                r = walk(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v)
                if r:
                    return r
        return None
    return walk(resp)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--ref", action="append", default=[])
    p.add_argument("--out", required=True)
    p.add_argument("--size", default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    prompt = open(a.prompt_file, encoding="utf-8").read().strip()
    for r in a.ref:
        if not r.startswith("http") and not os.path.exists(r):
            die(f"ref image not found: {r}")

    built = build_request(prompt, a.ref, a.size)
    if built is None or a.dry_run:  # provider=none 或显式 dry-run：只出计划
        plan = {"provider": PROVIDER, "will_call": built and f"{built[0]} {built[1]}",
                "prompt_chars": len(prompt), "refs": a.ref, "out": a.out,
                "note": "未实际生成。设置 MINIMAX_API_KEY 或 FANWORK_IMAGE_PROVIDER 后重跑。"}
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        sys.exit(0 if a.dry_run else 2)

    method, url, body = built
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method=method,
                                 headers={"Authorization": f"Bearer {KEY}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code}: {e.read().decode(errors='replace')[:600]}", 4)
    found = extract_image(resp)
    if not found:
        die(f"no image in response: {json.dumps(resp)[:600]}")
    kind, val = found
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    if kind == "b64":
        open(a.out, "wb").write(base64.b64decode(val))
    else:
        if val.startswith("file_"):  # MiniMax file_id 形态
            with urllib.request.urlopen(urllib.request.Request(
                f"{BASE}/v1/files/retrieve_content?file_id={val}",
                headers={"Authorization": f"Bearer {KEY}"}), timeout=180) as r:
                open(a.out, "wb").write(r.read())
        else:
            with urllib.request.urlopen(val, timeout=180) as r:
                open(a.out, "wb").write(r.read())
    print(json.dumps({"out": a.out, "bytes": os.path.getsize(a.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
