from dataclasses import dataclass
from enum import Enum

class RegionMode(Enum):
    URB = "urb"
    SUB = "sub"
    RUR = "rur"
    WOD = "wod"

@dataclass(frozen=True)
class RegionConfig:
    cells_x: int
    cells_y: int
    mode: RegionMode = RegionMode.SUB
    cell_size: int = 300
    zombie_size: int = 30

    @property
    def width(self) -> int:
        return self.cells_x * self.cell_size

    @property
    def height(self) -> int:
        return self.cells_y * self.cell_size
    
