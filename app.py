from __future__ import annotations

from pathlib import Path
import json
import math
import random
import sys
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DB_PATH = BASE_DIR / "converted_data.db"

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, QUrl, QRectF, QPointF, QSize
from PySide6.QtGui import (
	QBrush,
	QColor,
	QDesktopServices,
	QFont,
	QIcon,
	QLinearGradient,
	QPainter,
	QPainterPath,
	QPen,
	QPixmap,
	QPixmapCache,
)
from PySide6.QtWidgets import (
	QApplication,
	QFrame,
	QGraphicsDropShadowEffect,
	QGraphicsOpacityEffect,
	QHeaderView,
	QHBoxLayout,
	QFileDialog,
	QLabel,
	QLineEdit,
	QListWidget,
	QListWidgetItem,
	QMainWindow,
	QMessageBox,
	QPlainTextEdit,
	QProgressBar,
	QPushButton,
	QScrollArea,
	QSizePolicy,
	QSplitter,
	QStackedWidget,
	QStyle,
	QTabWidget,
	QTableWidget,
	QTableWidgetItem,
	QTextEdit,
	QTreeWidget,
	QTreeWidgetItem,
	QVBoxLayout,
	QWidget,
)

from json_sql_converter import JsonSqlConverter, clean_identifier


class Theme:
	BG = "#050816"
	SURFACE = "#0b1220"
	CARD = "rgba(12,18,36,0.75)"
	PANEL = "rgba(8,14,26,0.86)"
	PURPLE = "#7b2cff"
	BLUE = "#00aaff"
	CYAN = "#4defff"
	TEXT = "#eaf6ff"
	MUTED = "#9fb0d9"
	DANGER = "#ff4d6d"


PLACEHOLDER_DOC = (
	"SQLify dynamically parses nested NoSQL JSON, normalizes arrays into child tables, "
	"and generates relational SQL structures with live schema inspection."
)


def load_qss(app: QApplication, path: Path) -> None:
	try:
		app.setStyleSheet(path.read_text(encoding="utf-8"))
	except Exception:
		pass


def pretty_size(size_bytes: int) -> str:
	units = ["B", "KB", "MB", "GB"]
	size = float(size_bytes)
	for unit in units:
		if size < 1024 or unit == units[-1]:
			return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
		size /= 1024
	return f"{size:.1f} GB"


def summarize_json(data: Any) -> dict[str, int | bool]:
	stats = {"objects": 0, "arrays": 0, "keys": 0, "depth": 0, "valid": True}

	def walk(value: Any, depth: int = 1) -> None:
		stats["depth"] = max(stats["depth"], depth)
		if isinstance(value, dict):
			stats["objects"] += 1
			stats["keys"] += len(value)
			for child in value.values():
				walk(child, depth + 1)
		elif isinstance(value, list):
			stats["arrays"] += 1
			for child in value:
				walk(child, depth + 1)

	walk(data)
	return stats


def table_sql(schema) -> str:
	columns = ['"id" INTEGER PRIMARY KEY AUTOINCREMENT']
	if schema.parent_fk:
		columns.append(f'"{schema.parent_fk}" INTEGER NOT NULL')
	for name, typ in sorted(schema.columns.items()):
		columns.append(f'"{name}" {typ}')
	if schema.parent_fk:
		columns.append(
			f'FOREIGN KEY("{schema.parent_fk}") REFERENCES "{schema.parent_table}"("id") ON DELETE CASCADE'
		)
	return f'CREATE TABLE IF NOT EXISTS "{schema.name}" ({", ".join(columns)});'


