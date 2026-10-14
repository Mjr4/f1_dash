"""Layout: lista ordenada de paneles, serializable a JSON (versionado)."""
from pathlib import Path

from pydantic import BaseModel, Field

from f1_dash.panels import Panel, create


class Item(BaseModel):
    panel_id: str
    params: dict = {}
    span: int = Field(3, ge=1, le=3)  # ancho en tercios de fila

    def panel(self) -> Panel:
        return create(self.panel_id, self.params)  # valida id y params


class Layout(BaseModel):
    version: int = 1
    panels: list[Item] = []

    def add(self, panel_id: str, params: dict | None = None) -> None:
        item = Item(panel_id=panel_id, params=params or {})
        item.panel()  # falla ahora, no al renderizar
        self.panels.append(item)

    def remove(self, index: int) -> None:
        del self.panels[index]

    def move(self, index: int, new_index: int) -> None:
        self.panels.insert(new_index, self.panels.pop(index))

    def configure(self, index: int, params: dict) -> None:
        item = self.panels[index].model_copy(update={"params": params})
        item.panel()
        self.panels[index] = item

    def set_span(self, index: int, span: int) -> None:
        self.panels[index] = Item(**{**self.panels[index].model_dump(), "span": span})

    def rows(self) -> list[list[int]]:
        """Índices de paneles agrupados en filas de hasta 3 tercios, en orden."""
        rows, used = [], 3
        for i, item in enumerate(self.panels):
            if used + item.span > 3:
                rows.append([])
                used = 0
            rows[-1].append(i)
            used += item.span
        return rows

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path | str) -> "Layout":
        return cls.loads(Path(path).read_text())

    @classmethod
    def loads(cls, text: str | bytes) -> "Layout":
        layout = cls.model_validate_json(text)
        if layout.version != 1:
            raise ValueError(f"versión de layout no soportada: {layout.version}")
        for item in layout.panels:
            item.panel()
        return layout
