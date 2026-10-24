"""Panel de escritura: muestra el texto objetivo y captura cada pulsación."""

from __future__ import annotations

import html
import sys
import time
import unicodedata

from PySide6.QtCore import QMimeData, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QTextEdit,
                               QVBoxLayout, QWidget)

from ..capture import BACKSPACE, CHAR, DEAD, MOD, OTHER, SPACE, KeystrokeRecorder
from ..i18n import N_, _
from ..textutil import fold, normalize_typed
from . import theme
from .charts import Sparkline
from .keyboard import KeyboardWidget

K = Qt.Key
_MODIFIERS = {
    K.Key_Shift.value: "shift", K.Key_Control.value: "ctrl", K.Key_Alt.value: "alt",
    K.Key_AltGr.value: "altgr", K.Key_Meta.value: "meta", K.Key_CapsLock.value: "capslock",
    K.Key_Super_L.value: "meta", K.Key_Super_R.value: "meta",
}
# scancodes del shift izquierdo / derecho (Linux X11/Wayland y Windows)
_SHIFT_LEFT = {50, 42}
_SHIFT_RIGHT = {62, 54}
# macOS no da scancodes (Qt devuelve siempre 0 o 1): se usa el código de tecla virtual
MAC = sys.platform == "darwin"
_MAC_SHIFT_LEFT, _MAC_SHIFT_RIGHT = 56, 60   # kVK_Shift, kVK_RightShift

_DEAD_FIRST, _DEAD_LAST = 0x01001250, 0x010012FF
_DEAD_MARKS = {
    K.Key_Dead_Grave.value: ("dead_grave", "̀"),
    K.Key_Dead_Acute.value: ("dead_acute", "́"),
    K.Key_Dead_Circumflex.value: ("dead_circumflex", "̂"),
    K.Key_Dead_Tilde.value: ("dead_tilde", "̃"),
    K.Key_Dead_Diaeresis.value: ("dead_diaeresis", "̈"),
}


def char_label(text: str) -> str:
    """Etiqueta de una tecla de carácter: minúscula y sin tilde (la ñ y la ç son teclas propias)."""
    low = text.lower()
    if low in ("ñ", "ç"):
        return low
    return fold(low) or text


def classify_key(event: QKeyEvent, mac: bool = MAC) -> tuple[object, str, str]:
    """Devuelve (id físico, etiqueta, tipo) para una pulsación de Qt."""
    key = int(event.key())
    text = event.text()
    if mac:
        vk = event.nativeVirtualKey()
        key_id = ("vk", vk) if vk or key == K.Key_A.value else ("k", key)   # vk 0 es la tecla A
        left, right = vk == _MAC_SHIFT_LEFT, vk == _MAC_SHIFT_RIGHT
    else:
        sc = event.nativeScanCode()
        key_id = sc if sc else ("k", key)
        left, right = sc in _SHIFT_LEFT, sc in _SHIFT_RIGHT
    if key in _MODIFIERS:
        label = _MODIFIERS[key]
        if label == "shift":
            label = "shift_l" if left else "shift_r" if right else "shift"
        return key_id, label, MOD
    if key == K.Key_Backspace.value:
        return key_id, "backspace", BACKSPACE
    if key == K.Key_Space.value:
        return key_id, "space", SPACE
    if _DEAD_FIRST <= key <= _DEAD_LAST:
        return key_id, _DEAD_MARKS.get(key, ("dead", ""))[0], DEAD
    if len(text) == 1 and text.isprintable():
        return key_id, char_label(text), CHAR
    if mac and not text and key < 0x01000000:
        # macOS sin método de entrada: una tecla muerta (tilde, diéresis...) llega sin texto
        return key_id, "dead", DEAD
    return key_id, f"key_{key:x}", OTHER


