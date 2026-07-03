"""
DOUYlike Web 控制台
FastAPI 后端 + 单页前端
"""
import os
import sys
import json
import time
import threading
from pathlib import Path
from collections import deque

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict

from core.config import load_config, save_config, AppConfig

app = FastAPI(title="DOUYlike")

# ===== 运行状态 =====
_pipeline_status = {
    "running": False,
    "step": "",
    "progress": 0,
    "start_time": 0,
    "last_result": None,
}
_logs: deque = deque(maxlen=200)
_logs_lock = threading.Lock()


def _log(msg):
    ts = time.strftime("%H:%M:%S")
    with _logs_lock:
        _logs.append(f"[{ts}] {msg}")


# ===== 数据模型 =====
class FullConfig(BaseModel):
    douyin: dict
    whisper: dict
    llm: dict
    feishu: dict
    scheduler: dict
    dyd_path: str = "D:\\AI\\DyD下载器"


# ===== API =====

@app.get("/api/config")
def get_config():
    cfg = load_config()
    # 读取 prompts
    prompts = {}
    prompt_dir = Path(__file__).parent / "prompts"
    for f in prompt_dir.glob("*.txt"):
        prompts[f.stem] = f.read_text(encoding="utf-8")

    return {
        "douyin": {
            "chrome_debug_port": cfg.douyin.chrome_debug_port,
            "user_data_dir": cfg.douyin.user_data_dir,
            "max_downloads_per_task": cfg.douyin.max_downloads_per_task,
        },
        "whisper": {
            "model_size": cfg.whisper.model_size,
            "device": cfg.whisper.device,
            "compute_type": cfg.whisper.compute_type,
            "language": cfg.whisper.language,
        },
        "llm": {
            "base_url": cfg.llm.base_url,
            "api_key": cfg.llm.api_key,
            "model": cfg.llm.model,
            "max_tokens": cfg.llm.max_tokens,
            "temperature": cfg.llm.temperature,
        },
        "feishu": {
            "app_id": cfg.feishu.app_id,
            "app_secret": cfg.feishu.app_secret,
            "bitable_app_token": cfg.feishu.bitable_app_token,
            "table_ids": {k: getattr(cfg.feishu.table_ids, k) for k in
                          ["videos","transcripts","analysis","topics","competitors","hotspots","logs"]},
        },
        "scheduler": {
            "enabled": cfg.scheduler.enabled,
            "interval_hours": getattr(cfg.scheduler, 'interval_hours', 4),
            "timezone": cfg.scheduler.timezone,
        },
        "dyd_path": cfg.dyd_path,
        "prompts": prompts,
        "feishu_link": f"https://your-domain.feishu.cn/base/{cfg.feishu.bitable_app_token}" if cfg.feishu.bitable_app_token else "",
    }


@app.put("/api/config")
def update_config(data: FullConfig):
    cfg = load_config()

    d = data.douyin
    cfg.douyin.chrome_debug_port = d.get("chrome_debug_port", 9222)
    cfg.douyin.user_data_dir = d.get("user_data_dir", "")
    cfg.douyin.max_downloads_per_task = d.get("max_downloads_per_task", 100)

    w = data.whisper
    cfg.whisper.model_size = w.get("model_size", "medium")
    cfg.whisper.device = w.get("device", "cuda")
    cfg.whisper.compute_type = w.get("compute_type", "int8")
    cfg.whisper.language = w.get("language", "zh")

    l = data.llm
    if l.get("api_key") and len(l["api_key"]) > 8:
        cfg.llm.api_key = l["api_key"]
    if l.get("base_url"):
        cfg.llm.base_url = l["base_url"]
    cfg.llm.model = l.get("model", "gpt-4o")
    cfg.llm.max_tokens = l.get("max_tokens", 4096)
    cfg.llm.temperature = l.get("temperature", 0.7)

    f = data.feishu
    if f.get("app_id") and len(f["app_id"]) > 8:
        cfg.feishu.app_id = f["app_id"]
    if f.get("app_secret") and len(f["app_secret"]) > 8:
        cfg.feishu.app_secret = f["app_secret"]

    s = data.scheduler
    cfg.scheduler.enabled = s.get("enabled", True)
    cfg.scheduler.interval_hours = s.get("interval_hours", 4)
    cfg.scheduler.timezone = s.get("timezone", "Asia/Shanghai")

    cfg.dyd_path = data.dyd_path

    save_config(cfg)
    return {"success": True}


