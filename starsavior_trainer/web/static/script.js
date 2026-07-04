// Starsavior Trainer Web UI - JavaScript

let config = null;
let eventSource = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    setupTabs();
    setupLogStream();
    checkProcessStatus();
});

// Load configuration from server
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        config = await response.json();

        populateSelects();
        updateStatus('配置加载完成');
    } catch (error) {
        console.error('Failed to load config:', error);
        updateStatus('配置加载失败', 'error');
    }
}

// Populate select dropdowns
function populateSelects() {
    if (!config) return;

    // Profiles
    const profileSelects = ['profile', 'calibrate-profile', 'offline-profile'];
    profileSelects.forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            select.innerHTML = '';
            config.profiles.forEach(profile => {
                const option = document.createElement('option');
                option.value = profile;
                option.textContent = profile;
                if (profile.includes('2560x1440')) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
        }
    });

    // Characters
    const charSelect = document.getElementById('character');
    if (charSelect) {
        charSelect.innerHTML = '<option value="">-- 选择角色 --</option>';
        config.characters.forEach(char => {
            const option = document.createElement('option');
            option.value = char.name;
            option.textContent = `${char.name} (${char.class || '未知'})`;
            option.dataset.profile = char.profile;
            charSelect.appendChild(option);
        });

        // Auto-fill build profile when character changes
        charSelect.addEventListener('change', (e) => {
            const selectedOption = e.target.options[e.target.selectedIndex];
            const profile = selectedOption.dataset.profile;
            if (profile) {
                document.getElementById('build-profile').value = profile;
            }
        });
    }

    // Build profiles
    const buildSelect = document.getElementById('build-profile');
    if (buildSelect) {
        buildSelect.innerHTML = '';
        config.build_profiles.forEach(profile => {
            const option = document.createElement('option');
            option.value = profile;
            option.textContent = profile;
            if (profile === 'balanced') {
                option.selected = true;
            }
            buildSelect.appendChild(option);
        });
    }

    // Classify modes
    const classifySelect = document.getElementById('classify-mode');
    if (classifySelect) {
        classifySelect.innerHTML = '';
        config.classify_modes.forEach(mode => {
            const option = document.createElement('option');
            option.value = mode.flag;
            option.textContent = mode.label;
            if (mode.flag === '--hybrid-mode') {
                option.selected = true;
            }
            classifySelect.appendChild(option);
        });
    }
}

// Setup tab switching
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            // Remove active class from all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked
            btn.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
        });
    });
}

// Setup log streaming
function setupLogStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/logs/stream');

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.log) {
            appendLog(data.log);
        }
    };

    eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        setTimeout(setupLogStream, 5000); // Reconnect after 5s
    };
}

// Append log line
function appendLog(text) {
    const logContent = document.getElementById('log-content');
    const line = document.createElement('div');
    line.className = 'log-line';

    // Color coding
    if (text.includes('[ERROR]') || text.includes('Error') || text.includes('Failed')) {
        line.classList.add('error');
    } else if (text.includes('[WARN]') || text.includes('Warning')) {
        line.classList.add('warning');
    } else if (text.includes('[DONE]') || text.includes('Success')) {
        line.classList.add('success');
    } else if (text.includes('[CMD]')) {
        line.classList.add('cmd');
    }

    line.textContent = text;
    logContent.appendChild(line);

    // Auto-scroll to bottom
    logContent.scrollTop = logContent.scrollHeight;

    // Update log info
    document.getElementById('log-info').textContent = '最后更新: ' + new Date().toLocaleTimeString();
}

// Clear logs
async function clearLogs() {
    try {
        await fetch('/api/logs/clear', { method: 'POST' });
        document.getElementById('log-content').innerHTML = '';
        document.getElementById('log-info').textContent = '日志已清空';
        updateStatus('日志已清空');
    } catch (error) {
        console.error('Failed to clear logs:', error);
    }
}

// Update status
function updateStatus(message, type = 'info') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;

    // Remove old classes
    statusEl.classList.remove('error', 'warning', 'success');

    if (type === 'error') {
        statusEl.classList.add('error');
    } else if (type === 'warning') {
        statusEl.classList.add('warning');
    } else if (type === 'success') {
        statusEl.classList.add('success');
    }
}

// Check process status
async function checkProcessStatus() {
    try {
        const response = await fetch('/api/process/status');
        const data = await response.json();

        const stopBtn = document.getElementById('stop-btn');
        stopBtn.disabled = !data.running;

        if (data.running) {
            updateStatus('进程运行中...', 'success');
        }
    } catch (error) {
        console.error('Failed to check process status:', error);
    }

    // Check again in 2 seconds
    setTimeout(checkProcessStatus, 2000);
}

