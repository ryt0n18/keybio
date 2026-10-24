"""Informes en PDF de un usuario o de una comprobación.

Los gráficos se dibujan con los mismos widgets de la aplicación, siempre en
tema claro (el PDF es para leer o imprimir sobre blanco), y se insertan como
imágenes en un documento HTML que Qt pagina e imprime a PDF.
"""

from __future__ import annotations

import html
import statistics
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSize, QUrl
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import QWidget

from .. import APP_NAME, APP_VERSION
from ..features import SampleFeatures
from ..i18n import _, _n
from ..matcher import Candidate, Profile
from ..storage import User
from . import theme
from .charts import HBarChart, LineChart, RadarChart, RhythmChart
from .keyboard import KeyboardWidget
from .widgets import dwell_rows, radar_series

IMG_WIDTH = 760


@contextmanager
def _light_theme():
    saved = {k: getattr(theme, k) for k in theme.LIGHT}
    for k, v in theme.LIGHT.items():
        setattr(theme, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(theme, k, v)


def _grab(widget: QWidget, height: int) -> QImage:
    widget.resize(QSize(IMG_WIDTH, height))
    widget.setStyleSheet("background: #ffffff;")
    img = widget.grab().toImage()
    widget.deleteLater()
    return img


class _Doc:
    def __init__(self, title: str):
        self.doc = QTextDocument()
        self.parts: list[str] = []
        self.n = 0
        self.parts.append(
            "<html><body style='font-family: sans-serif; color:#0b0b0b'>"
            f"<h1 style='color:#1c5cab'>{html.escape(title)}</h1>"
            f"<p style='color:#52514e'>{APP_NAME} {APP_VERSION} · "
            + html.escape(_("generado el {date}", date=datetime.now().strftime('%d/%m/%Y %H:%M'))) + "</p>")

    def h2(self, text: str):
        self.parts.append(f"<h2 style='color:#1c5cab; margin-top:18px'>{html.escape(text)}</h2>")

    def p(self, text_html: str):
        self.parts.append(f"<p>{text_html}</p>")

    def table(self, rows: list[tuple[str, str]], cols: int = 2):
        cells = ""
        for i in range(0, len(rows), cols):
            cells += "<tr>"
            for label, value in rows[i:i + cols]:
                cells += (f"<td style='padding:4px 10px; color:#52514e'>{html.escape(label)}</td>"
                          f"<td style='padding:4px 18px 4px 4px'><b>{html.escape(value)}</b></td>")
            cells += "</tr>"
        self.parts.append(f"<table cellspacing='0' style='border-collapse:collapse'>{cells}</table>")

    def image(self, img: QImage, width: int = 640):
        self.n += 1
        name = f"img{self.n}"
        self.doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(name), img)
        self.parts.append(f"<p><img src='{name}' width='{width}'></p>")

    def save(self, path: Path):
        self.parts.append("</body></html>")
        self.doc.setHtml("".join(self.parts))
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        writer.setResolution(110)
        writer.setTitle(self.parts[0][:0] or APP_NAME)
        self.doc.print_(writer)


def _charts(doc: _Doc, f_list: list[SampleFeatures], profile: Profile | None, names, layout: str,
            others: list[dict] | None = None, rhythm: list[float] | None = None):
    with _light_theme():
        radar = RadarChart()
        metrics = [f.metrics for f in f_list]
        compare = [x.metrics for x in profile.features] if profile and names[1] else others
        axes, series = radar_series(metrics, names[0], compare or None, names[1] or _("Media del resto"))
        radar.set_data(axes, series)
        doc.h2(_("Huella de tecleo"))
        doc.image(_grab(radar, 420), 520)

        dwell: dict[str, list[float]] = {}
        for f in f_list:
            for k, v in f.dwell.items():
                dwell.setdefault(k, []).extend(v)
        kb = KeyboardWidget(layout)
        kb.set_heat({k: statistics.median(v) for k, v in dwell.items() if v}, _("pulsación mediana"), "ms")
        doc.h2(_("Mapa de calor: tiempo de pulsación por tecla"))
        doc.image(_grab(kb, 380), 600)

        if len(f_list) == 1:
            bars = HBarChart()
            bars.set_data(dwell_rows(f_list[0], profile if names[1] else None), names)
            doc.h2(_("Tiempo de pulsación por tecla"))
            doc.image(_grab(bars, bars.height()), 600)
        if rhythm:
            chart = RhythmChart()
            chart.set_data(rhythm)
            doc.h2(_("Ritmo de escritura"))
            doc.image(_grab(chart, 260), 600)


