# uv run python extra_addons/scripts/create_services_from_excel.py
"""
Script para crear servicios (product.template) en Odoo a partir del Excel
'codigos o conceptos de facturacion.xlsx'.

Columnas del Excel:
  - codigo      -> default_code (referencia interna)
  - descripcion -> name (nombre del producto)

Cada producto se crea con type='service'.
Si ya existe un producto con el mismo default_code, se omite.
"""

import xmlrpc.client
from pathlib import Path

import openpyxl

# ---------------------------------------------------------------------------
# Configuración de conexión
# ---------------------------------------------------------------------------
ODOO_URL: str = "http://localhost:8088"
ODOO_DB: str = "odoo17_comercial2"
ODOO_USER: str = "admin"
ODOO_PASSWORD: str = "admin"

EXCEL_PATH: Path = (
    Path(__file__).parent.parent
    / "context"
    / "Datos a migrar"
    / "codigos o conceptos de facturacion.xlsx"
)


def authenticate(url: str, db: str, user: str, password: str) -> int:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid: int = common.authenticate(db, user, password, {})
    if not uid:
        raise PermissionError(
            f"Autenticación fallida para el usuario '{user}' en la base de datos '{db}'."
        )
    print(f"Autenticado correctamente. UID: {uid}")
    return uid


def get_existing_codes(models: xmlrpc.client.ServerProxy, uid: int) -> set[str]:
    """Devuelve el conjunto de default_code ya existentes en Odoo."""
    records: list[dict] = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "product.template",
        "search_read",
        [[["default_code", "!=", False]]],
        {"fields": ["default_code"]},
    )
    return {str(r["default_code"]) for r in records}


def read_excel(path: Path) -> list[dict[str, str]]:
    """Lee el Excel y devuelve una lista de dicts con 'codigo' y 'descripcion'."""
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows: list[dict[str, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        codigo, descripcion = row[0], row[1]
        if codigo is None and descripcion is None:
            continue
        rows.append(
            {"codigo": str(codigo).strip(), "descripcion": str(descripcion).strip()}
        )
    return rows


def create_services(
    models: xmlrpc.client.ServerProxy,
    uid: int,
    rows: list[dict[str, str]],
    existing_codes: set[str],
) -> None:
    created: int = 0
    skipped: int = 0

    for row in rows:
        codigo: str = row["codigo"]
        descripcion: str = row["descripcion"]

        if not descripcion:
            print(f"  [OMITIDO] Fila sin descripción (codigo={codigo})")
            skipped += 1
            continue

        if codigo in existing_codes:
            print(f"  [OMITIDO] Ya existe default_code='{codigo}' ({descripcion})")
            skipped += 1
            continue

        product_id: int = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "product.template",
            "create",
            [
                {
                    "name": descripcion,
                    "default_code": codigo,
                    "type": "service",
                }
            ],
        )
        existing_codes.add(codigo)
        print(f"  [CREADO] ID={product_id} | codigo={codigo} | nombre='{descripcion}'")
        created += 1

    print(f"\nResumen: {created} servicios creados, {skipped} omitidos.")


def main() -> None:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo Excel en: {EXCEL_PATH}")

    print(f"Leyendo Excel: {EXCEL_PATH}")
    rows = read_excel(EXCEL_PATH)
    print(f"Filas encontradas: {len(rows)}")

    uid = authenticate(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)

    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

    print("Obteniendo referencias internas existentes...")
    existing_codes = get_existing_codes(models, uid)
    print(f"Productos existentes con default_code: {len(existing_codes)}")

    print("\nCreando servicios...")
    create_services(models, uid, rows, existing_codes)


if __name__ == "__main__":
    main()
