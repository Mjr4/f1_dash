"""Layout v2: paneles en una grilla libre de 12 columnas (x, y, w, h). Acepta también v1 y lo migra."""
from pydantic import BaseModel, model_validator

from f1_dash.panels import Panel, create

from .model import Layout

COLS = 12
ROW_H = 8  # alto por defecto de un panel, en filas de grilla


class Cell(BaseModel):
    panel_id: str
    params: dict = {}
    x: int
    y: int
    w: int
    h: int = ROW_H

    @model_validator(mode="after")
    def _en_grilla(self):
        if self.x < 0 or self.y < 0 or self.w < 1 or self.h < 1 or self.x + self.w > COLS:
            raise ValueError(f"celda fuera de la grilla de {COLS} columnas: x={self.x} y={self.y} w={self.w} h={self.h}")
        return self

    def panel(self) -> Panel:
        return create(self.panel_id, self.params)  # valida id y params


class GridLayout(BaseModel):
    version: int = 2
    panels: list[Cell] = []

    @classmethod
    def from_v1(cls, old: Layout) -> "GridLayout":
        """Cada tercio de fila (`span`) pasa a 4 columnas; cada fila de v1 a una banda de alto ROW_H."""
        cells = [Cell(panel_id=old.panels[i].panel_id, params=old.panels[i].params, x=sum(old.panels[j].span for j in row[:n]) * 4,
                      y=r * ROW_H, w=old.panels[i].span * 4)
                 for r, row in enumerate(old.rows()) for n, i in enumerate(row)]
        return cls(panels=cells)

    @classmethod
    def loads(cls, text: str | bytes) -> "GridLayout":
        # ponytail: no se valida solape entre celdas; la grilla del cliente (GridStack) lo resuelve al soltar
        import json
        v = json.loads(text).get("version")
        if v == 1:
            return cls.from_v1(Layout.loads(text))
        if v != 2:
            raise ValueError(f"versión de layout no soportada: {v}")
        layout = cls.model_validate_json(text)
        for cell in layout.panels:
            cell.panel()
        return layout