class AppRoot(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.phase = 0.0
		self.particles = [(random.random(), random.random(), random.uniform(0.6, 1.0)) for _ in range(40)]
		self.setObjectName("appRoot")
		self.setAutoFillBackground(False)

	def tick(self):
		self.phase += 0.01
		self.update()

	def paintEvent(self, event):
		p = QPainter(self)
		p.setRenderHint(QPainter.Antialiasing)
		w = self.width()
		h = self.height()

		bg = QLinearGradient(0, 0, 0, h)
		bg.setColorAt(0.0, QColor("#050816"))
		bg.setColorAt(1.0, QColor("#030411"))
		p.fillRect(self.rect(), bg)

		bg_path = ASSETS_DIR / "background.png"
		if bg_path.exists():
			pixmap = QPixmap(str(bg_path))
			if not pixmap.isNull():
				scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
				p.setOpacity(0.72)
				p.drawPixmap(0, 0, scaled)
				p.setOpacity(1.0)

		blob = QLinearGradient(0, h * 0.15, w, h * 0.9)
		blob.setColorAt(0.0, QColor(123, 44, 255, 45))
		blob.setColorAt(0.45, QColor(0, 170, 255, 28))
		blob.setColorAt(1.0, QColor(77, 239, 255, 18))
		p.fillRect(self.rect(), blob)

		grid_pen = QPen(QColor(255, 255, 255, 14))
		grid_pen.setWidth(1)
		p.setPen(grid_pen)
		for x in range(0, w, 80):
			p.drawLine(x, 0, x, h)
		for y in range(0, h, 80):
			p.drawLine(0, y, w, y)

		center = QPointF(w * 0.55, h * 0.32)
		for i in range(4):
			radius = 90 + i * 38
			pen = QPen(QColor(123, 44, 255, 50 - i * 8))
			pen.setWidth(2)
			p.setPen(pen)
			p.drawEllipse(center, radius, radius * 0.56)

		wave_y = h * 0.83
		path = QPainterPath()
		path.moveTo(0, wave_y)
		for x in range(0, w + 1, 10):
			y = wave_y + math.sin((x / max(1, w)) * 4.5 + self.phase * 6) * 18
			path.lineTo(x, y)
		wave_pen = QPen(QColor(123, 44, 255, 180))
		wave_pen.setWidth(2)
		p.setPen(wave_pen)
		p.drawPath(path)

		for x in range(0, w + 1, 16):
			y = int(wave_y + 18 + math.sin((x / max(1, w)) * 2.2 + self.phase * 3.0) * 8)
			p.setPen(Qt.NoPen)
			p.setBrush(QColor(77, 239, 255, 20))
			p.drawEllipse(QPointF(x, y), 2.5, 2.5)

		for px, py, power in self.particles:
			x = int(px * w)
			y = int(py * h)
			color = QColor(123, 44, 255, int(170 * power)) if random.random() > 0.5 else QColor(0, 170, 255, int(170 * power))
			p.setPen(Qt.NoPen)
			p.setBrush(color)
			p.drawEllipse(QPointF(x, y), 2.0 + power * 2.0, 2.0 + power * 2.0)

		vignette = QLinearGradient(w / 2, h / 2, w / 2, h / 2)
		vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
		vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
		p.fillRect(self.rect(), vignette)


class GlowFrame(QFrame):
	def __init__(self, parent=None, radius=22):
		super().__init__(parent)
		self.setObjectName("glassCard")
		self.setFrameShape(QFrame.NoFrame)
		self.setProperty("radius", radius)


class StatCard(GlowFrame):
	def __init__(self, title: str, value: str, subtitle: str = "", parent=None, on_click=None):
		super().__init__(parent)
		self._on_click = on_click
		self._click_target: QPushButton | None = None
		layout = QVBoxLayout(self)
		layout.setContentsMargins(18, 16, 18, 16)
		layout.setSpacing(6)
		self.title = QLabel(title)
		self.title.setObjectName("cardTitle")
		self.value = QLabel(value)
		self.value.setObjectName("cardValue")
		self.subtitle = QLabel(subtitle)
		self.subtitle.setObjectName("cardSubtitle")
		for label in (self.title, self.value, self.subtitle):
			label.setAttribute(Qt.WA_TransparentForMouseEvents)
		layout.addWidget(self.title)
		layout.addWidget(self.value)
		layout.addWidget(self.subtitle)
		layout.addStretch(1)
		if on_click is not None:
			self.setCursor(Qt.PointingHandCursor)
			self._click_target = QPushButton(self)
			self._click_target.setCursor(Qt.PointingHandCursor)
			self._click_target.setFlat(True)
			self._click_target.setStyleSheet("background: transparent; border: none;")
			self._click_target.clicked.connect(on_click)
			self._click_target.raise_()

	def setValue(self, value: str) -> None:
		self.value.setText(value)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self._click_target is not None:
			self._click_target.setGeometry(self.rect())

	def mousePressEvent(self, event):
		if self._on_click is not None and event.button() == Qt.LeftButton:
			self._on_click()
			return
		super().mousePressEvent(event)


class FeatureCard(GlowFrame):
	def __init__(self, icon_text: str, title: str, description: str, parent=None):
		super().__init__(parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(18, 16, 18, 16)
		layout.setSpacing(8)
		badge = QLabel(icon_text)
		badge.setObjectName("featureBadge")
		badge.setAlignment(Qt.AlignCenter)
		badge.setFixedSize(40, 40)
		title_label = QLabel(title)
		title_label.setObjectName("featureTitle")
		desc_label = QLabel(description)
		desc_label.setObjectName("featureDescription")
		desc_label.setWordWrap(True)
		layout.addWidget(badge, alignment=Qt.AlignLeft)
		layout.addWidget(title_label)
		layout.addWidget(desc_label)
		layout.addStretch(1)


class DataTree(QTreeWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setHeaderHidden(True)
		self.setObjectName("treeViewer")
		self.setUniformRowHeights(True)
		self.setIndentation(18)

	def populate(self, data: Any) -> None:
		self.clear()
		self._add_item(None, "root", data, 0)
		self.expandToDepth(2)

	def _add_item(self, parent, key: str, value: Any, depth: int) -> None:
		label = key if parent is None else f"{key}"
		if isinstance(value, dict):
			label = f"{key}  [object]"
		elif isinstance(value, list):
			label = f"{key}  [array x{len(value)}]"
		elif value is None:
			label = f"{key}: null"
		else:
			text = str(value)
			if len(text) > 80:
				text = text[:77] + "..."
			label = f"{key}: {text}"
		item = QTreeWidgetItem([label])
		item.setData(0, Qt.UserRole, depth)
		if parent is None:
			self.addTopLevelItem(item)
		else:
			parent.addChild(item)
		if isinstance(value, dict):
			for child_key, child_value in value.items():
				self._add_item(item, child_key, child_value, depth + 1)
		elif isinstance(value, list):
			for index, child_value in enumerate(value[:40]):
				self._add_item(item, f"[{index}]", child_value, depth + 1)


class PlainViewer(QPlainTextEdit):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setObjectName("codeViewer")
		self.setReadOnly(True)
		self.setLineWrapMode(QPlainTextEdit.NoWrap)
		font = QFont("Cascadia Mono")
		if not font.exactMatch():
			font = QFont("Consolas")
		font.setPointSize(10)
		self.setFont(font)


class EngineViz(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.phase = 0.0
		self.progress = 0.0
		self.setMinimumHeight(220)
		self.setMinimumWidth(340)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.timer = QTimer(self)
		self.timer.timeout.connect(self._tick)
		self.timer.start(35)

	def setProgress(self, value: float) -> None:
		self.progress = max(0.0, min(1.0, value))
		self.update()

	def _tick(self) -> None:
		self.phase += 0.02
		self.update()

	def paintEvent(self, event):
		p = QPainter(self)
		p.setRenderHint(QPainter.Antialiasing)
		p.setRenderHint(QPainter.TextAntialiasing)
		w = self.width()
		h = self.height()
		p.fillRect(self.rect(), QColor(0, 0, 0, 0))

		center = QPointF(w * 0.5, h * 0.45)
		# Background orbital rings
		for i in range(3):
			r = 85 + i * 32
			alpha = int(45 + 20 * math.sin(self.phase * 1.5 + i))
			pen = QPen(QColor(123, 44, 255, alpha))
			pen.setWidth(2)
			p.setPen(pen)
			p.drawEllipse(center, r, r * 0.65)

		# Top wave particle line
		p.setPen(Qt.NoPen)
		p.setBrush(QColor(77, 239, 255, 140))
		for x in range(10, w - 10, 16):
			y = int(h * 0.16 + math.sin(self.phase * 2.5 + x * 0.04) * 6)
			p.drawEllipse(QPointF(x, y), 2.0, 2.0)

		# 3 Process Badges
		steps = [
			("JSON INPUT", QColor(0, 170, 255)),
			("NORMALIZATION", QColor(123, 44, 255)),
			("SQLITE TABLES", QColor(77, 239, 255)),
		]
		card_w = min(140, max(110, int(w * 0.22)))
		card_h = 56
		y = int(h * 0.45)

		positions_x = [
			int(w * 0.20),
			int(w * 0.50),
			int(w * 0.80),
		]

		# Connecting flow arrows
		for i in range(2):
			sx = positions_x[i] + card_w // 2 + 10
			ex = positions_x[i + 1] - card_w // 2 - 10
			if ex > sx:
				arrow_pen = QPen(QColor(77, 239, 255, 200), 2.5)
				p.setPen(arrow_pen)
				p.drawLine(sx, y, ex, y)
				# Arrow head
				p.drawLine(ex, y, ex - 8, y - 6)
				p.drawLine(ex, y, ex - 8, y + 6)

		# Draw cards
		for i, (label, accent_color) in enumerate(steps):
			cx = positions_x[i]
			rect = QRectF(cx - card_w / 2, y - card_h / 2, card_w, card_h)

			# Card Background gradient
			grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
			grad.setColorAt(0, QColor(18, 26, 52, 235))
			grad.setColorAt(1, QColor(9, 14, 30, 245))

			# Glowing border
			p.setPen(QPen(accent_color, 1.8))
			p.setBrush(QBrush(grad))
			p.drawRoundedRect(rect, 14, 14)

			# Text label
			font = QFont("Segoe UI", 9, QFont.Bold)
			p.setFont(font)
			p.setPen(QColor(234, 246, 255))
			p.drawText(rect, Qt.AlignCenter, label)

		# Bottom Progress Bar
		bar_w = int(w * 0.84)
		bar_x = int((w - bar_w) / 2)
		bar_y = int(h * 0.82)
		bar = QRectF(bar_x, bar_y, bar_w, 8)

		p.setPen(Qt.NoPen)
		p.setBrush(QColor(255, 255, 255, 22))
		p.drawRoundedRect(bar, 4, 4)

		if self.progress > 0:
			fill = QRectF(bar.x(), bar.y(), bar.width() * self.progress, bar.height())
			fill_grad = QLinearGradient(fill.topLeft(), fill.topRight())
			fill_grad.setColorAt(0, QColor(123, 44, 255))
			fill_grad.setColorAt(1, QColor(77, 239, 255))
			p.setBrush(QBrush(fill_grad))
			p.drawRoundedRect(fill, 4, 4)


class RelationGraph(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.relations: list[tuple[str, str]] = []
		self.nodes: list[str] = []
		self._zoom = 0.85
		self.setMinimumHeight(220)
		self.setFocusPolicy(Qt.StrongFocus)

	def _set_zoom(self, value: float) -> None:
		self._zoom = max(0.45, min(2.5, value))
		self.update()

	def wheelEvent(self, event):
		delta = event.angleDelta().y()
		if delta == 0:
			event.ignore()
			return
		step = 1.12 if delta > 0 else 1 / 1.12
		self._set_zoom(self._zoom * step)
		event.accept()

	def setRelations(self, relations: list[tuple[str, str]]) -> None:
		self.relations = relations
		self.nodes = []
		for left, right in relations:
			if left not in self.nodes:
				self.nodes.append(left)
			if right not in self.nodes:
				self.nodes.append(right)
		self._set_zoom(0.85)
		self.update()

	def paintEvent(self, event):
		p = QPainter(self)
		p.setRenderHint(QPainter.Antialiasing)
		w = self.width()
		h = self.height()
		metrics = p.fontMetrics()
		if not self.nodes:
			p.setPen(QColor(234, 246, 255, 180))
			p.drawText(self.rect(), Qt.AlignCenter, "No relations available for this table")
			return
		p.translate(w / 2, h / 2)
		p.scale(self._zoom, self._zoom)
		positions: dict[str, QPointF] = {}
		cx = 0
		cy = 0
		radius = min(w, h) * 0.28
		for i, node in enumerate(self.nodes):
			angle = (2 * math.pi * i / max(1, len(self.nodes))) - math.pi / 2
			positions[node] = QPointF(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
		for left, right in self.relations:
			start = positions.get(left, QPointF(cx, cy))
			end = positions.get(right, QPointF(cx, cy))
			pen = QPen(QColor(77, 239, 255, 120))
			pen.setWidth(3)
			p.setPen(pen)
			p.drawLine(start, end)
		for node, pos in positions.items():
			label = node.replace("_", "\n")
			lines = label.splitlines() or [label]
			text_width = max(metrics.horizontalAdvance(line) for line in lines)
			rect_width = max(120, min(text_width + 28, 220))
			rect_height = max(56, min(len(lines) * metrics.lineSpacing() + 24, 140))
			rect = QRectF(pos.x() - rect_width / 2, pos.y() - rect_height / 2, rect_width, rect_height)
			grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
			grad.setColorAt(0, QColor(12, 18, 36, 240))
			grad.setColorAt(1, QColor(8, 12, 28, 245))
			p.setPen(QPen(QColor(123, 44, 255, 100), 1))
			p.setBrush(QBrush(grad))
			p.drawRoundedRect(rect, 18, 18)
			p.setPen(QColor(234, 246, 255))
			p.drawText(rect.adjusted(10, 8, -10, -8), Qt.AlignCenter | Qt.TextWordWrap, label)


class BasePage(QWidget):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(parent)
		self.main = main

	def refresh(self) -> None:
		pass


class HomePage(BasePage):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(main, parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(18)

		hero = GlowFrame()
		hero.setObjectName("heroCard")
		hero_layout = QVBoxLayout(hero)
		hero_layout.setContentsMargins(30, 30, 30, 24)
		hero_layout.setSpacing(16)

		top = QHBoxLayout()
		top.setSpacing(18)
		illustration = EngineViz()
		illustration.setMinimumHeight(220)
		illustration.setMaximumHeight(260)
		illustration.setMaximumWidth(460)
		top.addWidget(illustration, 1)

		copy = QVBoxLayout()
		copy.setSpacing(12)
		heading = QLabel("SQLify")
		heading.setObjectName("heroTitle")
		subtitle = QLabel("Convert nested NoSQL JSON structures into normalized SQL databases dynamically.")
		subtitle.setObjectName("heroDesc")
		subtitle.setWordWrap(True)
		subtitle.setMaximumWidth(560)
		copy.addStretch(1)
		copy.addWidget(heading)
		copy.addWidget(subtitle)
		copy.addSpacing(8)
		cta_row = QHBoxLayout()
		cta_row.setSpacing(12)
		open_btn = QPushButton("Open JSON File")
		open_btn.setObjectName("primaryButton")
		open_btn.clicked.connect(main.open_json_file)
		doc_btn = QPushButton("View Documentation")
		doc_btn.setObjectName("secondaryButton")
		doc_btn.clicked.connect(main.open_documentation)
		cta_row.addWidget(open_btn)
		cta_row.addWidget(doc_btn)
		cta_row.addStretch(1)
		copy.addLayout(cta_row)
		copy.addStretch(1)
		top.addLayout(copy, 1)
		hero_layout.addLayout(top)

		stats = QHBoxLayout()
		stats.setSpacing(12)
		for title, value, sub in [
			("Dynamic Parsing", "Live", "Detect structure at runtime"),
			("Auto Normalization", "1NF / 2NF / 3NF", "Separate arrays into child tables"),
			("Schema Detection", "Adaptive", "Infer SQL types and keys"),
			("SQL Generation", "SQLite", "Create tables and insert data"),
		]:
			stats.addWidget(FeatureCard("◆", title, f"{value}\n{sub}"))
		hero_layout.addLayout(stats)

		layout.addWidget(hero)


class JsonPage(BasePage):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(main, parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(14)

		self.metrics_row = QHBoxLayout()
		self.metrics_row.setSpacing(12)
		self.metric_cards = [
			StatCard("File Name", "-", "No file loaded"),
			StatCard("File Size", "-", ""),
			StatCard("Object Count", "-", ""),
			StatCard("Arrays Count", "-", ""),
			StatCard("Nesting Depth", "-", ""),
			StatCard("JSON Validity", "-", ""),
		]
		for card in self.metric_cards:
			self.metrics_row.addWidget(card)
		layout.addLayout(self.metrics_row)

		body = QSplitter(Qt.Horizontal)
		body.setChildrenCollapsible(False)

		left_panel = GlowFrame()
		left_panel.setObjectName("sidePanel")
		left_layout = QVBoxLayout(left_panel)
		left_layout.setContentsMargins(16, 16, 16, 16)
		left_layout.setSpacing(10)
		left_title = QLabel("JSON Hierarchy")
		left_title.setObjectName("panelTitle")
		self.search = QLineEdit()
		self.search.setPlaceholderText("Search keys...")
		self.search.setObjectName("searchBox")
		self.search.textChanged.connect(self._filter_tree)
		self.tree = DataTree()
		left_layout.addWidget(left_title)
		left_layout.addWidget(self.search)
		left_layout.addWidget(self.tree, 1)

		right_panel = GlowFrame()
		right_panel.setObjectName("codePanel")
		right_layout = QVBoxLayout(right_panel)
		right_layout.setContentsMargins(16, 16, 16, 16)
		right_layout.setSpacing(10)
		right_title = QLabel("Pretty JSON Viewer")
		right_title.setObjectName("panelTitle")
		self.viewer = PlainViewer()
		right_layout.addWidget(right_title)
		right_layout.addWidget(self.viewer, 1)

		body.addWidget(left_panel)
		body.addWidget(right_panel)
		body.setStretchFactor(0, 1)
		body.setStretchFactor(1, 1)
		layout.addWidget(body, 1)

		self.log_panel = PlainViewer()
		self.log_panel.setMaximumHeight(140)
		layout.addWidget(self.log_panel)

		self._current_data = None
		self._current_text = ""

	def _filter_tree(self, text: str) -> None:
		text = text.strip().lower()
		if not text:
			self.tree.collapseAll()
			self.tree.expandToDepth(1)
			return
		self.tree.expandAll()
		root = self.tree.topLevelItem(0)
		if root:
			self._filter_item(root, text)

	def _filter_item(self, item: QTreeWidgetItem, text: str) -> bool:
		match = text in item.text(0).lower()
		child_match = False
		for i in range(item.childCount()):
			child_match = self._filter_item(item.child(i), text) or child_match
		item.setHidden(not (match or child_match))
		return match or child_match

	def refresh(self) -> None:
		data = self.main.current_data
		if data is None:
			self._current_data = None
			self._current_text = ""
			self.tree.clear()
			self.viewer.setPlainText("No JSON loaded. Import a file to preview its structure here.")
			stats = {"objects": 0, "arrays": 0, "depth": 0, "valid": True}
		else:
			self._current_data = data
			self.tree.populate(data)
			self._current_text = json.dumps(data, indent=2, ensure_ascii=False)
			self.viewer.setPlainText(self._current_text)
			stats = summarize_json(data)
		path = self.main.current_json_path
		file_name = path.name if path else "No JSON loaded"
		size = pretty_size(path.stat().st_size) if path and path.exists() else "-"
		values = [
			file_name,
			size,
			str(stats["objects"]),
			str(stats["arrays"]),
			str(stats["depth"]),
			"Valid" if stats["valid"] else "Invalid",
		]
		for card, value in zip(self.metric_cards, values, strict=True):
			card.setValue(value)
		self.log_panel.setPlainText(
			"Parser status: ready\n"
			f"Detected objects: {stats['objects']}\n"
			f"Detected arrays: {stats['arrays']}\n"
			f"Maximum nesting depth: {stats['depth']}\n"
			"Structure inspection: complete"
		)


class ConvertPage(BasePage):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(main, parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(14)

		top = QSplitter(Qt.Horizontal)
		top.setChildrenCollapsible(False)

		left = GlowFrame()
		left.setObjectName("enginePanel")
		left_layout = QVBoxLayout(left)
		left_layout.setContentsMargins(16, 16, 16, 16)
		left_layout.setSpacing(10)
		left_title = QLabel("Conversion Engine")
		left_title.setObjectName("panelTitle")
		self.engine = EngineViz()
		self.engine.setMinimumHeight(360)
		self.flow_note = QLabel(
			"Flatten nested objects, generate child tables for arrays, and keep foreign keys connected to the parent table."
		)
		self.flow_note.setWordWrap(True)
		self.flow_note.setObjectName("heroDesc")
		left_layout.addWidget(left_title)
		left_layout.addWidget(self.engine, 1)
		left_layout.addWidget(self.flow_note)

		right = GlowFrame()
		right.setObjectName("logPanel")
		right_layout = QVBoxLayout(right)
		right_layout.setContentsMargins(16, 16, 16, 16)
		right_layout.setSpacing(10)
		right_title = QLabel("Live Conversion Logs")
		right_title.setObjectName("panelTitle")
		self.logs = PlainViewer()
		right_layout.addWidget(right_title)
		right_layout.addWidget(self.logs, 1)

		top.addWidget(left)
		top.addWidget(right)
		top.setStretchFactor(0, 2)
		top.setStretchFactor(1, 1)
		layout.addWidget(top, 1)

		viz_row = QHBoxLayout()
		viz_row.setSpacing(12)
		self.flatten_card = FeatureCard(
			"↘",
			"Flattening",
			"address.city → address_city\naddress.district → address_district",
		)
		self.normalize_card = FeatureCard(
			"⟷",
			"Array Normalization",
			"phones[] and courses[] become child tables with 1:N relations.",
		)
		self.relation_card = FeatureCard(
			"⇄",
			"Relation Mapping",
			"Primary keys and foreign keys remain linked across generated tables.",
		)
		viz_row.addWidget(self.flatten_card)
		viz_row.addWidget(self.normalize_card)
		viz_row.addWidget(self.relation_card)
		layout.addLayout(viz_row)

		bottom = GlowFrame()
		bottom.setObjectName("toolbarPanel")
		bottom_layout = QHBoxLayout(bottom)
		bottom_layout.setContentsMargins(16, 14, 16, 14)
		bottom_layout.setSpacing(14)
		self.progress = QProgressBar()
		self.progress.setRange(0, 100)
		self.progress.setValue(0)
		self.progress.setTextVisible(True)
		self.tables_label = QLabel("Tables: 0")
		self.relations_label = QLabel("Relations: 0")
		self.speed_label = QLabel("Speed: idle")
		self.convert_btn = QPushButton("Start Conversion")
		self.convert_btn.setObjectName("primaryButton")
		self.convert_btn.clicked.connect(self.main.convert_json)
		bottom_layout.addWidget(self.progress, 2)
		bottom_layout.addWidget(self.tables_label)
		bottom_layout.addWidget(self.relations_label)
		bottom_layout.addWidget(self.speed_label)
		bottom_layout.addWidget(self.convert_btn)
		layout.addWidget(bottom)

	def refresh(self) -> None:
		tables = self.main.converter.list_tables()
		relations = sum(1 for schema in self.main.converter.schemas.values() if schema.parent_fk)
		self.tables_label.setText(f"Tables: {len(tables)}")
		self.relations_label.setText(f"Relations: {relations}")
		self.speed_label.setText("Speed: ready")
		self.logs.setPlainText(
			"Detecting objects\n"
			"Detecting arrays\n"
			"Flattening nested objects\n"
			"Creating child tables\n"
			"Generating primary keys\n"
			"Creating foreign keys\n"
			"Building SQL queries\n"
			"Executing SQLite commands"
		)
		self.engine.setProgress(0.75 if tables else 0.2)


class TablesPage(BasePage):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(main, parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(14)

		self.analytics_row = QHBoxLayout()
		self.analytics_row.setSpacing(12)
		self.analytics_cards = [
			StatCard("Total Rows", "0"),
			StatCard("Total Columns", "0"),
			StatCard("Primary Keys", "0"),
			StatCard("Foreign Keys", "0"),
			StatCard("Relation Count", "0"),
			StatCard("Arrays Detected", "0"),
			StatCard("Nested Objects", "0"),
			StatCard("Table Size", "0"),
		]
		for card in self.analytics_cards:
			self.analytics_row.addWidget(card)
		layout.addLayout(self.analytics_row)

		body = QSplitter(Qt.Horizontal)
		body.setChildrenCollapsible(False)

		left = GlowFrame()
		left.setObjectName("sidePanel")
		left_layout = QVBoxLayout(left)
		left_layout.setContentsMargins(16, 16, 16, 16)
		left_layout.setSpacing(10)
		left_layout.addWidget(QLabel("Generated Tables"))
		self.tables_list = QListWidget()
		self.tables_list.currentTextChanged.connect(self.load_table)
		left_layout.addWidget(self.tables_list, 1)

		center = GlowFrame()
		center.setObjectName("codePanel")
		center_layout = QVBoxLayout(center)
		center_layout.setContentsMargins(16, 16, 16, 16)
		center_layout.setSpacing(10)
		self.table_widget = QTableWidget()
		self.table_widget.setObjectName("tableViewer")
		self.table_widget.setAlternatingRowColors(True)
		self.table_widget.setSortingEnabled(True)
		self.table_widget.setShowGrid(True)
		self.table_widget.setWordWrap(True)
		center_layout.addWidget(self.table_widget, 1)
		# only show the table preview in the center for clarity

		# add only left and center panels so the table is the main focus
		body.addWidget(left)
		body.addWidget(center)
		body.setStretchFactor(0, 1)
		body.setStretchFactor(1, 3)
		layout.addWidget(body, 1)

		self._all_tables: list[str] = []
		self._table_cache: dict[str, tuple[list[str], list[tuple[Any, ...]]]] = {}

	def refresh(self) -> None:
		self._all_tables = self.main.converter.list_tables()
		self.tables_list.clear()
		for table in self._all_tables:
			rows = self.main.converter.table_rows(table)[1]
			item = QListWidgetItem(f"{table}   ·   {len(rows)} rows")
			item.setData(Qt.UserRole, table)
			self.tables_list.addItem(item)
			self._table_cache[table] = self.main.converter.table_rows(table)
		if self.tables_list.count() and self.tables_list.currentRow() < 0:
			self.tables_list.setCurrentRow(0)
		elif self.tables_list.count():
			self.load_table(self.tables_list.currentItem().data(Qt.UserRole))
		else:
			self.table_widget.clear()
			self.table_widget.setRowCount(1)
			self.table_widget.setColumnCount(1)
			self.table_widget.setHorizontalHeaderLabels(["Info"])
			from PySide6.QtWidgets import QTableWidgetItem
			self.table_widget.setItem(0, 0, QTableWidgetItem("-- No tables yet"))
		self._update_analytics()

	def filter_tables(self, text: str) -> None:
		text = text.lower().strip()
		for row in range(self.tables_list.count()):
			item = self.tables_list.item(row)
			item.setHidden(text not in item.text().lower())

	def _update_analytics(self) -> None:
		tables = self.main.converter.list_tables()
		rows_total = 0
		cols_total = 0
		pk_total = len(tables)
		fk_total = 0
		relations = []
		arrays = 0
		nested = 0
		for table in tables:
			cols, rows = self.main.converter.table_rows(table)
			rows_total += len(rows)
			cols_total += max(0, len(cols) - 1)
			schema = self.main.converter.schemas.get(table)
			if schema and schema.parent_fk:
				fk_total += 1
				relations.append((schema.parent_table or "root", table))
			if schema and schema.parent_table:
				arrays += 1
			if schema and len(schema.columns) > 4:
				nested += 1
		for card, value in zip(self.analytics_cards, [
			str(rows_total), str(cols_total), str(pk_total), str(fk_total), str(len(relations)), str(arrays), str(nested), pretty_size(rows_total * max(1, cols_total) * 32),
		], strict=True):
			card.setValue(value)
		# right-side relation graph removed in compact view

	def load_table(self, table_name: str) -> None:
		if not table_name:
			return
		if isinstance(self.tables_list.currentItem(), QListWidgetItem):
			candidate = self.tables_list.currentItem().data(Qt.UserRole)
			if candidate:
				table_name = candidate
		if table_name not in self._table_cache:
			self._table_cache[table_name] = self.main.converter.table_rows(table_name)
		cols, rows = self._table_cache[table_name]
		self.table_widget.setColumnCount(len(cols))
		self.table_widget.setHorizontalHeaderLabels(cols)
		self.table_widget.setRowCount(len(rows))
		for r, row in enumerate(rows):
			for c, value in enumerate(row):
				item = QTableWidgetItem(str(value))
				item.setToolTip(str(value))
				self.table_widget.setItem(r, c, item)
		self.table_widget.resizeColumnsToContents()
		self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
		self.table_widget.horizontalHeader().setStretchLastSection(True)
		# compact view: only populate the table preview; other previews removed
		# keep table headers and rows already set above

	def _build_insert_preview(self, table_name: str, cols: list[str], rows: list[tuple[Any, ...]]) -> str:
		if not rows:
			return "-- No rows to preview"
		preview = []
		for row in rows[:6]:
			column_sql = ", ".join(f'"{c}"' for c in cols)
			values = []
			for value in row:
				if value is None:
					values.append("NULL")
				elif isinstance(value, str):
					values.append("'" + value.replace("'", "''") + "'")
				else:
					values.append(str(value))
			preview.append(
				f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({", ".join(values)});'
			)
		return "\n".join(preview)

	def _build_relation_preview(self, table_name: str) -> str:
		schema = self.main.converter.schemas.get(table_name)
		if not schema:
			return "-- No relations available"
		lines = [f"Table: {table_name}", f"Parent: {schema.parent_table or '-'}", f"Foreign key: {schema.parent_fk or '-'}"]
		for child_name, child_schema in self.main.converter.schemas.items():
			if child_schema.parent_table == table_name:
				lines.append(f"Child table: {child_name}  ->  {child_schema.parent_fk}")
		return "\n".join(lines)


class SchemaPage(BasePage):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(main, parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(14)

		stats_row = QHBoxLayout()
		stats_row.setSpacing(12)
		self.stats = [
			StatCard("Total Tables", "0"),
			StatCard("Total Columns", "0"),
			StatCard("Total Relations", "0"),
			StatCard("Arrays Detected", "0"),
			StatCard("Nested Structures", "0"),
			StatCard("Generated Foreign Keys", "0"),
		]
		for card in self.stats:
			stats_row.addWidget(card)
		layout.addLayout(stats_row)

		body = QSplitter(Qt.Horizontal)
		body.setChildrenCollapsible(False)

		left = GlowFrame()
		left_layout = QVBoxLayout(left)
		left_layout.setContentsMargins(16, 16, 16, 16)
		left_layout.setSpacing(10)
		left_layout.addWidget(QLabel("Detected Tables"))
		self.schema_tables = QListWidget()
		self.schema_tables.currentTextChanged.connect(self.load_schema)
		left_layout.addWidget(self.schema_tables, 1)

		center = GlowFrame()
		center_layout = QVBoxLayout(center)
		center_layout.setContentsMargins(16, 16, 16, 16)
		center_layout.setSpacing(10)
		center_layout.addWidget(QLabel("Schema Preview"))
		self.schema_summary = PlainViewer()
		self.schema_summary.setMaximumHeight(0)
		self.schema_summary.setVisible(False)

		self.detail_tabs = QTabWidget()
		self.sql_create = PlainViewer()
		self.sql_insert = PlainViewer()
		self.schema_graph = RelationGraph()
		self.detail_tabs.addTab(self.sql_create, "CREATE TABLE SQL")
		self.detail_tabs.addTab(self.sql_insert, "INSERT SQL")
		self.detail_tabs.addTab(self.schema_graph, "Relationships")
		center_layout.addWidget(self.detail_tabs, 1)

		right = GlowFrame()
		right_layout = QVBoxLayout(right)
		right_layout.setContentsMargins(16, 16, 16, 16)
		right_layout.setSpacing(10)
		right_layout.addWidget(QLabel("Normalization"))
		self.norm_cards = QHBoxLayout()
		self.norm_cards.setSpacing(10)
		self.n1 = FeatureCard("1", "1NF", "Atomic columns, no repeating groups.")
		self.n2 = FeatureCard("2", "2NF", "Dependent fields separated into child tables.")
		self.n3 = FeatureCard("3", "3NF", "Redundancy reduced through relation mapping.")
		for card in (self.n1, self.n2, self.n3):
			self.norm_cards.addWidget(card)
		right_layout.addLayout(self.norm_cards)
		self.schema_stats = PlainViewer()
		right_layout.addWidget(self.schema_stats, 1)

		body.addWidget(left)
		body.addWidget(center)
		body.addWidget(right)
		body.setStretchFactor(0, 1)
		body.setStretchFactor(1, 2)
		body.setStretchFactor(2, 1)
		layout.addWidget(body, 1)

	def refresh(self) -> None:
		tables = self.main.converter.list_tables()
		self.schema_tables.clear()
		for table in tables:
			self.schema_tables.addItem(table)
		if self.schema_tables.count():
			self.schema_tables.setCurrentRow(0)
			self.load_schema(self.schema_tables.currentItem().text())
		else:
			self.schema_summary.clear()
			self.schema_stats.setPlainText("No schema generated yet.")
			self.sql_create.setPlainText("-- Convert a JSON file to generate SQL schema")
			self.sql_insert.setPlainText("-- Convert a JSON file to generate insert previews")
			self.schema_graph.setRelations([])
		self._update_stats()

	def _update_stats(self) -> None:
		tables = self.main.converter.list_tables()
		columns = 0
		relations = 0
		arrays = 0
		nested = 0
		for name in tables:
			schema = self.main.converter.schemas.get(name)
			if schema:
				columns += len(schema.columns)
				if schema.parent_table:
					relations += 1
					arrays += 1
				if len(schema.columns) > 3:
					nested += 1
		for card, value in zip(self.stats, [str(len(tables)), str(columns), str(relations), str(arrays), str(nested), str(relations)], strict=True):
			card.setValue(value)
	def load_schema(self, table_name: str) -> None:
		schema = self.main.converter.schemas.get(table_name)
		if not schema:
			return
		columns_text = [f"{column} : {typ}" for column, typ in sorted(schema.columns.items())]
		self.schema_stats.setPlainText(
			"\n".join([
				f"Table: {table_name}",
				f"Parent table: {schema.parent_table or '-'}",
				f"Foreign key: {schema.parent_fk or '-'}",
				f"Columns detected: {len(schema.columns)}",
				f"Normalization status: {('1NF' if not schema.parent_table else '3NF-ready')}",
			])
		)
		self.schema_summary.clear()
		data_cols, data_rows = self.main.converter.table_rows(table_name)
		self.sql_create.setPlainText(table_sql(schema) + "\n\n" + self.main.converter.generated_schema_text())
		self.sql_insert.setPlainText(
			"\n".join(
				[
					f"INSERT INTO \"{table_name}\" (...) VALUES (...);",
					f"Rows available: {len(data_rows)}",
					f"Columns available: {len(data_cols)}",
				]
			)
		)
		relations = []
		for name, other in self.main.converter.schemas.items():
			if other.parent_table == table_name:
				relations.append((table_name, name))
		self.schema_graph.setRelations(relations)


class ResetPage(BasePage):
	def __init__(self, main: "MainWindow", parent=None):
		super().__init__(main, parent)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(18)
		card = GlowFrame()
		card.setObjectName("dangerCard")
		card_layout = QVBoxLayout(card)
		card_layout.setContentsMargins(40, 40, 40, 40)
		card_layout.setSpacing(16)
		title = QLabel("This will permanently remove all generated tables and data.")
		title.setObjectName("heroTitle")
		title.setWordWrap(True)
		title.setAlignment(Qt.AlignCenter)
		sub = QLabel("Use this only when you want to clear the local SQLite output and restart the conversion flow.")
		sub.setObjectName("heroDesc")
		sub.setWordWrap(True)
		sub.setAlignment(Qt.AlignCenter)
		buttons = QHBoxLayout()
		buttons.setSpacing(12)
		self.reset_btn = QPushButton("Reset Database")
		self.reset_btn.setObjectName("dangerButton")
		self.reset_btn.clicked.connect(main.reset_db)
		self.cancel_btn = QPushButton("Cancel")
		self.cancel_btn.setObjectName("secondaryButton")
		self.cancel_btn.clicked.connect(lambda: main.switch_page(0))
		buttons.addStretch(1)
		buttons.addWidget(self.reset_btn)
		buttons.addWidget(self.cancel_btn)
		buttons.addStretch(1)
		card_layout.addStretch(1)
		card_layout.addWidget(title)
		card_layout.addWidget(sub)
		card_layout.addLayout(buttons)
		card_layout.addStretch(1)
		layout.addStretch(1)
		layout.addWidget(card)
		layout.addStretch(1)


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("SQLify")
		self.resize(1500, 920)
		self.setMinimumSize(1280, 820)
		self.setAcceptDrops(True)
		self.converter = JsonSqlConverter(DB_PATH)
		self.current_json_path: Path | None = None
		self.current_data: Any | None = None
		self._page_anim: QPropertyAnimation | None = None

		root = AppRoot(self)
		self.setCentralWidget(root)
		root_layout = QVBoxLayout(root)
		root_layout.setContentsMargins(14, 14, 14, 14)
		root_layout.setSpacing(12)

		self.header = self._build_header()
		root_layout.addWidget(self.header)
		self.nav = self._build_nav()
		root_layout.addWidget(self.nav)

		self.panel = GlowFrame()
		self.panel.setObjectName("mainPanel")
		panel_layout = QVBoxLayout(self.panel)
		panel_layout.setContentsMargins(14, 14, 14, 14)
		panel_layout.setSpacing(0)

		self.stack = QStackedWidget()
		self.home_page = HomePage(self)
		self.json_page = JsonPage(self)
		self.convert_page = ConvertPage(self)
		self.tables_page = TablesPage(self)
		self.schema_page = SchemaPage(self)
		self.reset_page = ResetPage(self)
		for page in (self.home_page, self.json_page, self.convert_page, self.tables_page, self.schema_page, self.reset_page):
			self.stack.addWidget(page)
		self.stack.currentChanged.connect(self._on_stack_changed)
		panel_layout.addWidget(self.stack)
		root_layout.addWidget(self.panel, 1)

		self.toast = QLabel(self)
		self.toast.setObjectName("toast")
		self.toast.setVisible(False)
		self.toast.setAttribute(Qt.WA_TransparentForMouseEvents)
		self.toast_effect = QGraphicsOpacityEffect(self.toast)
		self.toast.setGraphicsEffect(self.toast_effect)

		self.bg_timer = QTimer(self)
		self.bg_timer.timeout.connect(root.tick)
		self.bg_timer.start(33)

		self._update_nav(0)
		self.switch_page(0, animate=False)
		self.update_header()

	def _build_header(self) -> QWidget:
		bar = GlowFrame()
		bar.setObjectName("topStatusBar")
		layout = QHBoxLayout(bar)
		layout.setContentsMargins(16, 12, 16, 12)
		layout.setSpacing(14)

		left = QHBoxLayout()
		left.setSpacing(12)
		logo = QLabel()
		logo.setFixedSize(40, 40)
		logo.setObjectName("appLogo")
		pixmap = QPixmap(str(ASSETS_DIR / "logo.svg"))
		if not pixmap.isNull():
			logo.setPixmap(QIcon(str(ASSETS_DIR / "logo.svg")).pixmap(40, 40))
		left.addWidget(logo)
		title_box = QVBoxLayout()
		title_box.setSpacing(2)
		title_box.setAlignment(Qt.AlignVCenter)
		app_title = QLabel("SQLify")
		app_title.setObjectName("headerTitle")
		# Make the header title larger and bold to align visually with the logo
		title_font = QFont()
		title_font.setPointSize(14)
		title_font.setBold(True)
		app_title.setFont(title_font)
		title_box.addWidget(app_title)
		left.addLayout(title_box)
		layout.addLayout(left, 2)

		center = QVBoxLayout()
		center.setSpacing(2)
		self.file_label = QLabel("No JSON loaded")
		self.file_label.setObjectName("headerCenterTitle")
		self.status_label = QLabel("Load a JSON file to inspect it")
		self.status_label.setObjectName("headerSubtitle")
		center.addWidget(self.file_label, alignment=Qt.AlignHCenter)
		center.addWidget(self.status_label, alignment=Qt.AlignHCenter)
		layout.addLayout(center, 2)

		right = QHBoxLayout()
		right.setSpacing(10)
		self.tables_badge = StatCard("Tables Generated", "0")
		self.tables_badge.setMaximumWidth(180)
		self.schema_badge = QPushButton("Schema Status: Waiting")
		self.schema_badge.setObjectName("schemaStatusButton")
		self.schema_badge.setMaximumWidth(220)
		self.schema_badge.setMinimumHeight(56)
		self.schema_badge.setCursor(Qt.PointingHandCursor)
		self.schema_badge.setToolTip("Open detected schema")
		self.schema_badge.pressed.connect(self.open_schema_page)
		self.import_btn = QPushButton("Import JSON")
		self.import_btn.setObjectName("secondaryButton")
		self.import_btn.clicked.connect(self.open_json_file)
		self.min_btn = QPushButton("−")
		self.max_btn = QPushButton("□")
		self.close_btn = QPushButton("×")
		for button in (self.min_btn, self.max_btn, self.close_btn):
			button.setObjectName("windowControl")
			button.setFixedSize(34, 34)
		self.min_btn.clicked.connect(self.showMinimized)
		self.max_btn.clicked.connect(self._toggle_maximize)
		self.close_btn.clicked.connect(self.close)
		right.addWidget(self.tables_badge)
		right.addWidget(self.schema_badge)
		right.addWidget(self.import_btn)
		right.addWidget(self.min_btn)
		right.addWidget(self.max_btn)
		right.addWidget(self.close_btn)
		layout.addLayout(right, 2)
		return bar

	def _build_nav(self) -> QWidget:
		bar = GlowFrame()
		bar.setObjectName("navRow")
		layout = QHBoxLayout(bar)
		layout.setContentsMargins(10, 10, 10, 10)
		layout.setSpacing(10)
		self.nav_buttons: list[QPushButton] = []
		items = [
			("HOME", QStyle.SP_DirHomeIcon),
			("LOADED JSON", QStyle.SP_FileIcon),
			("CONVERT TO SQL", QStyle.SP_MediaPlay),
			("SQL TABLES", QStyle.SP_FileDialogDetailedView),
			("DETECTED SCHEMA", QStyle.SP_ComputerIcon),
			("RESET DB", QStyle.SP_MessageBoxWarning),
		]
		for index, (text, icon_enum) in enumerate(items):
			button = QPushButton(text)
			button.setObjectName("navButton")
			button.setIcon(self.style().standardIcon(icon_enum))
			button.setIconSize(QSize(18, 18))
			button.clicked.connect(lambda _checked=False, idx=index: self.switch_page(idx))
			button.setCursor(Qt.PointingHandCursor)
			self.nav_buttons.append(button)
			layout.addWidget(button)
		return bar

	def _toggle_maximize(self) -> None:
		if self.isMaximized():
			self.showNormal()
		else:
			self.showMaximized()

	def _update_nav(self, active_index: int) -> None:
		for index, button in enumerate(self.nav_buttons):
			button.setProperty("active", index == active_index)
			button.style().unpolish(button)
			button.style().polish(button)
			button.update()

	def switch_page(self, index: int, animate: bool = True) -> None:
		refresh_map = {
			1: self.json_page.refresh,
			2: self.convert_page.refresh,
			3: self.tables_page.refresh,
			4: self.schema_page.refresh,
		}
		if index in refresh_map:
			refresh_map[index]()
		self._update_nav(min(index, len(self.nav_buttons) - 1))
		self.stack.setCurrentIndex(index)
		if animate:
			self._fade_in(self.stack.currentWidget())

	def _on_stack_changed(self, index: int) -> None:
		if index == 3:
			self.tables_page.refresh()
		elif index == 4:
			self.schema_page.refresh()

	def _fade_in(self, widget: QWidget) -> None:
		effect = QGraphicsOpacityEffect(widget)
		widget.setGraphicsEffect(effect)
		effect.setOpacity(0.0)
		anim = QPropertyAnimation(effect, b"opacity", self)
		anim.setDuration(240)
		anim.setStartValue(0.0)
		anim.setEndValue(1.0)
		anim.setEasingCurve(QEasingCurve.OutCubic)
		anim.finished.connect(lambda: widget.setGraphicsEffect(None))
		anim.start(QPropertyAnimation.DeleteWhenStopped)
		self._page_anim = anim

	def open_documentation(self) -> None:
		readme = BASE_DIR / "README.md"
		if readme.exists():
			QDesktopServices.openUrl(QUrl.fromLocalFile(str(readme)))
		else:
			QMessageBox.information(self, "Documentation", PLACEHOLDER_DOC)

	def open_json_file(self, file_path: str | None = None) -> None:
		path = file_path
		if not path:
			path, _ = QFileDialog.getOpenFileName(self, "Open JSON", str(BASE_DIR), "JSON Files (*.json);;All Files (*)")
		if not path:
			return
		try:
			data = json.loads(Path(path).read_text(encoding="utf-8"))
		except Exception as exc:
			QMessageBox.critical(self, "Invalid JSON", str(exc))
			return
		self.current_json_path = Path(path)
		self.current_data = data
		self.update_header()
		self.json_page.refresh()
		self.show_toast(f"Loaded {self.current_json_path.name}")
		self.switch_page(1)

	def dragEnterEvent(self, event):
		mime = event.mimeData()
		if mime.hasUrls():
			for url in mime.urls():
				if url.isLocalFile() and url.toLocalFile().lower().endswith(".json"):
					event.acceptProposedAction()
					return
		event.ignore()

	def dropEvent(self, event):
		for url in event.mimeData().urls():
			if url.isLocalFile() and url.toLocalFile().lower().endswith(".json"):
				self.open_json_file(url.toLocalFile())
				event.acceptProposedAction()
				return
		event.ignore()

	def convert_json(self) -> None:
		if not self.current_json_path:
			QMessageBox.warning(self, "No file", "Open a JSON file first.")
			return
		try:
			self.convert_page.engine.setProgress(0.2)
			self.show_toast("Starting conversion...")
			QApplication.processEvents()
			self.converter.convert_file(self.current_json_path)
			self.convert_page.engine.setProgress(1.0)
		except Exception as exc:
			QMessageBox.critical(self, "Conversion failed", str(exc))
			return
		self.update_header()
		self.tables_page.refresh()
		self.schema_page.refresh()
		self.convert_page.refresh()
		self.show_toast("Conversion done")
		QApplication.processEvents()
		self.switch_page(3)

	def reset_db(self) -> None:
		answer = QMessageBox.question(
			self,
			"Reset database",
			"This will permanently remove all generated tables and data. Continue?",
			QMessageBox.Yes | QMessageBox.No,
		)
		if answer != QMessageBox.Yes:
			return
		self.converter.reset_database()
		self.current_json_path = None
		self.current_data = None
		self.update_header()
		self.tables_page.refresh()
		self.schema_page.refresh()
		self.json_page.refresh()
		self.convert_page.refresh()
		self.show_toast("Database reset")
		self.switch_page(0)

	def update_header(self) -> None:
		file_name = self.current_json_path.name if self.current_json_path else "No JSON loaded"
		self.file_label.setText(file_name)
		if self.current_json_path and self.current_json_path.exists():
			stats = summarize_json(self.current_data) if self.current_data is not None else {"objects": 0, "arrays": 0, "depth": 0, "valid": True}
			self.status_label.setText(
				f"{stats['objects']} objects · {stats['arrays']} arrays · depth {stats['depth']}"
			)
		else:
			self.status_label.setText("Load a JSON file to inspect it")
		tables = self.converter.list_tables()
		self.tables_badge.setValue(str(len(tables)))
		self.schema_badge.setText(f"Schema Status: {'Ready' if tables else 'Waiting'}")

	def open_schema_page(self) -> None:
		self.show_toast("Opening detected schema")
		self.switch_page(4)

	def show_toast(self, message: str) -> None:
		self.toast.setText(message)
		self.toast.adjustSize()
		self.toast.move(self.width() - self.toast.width() - 28, 24)
		self.toast.setVisible(True)
		effect = QGraphicsOpacityEffect(self.toast)
		self.toast.setGraphicsEffect(effect)
		anim = QPropertyAnimation(effect, b"opacity", self)
		anim.setDuration(1800)
		anim.setStartValue(0.95)
		anim.setKeyValueAt(0.8, 0.95)
		anim.setEndValue(0.0)
		anim.finished.connect(lambda: self.toast.setVisible(False))
		anim.start(QPropertyAnimation.DeleteWhenStopped)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self.toast.isVisible():
			self.toast.move(self.width() - self.toast.width() - 28, 24)

	def closeEvent(self, event):
		try:
			self.converter.close()
		except Exception:
			pass
		super().closeEvent(event)


def main() -> None:
	app = QApplication(sys.argv)
	try:
		app.setFont(QFont("Segoe UI", 10))
	except Exception:
		pass
	load_qss(app, ASSETS_DIR / "styles.qss")
	window = MainWindow()
	window.show()
	sys.exit(app.exec())


if __name__ == "__main__":
	main()
