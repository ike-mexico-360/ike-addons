import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    category_mapping = {
        'custom_master_catalog.ike_product_category_vial': {
            'x_ref': 'vial',
            'x_input_res_model': 'ike.service.input.vial',
            'x_icon': 'fa fa-car',
            'x_survey_id': env.ref('ike_event.survey_vial').id,
        },
        'custom_master_catalog.ike_product_category_medical': {
            'x_ref': 'medical',
            'x_input_res_model': 'ike.service.input.medical',
            'x_icon': 'fa fa-user-md',
            'x_survey_id': env.ref('ike_event.survey_medical').id,
        },
        'custom_master_catalog.ike_product_category_home': {
            'x_ref': 'home',
            'x_input_res_model': '',
            'x_icon': 'fa fa-home',
            'x_survey_id': env.ref('ike_event.survey_home').id,
        },
        'custom_master_catalog.ike_product_category_legal': {
            'x_ref': 'legal',
            'x_input_res_model': '',
            'x_icon': 'fa fa-balance-scale',
            'x_survey_id': env.ref('ike_event.survey_legal').id,
        },
        'custom_master_catalog.ike_product_category_pets': {
            'x_ref': 'pets',
            'x_input_res_model': '',
            'x_icon': 'fa fa-paw',
            'x_survey_id': env.ref('ike_event.survey_pets').id,
        },
    }

    product_product_mapping = {
        'custom_master_catalog.ike_product_product_vial_truck': {
            'x_input_res_model': 'ike.service.input.vial.truck',
            'x_icon': 'fa fa-truck',
            'x_survey_id': env.ref('ike_event.survey_vial_truck').id,
        },
        'custom_master_catalog.ike_product_product_vial_tire': {
            'x_input_res_model': 'ike.service.input.vial.generic',
            'x_icon': 'fa fa-car',
            'x_survey_id': env.ref('ike_event.survey_vial_tire').id,
        },
        'custom_master_catalog.ike_product_product_medical_consultation': {
            'x_input_res_model': 'ike.service.input.medical.consultation',
            'x_icon': 'fa fa-stethoscope',
            'x_survey_id': env.ref('ike_event.survey_medical_consultation').id,
        },
    }

    for category_xml_id, category_data in category_mapping.items():
        category_id = env.ref(category_xml_id)
        category_new_data = {}
        if not category_id.x_ref:
            category_new_data['x_ref'] = category_data['x_ref']
        if not category_id.x_input_res_model:
            category_new_data['x_input_res_model'] = category_data['x_input_res_model']
        if not category_id.x_icon:
            category_new_data['x_icon'] = category_data['x_icon']
        if not category_id.x_survey_id:
            category_new_data['x_survey_id'] = category_data['x_survey_id']

        if category_new_data:
            _logger.info(f"Updating '{category_xml_id}' with {category_new_data}")
            category_id.write(category_new_data)

    for product_xml_id, product_data in product_product_mapping.items():
        product_id = env.ref(product_xml_id)
        product_new_data = {}
        if not product_id.x_input_res_model:
            product_new_data['x_input_res_model'] = product_data['x_input_res_model']
        if not product_id.x_icon:
            product_new_data['x_icon'] = product_data['x_icon']
        if not product_id.x_survey_id:
            product_new_data['x_survey_id'] = product_data['x_survey_id']

        if product_new_data:
            _logger.info(f"Updating '{product_xml_id}' with {product_new_data}")
            product_id.write(product_new_data)
