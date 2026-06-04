"""
Migración de compañías clientes desde el Excel 'Entidades.xlsx'.

Se ejecuta automáticamente en el post_init_hook del módulo partner_custom_fields.

Idempotencia garantizada:
  - Registros CON customer_number: se omiten si ya existe ese código.
  - Registros SIN customer_number pero CON vat (NIT): se omiten si ya existe ese NIT.
  - Registros SIN customer_number ni vat: se omiten si ya existe un partner con el mismo name.
  - Si se interrumpe y se re-ejecuta: los registros ya creados se detectan y omiten.
  - El parámetro de sistema 'partner_custom_fields.migration_companies_done' marca
    si la migración completó al 100%; si no está marcado, se puede re-ejecutar.

Columnas del Excel:
  Codigo(Versat) -> customer_number
  REEUP          -> reeup
  Nombre         -> name
  Abrev.         -> short_name
  Correo         -> email
  Telefono       -> phone
  NIT            -> vat
  Direccion      -> street
  Provincia      -> state_id
  Pais           -> country_id (si vacío usa Cuba)
"""

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

DEFAULT_COUNTRY_NAME = "Cuba"
MIGRATION_PARAM = "partner_custom_fields.migration_companies_done"

_MODULE_DIR = Path(__file__).parent.parent
EXCEL_SEARCH_PATHS = [
    _MODULE_DIR / "data" / "migration" / "Entidades.xlsx",
    _MODULE_DIR.parent / "context" / "Datos a migrar" / "Entidades.xlsx",
]


def _find_excel() -> Path | None:
    for path in EXCEL_SEARCH_PATHS:
        if path.exists():
            return path
    return None


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def _read_excel(path: Path) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        _logger.error("migrate_companies: openpyxl no está instalado. Migración omitida.")
        return []

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        (codigo, reeup, nombre, abrev, correo, telefono,
         nit, direccion, _ircc, provincia, pais) = row
        if not _clean(nombre):
            continue
        rows.append({
            "customer_number": _clean(codigo),
            "reeup": _clean(reeup),
            "name": _clean(nombre),
            "short_name": _clean(abrev),
            "email": _clean(correo),
            "phone": _clean(telefono),
            "vat": _clean(nit),
            "street": _clean(direccion),
            "provincia": _clean(provincia),
            "pais": _clean(pais),
        })
    return rows


def _resolve_unique_reeup(reeup: str, used_reeups: set) -> str:
    if not reeup or reeup not in used_reeups:
        return reeup
    counter = 2
    while f"{reeup}_{counter}" in used_reeups:
        counter += 1
    return f"{reeup}_{counter}"


def _already_exists(row: dict, existing_codes: set, existing_vats: set,
                    existing_names: set) -> bool:
    """
    Comprueba si el registro ya existe usando múltiples claves de deduplicación,
    en orden de prioridad:
      1. customer_number (clave principal)
      2. vat/NIT (clave alternativa robusta)
      3. name (fallback final)
    """
    if row["customer_number"] and row["customer_number"] in existing_codes:
        return True
    if row["vat"] and row["vat"] in existing_vats:
        return True
    # Solo usar name como fallback si no hay ninguna clave única disponible
    if not row["customer_number"] and not row["vat"]:
        if row["name"].lower() in existing_names:
            return True
    return False


def run(env) -> None:
    """Punto de entrada llamado desde post_init_hook."""

    # Comprobar si la migración ya completó previamente al 100%
    ICP = env["ir.config_parameter"].sudo()
    if ICP.get_param(MIGRATION_PARAM) == "1":
        _logger.info(
            "migrate_companies: migración ya completada anteriormente, omitiendo."
        )
        return

    excel_path = _find_excel()
    if not excel_path:
        _logger.warning(
            "migrate_companies: no se encontró 'Entidades.xlsx' en ninguna de las rutas "
            "conocidas. Coloque el archivo en '%s' para ejecutar la migración.",
            EXCEL_SEARCH_PATHS[0],
        )
        return

    _logger.info("migrate_companies: leyendo Excel desde %s", excel_path)
    rows = _read_excel(excel_path)
    if not rows:
        _logger.info("migrate_companies: el Excel no contiene filas válidas.")
        return
    _logger.info("migrate_companies: %d filas encontradas.", len(rows))

    Partner = env["res.partner"]

    # Catálogos
    countries = {r.name.lower(): r.id for r in env["res.country"].search([])}
    states = {r.name.lower(): r.id for r in env["res.country.state"].search([])}
    default_country_id = countries.get(DEFAULT_COUNTRY_NAME.lower())
    if not default_country_id:
        _logger.error(
            "migrate_companies: no se encontró el país '%s'. Migración abortada.",
            DEFAULT_COUNTRY_NAME,
        )
        return

    # Cargar todas las claves de deduplicación existentes en BD
    existing_codes = set(
        Partner.search([("customer_number", "!=", False)]).mapped("customer_number")
    )
    existing_vats = set(
        Partner.search([("vat", "!=", False)]).mapped("vat")
    )
    existing_names = {
        p.name.lower()
        for p in Partner.search([("is_company", "=", True)])
        if p.name
    }
    existing_reeups = set(
        Partner.search([("reeup", "!=", False)]).mapped("reeup")
    )

    created = skipped = 0
    for row in rows:
        if _already_exists(row, existing_codes, existing_vats, existing_names):
            _logger.debug(
                "migrate_companies: [OMITIDO] '%s' (customer_number='%s')",
                row["name"], row["customer_number"],
            )
            skipped += 1
            continue

        # Resolver REEUP único
        original_reeup = row["reeup"]
        unique_reeup = _resolve_unique_reeup(original_reeup, existing_reeups)
        if unique_reeup != original_reeup:
            _logger.info(
                "migrate_companies: [REEUP AJUSTADO] '%s' -> '%s' (%s)",
                original_reeup, unique_reeup, row["name"],
            )

        vals = {"name": row["name"], "is_company": True, "customer_rank": 1}
        for field in ("customer_number", "short_name", "email", "phone", "vat", "street"):
            if row[field]:
                vals[field] = row[field]
        if unique_reeup:
            vals["reeup"] = unique_reeup

        pais_key = row["pais"].lower()
        vals["country_id"] = countries.get(pais_key, default_country_id)
        provincia_key = row["provincia"].lower()
        if provincia_key and provincia_key in states:
            vals["state_id"] = states[provincia_key]

        partner = Partner.create(vals)

        # Actualizar sets en memoria para evitar duplicados dentro de la misma ejecución
        if row["customer_number"]:
            existing_codes.add(row["customer_number"])
        if row["vat"]:
            existing_vats.add(row["vat"])
        existing_names.add(row["name"].lower())
        if unique_reeup:
            existing_reeups.add(unique_reeup)

        _logger.info(
            "migrate_companies: [CREADO] ID=%d | customer_number=%s | nombre='%s'",
            partner.id, row["customer_number"], row["name"],
        )
        created += 1

    _logger.info(
        "migrate_companies: RESUMEN — %d compañías creadas, %d omitidas.",
        created, skipped,
    )

    # Marcar migración como completada solo si procesó todas las filas sin excepción
    ICP.set_param(MIGRATION_PARAM, "1")
    _logger.info("migrate_companies: migración marcada como completada.")
