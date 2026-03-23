"""
Loads SLD style definitions from the styles/ directory.

Each <name>.sld file corresponds to one GeoServer layer.
The style name registered in GeoServer is "<name>_style"
(as declared in the <Name> tag of each SLD's UserStyle).
"""
from pathlib import Path

_STYLES_DIR = Path(__file__).parent / "styles"

# "layer_name" -> SLD content
# Example: STYLES["dtm"] -> content of styles/dtm.sld
STYLES: dict[str, str] = {
    path.stem: path.read_text(encoding="utf-8")
    for path in sorted(_STYLES_DIR.glob("*.sld"))
}

# "layer_name" -> "geoserver_style_name"
# Example: STYLE_MAP["dtm"] -> "dtm_style"
STYLE_MAP: dict[str, str] = {name: f"{name}_style" for name in STYLES}
