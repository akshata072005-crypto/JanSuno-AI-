from __future__ import annotations

import streamlit as st
from streamlit.components.v1 import html


VOICE_HTML = """
<div style="width:100%;padding:12px;border:1px solid #dfe8f3;border-radius:12px;background:#f7fbff;">
    <div style="display:flex;gap:10px;align-items:center;">
        <button id="voiceButton" type="button" style="background:#0c6dfd;color:white;border:none;border-radius:8px;padding:10px 16px;cursor:pointer;font-weight:600;">🎤 Speak</button>
        <span id="voiceStatus" style="color:#284b63;font-size:14px;">Voice input is optional.</span>
    </div>
    <textarea id="voiceOutput" rows="4" style="width:100%;margin-top:10px;border-radius:8px;border:1px solid #dfe8f3;padding:8px;resize:vertical;" placeholder="Your spoken complaint appears here..."></textarea>
</div>
<script>
const VoiceRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const voiceButton = document.getElementById('voiceButton');
const voiceOutput = document.getElementById('voiceOutput');
const voiceStatus = document.getElementById('voiceStatus');

if (!VoiceRecognition) {
    voiceStatus.textContent = 'Voice recognition is not available in this browser.';
    voiceButton.disabled = true;
} else {
    const recognition = new VoiceRecognition();
    recognition.lang = 'en-IN';
    recognition.interimResults = false;
    recognition.continuous = false;

    voiceButton.addEventListener('click', () => {
        try {
            recognition.start();
            voiceStatus.textContent = 'Listening...';
        } catch (error) {
            voiceStatus.textContent = 'Microphone is already active.';
        }
    });

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        voiceOutput.value = transcript;
        voiceStatus.textContent = 'Voice captured successfully.';
        window.parent.postMessage({ type: 'streamlit:setComponentValue', value: transcript }, '*');
    };

    recognition.onerror = () => {
        voiceStatus.textContent = 'Voice capture failed. Please type manually.';
    };

    recognition.onend = () => {
        voiceStatus.textContent = 'Voice capture complete.';
    };
}
</script>
"""


def render_voice_input(default_value: str = "") -> str:
    """Return transcribed speech text if the browser supports speech recognition."""
    component_value = html(VOICE_HTML, height=200, scrolling=False)
    if component_value:
        return str(component_value)
    return default_value
