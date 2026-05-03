import webview

# ========== 你的 ABC 三个程序逻辑 ==========
def run_A():
    return "✅ 程序A 已运行：数据处理模块"

def run_B():
    return "✅ 程序B 已运行：文件解析模块"

def run_C():
    return "✅ 程序C 已运行：网络服务模块"

# ========== HTML 标签页UI（纯单窗口、无弹窗） ==========
html = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>多程序协作面板</title>
<style>
* {margin:0;padding:0;box-sizing:border-box;}
body {background:#f1f3f6;height:100vh;}

/* 标签栏 */
.tab-bar {
    display:flex;
    background:#fff;
    border-bottom:1px solid #ccc;
}
.tab-item {
    padding:10px 24px;
    cursor:pointer;
    border-right:1px solid #eee;
}
.tab-item.active {
    background:#409eff;
    color:#fff;
}

/* 页面容器 */
.tab-content {
    padding:30px;
    font-size:16px;
}
.page {display:none;}
.page.show {display:block;}
</style>
</head>
<body>

<!-- 顶部标签 -->
<div class="tab-bar">
    <div class="tab-item active" onclick="switchTab('pageA', this)">程序A</div>
    <div class="tab-item" onclick="switchTab('pageB', this)">程序B</div>
    <div class="tab-item" onclick="switchTab('pageC', this)">程序C</div>
</div>

<!-- 三个独立页面 -->
<div class="tab-content">
    <div id="pageA" class="page show">
        <h3>程序A 控制面板</h3>
        <button onclick="callA()">启动A任务</button>
        <p id="resA"></p>
    </div>
    <div id="pageB" class="page">
        <h3>程序B 控制面板</h3>
        <button onclick="callB()">启动B任务</button>
        <p id="resB"></p>
    </div>
    <div id="pageC" class="page">
        <h3>程序C 控制面板</h3>
        <button onclick="callC()">启动C任务</button>
        <p id="resC"></p>
    </div>
</div>

<script>
// 切换标签
function switchTab(pageId, el){
    // 标签样式
    document.querySelectorAll('.tab-item').forEach(t=>t.classList.remove('active'));
    el.classList.add('active');
    // 页面切换
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('show'));
    document.getElementById(pageId).classList.add('show');
}

// 调用Python三个程序（修改了调用语法）
async function callA(){
    let ret = await run_A();
    document.getElementById("resA").innerText = ret;
}
async function callB(){
    let ret = await run_B();
    document.getElementById("resB").innerText = ret;
}
async function callC(){
    let ret = await run_C();
    document.getElementById("resC").innerText = ret;
}
</script>
</body>
</html>
'''

if __name__ == "__main__":
    win = webview.create_window(
        title="ABC多程序协作工具",
        html=html,
        width=900,
        height=600,
        resizable=True
    )
    # 核心修复：直接传入函数，不使用字典
    win.expose(run_A, run_B, run_C)
    webview.start()
