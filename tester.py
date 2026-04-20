import sys
import json
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QLineEdit, QPushButton,
    QVBoxLayout, QWidget, QLabel, QScrollArea
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QTextCursor

class StreamWorker(QThread):
    chunk_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "grok",
                    "messages": [{"role": "user", "content": self.prompt}],
                    "stream": True
                },
                stream=True,
                timeout=(10, 300)
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == '{"done": true}':
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                self.chunk_received.emit(content)
                        except json.JSONDecodeError:
                            continue
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class GrokOllamaTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grok Ollama Wrapper Tester - Port 11434")
        self.setMinimumSize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Status
        self.status = QLabel("🟢 Ready - Server running on http://localhost:11434")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        # Chat display
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        layout.addWidget(self.chat_area)

        # Input
        input_layout = QVBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here and press Enter or Send...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send to Grok")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

        self.append_message("System", "Welcome! This GUI talks directly to your local Grok wrapper on port 11434.\nMake sure the Python server and grok.com userscript are running.", "gray")

    def append_message(self, role: str, text: str, color: str = "black"):
        self.chat_area.append(f'<b><span style="color:{color};">{role}:</span></b> {text}')
        self.chat_area.moveCursor(QTextCursor.MoveOperation.End)

    def send_message(self):
        prompt = self.input_field.text().strip()
        if not prompt:
            return

        self.append_message("You", prompt, "blue")
        self.input_field.clear()
        self.send_btn.setEnabled(False)

        # Prepare the UI for Grok's reply
        self.chat_area.insertHtml('<br><b><span style="color:green;">Grok:</span></b> ')
        self.chat_area.moveCursor(QTextCursor.MoveOperation.End)

        # Start streaming worker
        self.worker = StreamWorker(prompt)
        # CHANGE: Connect to handle_chunk instead of append_message
        self.worker.chunk_received.connect(self.handle_chunk)
        self.worker.finished.connect(self.on_stream_finished)
        self.worker.error.connect(lambda err: self.append_message("Error", f"❌ {err}", "red"))
        self.worker.start()

    def handle_chunk(self, chunk):
        # This inserts text at the cursor WITHOUT a new line
        self.chat_area.insertPlainText(chunk)
        # Auto-scroll to bottom
        self.chat_area.moveCursor(QTextCursor.MoveOperation.End)

    def on_stream_finished(self):
        self.send_btn.setEnabled(True)
        # Add a small separator for the next turn
        self.chat_area.insertHtml('<br><i><span style="color:gray;">✅ Response complete</span></i><br>')
        self.chat_area.moveCursor(QTextCursor.MoveOperation.End)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GrokOllamaTester()
    window.show()
    sys.exit(app.exec())