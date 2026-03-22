import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    category_mapping = {
        'Vial': 'ike_product_category_vial',
        'Médico': 'ike_product_category_medical',
        'Hogar': 'ike_product_category_home',
        'Legal': 'ike_product_category_legal',
        'Mascotas': 'ike_product_category_pets',
    }

    product_product_mapping = {
        'Arrastre de grúa': 'ike_product_product_vial_truck',
        'Cambio de llanta': 'ike_product_product_vial_tire',
        'Suministro de gasolina': 'ike_product_product_vial_fuel',
        'Otros líquidos': 'ike_product_product_vial_fluid',
        'Paso de corriente': 'ike_product_product_vial_battery',
        'Consulta Médica': 'ike_product_product_medical_consultation',
    }

    # ===== CATEGORIES ===== #
    for category_name, xmlid in category_mapping.items():
        # Buscar categorías con ese nombre
        cr.execute("""
            SELECT pc.id, imd.module, imd.name
            FROM product_category pc
            LEFT JOIN ir_model_data imd ON (imd.model = 'product.category' AND imd.res_id = pc.id)
            WHERE pc.name = %s
        """, (category_name,))

        results = cr.fetchall()

        if not results:
            _logger.info(f"'{category_name}' no existe, se creará desde XML")
            continue

        for cat_id, module, xml_name in results:
            if module is None:
                # No tiene XML ID -> asignarle el del módulo
                _logger.info(f"Asignando XML ID a '{category_name}' (ID: {cat_id})")
                cr.execute("""
                    INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                    VALUES (%s, %s, %s, %s, true)
                """, (xmlid, 'custom_master_catalog', 'product.category', cat_id))

            elif module != 'custom_master_catalog':
                # Tiene XML ID de otro módulo (sistema) -> renombrar
                new_name = f"{category_name}_old"
                _logger.info(f"Renombrando categoría del sistema: '{category_name}' -> '{new_name}' (módulo: {module})")
                cr.execute("""
                    UPDATE product_category
                    SET name = %s
                    WHERE id = %s
                """, (new_name, cat_id))
            else:
                # Ya tiene el XML ID correcto
                _logger.info(f"'{category_name}' ya tiene XML ID correcto")

    # ===== PRODUCTS ===== #
    for product_name, xmlid in product_product_mapping.items():
        # Buscar productos con ese nombre
        cr.execute("""
            SELECT pp.id, imd.module, imd.name
            FROM product_product pp
            INNER JOIN product_template pt ON (pt.id = pp.product_tmpl_id)
            LEFT JOIN ir_model_data imd ON (imd.model = 'product.product' AND imd.res_id = pp.id)
            WHERE pt.name ->> 'en_US' = %s
            AND pt.categ_id = %s
            AND pt.sale_ok = True
            AND pt.purchase_ok = False
            AND pt.type = 'service'
            AND pt.uom_id = %s
        """, (
            product_name,
            env.ref('custom_master_catalog.ike_product_category_vial').id,
            env.ref('l10n_mx.product_uom_service_unit').id
        ))
        results = cr.fetchall()

        if not results:
            _logger.info(f"'{product_name}' no existe, se creará desde XML")
            continue

        for prod_id, module, xml_name in results:
            if module is None:
                # No tiene XML ID -> asignarle el del módulo
                _logger.info(f"Asignando XML ID a '{product_name}' (ID: {prod_id})")
                cr.execute("""
                    INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                    VALUES (%s, %s, %s, %s, true)
                """, (xmlid, 'custom_master_catalog', 'product.product', prod_id))

            elif module != 'custom_master_catalog':
                # Tiene XML ID de otro módulo (sistema) -> renombrar
                new_name = f"{product_name}_old"
                _logger.info(f"Renombrando producto del sistema: '{product_name}' -> '{new_name}' (módulo: {module})")
                cr.execute("""
                    UPDATE product_product
                    SET name = %s
                    WHERE id = %s
                """, (new_name, prod_id))
            else:
                # Ya tiene el XML ID correcto
                _logger.info(f"'{product_name}' ya tiene XML ID correcto")
