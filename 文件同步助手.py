# clipboard_sync_final.py
from flask import Flask, request, render_template_string, send_from_directory
from flask_socketio import SocketIO, emit
import os
import datetime
import pyperclip
from socket import gethostbyname, gethostname
import mimetypes

app = Flask(__name__)
app.config['SECRET_KEY'] = 'final-fix-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
socketio = SocketIO(app, cors_allowed_origins="*")

# ======================== 前端代码 ========================
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件同步助手</title>
    <style>
        body { margin: 0; padding: 10px; font-family: Arial; }
        .chat-box { height: 70vh; border: 1px solid #ccc; overflow-y: auto; padding: 10px; }
        .message { margin: 5px; padding: 8px; border-radius: 5px; max-width: 80%; }
        .received { background: #e5e5ea; float: left; }
        .sent { background: #0084ff; color: white; float: right; }
        #file-input { display: none; }
        .file-link { color: blue; text-decoration: underline; cursor: pointer; }
        .progress-bar { width: 200px; height: 5px; background: #ddd; margin-top: 5px; }
        .progress { height: 100%; background: #4CAF50; }
        .preview { max-width: 200px; max-height: 200px; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="chat-box" id="chat-box"></div>
    <div>
        <input type="text" id="message-input" placeholder="输入文字..." onkeypress="handleKeyPress(event)">
        <button onclick="sendText()">发送文字</button>
        <button onclick="triggerFileInput()">发送文件</button>
    </div>
    <input type="file" id="file-input" onchange="handleFileSelect(this.files)">

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io('http://' + window.location.hostname + ':5000');
        const chatBox = document.getElementById('chat-box');
        const messageInput = document.getElementById('message-input');

        // ================ 核心逻辑================
        // 处理回车键
        function handleKeyPress(e) {
            if (e.key === 'Enter') sendText();
        }

        // 触发文件选择
        function triggerFileInput() {
            document.getElementById('file-input').click();
        }

        // 发送文字消息
        function sendText() {
            const text = messageInput.value.trim();
            if (!text) return;
            
            // 本地立即显示
            addMessage(text, 'sent');
            
            // 发送到服务器
            socket.emit('text_message', { content: text });
            messageInput.value = '';
        }

        // 处理文件选择
        function handleFileSelect(files) {
            const file = files[0];
            if (!file) return;

            // 显示上传进度
            const progressId = Date.now();
            showProgress(progressId, file.name);

            // 创建上传请求
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);

            // 进度更新
            xhr.upload.onprogress = (e) => {
                const percent = Math.round((e.loaded / e.total) * 100);
                updateProgress(progressId, percent);
            };

            // 上传完成
            xhr.onload = () => {
                removeProgress(progressId);
                if (xhr.status === 200) {
                    const data = JSON.parse(xhr.responseText);
                    // 本地显示文件
                    showFileMessage(data, 'sent');
                    // 通知其他设备
                    socket.emit('file_message', data);
                }
            };

            // 发送文件
            const formData = new FormData();
            formData.append('file', file);
            xhr.send(formData);
        }

        // ================ 工具函数 ================
        // 显示文本消息
        function addMessage(content, direction) {
            const div = document.createElement('div');
            div.className = `message ${direction}`;
            div.textContent = content;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // 显示文件消息
        function showFileMessage(data, direction) {
            const div = document.createElement('div');
            div.className = `message ${direction}`;
            
            let preview = '';
            switch(data.type) {
                case 'image':
                    preview = `<img src="${data.url}" class="preview">`;
                    break;
                case 'video':
                    preview = `<video controls class="preview"><source src="${data.url}"></video>`;
                    break;
                case 'audio':
                    preview = `<audio controls><source src="${data.url}"></audio>`;
                    break;
            }

            div.innerHTML = `
                <div>文件：${data.filename}</div>
                <a href="${data.url}" class="file-link" download>下载文件</a>
                ${preview}
            `;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // 进度条管理
        function showProgress(id, filename) {
            const container = document.createElement('div');
            container.className = 'message sent';
            container.id = `progress-${id}`;
            container.innerHTML = `
                <div>正在上传 ${filename}</div>
                <div class="progress-bar">
                    <div class="progress" id="progress-bar-${id}"></div>
                </div>
            `;
            chatBox.appendChild(container);
        }

        function updateProgress(id, percent) {
            const bar = document.getElementById(`progress-bar-${id}`);
            if (bar) bar.style.width = percent + '%';
        }

        function removeProgress(id) {
            const elem = document.getElementById(`progress-${id}`);
            if (elem) elem.remove();
        }

        // ================ 接收消息 ================
        socket.on('text_message', (data) => {
            addMessage(data.content, 'received');
        });

        socket.on('file_message', (data) => {
            showFileMessage(data, 'received');
        });
    </script>
</body>
</html>
'''

# ======================== 后端代码 ========================
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload', methods=['POST'])
def handle_upload():
    file = request.files['file']
    if not file:
        return {'status': 'fail'}
    
    # 生成唯一文件名
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{timestamp}_{file.filename}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    # 获取文件类型
    mime_type, _ = mimetypes.guess_type(filename)
    file_type = mime_type.split('/')[0] if mime_type else 'file'
    
    return {
        'status': 'success',
        'url': f'/download/{filename}',
        'filename': file.filename,
        'type': file_type
    }

@app.route('/download/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('text_message')
def forward_text(data):
    # 剪贴板同步
    pyperclip.copy(data['content'])
    # 转发给其他客户端（排除自己）
    emit('text_message', data, broadcast=True, include_self=False)

@socketio.on('file_message')
def forward_file(data):
    # 转发给其他客户端（排除自己）
    emit('file_message', data, broadcast=True, include_self=False)

# ======================== 启动服务 ========================
def print_access_info():
    ip = gethostbyname(gethostname())
    print(f"\n✅ 服务地址：http://{ip}:5000")
    print("✅ 手机访问：请确保同一WiFi")
    print("✅ 已自动配置防火墙规则")

if __name__ == '__main__':
    print_access_info()
    # 自动配置防火墙（Windows）
    if os.name == 'nt':
        os.system('netsh advfirewall firewall delete rule name="ClipSync" >nul 2>&1')
        os.system('netsh advfirewall firewall add rule name="ClipSync" dir=in action=allow protocol=TCP localport=5000')
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)