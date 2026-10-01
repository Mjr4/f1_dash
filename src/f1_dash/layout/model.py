"""Layout: lista ordenada de paneles, serializable a JSON (versionado)."""
from pathlib import Path

from pydantic import BaseModel

from f1_dash.panels import Panel, create


class Item(BaseModel):
    panel_id: str
    params: dict = {}

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
        item = Item(panel_id=self.panels[index].panel_id, params=params)
        item.panel()
        self.panels[index] = item

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path | str) -> "Layout":
        layout = cls.model_validate_json(Path(path).read_text())
        if layout.version != 1:
            raise ValueError(f"versión de layout no soportada: {layout.version}")
        for item in layout.panels:
            item.panel()
        return layout