// Stop process
async function stopProcess() {
    try {
        const response = await fetch('/api/process/stop', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            updateStatus('进程已停止', 'warning');
        } else {
            updateStatus(data.error || '停止失败', 'error');
        }
    } catch (error) {
        console.error('Failed to stop process:', error);
        updateStatus('停止失败', 'error');
    }
}

// Start training (journey + training loop)
async function startTraining() {
    const character = document.getElementById('character').value;
    if (!character) {
        updateStatus('请先选择角色', 'error');
        return;
    }

    const data = {
        window_title: document.getElementById('window-title').value,
        interval: parseFloat(document.getElementById('interval').value),
        max_rounds: document.getElementById('max-rounds').value || null,
        profile: document.getElementById('profile').value,
        character: character,
        build_profile: document.getElementById('build-profile').value,
        classify_flag: document.getElementById('classify-mode').value,
        execute_clicks: document.getElementById('execute-clicks').checked,
        journey_difficulty: document.getElementById('journey-difficulty').value,
        seal_slot1: parseInt(document.getElementById('seal-slot1').value),
        seal_slot2: parseInt(document.getElementById('seal-slot2').value),
        support_card_group: parseInt(document.getElementById('support-card-group').value),
        friend_name: document.getElementById('friend-name').value,
    };

    try {
        updateStatus('启动旅程 + 训练循环...', 'info');
        const response = await fetch('/api/train/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('一键启动成功（旅程 → 训练）', 'success');
            appendLog(`\n[INFO] 旅程命令: ${result.journey_command}\n`);
            appendLog(`[INFO] 训练命令: ${result.train_command}\n`);
        } else {
            updateStatus(`启动失败: ${result.error || '未知错误'}`, 'error');
        }
    } catch (error) {
        console.error('Failed to start training:', error);
        updateStatus('启动失败', 'error');
    }
}

// Reload characters
async function reloadCharacters() {
    updateStatus('重载角色名册中...');
    await loadConfig();
    updateStatus('角色名册已重载', 'success');
}

// Start journey
async function startJourney() {
    const character = document.getElementById('character').value;
    if (!character) {
        updateStatus('请先选择角色', 'error');
        return;
    }

    const data = {
        character: character,
        difficulty: document.getElementById('journey-difficulty').value,
        seal_slot1: parseInt(document.getElementById('seal-slot1').value),
        seal_slot2: parseInt(document.getElementById('seal-slot2').value),
        support_card_group: parseInt(document.getElementById('support-card-group').value),
        friend_name: document.getElementById('friend-name').value,
    };

    try {
        updateStatus('启动旅程中...', 'info');
        const response = await fetch('/api/journey/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('旅程启动成功', 'success');
            appendLog(`\n[INFO] 旅程启动: ${character} - ${data.difficulty}\n`);
        } else {
            updateStatus(`旅程启动失败: ${result.error || '未知错误'}`, 'error');
        }
    } catch (error) {
        console.error('Failed to start journey:', error);
        updateStatus('旅程启动失败', 'error');
    }
}

// Capture screenshot
async function captureScreenshot() {
    const data = {
        window_title: document.getElementById('capture-window-title').value,
        output_path: document.getElementById('output-path').value,
        timestamp: document.getElementById('timestamp').checked,
    };

    try {
        const response = await fetch('/api/capture/screenshot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('截图命令已发送', 'success');
        }
    } catch (error) {
        console.error('Failed to capture screenshot:', error);
        updateStatus('截图失败', 'error');
    }
}

// List windows
async function listWindows() {
    try {
        const response = await fetch('/api/capture/list-windows', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            updateStatus('列出窗口命令已发送', 'success');
        }
    } catch (error) {
        console.error('Failed to list windows:', error);
        updateStatus('列出窗口失败', 'error');
    }
}

// Crop regions
async function cropRegions() {
    const imagePath = document.getElementById('calibrate-image').value;

    if (!imagePath) {
        updateStatus('请输入图片路径', 'error');
        return;
    }

    const data = {
        image_path: imagePath,
        profile: document.getElementById('calibrate-profile').value,
    };

    try {
        const response = await fetch('/api/calibrate/crop-regions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('裁剪区域命令已发送', 'success');
        } else {
            updateStatus(result.error || '裁剪失败', 'error');
        }
    } catch (error) {
        console.error('Failed to crop regions:', error);
        updateStatus('裁剪失败', 'error');
    }
}

