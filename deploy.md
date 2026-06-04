# Guía de Despliegue — Módulos Personalizados Odoo 17

**Autor:** Osliani Figueiras Saucedo  
**Versión de Odoo:** 17.0  

---

## Módulos incluidos

| Módulo | Descripción | Depende de |
|--------|-------------|------------|
| `telegram_notifier` | Notificaciones al desarrollador vía Telegram | `base` |
| `partner_custom_fields` | Campos personalizados en contactos y empresas | `base`, `contacts`, `telegram_notifier` |
| `contratos` | Gestión de contratos marco (MiPyme, TCP, Empresa) | `partner_custom_fields`, `telegram_notifier` |
| `contratos_especificos` | Contratos específicos con líneas de servicio | `contratos`, `partner_custom_fields`, `telegram_notifier` |
| `signature_management` | Firmas digitales, facturación y notificaciones de vencimiento | `contratos`, `contratos_especificos`, `partner_custom_fields`, `telegram_notifier` |

> ⚠️ **Orden de instalación obligatorio:** instalar en el orden de la tabla, de arriba hacia abajo.

---

## Requisitos previos

### wkhtmltopdf (para reportes PDF)
```bash
sudo apt-get install wkhtmltopdf
# Verificar versión compatible con Odoo 17:
wkhtmltopdf --version
# Debe ser >= 0.12.6
```
En Ubuntu 22.04 el binario queda en `/usr/bin/wkhtmltopdf`.

---

## Dependencias de Python

Instalar en el entorno virtual de Odoo:

```bash
# Activar el entorno virtual de Odoo
source /opt/odoo/venv/bin/activate  # ajusta la ruta si es diferente

# Dependencias adicionales requeridas por los módulos personalizados
pip install requests python-dotenv
```
---

## Variables de entorno

Los módulos requieren un archivo `.env` ubicado **dentro de la carpeta `extra_addons/`**.  
Este archivo **no está incluido en el repositorio** por contener credenciales.

Crear el archivo en el servidor:

Contenido del archivo:

```ini
TELEGRAM_BOT_TOKEN_NOTIFIER=<token_del_bot_de_telegram>
TELEGRAM_DEV_CHAT_ID=<chat_id_del_desarrollador>
```

---

## Configuración de odoo.conf

Agregar o actualizar el archivo `odoo.conf` en el servidor. Puntos críticos:

```ini
[options]
addons_path = /ruta/a/odoo/addons,/ruta/al/extra_addons
; Ajustar la ruta a wkhtmltopdf en Linux:
wkhtmltopdf_path = /usr/bin/wkhtmltopdf
; Resto de configuración: db_host, db_user, db_password, etc.
```

---
