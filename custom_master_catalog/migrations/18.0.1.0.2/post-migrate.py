import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migrar datos de res.partner.supplier_drivers.rel a res.partner.supplier_users.rel
    """
    # Verificar si la tabla antigua existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'res_partner_supplier_drivers_rel'
        );
    """)
    tabla_existe = cr.fetchone()[0]

    if not tabla_existe:
        return

    # Migrar los datos de la tabla antigua a la nueva
    cr.execute("""
        INSERT INTO res_partner_supplier_users_rel (
            user_id, partner_id, user_type, center_of_attention_id,
            supplier_id, create_uid, create_date, write_uid, write_date
        )
        SELECT
            u.id as user_id,
            old.driver_id as partner_id,
            'operator' as user_type,  -- Valor por defecto
            old.center_of_attention_id,
            old.supplier_id,
            old.create_uid,
            old.create_date,
            old.write_uid,
            old.write_date
        FROM res_partner_supplier_drivers_rel old
        INNER JOIN res_partner rp ON rp.id = old.driver_id
        INNER JOIN res_users u ON u.partner_id = rp.id
        WHERE NOT EXISTS (
            SELECT 1 FROM res_partner_supplier_users_rel new_rel
            WHERE new_rel.user_id = u.id
            AND new_rel.center_of_attention_id = old.center_of_attention_id
        );
    """)

    # cr.execute("DROP TABLE IF EXISTS res_partner_supplier_drivers_rel CASCADE;")
