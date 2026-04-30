# uv run python extra_addons/scripts/create_companies_from_excel.py
"""
Script para migrar clientes de tipo compañía a Odoo desde el Excel 'Entidades.xlsx'.

Mapeo de columnas:
  Codigo(Versat) -> customer_number
  REEUP          -> reeup
  Nombre         -> name
  Abrev.         -> short_name
  Correo         -> email
  Telefono       -> phone
  NIT            -> vat
  Direccion      -> street
  Provincia      -> state_id  (busca por nombre en res.country.state)
  Pais           -> country_id (busca por nombre en res.country; si vacío usa Cuba)

Cada registro se crea como res.partner con:
  - is_company = True
  - customer_rank = 1

Si ya existe un partner con el mismo customer_number, se omite.
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
    Path(__file__).parent.parent / "context" / "Datos a migrar" / "Entidades.xlsx"
)

DEFAULT_COUNTRY_NAME: str = "Cuba"


# ---------------------------------------------------------------------------
# Helpers de conexión
# ---------------------------------------------------------------------------
def authenticate(url: str, db: str, user: str, password: str) -> int:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid: int = common.authenticate(db, user, password, {})
    if not uid:
        raise PermissionError(
            f"Autenticación fallida para el usuario '{user}' en la base de datos '{db}'."
        )
    print(f"Autenticado correctamente. UID: {uid}")
    return uid


# ---------------------------------------------------------------------------
# Carga de catálogos desde Odoo
# ---------------------------------------------------------------------------
def load_countries(models: xmlrpc.client.ServerProxy, uid: int) -> dict[str, int]:
    """Devuelve {nombre_lower: id} para todos los países."""
    records: list[dict] = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "res.country",
        "search_read",
        [[]],
        {"fields": ["id", "name"]},
    )
    return {r["name"].lower(): r["id"] for r in records}


def load_states(models: xmlrpc.client.ServerProxy, uid: int) -> dict[str, int]:
    """Devuelve {nombre_lower: id} para todos los estados/provincias."""
    records: list[dict] = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "res.country.state",
        "search_read",
        [[]],
        {"fields": ["id", "name"]},
    )
    return {r["name"].lower(): r["id"] for r in records}


def load_existing_customer_numbers(
    models: xmlrpc.client.ServerProxy, uid: int
) -> set[str]:
    """Devuelve el conjunto de customer_number ya registrados."""
    records: list[dict] = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "res.partner",
        "search_read",
        [[["customer_number", "!=", False]]],
        {"fields": ["customer_number"]},
    )
    return {str(r["customer_number"]) for r in records}


def load_existing_reeups(models: xmlrpc.client.ServerProxy, uid: int) -> set[str]:
    """Devuelve el conjunto de reeup ya registrados en Odoo."""
    records: list[dict] = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "res.partner",
        "search_read",
        [[["reeup", "!=", False]]],
        {"fields": ["reeup"]},
    )
    return {str(r["reeup"]) for r in records}


# ---------------------------------------------------------------------------
# Lectura del Excel
# ---------------------------------------------------------------------------
def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def read_excel(path: Path) -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows: list[dict[str, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        (
            codigo,
            reeup,
            nombre,
            abrev,
            correo,
            telefono,
            nit,
            direccion,
            _ircc,
            provincia,
            pais,
        ) = row
        if not clean(nombre):
            continue
        rows.append(
            {
                "customer_number": clean(codigo),
                "reeup": clean(reeup),
                "name": clean(nombre),
                "short_name": clean(abrev),
                "email": clean(correo),
                "phone": clean(telefono),
                "vat": clean(nit),
                "street": clean(direccion),
                "provincia": clean(provincia),
                "pais": clean(pais),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Creación de partners
# ---------------------------------------------------------------------------
def resolve_unique_reeup(reeup: str, used_reeups: set[str]) -> str:
    """Devuelve el reeup tal cual si no está en uso, o con sufijo _2, _3... si ya existe."""
    if not reeup or reeup not in used_reeups:
        return reeup
    counter: int = 2
    while f"{reeup}_{counter}" in used_reeups:
        counter += 1
    return f"{reeup}_{counter}"


def build_partner_vals(
    row: dict[str, str],
    countries: dict[str, int],
    states: dict[str, int],
    default_country_id: int,
) -> dict:
    vals: dict = {
        "name": row["name"],
        "is_company": True,
        "customer_rank": 1,
    }

    optional_char_fields = [
        "customer_number",
        "reeup",
        "short_name",
        "email",
        "phone",
        "vat",
        "street",
    ]
    for field in optional_char_fields:
        if row[field]:
            vals[field] = row[field]

    # País
    pais_key = row["pais"].lower()
    if pais_key and pais_key in countries:
        vals["country_id"] = countries[pais_key]
    else:
        vals["country_id"] = default_country_id

    # Provincia
    provincia_key = row["provincia"].lower()
    if provincia_key and provincia_key in states:
        vals["state_id"] = states[provincia_key]

    return vals


def create_companies(
    models: xmlrpc.client.ServerProxy,
    uid: int,
    rows: list[dict[str, str]],
    existing_codes: set[str],
    existing_reeups: set[str],
    countries: dict[str, int],
    states: dict[str, int],
    default_country_id: int,
) -> None:
    created: int = 0
    skipped: int = 0

    for row in rows:
        customer_number = row["customer_number"]

        if customer_number and customer_number in existing_codes:
            print(
                f"  [OMITIDO] Ya existe customer_number='{customer_number}' ({row['name']})"
            )
            skipped += 1
            continue

        # Resolver REEUP único: si ya está en uso agrega sufijo _2, _3...
        original_reeup: str = row["reeup"]
        unique_reeup: str = resolve_unique_reeup(original_reeup, existing_reeups)
        if unique_reeup != original_reeup:
            print(
                f"  [REEUP AJUSTADO] '{original_reeup}' -> '{unique_reeup}' ({row['name']})"
            )
        row = {**row, "reeup": unique_reeup}

        vals = build_partner_vals(row, countries, states, default_country_id)

        partner_id: int = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "res.partner",
            "create",
            [vals],
        )

        if customer_number:
            existing_codes.add(customer_number)
        if unique_reeup:
            existing_reeups.add(unique_reeup)

        print(
            f"  [CREADO] ID={partner_id} | "
            f"customer_number={customer_number} | "
            f"nombre='{row['name']}'"
        )
        created += 1

    print(f"\nResumen: {created} compañías creadas, {skipped} omitidas.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo Excel en: {EXCEL_PATH}")

    print(f"Leyendo Excel: {EXCEL_PATH}")
    rows = read_excel(EXCEL_PATH)
    print(f"Filas encontradas: {len(rows)}")

    uid = authenticate(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

    print("Cargando catálogos de Odoo...")
    countries = load_countries(models, uid)
    states = load_states(models, uid)

    default_country_id = countries.get(DEFAULT_COUNTRY_NAME.lower())
    if not default_country_id:
        raise ValueError(f"No se encontró el país '{DEFAULT_COUNTRY_NAME}' en Odoo.")

    print("Obteniendo customer_numbers existentes...")
    existing_codes = load_existing_customer_numbers(models, uid)
    print(f"Partners con customer_number existentes: {len(existing_codes)}")

    print("Obteniendo REEUPs existentes...")
    existing_reeups = load_existing_reeups(models, uid)
    print(f"Partners con REEUP existentes: {len(existing_reeups)}")

    print("\nCreando compañías...")
    create_companies(
        models,
        uid,
        rows,
        existing_codes,
        existing_reeups,
        countries,
        states,
        default_country_id,
    )


if __name__ == "__main__":
    main()
