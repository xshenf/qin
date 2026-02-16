"""
PySide6 主窗口 — 实时波形、电平表、音高显示

使用 pyqtgraph 实现高性能实时波形绘制，
集成 AudioIO 和 MIR 引擎的检测结果。
"""

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QStatusBar,
    QProgressBar, QGroupBox, QSplitter, QFrame,
    QFileDialog, QSlider
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor
import pyqtgraph as pg

from src.audio.audio_io import AudioIO
from src.ui.score_view import ScoreView


class WaveformWidget(pg.PlotWidget):
    """实时波形显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground('#1a1a2e')
        self.setTitle("实时波形", color='#e0e0e0', size='11pt')
        self.setLabel('left', '幅度')
        self.setLabel('bottom', '时间 (ms)')
        self.setYRange(-1, 1)
        self.showGrid(x=True, y=True, alpha=0.3)

        # 波形曲线
        pen = pg.mkPen(color='#00d4ff', width=1.5)
        self.curve = self.plot(pen=pen)

        # 配置
        self.display_ms = 100  # 显示最近 100ms

    def update_waveform(self, audio_data: np.ndarray, sample_rate: int):
        """更新波形显示"""
        n = len(audio_data)
        t = np.linspace(0, n / sample_rate * 1000, n)
        self.curve.setData(t, audio_data)


class SpectrumWidget(pg.PlotWidget):
    """实时频谱显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground('#1a1a2e')
        self.setTitle("频谱", color='#e0e0e0', size='11pt')
        self.setLabel('left', '幅度 (dB)')
        self.setLabel('bottom', '频率 (Hz)')
        self.setXRange(50, 2000)
        self.setYRange(-80, 0)
        self.setLogMode(x=True, y=False)
        self.showGrid(x=True, y=True, alpha=0.3)

        # 频谱曲线
        pen = pg.mkPen(color='#ff6b6b', width=1.5)
        self.curve = self.plot(pen=pen)

    def update_spectrum(self, audio_data: np.ndarray, sample_rate: int):
        """更新频谱显示"""
        if len(audio_data) < 1024:
            return

        # 使用 Hanning 窗
        windowed = audio_data[-2048:] * np.hanning(min(2048, len(audio_data[-2048:])))
        n = len(windowed)

        # FFT
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft) / n
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

        # 只显示 50-4000Hz
        mask = (freqs >= 50) & (freqs <= 4000)
        self.curve.setData(freqs[mask], magnitude_db[mask])


class LevelMeter(QProgressBar):
    """电平表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMinimum(-80)
        self.setMaximum(0)
        self.setValue(-80)
        self.setTextVisible(True)
        self.setFormat('%v dB')
        self.setFixedWidth(40)
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #333;
                border-radius: 3px;
                background: #1a1a2e;
                text-align: center;
                color: #e0e0e0;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff4444, stop:0.15 #ff8800,
                    stop:0.3 #ffcc00, stop:0.6 #44ff44,
                    stop:1 #00cc44
                );
            }
        """)