// Read regions
async function readRegions() {
    const imagePath = document.getElementById('calibrate-image').value;

    if (!imagePath) {
        updateStatus('请输入图片路径', 'error');
        return;
    }

    const data = {
        image_path: imagePath,
        profile: document.getElementById('calibrate-profile').value,
        engine: document.getElementById('ocr-engine').value,
        prefix: document.getElementById('region-prefix').value || null,
    };

    try {
        const response = await fetch('/api/calibrate/read-regions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('读取 OCR 命令已发送', 'success');
        } else {
            updateStatus(result.error || '读取失败', 'error');
        }
    } catch (error) {
        console.error('Failed to read regions:', error);
        updateStatus('读取失败', 'error');
    }
}

// Run offline demo
async function runOfflineDemo() {
    const data = {
        profile: document.getElementById('offline-profile').value,
    };

    try {
        const response = await fetch('/api/offline/demo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('离线 Demo 已启动', 'success');
        }
    } catch (error) {
        console.error('Failed to run offline demo:', error);
        updateStatus('启动失败', 'error');
    }
}

// Run offline manifest
async function runOfflineManifest() {
    const manifestPath = document.getElementById('manifest-path').value;

    if (!manifestPath) {
        updateStatus('请输入 Manifest 路径', 'error');
        return;
    }

    const data = {
        manifest_path: manifestPath,
        jsonl: document.getElementById('jsonl-output').checked,
    };

    try {
        const response = await fetch('/api/offline/manifest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (result.success) {
            updateStatus('离线 Manifest 已启动', 'success');
        } else {
            updateStatus(result.error || '启动失败', 'error');
        }
    } catch (error) {
        console.error('Failed to run offline manifest:', error);
        updateStatus('启动失败', 'error');
    }
}

// Run tests
async function runTests() {
    try {
        const response = await fetch('/api/tests/run', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            updateStatus('单元测试已启动', 'success');
        }
    } catch (error) {
        console.error('Failed to run tests:', error);
        updateStatus('启动失败', 'error');
    }
}

// Log viewer functions
async function refreshLogList() {
    try {
        const response = await fetch('/api/logs/list');
        const result = await response.json();

        const select = document.getElementById('log-file-select');
        select.innerHTML = '<option value="">-- 选择日志文件 --</option>';

        result.files.forEach(file => {
            const option = document.createElement('option');
            option.value = file.name;
            const sizeKB = (file.size / 1024).toFixed(2);
            const date = new Date(file.modified * 1000).toLocaleString('zh-CN');
            option.textContent = `${file.name} (${sizeKB} KB, ${date})`;
            select.appendChild(option);
        });

        updateStatus(`找到 ${result.files.length} 个日志文件`, 'success');
    } catch (error) {
        console.error('Failed to load log list:', error);
        updateStatus('加载日志列表失败', 'error');
    }
}

async function loadLogFile() {
    const select = document.getElementById('log-file-select');
    const filename = select.value;

    if (!filename) {
        document.getElementById('log-viewer-content').textContent = '暂无内容';
        document.getElementById('log-viewer-info').textContent = '请选择日志文件';
        return;
    }

    try {
        const response = await fetch(`/api/logs/read?filename=${encodeURIComponent(filename)}`);
        const result = await response.json();

        if (result.success) {
            document.getElementById('log-viewer-content').textContent = result.content;
            document.getElementById('log-viewer-info').textContent = `${filename} (最后 1000 行)`;

            // 自动滚动到底部
            const viewer = document.getElementById('log-viewer-content');
            viewer.scrollTop = viewer.scrollHeight;

            updateStatus('日志加载成功', 'success');
        } else {
            document.getElementById('log-viewer-content').textContent = `错误: ${result.error}`;
            updateStatus('日志加载失败', 'error');
        }
    } catch (error) {
        console.error('Failed to load log file:', error);
        updateStatus('日志加载失败', 'error');
    }
}

function downloadCurrentLog() {
    const select = document.getElementById('log-file-select');
    const filename = select.value;

    if (!filename) {
        alert('请先选择日志文件');
        return;
    }

    const content = document.getElementById('log-viewer-content').textContent;
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);

    updateStatus('日志已下载', 'success');
}

// Auto-refresh log list when logs tab is opened
document.addEventListener('DOMContentLoaded', () => {
    const logsTab = document.querySelector('[data-tab="logs"]');
    if (logsTab) {
        logsTab.addEventListener('click', () => {
            setTimeout(refreshLogList, 100);
        });
    }
});
