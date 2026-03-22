/** @odoo-module **/
import { IkeEventScreenFormController } from "@ike_event/views/ike_event_screen_form";
import { patch } from "@web/core/utils/patch";


patch(IkeEventScreenFormController.prototype, {
    setup() {
        super.setup();
    },

    async actionForward(save = false) {
        if (this.state.sections.survey_data === true) {
            const { resModel, resId } = this.state.serviceInputViewProps;
            if (this.state.serviceSurveyInputViewProps && resModel === 'ike.service.input.vial') {
                const dbNeutralized = await this.orm.call(
                    "ir.config_parameter",
                    "get_param",
                    ["database.is_neutralized"]
                );
                if (dbNeutralized) {
                    console.log("Neutralized database, skipping OpenAI call");
                }
                const ia_suggestion_done = this.model.root.data.ia_suggestion_done;
                if (!ia_suggestion_done && !dbNeutralized) {
                    this.env.services.ui.block();
                    try {
                        await this.setIASuggestions();
                    } catch (err) {
                        console.error("setIASuggestions", err);
                    } finally {
                        this.env.services.ui.unblock();
                    }
                }
            }
        }
        await super.actionForward(save);
    },
    async setIASuggestions() {
        const { resModel: serviceResModel, resId: serviceResId } = this.state.serviceInputViewProps;
        const { resModel: subServiceResModel, resId: subServiceResId } = this.state.subServiceInputViewProps;
        const { resModel: surveyResModel, resId: surveyResId } = this.state.subServiceSurveyInputViewProps;
        const eventId = this.props.resId;
        const { service_id, sub_service_id } = this.model.root.data;
        const service_data = await this.orm.searchRead(serviceResModel, [['id', '=', serviceResId]], ['vehicle_brand', 'vehicle_model']);
        const vehicle = {
            brand: service_data[0]['vehicle_brand'],
            model: service_data[0]['vehicle_model'],
        };
        // Survey Data
        const { records: survey_data } = await this.orm.webSearchRead(
            surveyResModel, [['id', '=', surveyResId]], {
            specification: {
                display_name: {},
                user_input_line_ids: {
                    fields: {
                        question_id: {
                            fields: {
                                title: {},
                                description: {},
                            }
                        },
                        display_name: {},
                    }
                },
            },
        });
        if (!survey_data || survey_data.length === 0) {
            return;
        }
        // console.log("survey_data", survey_data);
        function stripHtml(html) {
            if (!html || typeof html !== 'string') return html || '';
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            return doc.body.textContent || '';
        }
        const questions = survey_data[0].user_input_line_ids
            .filter(x => x.question_id)
            .map(x => ({
                title: x.question_id.title || '',
                question: stripHtml(x.question_id.description),
                answer: x.display_name
            }));

        // Fleet extra data
        const accessories_domain = await this.orm.call('product.product', 'get_accessories_domain', []);

        const [concepts, accessories, vehicle_types] = await Promise.all([
            this.orm.searchRead(
                "product.product", [["x_product_id", "=", sub_service_id[0]]], ["id", "name"]),
            this.orm.searchRead(
                "product.product", accessories_domain, ["id", "name"]),
            this.orm.searchRead(
                "custom.vehicle.type", [["x_subservice_id", "=", sub_service_id[0]]], ["id", "name"]),
        ]);

        // IA Data
        const data = {
            id: eventId,
            vehicle: vehicle,
            questions: questions,
            service: { id: service_id?.[0], name: service_id?.[1] },
            sub_service: { id: sub_service_id?.[0], name: sub_service_id?.[1] },
            concepts: concepts,
            accessories: accessories,
            vehicles_types: vehicle_types,
        }

        console.log('data_sent_to_api', data);

        let suggestedAccessories = [];
        let suggestedConcepts = [];
        let suggestedVehicleTypes = [];
        try {
            const apiResponseOpenAI = await fetch('/openai/assistant/call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            })
            const data_response_OpenAI = await apiResponseOpenAI.json();
            switch (apiResponseOpenAI.status) {
                case 200:
                    suggestedAccessories = data_response_OpenAI?.suggested_accesories || [];
                    suggestedConcepts = data_response_OpenAI?.suggested_concepts || [];
                    suggestedVehicleTypes = data_response_OpenAI?.suggested_vehicle_types || [];
                    console.log('200: data_response_by_api_OpenAI', data_response_OpenAI);
                    break;
                case 204:
                    console.log('204: No se encontró respuesta del assistant');
                    break;
                case 400:
                    console.log('400: ', data_response_OpenAI.error);
                    break;
                case 409:
                    console.log('409: ', data_response_OpenAI.error);
                    break;
                case 500:
                    console.log('500: ', data_response_OpenAI.error);
                    break;
                default:
                    console.log('Default case: ', data_response_OpenAI);
                    break;
            }
        } catch (error) {
            console.error('Error en la petición:', error);
        }
        try {
            await this.orm.write(
                subServiceResModel,
                [subServiceResId],
                {
                    suggested_accessories: suggestedAccessories.map(a => a.id),
                    service_accessory_ids: [[6, 0, suggestedAccessories.map(a => a.id)]],
                }
            );
            await this.orm.write(
                subServiceResModel,
                [subServiceResId],
                {
                    suggested_vehicle_types: suggestedVehicleTypes.map(v => v.name.toUpperCase()),
                    service_vehicle_type_ids: [[6, 0, suggestedVehicleTypes.map(v => v.id)]],
                }
            );
            await this.orm.write("ike.event", [eventId], {
                ia_suggestion_product_ids: suggestedConcepts?.map(c => c.id),
                ia_suggestion_done: true,
            });
        } catch (error) {
            console.error('Error guardando datos de sugerencia de vehículos', error);
        }
    }
});