@app.get("/api/stats")
def get_stats():
    from core.database import Database
    cfg = load_config()
    db = Database(cfg)
    db.connect()
    stats = db.get_stats()
    db.close()
    return stats


@app.get("/api/chrome/status")
def chrome_status():
    import subprocess
    cfg = load_config()
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5)
        return {"running": f":{cfg.douyin.chrome_debug_port}" in r.stdout, "port": cfg.douyin.chrome_debug_port}
    except Exception:
        return {"running": False, "port": cfg.douyin.chrome_debug_port}


@app.post("/api/chrome/start")
def start_chrome():
    import subprocess
    cfg = load_config()
    port = cfg.douyin.chrome_debug_port
    user_data_dir = os.path.expandvars(cfg.douyin.user_data_dir)

    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5)
        if f":{port}" in r.stdout:
            return {"success": True, "message": f"Chrome 已在运行 (端口 {port})"}
    except Exception:
        pass

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
    if not chrome_exe:
        return {"success": False, "message": "未找到 Chrome"}

    try:
        os.makedirs(user_data_dir, exist_ok=True)
        subprocess.Popen([chrome_exe, f"--remote-debugging-port={port}", f"--user-data-dir={user_data_dir}", "https://www.douyin.com"])
        time.sleep(2)
        return {"success": True, "message": f"Chrome 已启动"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/feishu/test")
def test_feishu():
    import httpx
    cfg = load_config()
    try:
        resp = httpx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                          json={"app_id": cfg.feishu.app_id, "app_secret": cfg.feishu.app_secret}, timeout=10)
        data = resp.json()
        return {"success": data.get("code") == 0, "message": "连接成功" if data.get("code") == 0 else data.get("msg")}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/pipeline/run")
def run_pipeline(steps: str = ""):
    if _pipeline_status["running"]:
        return {"success": False, "message": "流水线正在运行中"}

    step_list = [s.strip() for s in steps.split(",") if s.strip()] if steps else None

    def _run():
        _pipeline_status["running"] = True
        _pipeline_status["start_time"] = time.time()
        _pipeline_status["step"] = "初始化..."
        _log("流水线启动")

        def progress_cb(msg):
            _pipeline_status["step"] = msg
            _log(msg)

        try:
            from core.pipeline import Pipeline
            cfg = load_config()
            pipeline = Pipeline(cfg)
            result = pipeline.run(steps=step_list, progress_callback=progress_cb)
            _pipeline_status["last_result"] = result
            _log(f"流水线完成: {result.get('total_time', 0):.1f}秒")
        except Exception as e:
            _log(f"流水线异常: {e}")
            _pipeline_status["last_result"] = {"success": False, "error": str(e)}
        finally:
            _pipeline_status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"success": True}


@app.get("/api/pipeline/status")
def pipeline_status():
    elapsed = time.time() - _pipeline_status["start_time"] if _pipeline_status["start_time"] else 0
    return {
        "running": _pipeline_status["running"],
        "step": _pipeline_status["step"],
        "elapsed": round(elapsed, 1),
        "last_result": _pipeline_status["last_result"],
    }


@app.get("/api/logs")
def get_logs():
    with _logs_lock:
        return {"logs": list(_logs)}


@app.get("/api/prompts")
def get_prompts():
    prompts = {}
    prompt_dir = Path(__file__).parent / "prompts"
    for f in prompt_dir.glob("*.txt"):
        prompts[f.stem] = f.read_text(encoding="utf-8")
    return prompts


@app.put("/api/prompts/{name}")
def save_prompt(name: str, body: dict):
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_dir.mkdir(exist_ok=True)
    (prompt_dir / f"{name}.txt").write_text(body.get("content", ""), encoding="utf-8")
    return {"success": True}


