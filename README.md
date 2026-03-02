# Odoo Extra Addons

Este proyecto contiene módulos personalizados para mejorar la gestión comercial en Odoo 17.

## Módulos Disponibles

### 📝 Master Contracts (`contratos`)
Este módulo facilita la gestión de **Contratos Marcos** para diferentes tipos de entidades (MiPymes, TCP, Empresas).
- **Generación Automática**: Crea el contenido del contrato combinando plantillas con la información de los contactos.
- **Gestión de Plantillas**: Permite sincronizar plantillas desde el sistema de archivos y validarlas para asegurar que contengan toda la información necesaria.
- **Flujo de Firma**: Permite marcar contratos como firmados, protegiéndolos contra modificaciones accidentales.
- **Trazabilidad**: Registra quién creó cada contrato y a qué compañía pertenece.

### � Specific Contracts (`contratos_especificos`)
Módulo para la gestión de acuerdos detallados que dependen de un Contrato Marco.
- **Vínculo Jerárquico**: Cada contrato específico está asociado obligatoriamente a un Contrato Marco firmado.
- **Detalle de Servicios**: Permite definir líneas de servicios o productos con cantidades, precios y fechas de ejecución opcionales.
- **Líderes de Proyecto**: Permite asignar un líder del proyecto tanto por la parte del prestador (nosotros) como por la del cliente.
- **Inmutabilidad**: Una vez que el contrato es firmado, todos sus datos quedan bloqueados para garantizar la integridad de lo acordado.

### �👥 Partner Custom Fields (`partner_custom_fields`)
Añade campos especializados a los registros de Contactos y Compañías.
- **Clasificación**: Permite categorizar a los socios comerciales según su tipo legal.
- **Datos Estatales**: Incluye campos para el Ministerio, REEUP y NIT, esenciales para la gestión comercial y legal.
- **Campos de Registro**: Añade información de registro mercantil y tomos.
- **Validación de CI**: Incluye lógica para validar números de carnet de identidad.

### ✍️ Signature Management (`signature_management`)
Gestión centralizada de firmas digitales y su aplicación en contratos y facturas.
- **Repositorio de Firmas**: Mantiene un registro de firmas autorizadas con su imagen y cargo.
- **Vinculación**: Rastrea qué contactos y contratos utilizan cada firma.
- **Integración con Facturación**: Permite seleccionar firmas y formas de pago al generar facturas desde contratos.

## Validaciones Implementadas

Para garantizar la integridad de los datos y el cumplimiento de las reglas de negocio, se han implementado las siguientes validaciones:

### Contactos (`res.partner`)
- **Carnet de Identidad**: El CI debe contener exactamente 11 dígitos numéricos.
- **Restricción de CI**: Las compañías no pueden tener CI; este campo es exclusivo para personas físicas.
- **MiPymes**: Para entidades clasificadas como MiPyme, el REEUP y el NIT deben ser idénticos.
- **Titular de Cuenta**: El campo "Titular de cuenta bancaria" está restringido y solo es visible/editable para compañías.

### Contratos (Marcos y Específicos)
- **Firmas Obligatorias**: Un contrato (Marco o Específico) solo puede pasar al estado **Firmado** si se han seleccionado tanto la firma del prestador como la del cliente.
- **Integridad de Firma**: Una vez firmado, el contenido del contrato queda bloqueado para evitar modificaciones.
- **Flujo de Estados**: Se prohíbe el paso directo de **Firmado** a **Borrador**. Para revertir un contrato firmado, primero debe ser cancelado.
- **Protección de Eliminación**: No se permite eliminar un **Contrato Marco** si existen **Contratos Específicos** vinculados a él.
- **Eliminación en Cascada**: Al eliminar un **Contrato Específico**, el sistema elimina automáticamente todas las facturas asociadas para mantener la consistencia.
- **Control de Acceso**: Solo los contactos definidos como "Contactos Autorizados" en el Contrato Marco (o administradores) tienen permiso para cambiar el estado del Contrato Marco y de sus Contratos Específicos.

### Facturación (`account.move`)
- **Prerrequisito de Firma**: Solo se pueden generar facturas desde contratos que se encuentren en estado **Firmado**.
- **Sincronización de Estado**: Si se elimina una factura vinculada a una línea de servicio, el estado de dicha línea se actualiza automáticamente a "no facturada".
- **Lógica de Reversión**: Si un usuario desmarca manualmente una línea de servicio como "facturada", el sistema procede a eliminar la factura asociada (siempre que sea posible según el estado de la misma).
- **Bloqueo Administrativo**: No se puede devolver un contrato a estado **Borrador** si ya tiene líneas de servicio facturadas.

---
**Autor:** Osliani Figueiras Saucedo
**Copyright:** Osliani Figueiras Saucedo