class TypingInput(QPlainTextEdit):
    """Caja de texto que registra pulsaciones y bloquea pegar/editar fuera de orden."""

    keystroke = Signal()
    enter_pressed = Signal()
    key_down = Signal(str)
    key_up = Signal(str)
    caps_lock = Signal(bool)
    focus_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("typingInput")
        self.recorder: KeystrokeRecorder | None = None
        self.locked = True
        self._pending_mark: str | None = None
        self._labels: dict[object, str] = {}
        self.setUndoRedoEnabled(False)
        self.setTabChangesFocus(False)
        self.setAcceptDrops(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        # Sin método de entrada: los eventos de teclado llegan directos y con
        # su tiempo real. Las tildes con tecla muerta se componen aquí.
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)

    # -- pegar / arrastrar / ratón: bloqueados -------------------------------
    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return False

    def insertFromMimeData(self, source: QMimeData) -> None:
        if self.recorder:
            self.recorder.block()

    def mousePressEvent(self, event):
        self.setFocus()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        for label in self._labels.values():   # las teclas pulsadas ya no se verán soltar
            self.key_up.emit(label)
        self._labels.clear()
        self.focus_changed.emit(False)

    # -- teclado --------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        t = time.perf_counter_ns()
        rec = self.recorder
        if rec is None or self.locked:
            event.accept()
            return
        key_id, label, kind = classify_key(event)
        rec.press(key_id, label, kind, t, event.isAutoRepeat())
        if not event.isAutoRepeat():
            self._labels[key_id] = label
            self.key_down.emit(label)
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        # Ctrl+tecla llega sin texto imprimible (salvo AltGr = Ctrl+Alt en Windows, que sí escribe);
        # en macOS, Cmd (ControlModifier en Qt) + tecla trae la letra como texto
        ctrl_combo = bool(mods & Qt.KeyboardModifier.ControlModifier) and (kind != CHAR or MAC)
        if ctrl_combo and MAC and kind != MOD:   # macOS no envía la liberación de una tecla pulsada con Cmd
            rec.release(key_id, t)
            if self._labels.pop(key_id, None) is not None:
                self.key_up.emit(label)

        if kind == MOD:
            event.accept()
        elif kind == DEAD:
            self._pending_mark = _DEAD_MARKS.get(int(event.key()), ("", ""))[1] or None
            event.accept()
        elif kind == OTHER or ctrl_combo:
            if int(event.key()) in (K.Key_Return.value, K.Key_Enter.value):
                self.enter_pressed.emit()      # en texto libre sirve para terminar
            else:
                rec.block()
            event.accept()
        elif kind == BACKSPACE:
            self._pending_mark = None
            self.moveCursor(self.textCursor().MoveOperation.End)
            self.textCursor().deletePreviousChar()
        else:  # CHAR o SPACE
            self.moveCursor(self.textCursor().MoveOperation.End)
            text = event.text()
            if text.isalpha() and text.lower() != text.upper():
                self.caps_lock.emit(text.isupper() != shift)
            if self._pending_mark and kind == CHAR:
                composed = unicodedata.normalize("NFC", text + self._pending_mark)
                if len(composed) == 1:
                    text = composed
            self._pending_mark = None
            self.insertPlainText(text)
        self.keystroke.emit()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        t = time.perf_counter_ns()
        key_id = classify_key(event)[0]
        if self.recorder is not None:
            self.recorder.release(key_id, t, event.isAutoRepeat())
        if not event.isAutoRepeat() and key_id in self._labels:
            self.key_up.emit(self._labels.pop(key_id))
        event.accept()

    def focusNextPrevChild(self, next_: bool) -> bool:
        return False


FREE_MIN_CHARS = 280   # texto libre: caracteres mínimos para tener suficientes dígrafos