# ===== 前端页面 =====

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DOUYlike</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f6f7;color:#1f2329;min-height:100vh}
.header{background:#3370ff;color:#fff;padding:16px 32px;display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:20px;font-weight:600}
.header .sub{font-size:13px;opacity:.8}
.tabs{display:flex;gap:0;background:#fff;border-bottom:1px solid #e8e8e8;position:sticky;top:0;z-index:10}
.tab{padding:12px 24px;cursor:pointer;font-size:14px;font-weight:500;color:#646a73;border-bottom:2px solid transparent;transition:.2s}
.tab:hover{color:#3370ff}
.tab.active{color:#3370ff;border-bottom-color:#3370ff}
.page{display:none;max-width:1000px;margin:20px auto;padding:0 20px}
.page.active{display:block}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:16px;overflow:hidden}
.card-h{padding:14px 20px;border-bottom:1px solid #e8e8e8;font-size:15px;font-weight:600;display:flex;align-items:center;justify-content:space-between}
.card-b{padding:16px 20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.fg{display:flex;flex-direction:column;gap:5px}
.fg.full{grid-column:1/-1}
.fg label{font-size:12px;font-weight:500;color:#646a73}
.fg input,.fg select,.fg textarea{padding:8px 10px;border:1px solid #dee0e3;border-radius:6px;font-size:13px;outline:none;transition:.2s;font-family:inherit}
.fg input:focus,.fg select:focus,.fg textarea:focus{border-color:#3370ff;box-shadow:0 0 0 2px rgba(51,112,255,.12)}
.fg textarea{min-height:120px;resize:vertical}
.btn{padding:7px 18px;border-radius:6px;border:none;font-size:13px;font-weight:500;cursor:pointer;transition:.2s}
.btn-p{background:#3370ff;color:#fff}.btn-p:hover{background:#2860e0}
.btn-s{background:#34c724;color:#fff}.btn-s:hover{background:#2aad1a}
.btn-o{background:#fff;color:#3370ff;border:1px solid #3370ff}.btn-o:hover{background:#f0f5ff}
.btn-d{background:#f54a45;color:#fff}.btn-d:hover{background:#d93630}
.btn:disabled{opacity:.5;cursor:not-allowed}
.acts{display:flex;gap:10px;padding:12px 20px;border-top:1px solid #e8e8e8;justify-content:flex-end}
.stat-bar{display:flex;gap:10px;margin-bottom:16px}
.stat{flex:1;background:#fff;border-radius:8px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,.08);text-align:center}
.stat .n{font-size:26px;font-weight:700;color:#3370ff}
.stat .l{font-size:11px;color:#8f959e;margin-top:2px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.dot.on{background:#34c724}.dot.off{background:#f54a45}
.dot.run{background:#ff9500;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.toast{position:fixed;top:16px;right:16px;padding:10px 18px;border-radius:8px;color:#fff;font-size:13px;z-index:1000;opacity:0;transform:translateY(-8px);transition:.3s}
.toast.show{opacity:1;transform:translateY(0)}
.toast.ok{background:#34c724}.toast.err{background:#f54a45}
.feishu-link{color:#3370ff;text-decoration:none;font-size:13px;font-weight:500}
.feishu-link:hover{text-decoration:underline}
.log-box{background:#1e1e1e;color:#d4d4d4;border-radius:6px;padding:12px;font-family:"Cascadia Code","Fira Code",Consolas,monospace;font-size:12px;max-height:400px;overflow-y:auto;line-height:1.6}
.log-box .ts{color:#6a9955}
.log-box .err{color:#f44747}
.pipeline-status{display:flex;align-items:center;gap:10px;padding:12px 16px;background:#fff8e1;border-radius:8px;margin-bottom:16px;border:1px solid #ffe082}
.pipeline-status.idle{background:#f5f6f7;border-color:#e8e8e8}
.prompt-item{margin-bottom:16px}
.prompt-item h4{font-size:13px;color:#646a73;margin-bottom:6px}
</style>
</head>
<body>
<div class="header">
  <div><h1>DOUYlike</h1><div class="sub">抖音收藏夹自动更新系统</div></div>
  <a class="feishu-link" id="feishu-link" href="#" target="_blank" style="display:none">打开飞书表格</a>
</div>

<div class="tabs">
  <div class="tab active" data-page="dashboard">控制台</div>
  <div class="tab" data-page="config">配置</div>
  <div class="tab" data-page="prompts">提示词</div>
  <div class="tab" data-page="logs">日志</div>
</div>

<!-- 控制台 -->
<div class="page active" id="page-dashboard">
  <div class="stat-bar">
    <div class="stat"><div class="n" id="s-v">-</div><div class="l">视频</div></div>
    <div class="stat"><div class="n" id="s-t">-</div><div class="l">转写</div></div>
    <div class="stat"><div class="n" id="s-a">-</div><div class="l">分析</div></div>
    <div class="stat"><div class="n" id="s-f">-</div><div class="l">飞书同步</div></div>
  </div>

  <div class="pipeline-status idle" id="p-status">
    <span class="dot off" id="p-dot"></span>
    <span id="p-text">空闲</span>
    <span id="p-time" style="margin-left:auto;font-size:12px;color:#8f959e"></span>
  </div>

  <div class="card">
    <div class="card-h">Chrome <span id="chrome-st"><span class="dot off"></span>检查中</span></div>
    <div class="acts">
      <button class="btn btn-s" onclick="startChrome()">启动 Chrome</button>
      <button class="btn btn-o" onclick="checkChrome()">刷新</button>
    </div>
  </div>

  <div class="card">
    <div class="card-h">执行</div>
    <div class="card-b" style="display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-p" id="btn-run" onclick="runPipeline()">执行完整流水线</button>
      <button class="btn btn-o" onclick="runStep('collect')">仅采集</button>
      <button class="btn btn-o" onclick="runStep('transcribe')">仅转写</button>
      <button class="btn btn-o" onclick="runStep('analyze')">仅分析</button>
      <button class="btn btn-o" onclick="runStep('sync')">仅同步飞书</button>
    </div>
  </div>

  <div class="card">
    <div class="card-h">最近日志</div>
    <div class="card-b"><div class="log-box" id="dash-log">等待操作...</div></div>
  </div>
</div>

<!-- 配置 -->
<div class="page" id="page-config">
  <div class="card">
    <div class="card-h">飞书</div>
    <div class="card-b"><div class="grid">
      <div class="fg"><label>App ID</label><input id="c-fid"></div>
      <div class="fg"><label>App Secret</label><input id="c-fs" type="password"></div>
      <div class="fg full"><label>Bitable Token</label><input id="c-fbt" readonly style="background:#f5f6f7"></div>
    </div></div>
    <div class="acts"><button class="btn btn-o" onclick="testFeishu()">测试连接</button></div>
  </div>

  <div class="card">
    <div class="card-h">LLM</div>
    <div class="card-b"><div class="grid">
      <div class="fg full"><label>API Base URL</label><input id="c-url"></div>
      <div class="fg full"><label>API Key</label><input id="c-key" type="password"></div>
      <div class="fg"><label>模型</label><input id="c-model"></div>
      <div class="fg"><label>Max Tokens</label><input id="c-mt" type="number"></div>
      <div class="fg"><label>Temperature</label><input id="c-temp" type="number" step="0.1" min="0" max="2"></div>
    </div></div>
  </div>

  <div class="card">
    <div class="card-h">Whisper</div>
    <div class="card-b"><div class="grid">
      <div class="fg"><label>模型</label><select id="c-wm"><option value="base">base</option><option value="medium" selected>medium</option><option value="large">large</option></select></div>
      <div class="fg"><label>设备</label><select id="c-wd"><option value="cuda">CUDA (GPU)</option><option value="cpu">CPU</option></select></div>
      <div class="fg"><label>精度</label><select id="c-wc"><option value="int8">int8</option><option value="float16">float16</option><option value="float32">float32</option></select></div>
      <div class="fg"><label>语言</label><select id="c-wl"><option value="zh" selected>中文</option><option value="en">英文</option></select></div>
    </div></div>
  </div>

  <div class="card">
    <div class="card-h">抖音</div>
    <div class="card-b"><div class="grid">
      <div class="fg"><label>Chrome 端口</label><input id="c-port" type="number"></div>
      <div class="fg"><label>最大下载数</label><input id="c-max" type="number"></div>
      <div class="fg full"><label>Chrome 数据目录</label><input id="c-udir"></div>
    </div></div>
  </div>

  <div class="card">
    <div class="card-h">定时任务</div>
    <div class="card-b"><div class="grid">
      <div class="fg"><label>启用</label><select id="c-sch"><option value="true">是</option><option value="false">否</option></select></div>
      <div class="fg"><label>间隔（小时）</label><input id="c-interval" type="number" min="1" max="168"></div>
    </div></div>
  </div>

  <div class="card">
    <div class="acts"><button class="btn btn-p" onclick="saveConfig()">保存配置</button></div>
  </div>
</div>

<!-- 提示词 -->
<div class="page" id="page-prompts">
  <div class="card">
    <div class="card-h">AI 分析提示词</div>
    <div class="card-b" id="prompts-container">加载中...</div>
  </div>
  <div class="card">
    <div class="acts"><button class="btn btn-p" onclick="savePrompts()">保存所有提示词</button></div>
  </div>
</div>

<!-- 日志 -->
<div class="page" id="page-logs">
  <div class="card">
    <div class="card-h">运行日志 <button class="btn btn-o" onclick="loadLogs()" style="margin-left:auto;padding:4px 12px">刷新</button></div>
    <div class="card-b"><div class="log-box" id="full-log" style="min-height:400px">加载中...</div></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// === Tabs ===
document.querySelectorAll('.tab').forEach(t=>{
  t.onclick=()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById('page-'+t.dataset.page).classList.add('active');
    if(t.dataset.page==='logs') loadLogs();
  }
});

// === Toast ===
function toast(m,t='ok'){const e=document.getElementById('toast');e.textContent=m;e.className='toast '+t+' show';setTimeout(()=>e.className='toast',3000)}

// === Config ===
async function loadConfig(){
  try{
    const r=await fetch('/api/config');const c=await r.json();
    document.getElementById('c-fid').value=c.feishu.app_id||'';
    document.getElementById('c-fs').value=c.feishu.app_secret||'';
    document.getElementById('c-fbt').value=c.feishu.bitable_app_token||'';
    document.getElementById('c-url').value=c.llm.base_url||'';
    document.getElementById('c-key').value=c.llm.api_key||'';
    document.getElementById('c-model').value=c.llm.model||'';
    document.getElementById('c-mt').value=c.llm.max_tokens||4096;
    document.getElementById('c-temp').value=c.llm.temperature||0.7;
    document.getElementById('c-wm').value=c.whisper.model_size||'medium';
    document.getElementById('c-wd').value=c.whisper.device||'cuda';
    document.getElementById('c-wc').value=c.whisper.compute_type||'int8';
    document.getElementById('c-wl').value=c.whisper.language||'zh';
    document.getElementById('c-port').value=c.douyin.chrome_debug_port||9222;
    document.getElementById('c-max').value=c.douyin.max_downloads_per_task||100;
    document.getElementById('c-udir').value=c.douyin.user_data_dir||'';
    document.getElementById('c-sch').value=c.scheduler.enabled?'true':'false';
    document.getElementById('c-interval').value=c.scheduler.interval_hours||4;
    // feishu link
    if(c.feishu_link){
      const el=document.getElementById('feishu-link');
      el.href=c.feishu_link;el.style.display='inline';
    }
    // prompts
    if(c.prompts) renderPrompts(c.prompts);
  }catch(e){toast('加载失败','err')}
}

async function saveConfig(){
  const d={
    douyin:{chrome_debug_port:+document.getElementById('c-port').value,user_data_dir:document.getElementById('c-udir').value,max_downloads_per_task:+document.getElementById('c-max').value},
    whisper:{model_size:document.getElementById('c-wm').value,device:document.getElementById('c-wd').value,compute_type:document.getElementById('c-wc').value,language:document.getElementById('c-wl').value},
    llm:{base_url:document.getElementById('c-url').value,api_key:document.getElementById('c-key').value,model:document.getElementById('c-model').value,max_tokens:+document.getElementById('c-mt').value,temperature:+document.getElementById('c-temp').value},
    feishu:{app_id:document.getElementById('c-fid').value,app_secret:document.getElementById('c-fs').value,bitable_app_token:document.getElementById('c-fbt').value,table_ids:{}},
    scheduler:{enabled:document.getElementById('c-sch').value==='true',interval_hours:+document.getElementById('c-interval').value,timezone:'Asia/Shanghai'},
    dyd_path:'D:\\AI\\DyD下载器'
  };
  try{const r=await fetch('/api/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});const j=await r.json();toast(j.success?'已保存':'保存失败',j.success?'ok':'err')}catch(e){toast('保存失败','err')}
}

// === Stats ===
async function loadStats(){
  try{const r=await fetch('/api/stats');const s=await r.json();
  document.getElementById('s-v').textContent=s.total_videos||0;
  document.getElementById('s-t').textContent=s.transcribed||0;
  document.getElementById('s-a').textContent=s.analyzed||0;
  document.getElementById('s-f').textContent=s.synced_feishu||0;}catch(e){}
}

// === Chrome ===
async function checkChrome(){
  try{const r=await fetch('/api/chrome/status');const s=await r.json();
  const el=document.getElementById('chrome-st');
  el.innerHTML=s.running?`<span class="dot on"></span>已连接 :${s.port}`:`<span class="dot off"></span>未连接`;}catch(e){}
}
async function startChrome(){
  try{const r=await fetch('/api/chrome/start',{method:'POST'});const j=await r.json();toast(j.message,j.success?'ok':'err');setTimeout(checkChrome,2000);}catch(e){toast('失败','err')}
}

// === Pipeline ===
async function runPipeline(){
  try{const r=await fetch('/api/pipeline/run',{method:'POST'});const j=await r.json();toast(j.message||'已启动',j.success?'ok':'err');if(j.success)startPolling();}catch(e){toast('失败','err')}
}
async function runStep(step){
  try{const r=await fetch('/api/pipeline/run?steps='+step,{method:'POST'});const j=await r.json();toast(j.message||'已启动',j.success?'ok':'err');if(j.success)startPolling();}catch(e){toast('失败','err')}
}

let pollTimer=null;
function startPolling(){
  if(pollTimer) return;
  pollTimer=setInterval(async()=>{
    try{
      const r=await fetch('/api/pipeline/status');const s=await r.json();
      const el=document.getElementById('p-status');
      const dot=document.getElementById('p-dot');
      const txt=document.getElementById('p-text');
      const tm=document.getElementById('p-time');
      if(s.running){
        el.className='pipeline-status';dot.className='dot run';
        txt.textContent=s.step||'运行中...';
        tm.textContent=s.elapsed?s.elapsed+'秒':'';
        document.getElementById('btn-run').disabled=true;
      }else{
        el.className='pipeline-status idle';dot.className='dot off';
        txt.textContent=s.last_result?(s.last_result.success?'上次完成':'上次失败'):'空闲';
        tm.textContent='';
        document.getElementById('btn-run').disabled=false;
        stopPolling();loadStats();
      }
      loadLogs();
    }catch(e){}
  },1500);
}
function stopPolling(){if(pollTimer){clearInterval(pollTimer);pollTimer=null}}

// === Logs ===
async function loadLogs(){
  try{const r=await fetch('/api/logs');const d=await r.json();
  const html=d.logs.map(l=>`<div>${l}</div>`).join('');
  const el=document.getElementById('full-log');if(el)el.innerHTML=html||'暂无日志';
  const el2=document.getElementById('dash-log');if(el2)el2.innerHTML=d.logs.slice(-15).map(l=>`<div>${l}</div>`).join('')||'等待操作...';
  if(el)el.scrollTop=el.scrollHeight;
  if(el2)el2.scrollTop=el2.scrollHeight;
}catch(e){}}

// === Prompts ===
let promptsData={};
const promptNames={'analyze_video':'视频内容分析','analyze_topic':'选题趋势分析','analyze_viral':'爆款公式提炼'};
function renderPrompts(prompts){
  promptsData=prompts;
  const c=document.getElementById('prompts-container');
  c.innerHTML='';
  for(const[k,v]of Object.entries(prompts)){
    c.innerHTML+=`<div class="prompt-item"><h4>${promptNames[k]||k}</h4><textarea id="p-${k}" style="width:100%;min-height:150px;font-size:13px;padding:10px;border:1px solid #dee0e3;border-radius:6px;resize:vertical">${escHtml(v)}</textarea></div>`;
  }
}
function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
async function savePrompts(){
  for(const k of Object.keys(promptsData)){
    const ta=document.getElementById('p-'+k);
    if(!ta)continue;
    try{await fetch('/api/prompts/'+k,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:ta.value})})}catch(e){}
  }
  toast('提示词已保存');
}

// === Feishu test ===
async function testFeishu(){
  try{const r=await fetch('/api/feishu/test',{method:'POST'});const j=await r.json();toast(j.message,j.success?'ok':'err')}catch(e){toast('失败','err')}
}

// === Init ===
loadConfig();loadStats();checkChrome();loadLogs();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("\n  DOUYlike - http://localhost:8088\n")
    uvicorn.run(app, host="0.0.0.0", port=8088)
