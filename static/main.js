// Global state
let ws, audioContext, processor, source, stream;
let isRecording = false;
let timerInterval;
let startTime;
let audioBuffer = new Int16Array(0);
let wsConnected = false;
let streamInitialized = false;
let isAutoStarted = false;

// DOM elements
const recordButton = document.getElementById('recordButton');
const transcript = document.getElementById('transcript');
const enhancedTranscript = document.getElementById('enhancedTranscript');
const copyButton = document.getElementById('copyButton');
const copyEnhancedButton = document.getElementById('copyEnhancedButton');
const readabilityButton = document.getElementById('readabilityButton');
const correctnessButton = document.getElementById('correctnessButton');
const settingsButton = document.getElementById('settingsButton');
const settingsModal = document.getElementById('settingsModal');
const closeSettings = document.getElementById('closeSettings');
const saveSettings = document.getElementById('saveSettings');
const resetPrompts = document.getElementById('resetPrompts');
const readabilityPrompt = document.getElementById('readabilityPrompt');
const correctnessPrompt = document.getElementById('correctnessPrompt');

// Configuration
const targetSeconds = 5;
const urlParams = new URLSearchParams(window.location.search);
const autoStart = urlParams.get('start') === '1';

// Utility functions
const isMobileDevice = () => /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

async function copyToClipboard(text, button) {
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
        showCopiedFeedback(button, 'Copied!');
    } catch (err) {
        console.error('Clipboard copy failed:', err);
        // alert('Clipboard copy failed: ' + err.message);
        // We don't show this message because it's not accurate. We could still write to the clipboard in this case.
    }
}

function showCopiedFeedback(button, message) {
    if (!button) return;
    const originalText = button.textContent;
    button.textContent = message;
    setTimeout(() => {
        button.textContent = originalText;
    }, 2000);
}

// Timer functions
function startTimer() {
    clearInterval(timerInterval);
    document.getElementById('timer').textContent = '00:00';
    startTime = Date.now();
    timerInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const minutes = Math.floor(elapsed / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        document.getElementById('timer').textContent = 
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopTimer() {
    clearInterval(timerInterval);
}

// Audio processing
function createAudioProcessor() {
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (e) => {
        if (!isRecording) return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        const pcmData = new Int16Array(inputData.length);
        
        for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-32768, Math.min(32767, Math.floor(inputData[i] * 32767)));
        }
        
        const combinedBuffer = new Int16Array(audioBuffer.length + pcmData.length);
        combinedBuffer.set(audioBuffer);
        combinedBuffer.set(pcmData, audioBuffer.length);
        audioBuffer = combinedBuffer;
        
        if (audioBuffer.length >= 24000) {
            const sendBuffer = audioBuffer.slice(0, 24000);
            audioBuffer = audioBuffer.slice(24000);
            
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(sendBuffer.buffer);
            }
        }
    };
    return processor;
}

async function initAudio(stream) {
    audioContext = new AudioContext();
    source = audioContext.createMediaStreamSource(stream);
    processor = createAudioProcessor();
    source.connect(processor);
    processor.connect(audioContext.destination);
}

// WebSocket handling
function updateConnectionStatus(status) {
    const statusDot = document.getElementById('connectionStatus');
    statusDot.classList.remove('connected', 'connecting', 'idle');
    
    switch (status) {
        case 'connected':  // OpenAI is connected and ready
            statusDot.classList.add('connected');
            statusDot.style.backgroundColor = '#34C759';  // Green
            break;
        case 'connecting':  // Establishing OpenAI connection
            statusDot.classList.add('connecting');
            statusDot.style.backgroundColor = '#FF9500';  // Orange
            break;
        case 'idle':  // Client connected, OpenAI not connected
            statusDot.classList.add('idle');
            statusDot.style.backgroundColor = '#007AFF';  // Blue
            break;
        default:  // Disconnected
            statusDot.style.backgroundColor = '#FF3B30';  // Red
    }
}

function initializeWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${protocol}://${window.location.host}/api/v1/ws`);
    
    ws.onopen = () => {
        wsConnected = true;
        updateConnectionStatus(true);
        if (autoStart && !isRecording && !isAutoStarted) startRecording();
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch (data.type) {
            case 'status':
                updateConnectionStatus(data.status);
                if (data.status === 'idle') {
                    copyToClipboard(transcript.value, copyButton);
                }
                break;
            case 'text':
                if (data.isNewResponse) {
                    transcript.value = data.content;
                } else {
                    transcript.value += data.content;
                }
                transcript.scrollTop = transcript.scrollHeight;
                break;
            case 'error':
                alert(data.content);
                updateConnectionStatus('idle');
                break;
        }
    };
    
    ws.onclose = () => {
        wsConnected = false;
        updateConnectionStatus(false);
        setTimeout(initializeWebSocket, 1000);
    };
}

// Recording control
async function startRecording() {
    if (isRecording) return;
    
    try {
        transcript.value = '';
        enhancedTranscript.value = '';

        if (!streamInitialized) {
            stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                } 
            });
            streamInitialized = true;
        }

        if (!stream) throw new Error('Failed to initialize audio stream');
        if (!audioContext) await initAudio(stream);

        isRecording = true;
        await ws.send(JSON.stringify({ type: 'start_recording' }));
        
        startTimer();
        recordButton.classList.add('recording');
        
    } catch (error) {
        console.error('Error starting recording:', error);
        alert('Error accessing microphone: ' + error.message);
    }
}

async function stopRecording() {
    if (!isRecording) return;
    
    isRecording = false;
    stopTimer();
    
    if (audioBuffer.length > 0 && ws.readyState === WebSocket.OPEN) {
        ws.send(audioBuffer.buffer);
        audioBuffer = new Int16Array(0);
    }
    
    await new Promise(resolve => setTimeout(resolve, 500));
    await ws.send(JSON.stringify({ type: 'stop_recording' }));
    
    recordButton.classList.remove('recording');
}

// Event listeners
recordButton.onclick = () => isRecording ? stopRecording() : startRecording();
copyButton.onclick = () => copyToClipboard(transcript.value, copyButton);
copyEnhancedButton.onclick = () => copyToClipboard(enhancedTranscript.value, copyEnhancedButton);

// Handle spacebar toggle
document.addEventListener('keydown', (event) => {
    if (event.code === 'Space') {
        const activeElement = document.activeElement;
        if (!activeElement.tagName.match(/INPUT|TEXTAREA/) && !activeElement.isContentEditable) {
            event.preventDefault();
            recordButton.click();
        }
    }
});

// Settings management
function loadPrompts() {
    const defaultReadabilityPrompt = "这是一个语音转文字的文本，可能有识别不清和语义不明。请你理解文字背后的意思和意图，并对文本进行优化，使其更加清晰易读，结构明确。注意，保持原意不变，不用写你的整理思路和建议，直接输出你的整理结果，不要有任何其他多余的内容，比如“以下是整理后的内容”类似这种多余的话：";
    const defaultCorrectnessPrompt = "这是一个语音转文字的文本，可能有识别不清和语义不明。请你理解文字背后的意思和意图，并对文本进行一句话总结，大约30-60字，你自己把握，要求精炼要点。注意，保持原意不变，不用写你的整理思路和建议，直接输出你的整理结果，不要有任何其他多余的内容：";
    
    readabilityPrompt.value = localStorage.getItem('readabilityPrompt') || defaultReadabilityPrompt;
    correctnessPrompt.value = localStorage.getItem('correctnessPrompt') || defaultCorrectnessPrompt;
}

function savePrompts() {
    localStorage.setItem('readabilityPrompt', readabilityPrompt.value);
    localStorage.setItem('correctnessPrompt', correctnessPrompt.value);
}

function resetPromptsToDefault() {
    const defaultReadabilityPrompt = "这是一个语音转文字的文本，可能有识别不清和语义不明。请你理解文字背后的意思和意图，并对文本进行优化，使其更加清晰易读，结构明确。注意，保持原意不变，不用写你的整理思路和建议，直接输出你的整理结果，不要有任何其他多余的内容，比如“以下是整理后的内容”类似这种多余的话：";
    const defaultCorrectnessPrompt = "这是一个语音转文字的文本，可能有识别不清和语义不明。请你理解文字背后的意思和意图，并对文本进行一句话总结，大约30-60字，你自己把握，要求精炼要点。注意，保持原意不变，不用写你的整理思路和建议，直接输出你的整理结果，不要有任何其他多余的内容：";
    
    readabilityPrompt.value = defaultReadabilityPrompt;
    correctnessPrompt.value = defaultCorrectnessPrompt;
}

