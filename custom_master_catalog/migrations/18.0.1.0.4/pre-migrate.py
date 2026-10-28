
MODULE = 'custom_master_catalog'


def migrate(cr, version):
    # custom.type.event
    custom_event_types = {
        'Carretero': 'custom_type_event_highway',
        'No carretero': 'custom_type_event_no_highway',
    }

    for name, xml_name in custom_event_types.items():
        cr.execute("""
            SELECT id
            FROM custom_type_event
            WHERE name = %s
            LIMIT 1
        """, (name,))

        row = cr.fetchone()

        if not row:
            continue

        cr.execute("""
            INSERT INTO ir_model_data (
                module,
                name,
                model,
                res_id,
                noupdate
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (module, name)
            DO UPDATE SET
                model = EXCLUDED.model,
                res_id = EXCLUDED.res_id
        """, (
            MODULE,
            xml_name,
            'custom.type.event',
            row[0],
            True,
        ))