class TypingPanel(QWidget):
    """Texto objetivo + caja de escritura + estadísticas y teclado en vivo.

    Con ``free=True`` no hay texto objetivo: la persona escribe lo que quiera y
    termina con el botón «Terminar» o con Intro al llegar al mínimo de caracteres."""

    finished = Signal(object)   # Sample

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target = ""
        self.free = False
        self._target_norm = ""
        self._text_id = ""
        self._kind = "enroll"
        self._pos = 0
        self._status: list[bool] = []
        self.recorder: KeystrokeRecorder | None = None

        self.header = QLabel()
        self.header.setObjectName("section")
        self.hint = QLabel(_("Escribe el texto tal y como aparece. El tiempo empieza con la primera "
                             "tecla. Puedes corregir con retroceso; no se puede pegar texto."))
        self.hint.setObjectName("subtitle")
        self.hint.setWordWrap(True)

        self.target_view = QTextEdit()
        self.target_view.setObjectName("targetText")
        self.target_view.setReadOnly(True)
        self.target_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.target_view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.target_view.setMinimumHeight(130)

        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setVisible(False)
        self._caps = False
        self._focus = True

        self.input = TypingInput()

        self.input.setPlaceholderText(_("Haz clic aquí y empieza a escribir…"))
        self.input.textChanged.connect(self._on_text_changed)
        self.input.caps_lock.connect(self._on_caps)
        self.input.focus_changed.connect(self._on_focus)
        self.input.enter_pressed.connect(self._finish_free)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)

        self.stats = {}
        stats_row = QHBoxLayout()
        stats_row.setSpacing(22)
        for key, title in (("time", N_("Tiempo")), ("wpm", N_("Palabras/min")), ("acc", N_("Precisión")),
                           ("err", N_("Errores")), ("bs", N_("Retrocesos"))):
            box = QVBoxLayout()
            box.setSpacing(0)
            value = QLabel("—")
            value.setObjectName("tileValue")
            lbl = QLabel(_(title))
            lbl.setObjectName("tileLabel")
            box.addWidget(value)
            box.addWidget(lbl)
            stats_row.addLayout(box)
            self.stats[key] = value
        spark_box = QVBoxLayout()
        spark_box.setSpacing(0)
        self.spark = Sparkline()
        spark_lbl = QLabel(_("Ritmo"))
        spark_lbl.setObjectName("tileLabel")
        spark_box.addWidget(self.spark)
        spark_box.addWidget(spark_lbl)
        stats_row.addLayout(spark_box)
        stats_row.addStretch(1)
        self.finish_btn = QPushButton(_("Terminar"))
        self.finish_btn.setObjectName("primary")
        self.finish_btn.setVisible(False)
        self.finish_btn.clicked.connect(self._finish_free)
        stats_row.addWidget(self.finish_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self.keyboard = KeyboardWidget()
        self.keyboard.setMaximumWidth(760)
        self.keyboard.setMinimumHeight(110)
        self.input.key_down.connect(self.keyboard.press)
        self.input.key_up.connect(self.keyboard.release)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self.header)
        lay.addWidget(self.hint)
        lay.addWidget(self.target_view)
        lay.addWidget(self.progress)
        lay.addWidget(self.banner)
        lay.addWidget(self.input)
        lay.addLayout(stats_row)
        lay.addWidget(self.keyboard, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_stats)

    def configure(self, show_keyboard: bool, layout: str) -> None:
        self.keyboard.setVisible(show_keyboard)
        self.keyboard.set_layout(layout)
        self.fit_heights()

    def fit_heights(self) -> None:
        """Alturas según el tamaño de letra: 3 líneas de texto objetivo y 2 de escritura."""
        self.target_view.ensurePolished()
        self.input.ensurePolished()
        line = self.target_view.fontMetrics().lineSpacing() * 1.55
        self.target_view.setMinimumHeight(int(3 * line + 34))
        self.target_view.setMaximumHeight(int(4.6 * line + 34))
        line_in = self.input.fontMetrics().lineSpacing()
        self.input.setMinimumHeight(int(2 * line_in + 30))
        self.input.setMaximumHeight(int(3.2 * line_in + 30))

    # -- ciclo de vida ------------------------------------------------------
    def start(self, target: str, text_id: str, kind: str, header: str = "", free: bool = False) -> None:
        self.free = free
        self.finish_btn.setVisible(free)
        self.hint.setText(
            _("Escribe lo que quieras con naturalidad: un recuerdo, qué has hecho hoy, lo que se te ocurra. "
              "Cuando llegues a {n} caracteres pulsa «Terminar» o Intro.", n=FREE_MIN_CHARS) if free else
            _("Escribe el texto tal y como aparece. El tiempo empieza con la primera "
              "tecla. Puedes corregir con retroceso; no se puede pegar texto."))
        self.target = "" if free else unicodedata.normalize("NFC", target)
        self._target_norm = normalize_typed(self.target, self.target)
        self._text_id = text_id
        self._kind = kind
        self.header.setText(header)
        self.fit_heights()
        self.restart()

    def restart(self) -> None:
        self.recorder = KeystrokeRecorder(self.target, self._text_id, self._kind, free=self.free)
        self.input.recorder = None
        self.input.blockSignals(True)
        self.input.clear()
        self.input.blockSignals(False)
        self.input.recorder = self.recorder
        self.input.locked = False
        self.keyboard.clear_active()
        self.spark.set_data([])
        self._caps = False
        self._focus = True
        self._update_banner()
        self._pos, self._status = 0, []
        self.render()
        self._update_stats()
        self._timer.start()
        self.input.setFocus()

    def stop(self) -> None:
        self._timer.stop()
        self.input.locked = True
        self.input.recorder = None
        self.keyboard.clear_active()

    # -- avisos ---------------------------------------------------------------
    def _on_caps(self, on: bool) -> None:
        self._caps = on
        self._update_banner()

    def _on_focus(self, focused: bool) -> None:
        self._focus = focused
        self._update_banner()

    def _update_banner(self) -> None:
        typing = self.recorder is not None and self.recorder.started and not self.input.locked
        if typing and not self._focus:
            text, level = _("Escritura en pausa: haz clic en la caja de texto para continuar."), "warn"
        elif self._caps:
            text, level = _("Bloq Mayús está activado."), "warn"
        else:
            self.banner.setVisible(False)
            return
        self.banner.setText(text)
        self.banner.setStyleSheet(f"QLabel#banner {{ background: {theme.status_soft(level)}; "
                                  f"color: {theme.status_color(level)}; }}")
        self.banner.setVisible(True)

    # -- actualización ------------------------------------------------------
    def _on_text_changed(self) -> None:
        rec = self.recorder
        if rec is None or self.input.recorder is None:
            return
        typed = self.input.toPlainText()
        rec.text_changed(typed)
        if self.free:
            self._pos = len(typed)
            self.render()
            self._update_stats()
            return
        norm = normalize_typed(typed, self.target)
        self._status = [i < len(self._target_norm) and c == self._target_norm[i] for i, c in enumerate(norm)]
        self._pos = len(norm)
        self.render()
        self._update_stats()
        if len(norm) >= len(self._target_norm) and not self.input.locked:
            # Fin del texto: se esperan las últimas liberaciones de teclas
            self.input.locked = True
            QTimer.singleShot(400, self._finish)

    def _finish_free(self) -> None:
        if not self.free or self.input.locked or self.recorder is None:
            return
        if len(self.input.toPlainText().strip()) < FREE_MIN_CHARS:
            self.banner.setText(_("Escribe al menos {n} caracteres para que el análisis sea fiable.", n=FREE_MIN_CHARS))
            self.banner.setStyleSheet(f"QLabel#banner {{ background: {theme.status_soft('warn')}; "
                                      f"color: {theme.status_color('warn')}; }}")
            self.banner.setVisible(True)
            return
        self.input.locked = True
        QTimer.singleShot(400, self._finish)

    def snapshot(self):
        """Muestra parcial con lo escrito hasta ahora (para la identificación en directo)."""
        rec = self.recorder
        if rec is None or not rec.started:
            return None
        sample = rec.build_sample()
        if not self.free:
            sample.target = sample.target[:len(sample.typed)]
        return sample

    def finish_now(self) -> None:
        """Termina antes del final del texto (decisión progresiva): la muestra es lo escrito."""
        if self.free or self.input.locked or self.recorder is None:
            return
        self.input.locked = True
        QTimer.singleShot(300, self._finish_partial)   # se esperan las últimas liberaciones

    def _finish_partial(self) -> None:
        sample = self.snapshot()
        self.stop()
        if sample is not None:
            self.finished.emit(sample)

    def _finish(self) -> None:
        rec = self.recorder
        if rec is None:
            return
        self.stop()
        self.finished.emit(rec.build_sample())

    def render(self) -> None:
        """Pinta el texto objetivo coloreado según lo escrito (también al cambiar de tema)."""
        pos, status = self._pos, self._status
        if self.free:
            done = min(pos, FREE_MIN_CHARS)
            self.target_view.setHtml(
                f'<div style="line-height:155%;color:{theme.TEXT_2}">'
                f'<b style="color:{theme.TEXT}">{_("Texto libre")}</b><br>'
                + _("Escribe lo que quieras en la caja de abajo.") + " "
                + (_("Llevas <b>{n}</b> caracteres de {min} como mínimo.", n=pos, min=FREE_MIN_CHARS)
                   if pos < FREE_MIN_CHARS else
                   _("Llevas <b>{n}</b> caracteres: ya puedes pulsar «Terminar» o Intro (puedes seguir escribiendo "
                     "si quieres).", n=pos))
                + "</div>")
            self.progress.setValue(int(100 * done / FREE_MIN_CHARS))
            self.finish_btn.setEnabled(pos >= FREE_MIN_CHARS)
            return
        parts = []
        for i, ch in enumerate(self.target):
            esc = html.escape(ch)
            if i < pos:
                if status[i]:
                    parts.append(f'<span style="color:{theme.TEXT}">{esc}</span>')
                else:
                    shown = "·" if ch == " " else esc
                    parts.append(f'<span style="color:{theme.BAD};background:{theme.BAD_SOFT}">{shown}</span>')
            elif i == pos:
                parts.append(f'<span style="background:{theme.ACCENT_SOFT};color:{theme.TEXT};'
                             f'text-decoration:underline">{esc}</span>')
            else:
                parts.append(f'<span style="color:{theme.MUTED}">{esc}</span>')
        self.target_view.setHtml(f'<div style="line-height:155%">{"".join(parts)}</div>')
        # mantener visible la posición actual en textos largos o con letra grande
        cursor = self.target_view.textCursor()
        cursor.setPosition(min(pos + 25, max(len(self.target) - 1, 0)))
        self.target_view.setTextCursor(cursor)
        self.target_view.ensureCursorVisible()
        cursor.setPosition(min(pos, max(len(self.target) - 1, 0)))
        self.target_view.setTextCursor(cursor)
        self.target_view.ensureCursorVisible()
        self.progress.setValue(int(100 * min(pos, len(self.target)) / max(len(self.target), 1)))

    def _update_stats(self) -> None:
        rec = self.recorder
        if rec is None:
            return
        elapsed = rec.elapsed_ms() if rec.started else 0.0
        if self.free:
            norm = rec.typed
            minutes = elapsed / 60000.0
            wpm = (len(norm) / 5.0) / minutes if minutes > 0.02 else 0.0
            self.stats["time"].setText(f"{elapsed / 1000:0.1f} s")
            self.stats["wpm"].setText(f"{wpm:0.0f}" if wpm else "—")
            self.stats["acc"].setText("—")
            self.stats["err"].setText("—")
            self.stats["bs"].setText(str(sum(k.kind == BACKSPACE for k in rec.keystrokes)))
            typing = [k for k in rec.keystrokes[-41:] if k.kind in (CHAR, SPACE)]
            self.spark.set_data([b.press - a.press for a, b in zip(typing, typing[1:])])
            return
        norm = normalize_typed(rec.typed, self.target)
        correct = sum(1 for i, c in enumerate(norm) if i < len(self._target_norm) and c == self._target_norm[i])
        minutes = elapsed / 60000.0
        wpm = (len(norm) / 5.0) / minutes if minutes > 0.02 else 0.0
        acc = 100.0 * correct / len(norm) if norm else 100.0
        backspaces = sum(k.kind == BACKSPACE for k in rec.keystrokes)
        self.stats["time"].setText(f"{elapsed / 1000:0.1f} s")
        self.stats["wpm"].setText(f"{wpm:0.0f}" if wpm else "—")
        self.stats["acc"].setText(f"{acc:0.0f} %")
        self.stats["err"].setText(str(rec.errors_committed))
        self.stats["bs"].setText(str(backspaces))
        typing = [k for k in rec.keystrokes[-41:] if k.kind in (CHAR, SPACE)]
        self.spark.set_data([b.press - a.press for a, b in zip(typing, typing[1:])])
