import os

from lxml import etree

root = etree.Element("odoo")
data = etree.SubElement(root, "data", noupdate="1")

templates = [
    {
        "id": "template_cgm_disponibilidad",
        "name": "CGM Disponibilidad y Soporte",
        "type": "cgm_disponibilidad",
        "content": """
            <p>CONTRATO ESPECÍFICO No. {{specific_number}}</p>
            <p>AL CONTRATO MARCO DE PRESTACIÓN DE SERVICIOS INFORMÁTICOS No. {{marco_number}}</p>
            <p>DE UNA PARTE: Sociedad Mercantil Soluciones DTeam S.U.R.L, Sociedad Unipersonal de Responsabilidad Limitada, de carácter estatal, representada en este acto por {{our_representative}}, quien comparece en su condición de {{our_rep_function}}, según Acuerdo Número {{our_rep_decision_number}} tomado en la Primera Reunión del Consejo de la Administración en fecha 2 de Octubre de 2023, donde se le otorga la facultad de firmar contratos económicos con clientes en representación de la Sociedad, lo que fue autorizado previamente por el Socio Único mediante la Decisión No. 5 tomada en fecha 15 de septiembre de 2023, y en uso de tal facultad, en lo adelante y a los efectos del presente instrumento jurídico se denominará EL PRESTADOR.</p>
            <p>DE LA OTRA PARTE: La {{partner_name}}, a través de {{partner_via}} en forma abreviada {{partner_short_name}}, quien en lo adelante y a los efectos del presente contrato se denominará EL CLIENTE.</p>
            <p>AMBAS PARTES: Reconociéndose recíprocamente la representación, el carácter y personalidad con que comparecen a nombre de sus respectivas entidades, y dando fe que mantienen los datos referentes a la personalidad jurídica que obran en el Contrato Marco convienen lo siguiente:</p>
            <p>DEFINICIONES:</p>
            <p>• PRODUCTOR: División Territorial Desoft Granma de la Empresa de Aplicaciones Informáticas, DESOFT.</p>
            <p>• Disponibilidad a la aplicación: Permite el acceso total a la funcionalidad de la solución informática, le garantiza al cliente disponer de todas las correcciones y mejoras que se le hagan a la solución.</p>
            <p>• Soporte: Es el servicio de asistencia técnica que brinda el distribuidor de una aplicación relacionada con aclaración de dudas de operación o errores de operación, aunque impliquen la modificación de los programas y corrección o ajuste de las bases de datos. Se realiza de manera presencial.</p>
            <p>CLÁUSULAS:</p>
            <p>1. OBJETO DEL CONTRATO</p>
            <p>1.1 El presente Contrato tiene como objeto establecer las Condiciones Específicas para la prestación de los servicios de Disponibilidad y Soporte a la aplicación Sistema para el Control y Gestión de Multas (CGM) la cual se encuentra hospedada en el Centro de Datos administrado por DESOFT.</p>
            <p>5. OTROS</p>
            <p>5.1 Todo lo que no se encuentre estipulado en este contrato será regido por lo pactado en el Contrato Marco No. {{marco_number}} de fecha {{marco_date}}; lo cual es de entera vigencia para LAS PARTES.</p>
            <p>6. VIGENCIA</p>
            <p>6.1 El presente Contrato, subscrito entre las partes, entrará en vigor a partir de fecha {{start_date}} y mantendrá su vigencia por el término de un (1) año natural.</p>
            <p>Y para que así conste, se subscribe el presente Contrato, en dos ejemplares, a un mismo tenor y efectos legales, en la ciudad de Sancti Spíritus a los {{day}} días del mes de {{month}} del año {{year}}.</p>
            <br/>
            <p><strong>Anexo No.1: DESCRIPCIÓN DE LOS SERVICIOS Y FORMA DE PAGO</strong></p>
            {{service_lines_table}}
        """,
    },
    {
        "id": "template_productos_soporte",
        "name": "Productos Soporte",
        "type": "productos_soporte",
        "content": """
            <p>CONTRATO ESPECÍFICO No. {{specific_number}}</p>
            <p>AL CONTRATO MARCO DE PRESTACIÓN DE SERVICIOS INFORMÁTICOS No. {{marco_number}}</p>
            <p>DE UNA PARTE: Sociedad Mercantil Soluciones DTeam S.U.R.L, Sociedad Unipersonal de Responsabilidad Limitada, de carácter estatal, representada en este acto por {{our_representative}}, quien comparece en su condición de {{our_rep_function}}, según Acuerdo Número {{our_rep_decision_number}} tomado en la Primera Reunión del Consejo de la Administración en fecha 2 de Octubre de 2023, donde se le otorga la facultad de firmar contratos económicos con clientes en representación de la Sociedad, lo que fue autorizado previamente por el Socio Único mediante la Decisión No. 5 tomada en fecha 15 de septiembre de 2023, y en uso de tal facultad, en lo adelante y a los efectos del presente instrumento jurídico se denominará EL PRESTADOR.</p>
            <p>DE LA OTRA PARTE: La {{partner_name}}, a través de {{partner_via}} en forma abreviada {{partner_short_name}}, quien en lo adelante y a los efectos del presente contrato se denominará EL CLIENTE.</p>
            <p>1. OBJETO DEL CONTRATO</p>
            <p>1.1 El presente Contrato tiene como objeto establecer las Condiciones Específicas para la prestación del servicio de Soporte a la aplicación {{application_name}}.</p>
            <p>3. OTROS</p>
            <p>3.1 Todo lo que no se encuentre estipulado en este contrato será regido por lo pactado en el Contrato Marco No. {{marco_number}} de fecha {{marco_date}}; lo cual es de entera vigencia para LAS PARTES.</p>
            <p>4. VIGENCIA</p>
            <p>4.1 El presente Contrato, subscrito entre las partes, entrará en vigor a partir de fecha {{start_date}} y mantendrá su vigencia por el término de un (1) año natural.</p>
            <p>Y para que así conste, se subscribe el presente Contrato, en dos ejemplares, a un mismo tenor y efectos legales, en la ciudad de Sancti Spíritus a los {{day}} días del mes de {{month}} del año {{year}}.</p>
            <br/>
            <p><strong>Anexo No.1 Price of the support service to the Application {{application_name}}.</strong></p>
            {{service_lines_table}}
        """,
    },
    {
        "id": "template_soporte_desarrollo",
        "name": "Servicio Soporte Desarrollo",
        "type": "soporte_desarrollo",
        "content": """
            <p>CONTRATO ESPECÍFICO No. {{specific_number}}</p>
            <p>AL CONTRATO MARCO DE PRESTACIÓN DE SERVICIOS INFORMÁTICOS No. {{marco_number}}</p>
            <p>DE UNA PARTE: Sociedad Mercantil Soluciones DTeam S.U.R.L, Sociedad Unipersonal de Responsabilidad Limitada, de carácter estatal, que en lo adelante y a los efectos de este Contrato se denominará EL PRESTADOR.</p>
            <p>DE LA OTRA PARTE: La {{partner_name}}, a través de {{partner_via}} en forma abreviada {{partner_short_name}}, quien en lo adelante y a los efectos del presente contrato se denominará EL CLIENTE.</p>
            <p>1. OBJETO DEL CONTRATO</p>
            <p>1.1 El presente Contrato tiene como objeto establecer las Condiciones Específicas para la prestación del servicio de Soporte al Desarrollo a la Medida {{application_name}}, como se relaciona en el Anexo No.1, que forma parte integrante del presente instrumento jurídico.</p>
            <p>4. OTROS</p>
            <p>4.1 Todo lo que no se encuentre estipulado en este contrato será regido por lo pactado en el Contrato Marco No. {{marco_number}} de fecha {{marco_date}}; lo cual es de entera vigencia para LAS PARTES.</p>
            <p>5. VIGENCIA</p>
            <p>5.1 El presente Contrato, subscrito entre las partes, entrará en vigor a partir de fecha {{start_date}} y mantendrá su vigencia por el término de un (1) año natural.</p>
            <p>Y para que así conste, se subscribe el presente Contrato, en dos ejemplares, a un mismo tenor y efectos legales, en la ciudad de Sancti Spíritus a los {{day}} días del mes de {{month}} del año {{year}}.</p>
            <br/>
            <p><strong>Anexo No.1: DESCRIPCIÓN DE LOS SERVICIOS Y FORMA DE PAGO</strong></p>
            {{service_lines_table}}
        """,
    },
    {
        "id": "template_versat_iniciales",
        "name": "Versat Servicios Iniciales",
        "type": "versat_iniciales",
        "content": """
            <p>CONTRATO ESPECÍFICO No. {{specific_number}}</p>
            <p>AL CONTRATO MARCO DE PRESTACIÓN DE SERVICIOS INFORMÁTICOS No. {{marco_number}}</p>
            <p>DE UNA PARTE: Sociedad Mercantil Soluciones DTeam S.U.R.L, Sociedad Unipersonal de Responsabilidad Limitada, de carácter estatal, que en lo adelante y a los efectos de este Contrato se denominará EL PRESTADOR.</p>
            <p>DE LA OTRA PARTE: La {{partner_name}}, a través de {{partner_via}} en forma abreviada {{partner_short_name}}, quien en lo adelante y a los efectos del presente contrato se denominará EL CLIENTE.</p>
            <p>1. OBJETO DEL CONTRATO</p>
            <p>1.1 El presente Contrato tiene como objeto establecer las Condiciones Específicas para la prestación de los servicios de Diagnóstico, Instalación, Configuración, Carga Inicial de datos, Puesta en Marcha y Adiestramiento al producto Versat Sarasola versión 2.10.</p>
            <p>2.1.1 Se designa como Líder del Proyecto a {{project_leader}}, quien será el responsable del Proyecto.</p>
            <p>3. OTROS</p>
            <p>3.1 Todo lo que no se encuentre estipulado en este contrato será regido por lo pactado en el Contrato Marco No. {{marco_number}} de fecha {{marco_date}}; lo cual es de entera vigencia para LAS PARTES.</p>
            <p>4. VIGENCIA</p>
            <p>4.1 El presente Contrato entrará en vigor a partir de la fecha de su firma por ambas partes y mantendrá su vigencia hasta que se culmine el servicio pactado.</p>
            <p>Y para que así conste, se subscribe el presente Contrato, en dos ejemplares, a un mismo tenor y efectos legales, en la ciudad de Sancti Spíritus a los {{day}} días del mes de {{month}} del año {{year}}.</p>
            <br/>
            <p><strong>Anexo No.1: DESCRIPCIÓN DE LOS SERVICIOS Y FORMA DE PAGO</strong></p>
            {{service_lines_table}}
        """,
    },
]

for t in templates:
    record = etree.SubElement(
        data, "record", id=t["id"], model="contrato.especifico.template"
    )
    etree.SubElement(record, "field", name="name").text = t["name"]
    etree.SubElement(record, "field", name="type").text = t["type"]
    field_content = etree.SubElement(record, "field", name="content", type="html")
    field_content.text = etree.CDATA(t["content"].strip())

output_path = r"c:\Users\lilia\Desktop\Projects\Odoo\instancias\odoo17_comercial2\extra_addons\contratos_especificos\data\specific_template_data.xml"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, "wb") as f:
    f.write(
        etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True)
    )

print(f"Generated {output_path}")
print(f"Generated {output_path}")