// Settings modal handlers
settingsButton.onclick = () => {
    settingsModal.style.display = 'flex';
    loadPrompts();
};

closeSettings.onclick = () => {
    settingsModal.style.display = 'none';
};

saveSettings.onclick = () => {
    savePrompts();
    settingsModal.style.display = 'none';
    showCopiedFeedback(saveSettings, '已保存！');
};

resetPrompts.onclick = () => {
    resetPromptsToDefault();
    showCopiedFeedback(resetPrompts, '已重置！');
};

// Close modal when clicking outside
settingsModal.onclick = (e) => {
    if (e.target === settingsModal) {
        settingsModal.style.display = 'none';
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeWebSocket();
    initializeTheme();
    loadPrompts();
    if (autoStart) initializeAudioStream();
});
// Readability and AI handlers
readabilityButton.onclick = async () => {
    startTimer();
    const inputText = transcript.value.trim();
    if (!inputText) {
        alert('Please enter text to enhance readability.');
        stopTimer();
        return;
    }

    try {
        const customPrompt = localStorage.getItem('readabilityPrompt') || "这是一个语音转文字的文本，可能有识别不清和语义不明。请你理解文字背后的意思和意图，并对文本进行优化，使其更加清晰易读，结构明确。注意，保持原意不变，不用写你的整理思路和建议，直接输出你的整理结果，不要有任何其他多余的内容，比如“以下是整理后的内容”类似这种多余的话：";
        const response = await fetch('/api/v1/readability', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: inputText,
                prompt: customPrompt
            })
        });

        if (!response.ok) throw new Error('Readability enhancement failed');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            fullText += decoder.decode(value, { stream: true });
            enhancedTranscript.value = fullText;
            enhancedTranscript.scrollTop = enhancedTranscript.scrollHeight;
        }

        if (!isMobileDevice()) copyToClipboard(fullText, copyEnhancedButton);
        stopTimer();

    } catch (error) {
        console.error('Error:', error);
        alert('Error enhancing readability');
        stopTimer();
    }
};



correctnessButton.onclick = async () => {
    startTimer();
    const inputText = transcript.value.trim();
    if (!inputText) {
        alert('请输入文本以生成一句话要点。');
        stopTimer();
        return;
    }

    try {
        const customPrompt = localStorage.getItem('correctnessPrompt') || "这是一个语音转文字的文本，可能有识别不清和语义不明。请你理解文字背后的意思和意图，并对文本进行一句话总结，大约30-60字，你自己把握，要求精炼要点。注意，保持原意不变，不用写你的整理思路和建议，直接输出你的整理结果，不要有任何其他多余的内容：";
        const response = await fetch('/api/v1/correctness', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: inputText,
                prompt: customPrompt
            })
        });

        if (!response.ok) throw new Error('生成一句话要点失败');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            fullText += decoder.decode(value, { stream: true });
            enhancedTranscript.value = fullText;
            enhancedTranscript.scrollTop = enhancedTranscript.scrollHeight;
        }

        if (!isMobileDevice()) copyToClipboard(fullText, copyEnhancedButton);
        stopTimer();

    } catch (error) {
        console.error('Error:', error);
        alert('生成一句话要点时发生错误');
        stopTimer();
    }
};

// Theme handling
function toggleTheme() {
    const body = document.body;
    const themeToggle = document.getElementById('themeToggle');
    const isDarkTheme = body.classList.toggle('dark-theme');
    
    // Update button text
    themeToggle.textContent = isDarkTheme ? '☀️' : '🌙';
    
    // Save preference to localStorage
    localStorage.setItem('darkTheme', isDarkTheme);
}

// Initialize theme from saved preference
function initializeTheme() {
    const darkTheme = localStorage.getItem('darkTheme') === 'true';
    const themeToggle = document.getElementById('themeToggle');
    
    if (darkTheme) {
        document.body.classList.add('dark-theme');
        themeToggle.textContent = '☀️';
    }
}

// Add to your existing event listeners
document.getElementById('themeToggle').onclick = toggleTheme;
