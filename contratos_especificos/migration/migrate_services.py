"""
Migración de servicios (product.template) desde el Excel
'codigos o conceptos de facturacion.xlsx'.

Se ejecuta automáticamente en el post_init_hook del módulo contratos_especificos.

Idempotencia garantizada:
  - Registros CON default_code: se omiten si ya existe ese código.
  - Registros SIN default_code: se omiten (no tienen clave única, no se crean).
  - Si se interrumpe y se re-ejecuta: los productos ya creados se detectan y omiten.
  - El parámetro 'contratos_especificos.migration_services_done' marca si completó al 100%.

Columnas del Excel:
  codigo      -> default_code (referencia interna)
  descripcion -> name (nombre del producto)
"""

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

MIGRATION_PARAM = "contratos_especificos.migration_services_done"
_EXCEL_FILENAME = "codigos o conceptos de facturacion.xlsx"
_MODULE_DIR = Path(__file__).parent.parent

EXCEL_SEARCH_PATHS = [
    _MODULE_DIR / "data" / "migration" / _EXCEL_FILENAME,
    _MODULE_DIR.parent / "context" / "Datos a migrar" / _EXCEL_FILENAME,
]


def _find_excel() -> Path | None:
    for path in EXCEL_SEARCH_PATHS:
        if path.exists():
            return path
    return None


def _read_excel(path: Path) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        _logger.error("migrate_services: openpyxl no está instalado. Migración omitida.")
        return []

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        codigo = row[0]
        descripcion = row[1]
        if codigo is None and descripcion is None:
            continue
        rows.append({
            "codigo": str(codigo).strip() if codigo is not None else "",
            "descripcion": str(descripcion).strip() if descripcion is not None else "",
        })
    return rows


def run(env) -> None:
    """Punto de entrada llamado desde post_init_hook."""

    # Comprobar si la migración ya completó previamente al 100%
    ICP = env["ir.config_parameter"].sudo()
    if ICP.get_param(MIGRATION_PARAM) == "1":
        _logger.info(
            "migrate_services: migración ya completada anteriormente, omitiendo."
        )
        return

    excel_path = _find_excel()
    if not excel_path:
        _logger.warning(
            "migrate_services: no se encontró '%s' en ninguna de las rutas conocidas. "
            "Coloque el archivo en '%s' para ejecutar la migración.",
            _EXCEL_FILENAME, EXCEL_SEARCH_PATHS[0],
        )
        return

    _logger.info("migrate_services: leyendo Excel desde %s", excel_path)
    rows = _read_excel(excel_path)
    if not rows:
        _logger.info("migrate_services: el Excel no contiene filas válidas.")
        return
    _logger.info("migrate_services: %d filas encontradas.", len(rows))

    ProductTemplate = env["product.template"]

    existing_codes = set(
        ProductTemplate.search([("default_code", "!=", False)]).mapped("default_code")
    )
    _logger.info(
        "migrate_services: %d productos con default_code ya existentes.", len(existing_codes)
    )

    created = skipped = errors = 0
    for row in rows:
        codigo = row["codigo"]
        descripcion = row["descripcion"]

        # Sin descripción: fila vacía o inválida
        if not descripcion:
            _logger.debug(
                "migrate_services: [OMITIDO] fila sin descripción (codigo=%s)", codigo
            )
            skipped += 1
            continue

        # Sin código: no hay clave única → omitir para evitar duplicados
        if not codigo:
            _logger.warning(
                "migrate_services: [OMITIDO] '%s' no tiene código (default_code vacío). "
                "No se crea para evitar duplicados en re-ejecuciones.",
                descripcion,
            )
            skipped += 1
            continue

        # Ya existe con ese código
        if codigo in existing_codes:
            _logger.debug(
                "migrate_services: [OMITIDO] ya existe default_code='%s' (%s)",
                codigo, descripcion,
            )
            skipped += 1
            continue

        try:
            product = ProductTemplate.create({
                "name": descripcion,
                "default_code": codigo,
                "type": "service",
            })
            existing_codes.add(codigo)
            _logger.info(
                "migrate_services: [CREADO] ID=%d | codigo=%s | nombre='%s'",
                product.id, codigo, descripcion,
            )
            created += 1
        except Exception as exc:
            _logger.error(
                "migrate_services: [ERROR] no se pudo crear codigo='%s' (%s): %s",
                codigo, descripcion, exc,
            )
            errors += 1

    _logger.info(
        "migrate_services: RESUMEN — %d creados, %d omitidos, %d errores.",
        created, skipped, errors,
    )

    # Marcar como completada solo si no hubo errores
    if errors == 0:
        ICP.set_param(MIGRATION_PARAM, "1")
        _logger.info("migrate_services: migración marcada como completada.")
    else:
        _logger.warning(
            "migrate_services: migración terminó con %d errores. "
            "No se marcó como completada; se reintentará en la próxima ejecución.",
            errors,
        )