def user_report(service, user: User, path: Path, layout: str = "es") -> None:
    prof = service.profile(user)
    feats = [service.features(s) for s in user.samples]
    ms = [f.metrics for f in feats]

    def avg(k):
        return statistics.fmean(m[k] for m in ms) if ms else 0.0

    level, quality = service.quality(user, prof)
    doc = _Doc(_("Informe de usuario: {name}", name=user.name))
    n_ses = service.session_count(user)
    doc.p(html.escape(_("Alta: {date}", date=user.created[:10]) + " · " + _n("{n} muestra", "{n} muestras", len(user.samples))
                      + " · " + _n("{n} sesión", "{n} sesiones", n_ses))
          + f" · <b>{html.escape(quality)}</b>")
    doc.h2(_("Resumen"))
    sens = service.sensitivity
    doc.table([
        (_("Palabras por minuto"), f"{avg('wpm'):.0f}"), (_("Precisión media"), f"{avg('accuracy'):.1f} %"),
        (_("Pulsación media"), f"{avg('dwell_mean'):.0f} ms"), (_("Vuelo medio"), f"{avg('flight_mean'):.0f} ms"),
        (_("Solapamiento"), f"{avg('rollover_pct'):.0f} %"), (_("Regularidad"), f"{avg('consistency'):.0f} %"),
        (_("Errores por texto"), f"{avg('errors_committed'):.1f}"), (_("Retrocesos por texto"), f"{avg('backspaces'):.1f}"),
        (_("Distancia típica (m)"), f"{prof.m:.3f}"), (_("Variación (s)"), f"{prof.s:.3f}"),
        (_("Umbral actual"), f"{prof.threshold(sens):.3f} ({service.sensitivity_label})"),
        (_("Sesiones de registro"), str(service.session_count(user))),
    ])
    others = [service.features(s).metrics for u in service.users() if u.id != user.id for s in u.samples]
    _charts(doc, feats, None, (user.name, ""), layout, others)
    with _light_theme():
        order = sorted(user.samples, key=lambda s: s.created)
        line = LineChart(_("ppm"))
        line.set_data([(s.created[:16].replace("T", " "), service.features(s).metrics["wpm"]) for s in order])
        doc.h2(_("Evolución de la velocidad"))
        doc.image(_grab(line, 240), 600)
    doc.h2(_("Muestras"))
    doc.table([(s.created[:16].replace("T", " ") + f" · {s.text_id}",
                _("{wpm} ppm", wpm=f"{service.features(s).metrics['wpm']:.0f}") + f", {s.accuracy * 100:.0f} %")
               for s in user.samples], 1)
    doc.save(path)


def result_report(service, f: SampleFeatures, result, shown: Candidate | None, title: str, subtitle: str,
                  path: Path, layout: str = "es") -> None:
    doc = _Doc(_("Informe de comprobación: {title}", title=title))
    doc.p(html.escape(subtitle))
    m = f.metrics
    doc.h2(_("Muestra"))
    doc.table([
        (_("Palabras por minuto"), f"{m['wpm']:.0f}"), (_("Precisión"), f"{m['accuracy']:.1f} %"),
        (_("Duración"), f"{m['duration_s']:.1f} s"), (_("Pulsaciones"), str(m["keystrokes"])),
        (_("Errores cometidos"), str(m["errors_committed"])), (_("Retrocesos"), str(m["backspaces"])),
        (_("Pulsación media"), f"{m['dwell_mean']:.0f} ms"), (_("Vuelo medio"), f"{m['flight_mean']:.0f} ms"),
    ])
    doc.h2(_("Comparación con los usuarios registrados"))
    doc.table([(c.name, _("distancia {distance} · umbral {threshold} · confianza {confidence} %",
                          distance=f"{c.distance:.3f}", threshold=f"{c.threshold:.3f}", confidence=f"{c.confidence:.0f}")
                + (" · " + _("ACEPTADO") if c.accepted else "")) for c in result.candidates], 1)
    prof = None
    if shown:
        user = service.storage.get_user(shown.user_id)
        prof = service.profile(user) if user else None
    _charts(doc, [f], prof, (_("Esta muestra"), _("Perfil de {name}", name=shown.name) if shown else ""), layout,
            rhythm=f.rhythm)
    doc.save(path)