class PitchDisplay(QLabel):
    """音高显示组件"""

    def __init__(self, parent=None):
        super().__init__("--", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Consolas", 48, QFont.Weight.Bold))
        self.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
            }
        """)

    def set_pitch(self, note: str, frequency: float, cents: float):
        """设置检测到的音高"""
        cents_str = f"+{cents:.0f}" if cents >= 0 else f"{cents:.0f}"
        self.setText(f"{note}\n{frequency:.1f} Hz  ({cents_str}¢)")

        # 根据音准偏移着色
        if abs(cents) < 5:
            color = '#44ff44'  # 准确
        elif abs(cents) < 15:
            color = '#ffcc00'  # 偏差小
        else:
            color = '#ff4444'  # 偏差大

        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
            }}
        """)

    def clear_pitch(self):
        """清除显示"""
        self.setText("--")
        self.setStyleSheet("""
            QLabel {
                color: #555;
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
            }
        """)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guitar Pro — 专业吉他练习")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background: #0a0a1a;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1a3a6a;
            }
            QPushButton:pressed {
                background: #0f3460;
            }
            QPushButton:checked {
                background: #e94560;
                border-color: #e94560;
            }
            QLabel {
                color: #e0e0e0;
            }
            QComboBox {
                background: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QStatusBar {
                background: #0f0f23;
                color: #888;
            }
        """)

        # 音频引擎
        self.audio = AudioIO(sample_rate=44100, block_size=256)

        # 构建 UI
        self._build_ui()

        # 定时器：30fps 刷新 UI
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.setInterval(33)  # ~30fps

    def _build_ui(self):
        """构建界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === 顶部工具栏 ===
        toolbar = QHBoxLayout()

        # 打开文件按钮
        self.btn_open = QPushButton("📂 打开乐谱")
        self.btn_open.clicked.connect(self._open_score_file)
        toolbar.addWidget(self.btn_open)

        # 播放控制
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.clicked.connect(self._toggle_playback)
        toolbar.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.clicked.connect(self._stop_playback)
        toolbar.addWidget(self.btn_stop)

        # 速度滑块
        toolbar.addWidget(QLabel("速度:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(25)
        self.speed_slider.setMaximum(200)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        toolbar.addWidget(self.speed_slider)
        self.speed_label = QLabel("100%")
        self.speed_label.setFixedWidth(40)
        toolbar.addWidget(self.speed_label)

        # 谱面模式
        self.stave_combo = QComboBox()
        self.stave_combo.addItem("六线谱", "Tab")
        self.stave_combo.addItem("五线谱", "Score")
        self.stave_combo.addItem("五线+六线", "ScoreTab")
        self.stave_combo.currentIndexChanged.connect(self._on_stave_changed)
        toolbar.addWidget(self.stave_combo)

        toolbar.addStretch()

        # 设备选择
        toolbar.addWidget(QLabel("音频设备:"))
        self.device_combo = QComboBox()
        self._populate_devices()
        toolbar.addWidget(self.device_combo)

        # 录音按钮
        self.btn_record = QPushButton("🎤 开始采集")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._toggle_recording)
        toolbar.addWidget(self.btn_record)

        # 练习按钮
        self.btn_practice = QPushButton("🎸 练习模式")
        self.btn_practice.setCheckable(True)
        self.btn_practice.setEnabled(False)  # 先开启采集才能练习
        toolbar.addWidget(self.btn_practice)

        main_layout.addLayout(toolbar)

        # === 中间内容区 ===
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上半部：乐谱区域（AlphaTab WebView）
        self.score_view = ScoreView()
        self.score_view.scoreLoaded.connect(self._on_score_loaded)
        self.score_view.beatChanged.connect(self._on_beat_changed)
        self.score_view.positionChanged.connect(self._on_position_changed)
        self.score_view.playerFinished.connect(self._on_player_finished)
        splitter.addWidget(self.score_view)

        # 下半部：音频分析区域
        analysis_widget = QWidget()
        analysis_layout = QHBoxLayout(analysis_widget)
        analysis_layout.setSpacing(8)

        # 波形 + 频谱
        viz_layout = QVBoxLayout()
        self.waveform = WaveformWidget()
        self.spectrum = SpectrumWidget()
        viz_layout.addWidget(self.waveform)
        viz_layout.addWidget(self.spectrum)
        analysis_layout.addLayout(viz_layout, stretch=3)

        # 右侧面板：电平 + 音高
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # 电平表
        self.level_meter = LevelMeter()
        level_group = QGroupBox("电平")
        level_layout = QVBoxLayout(level_group)
        level_layout.addWidget(self.level_meter, alignment=Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(level_group)

        # 音高显示
        self.pitch_display = PitchDisplay()
        pitch_group = QGroupBox("检测音高")
        pitch_layout = QVBoxLayout(pitch_group)
        pitch_layout.addWidget(self.pitch_display)
        right_panel.addWidget(pitch_group)

        right_panel.addStretch()
        analysis_layout.addLayout(right_panel, stretch=1)

        splitter.addWidget(analysis_widget)
        splitter.setSizes([300, 400])  # 初始比例
        main_layout.addWidget(splitter)

        # === 状态栏 ===
        self.statusBar().showMessage("就绪 — 点击 🎤 开始采集 开始")

    def _populate_devices(self):
        """填充音频设备列表"""
        import sounddevice as sd
        devices = sd.query_devices()
        self.device_combo.clear()
        self.device_combo.addItem("默认设备", None)
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = f"[{i}] {dev['name']} ({dev['max_input_channels']}ch)"
                self.device_combo.addItem(name, i)

    def _toggle_recording(self, checked):
        """切换音频采集"""
        if checked:
            # 获取选择的设备
            device = self.device_combo.currentData()
            self.audio.device = device
            try:
                self.audio.start()
                self.btn_record.setText("⏹ 停止采集")
                self.btn_practice.setEnabled(True)
                self.ui_timer.start()
                self.statusBar().showMessage(
                    f"采集中 — SR: {self.audio.sample_rate}Hz, "
                    f"Block: {self.audio.block_size} samples "
                    f"({self.audio.block_size / self.audio.sample_rate * 1000:.1f}ms)"
                )
            except Exception as e:
                self.btn_record.setChecked(False)
                self.statusBar().showMessage(f"错误: {e}")
        else:
            self.audio.stop()
            self.ui_timer.stop()
            self.btn_record.setText("🎤 开始采集")
            self.btn_practice.setEnabled(False)
            self.pitch_display.clear_pitch()
            self.statusBar().showMessage("已停止")

    @Slot()
    def _update_ui(self):
        """UI 刷新（30fps 定时器触发）"""
        if not self.audio.is_running:
            return

        sr = self.audio.sample_rate

        # 获取音频数据
        waveform_data = self.audio.get_buffer(duration_ms=100)
        spectrum_data = self.audio.get_buffer(duration_ms=50)

        # 更新波形
        self.waveform.update_waveform(waveform_data, sr)

        # 更新频谱
        self.spectrum.update_spectrum(spectrum_data, sr)

        # 更新电平表
        rms_db = self.audio.get_rms_db()
        self.level_meter.setValue(int(max(-80, rms_db)))

        # TODO: 集成 MIR 引擎后更新音高显示
        # 暂时用简单的 FFT 峰值做演示
        if rms_db > -40:
            self._simple_pitch_detect(spectrum_data, sr)
        else:
            self.pitch_display.clear_pitch()

    def _simple_pitch_detect(self, audio: np.ndarray, sr: int):
        """简易 FFT 峰值音高检测（临时，后续替换为 CREPE/Basic Pitch）"""
        if len(audio) < 2048:
            return

        windowed = audio[-2048:] * np.hanning(2048)
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(2048, 1.0 / sr)

        # 限制在吉他范围
        mask = (freqs >= 70) & (freqs <= 1500)
        if not np.any(mask):
            return

        masked_mag = magnitude[mask]
        masked_freq = freqs[mask]

        peak_idx = np.argmax(masked_mag)
        freq = masked_freq[peak_idx]

        if freq < 70:
            return

        # 计算音名
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        midi = 69 + 12 * np.log2(freq / 440.0)
        note_idx = int(round(midi)) % 12
        octave = int(round(midi)) // 12 - 1
        cents = (midi - round(midi)) * 100

        note_name = f"{note_names[note_idx]}{octave}"
        self.pitch_display.set_pitch(note_name, freq, cents)

    # ==== 乐谱相关 ====

    def _open_score_file(self):
        """打开乐谱文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开乐谱文件",
            "",
            "乐谱文件 (*.gp3 *.gp4 *.gp5 *.gpx *.gp *.musicxml *.mxl *.xml *.mid *.midi);;所有文件 (*)"
        )
        if file_path:
            self.score_view.load_file(file_path)
            self.statusBar().showMessage(f"正在加载: {file_path}")

    def _toggle_playback(self):
        """播放/暂停切换"""
        self.score_view.play_pause()

    def _stop_playback(self):
        """停止播放"""
        self.score_view.stop()

    def _on_speed_changed(self, value):
        """速度滑块变化"""
        speed = value / 100.0
        self.speed_label.setText(f"{value}%")
        self.score_view.set_speed(speed)

    def _on_stave_changed(self, index):
        """谱面模式切换"""
        profile = self.stave_combo.currentData()
        if profile:
            self.score_view.set_stave_profile(profile)

    def _on_score_loaded(self, info: dict):
        """乐谱加载完成"""
        title = info.get('title', '未命名')
        artist = info.get('artist', '')
        tempo = info.get('tempo', '?')
        self.setWindowTitle(f"Guitar Pro — {title} - {artist}")
        self.statusBar().showMessage(f"已加载: {title} | {artist} | ♩={tempo}")

    def _on_beat_changed(self, data: dict):
        """当前拍子变化（练习模式用）"""
        # TODO: 连接到 PracticeEngine
        pass

    def _on_position_changed(self, data: dict):
        """播放位置变化"""
        # 更新状态栏时间
        current = data.get('currentTime', 0)
        end = data.get('endTime', 0)
        m1, s1 = divmod(int(current / 1000), 60)
        m2, s2 = divmod(int(end / 1000), 60)
        self.statusBar().showMessage(f"播放中: {m1}:{s1:02d} / {m2}:{s2:02d}")

    def _on_player_finished(self):
        """播放完成"""
        self.statusBar().showMessage("播放完成")

    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        self.ui_timer.stop()
        if self.audio.is_running:
            self.audio.stop()
        event.accept()
