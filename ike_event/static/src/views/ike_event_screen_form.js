import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { effect } from "@web/core/utils/reactive";
import { FormController } from '@web/views/form/form_controller';
import { IkeEventFormController } from "./ike_event_form";
import { formView } from "@web/views/form/form_view";
import { View } from "@web/views/view";

const { onMounted, status, useState, useRef } = owl;

const VIEW_IDS = {
    'ike.service.input.vial': 'service_input_vial_form_id',
    'ike.service.input.vial.truck': 'service_input_vial_truck_form_id',
    'ike.service.input.vial.generic': 'service_input_vial_generic_form_id',
    'ike.service.input.medical': 'service_input_medical_form_id',
    'survey.user_input': 'survey_user_input_form_id',
    'ike.event.supplier': 'service_supplier_screen_form_id',
};


export class IkeEventScreenFormController extends IkeEventFormController {
    setup() {
        // console.log("IkeEventScreenForm", this);
        super.setup();
        this.state = useState({
            serviceInputId: null,
            serviceInputAux: true,
            serviceInputViewProps: {},

            serviceSurveyInputId: null,
            serviceSurveyInputAux: true,
            serviceSurveyInputViewProps: {},

            subServiceSurveyInputId: null,
            subServiceSurveyInputAux: true,
            subServiceSurveyInputViewProps: {},

            serviceSupplierId: null,
            serviceSupplierAux: true,
            serviceSupplierViewProps: {},

            stage_ref: '',
            step_number: 1,
            sections: {},
        });

        onMounted(() => {
            this.onMounted();
        });
    }
    onMounted() {
        effect((model) => {
            if (status(this) === "mounted") {
                const stepChanged = (
                    this.state.step_number != model.root.data.step_number
                    || this.state.stage_ref != model.root.data.stage_ref
                );
                this.state.stage_ref = model.root.data.stage_ref;
                this.state.step_number = model.root.data.step_number;
                this.state.sections = model.root.data.sections;

                // SERVICE VIEW
                if (model.root.data.service_res_id) {
                    if (model.root.data.service_res_id.resId != this.state.serviceInputId) {
                        let serviceResModel = model.root.data.service_res_model;
                        let serviceResId = model.root.data.service_res_id.resId;
                        let serviceViewId = this.props.context[VIEW_IDS[serviceResModel]];
                        let context = {
                            'ike_event_screen': true,
                        };
                        this.state.serviceInputId = serviceResId;
                        this.state.serviceInputViewProps = this.getViewProps(
                            serviceResModel,
                            serviceResId,
                            serviceViewId,
                            context,
                            this.saveViewData.bind(this),
                            this.actionBackward.bind(this),
                        );
                    }
                    if (stepChanged) {
                        this.state.serviceInputAux = !this.state.serviceInputAux;
                    }
                } else {
                    this.state.serviceInputId = null;
                }
                // SURVEY VIEW
                if (model.root.data.service_survey_input_id) {
                    if (model.root.data.service_survey_input_id != this.state.serviceSurveyInputId) {
                        let surveyInputResModel = "survey.user_input";
                        let surveyInputResId = model.root.data.service_survey_input_id[0];
                        let surveyInputViewId = this.props.context[VIEW_IDS[surveyInputResModel]];
                        let context = {
                            'ike_event_screen': true,
                        };
                        this.state.serviceSurveyInputId = surveyInputResId;
                        this.state.serviceSurveyInputViewProps = this.getViewProps(
                            surveyInputResModel,
                            surveyInputResId,
                            surveyInputViewId,
                            context,
                            this.saveViewData.bind(this),
                            this.actionBackward.bind(this),
                        );
                    }
                    if (stepChanged) {
                        this.state.serviceSurveyInputAux = !this.state.serviceSurveyInputAux;
                    }
                }
                if (model.root.data.sub_service_survey_input_id) {
                    if (model.root.data.sub_service_survey_input_id != this.state.subServiceSurveyInputId) {
                        let surveyInputResModel = "survey.user_input";
                        let surveyInputResId = model.root.data.sub_service_survey_input_id[0];
                        let surveyInputViewId = this.props.context[VIEW_IDS[surveyInputResModel]];
                        let context = {
                            'ike_event_screen': true,
                        };
                        this.state.subServiceSurveyInputId = surveyInputResId;
                        this.state.subServiceSurveyInputViewProps = this.getViewProps(
                            surveyInputResModel,
                            surveyInputResId,
                            surveyInputViewId,
                            context,
                            this.saveViewData.bind(this),
                            this.actionBackward.bind(this),
                        );
                    }
                    if (stepChanged) {
                        this.state.subServiceSurveyInputAux = !this.state.subServiceSurveyInputAux;
                    }
                }

                // SUB SERVICE VIEW
                if (model.root.data.sub_service_res_id) {
                    if (model.root.data.sub_service_res_id.resId != this.state.subServiceInputId) {
                        let serviceResModel = model.root.data.sub_service_res_model;
                        let serviceResId = model.root.data.sub_service_res_id.resId;
                        let serviceViewId = this.props.context[VIEW_IDS[serviceResModel]];
                        let context = {
                            'ike_event_screen': true,
                        };
                        this.state.subServiceInputId = serviceResId;
                        this.state.subServiceInputViewProps = this.getViewProps(
                            serviceResModel,
                            serviceResId,
                            serviceViewId,
                            context,
                            this.saveViewData.bind(this),
                            this.actionBackward.bind(this),
                        );
                    }
                    if (stepChanged) {
                        this.state.subServiceInputAux = !this.state.subServiceInputAux;
                    }
                } else {
                    this.state.subServiceInputId = null;
                }

                // EVENT SUPPLIER VIEW
                if (['assigned', 'in_progress', 'completed', 'close'].includes(model.root.data.stage_ref)) {
                    const service_supplier_ids = model.root.data.service_supplier_ids.records;
                    const selected_service_supplier_id = service_supplier_ids.find(supplier_id => supplier_id.data.state == 'accepted');
                    if (selected_service_supplier_id) {
                        let serviceResModel = selected_service_supplier_id.resModel;
                        let serviceResId = selected_service_supplier_id.resId;
                        let serviceViewId = this.props.context[VIEW_IDS[serviceResModel]];
                        let context = {
                            'ike_event_screen': true,
                        };
                        this.state.serviceSupplierId = serviceResId;
                        this.state.serviceSupplierViewProps = this.getViewProps(
                            serviceResModel,
                            serviceResId,
                            serviceViewId,
                            context,
                            this.saveViewData.bind(this),
                            this.actionBackward.bind(this),
                        );
                    }
                    if (stepChanged) {
                        this.state.serviceSupplierAux = !this.state.serviceSupplierAux;
                    }
                }
            }
        }, [this.model]);
    }

    getViewProps(resModel, resId, viewId, context, saveCallback, discardCallback) {
        const viewProps = {
            resId: resId,
            resModel: resModel,
            preventCreate: true,
            viewId: viewId,
            searchViewId: null,
            display: { controlPanel: false, searchPanel: false },
            mode: "edit",
            type: "form",
            context: context,
            onSave: async (record, options) => {
                if (saveCallback) {
                    await saveCallback(record, options);
                }
            },
            onDiscard: async () => {
                if (discardCallback) {
                    await discardCallback();
                }
            },
        };
        // console.log("viewProps", viewProps);
        return viewProps;
    }

    async saveViewData(record, options) {
        // console.log("saveViewData", options)
        if (options.special == "save") {
            this.actionForward();
        }
    }
    async actionForward(save = false) {
        if (save) {
            await this.env.bus.trigger("IKE_EVENT_SAVE_DATA", {});
        }

        await this._executeAction(this.model.root, "action_forward");
    }
    async actionBackward(save = false) {
        if (save) {
            await this.env.bus.trigger("IKE_EVENT_SAVE_DATA", {});
        }
        this._executeAction(this.model.root, "action_backward");
    }
    async beforeLeave() {
        this.env.bus.trigger("IKE_EVENT_SAVE_DATA", {});
        return super.beforeLeave()
    }

    // async actionForwardTest(save = false) {
    //     if (this.state.sections.survey_data === true) {
    //         const { resModel, resId } = this.state.serviceInputViewProps;
    //         if (this.state.serviceSurveyInputViewProps && resModel === 'ike.service.input.vial') {
    //             const ia_suggestion_done = this.model.root.data.ia_suggestion_done;
    //             if (ia_suggestion_done) {
    //                 this.env.services.ui.block();
    //                 try {
    //                     await this.setIASuggestionsTest();
    //                 } catch (err) {
    //                     console.error("setIASuggestions", err);
    //                 } finally {
    //                     this.env.services.ui.unblock();
    //                 }
    //             }
    //         }
    //     }
    //     if (save) {
    //         await this.env.bus.trigger("IKE_EVENT_SAVE_DATA", {});
    //     }

    //     await this._executeAction(this.model.root, "action_forward");
    // }
    // async setIASuggestionsTest() {
    //     const { resModel: serviceResModel, resId: serviceResId } = this.state.serviceInputViewProps;
    //     const { resModel: subServiceResModel, resId: subServiceResId } = this.state.subServiceInputViewProps;
    //     const { resModel: surveyResModel, resId: surveyResId } = this.state.subServiceSurveyInputViewProps;
    //     const eventId = this.props.resId;
    //     const { service_id, sub_service_id } = this.model.root.data;
    //     const service_data = await this.orm.searchRead(serviceResModel, [['id', '=', serviceResId]], ['vehicle_brand', 'vehicle_model']);
    //     const vehicle = {
    //         brand: service_data[0]['vehicle_brand'],
    //         model: service_data[0]['vehicle_model'],
    //     };
    //     // Survey Data
    //     const { records: survey_data } = await this.orm.webSearchRead(
    //         surveyResModel, [['id', '=', surveyResId]], {
    //         specification: {
    //             display_name: {},
    //             user_input_line_ids: {
    //                 fields: {
    //                     question_id: {
    //                         fields: {
    //                             title: {},
    //                             description: {},
    //                         }
    //                     },
    //                     display_name: {},
    //                 }
    //             },
    //         },
    //     });
    //     if (!survey_data || survey_data.length === 0) {
    //         return;
    //     }
    //     console.log(survey_data);
    //     function stripHtml(html) {
    //         if (!html || typeof html !== 'string') return html || '';
    //         const parser = new DOMParser();
    //         const doc = parser.parseFromString(html, 'text/html');
    //         return doc.body.textContent || '';
    //     }
    //     const questions = survey_data[0].user_input_line_ids
    //         .filter(x => x.question_id)
    //         .map(x => ({
    //             title: x.question_id.title || '',
    //             question: stripHtml(x.question_id.description),
    //             answer: x.display_name
    //         }));

    //     // Fleet extra data
    //     const accessories_domain = await this.orm.call('product.product', 'get_accessories_domain', []);

    //     const [concepts, accessories, vehicle_types] = await Promise.all([
    //         this.orm.searchRead(
    //             "product.product", [["x_product_id", "=", sub_service_id[0]]], ["id", "name"]),
    //         this.orm.searchRead(
    //             "product.product", accessories_domain, ["id", "name"]),
    //         this.orm.searchRead(
    //             "custom.vehicle.type", [["x_subservice_id", "=", sub_service_id[0]]], ["id", "name"]),
    //     ]);

    //     // IA Data
    //     const data = {
    //         id: eventId,
    //         vehicle: vehicle,
    //         questions: questions,
    //         service: { id: service_id?.[0], name: service_id?.[1] },
    //         sub_service: { id: sub_service_id?.[0], name: sub_service_id?.[1] },
    //         concepts: concepts,
    //         accessories: accessories,
    //         vehicles_types: vehicle_types,
    //     }

    //     console.log('data_sent_to_api', data);

    //     const dbNeutralized = await this.orm.call(
    //         "ir.config_parameter",
    //         "get_param",
    //         ["database.is_neutralized"]
    //     );
    //     if (dbNeutralized) {
    //         console.log("Neutralized database, skipping OpenAI call");
    //         return;
    //     }

    //     let suggestedAccessories = [];
    //     let suggestedConcepts = [];
    //     let suggestedVehicleTypes = [];
    //     try {
    //         const apiResponseOpenAI = await fetch('/openai/assistant/call_test', {
    //             method: 'POST',
    //             headers: {
    //                 'Content-Type': 'application/json',
    //             },
    //             body: JSON.stringify(data),
    //         })
    //         const data_response_OpenAI = await apiResponseOpenAI.json();
    //         switch (apiResponseOpenAI.status) {
    //             case 200:
    //                 suggestedAccessories = data_response_OpenAI?.suggested_accessories || [];
    //                 suggestedConcepts = data_response_OpenAI?.suggested_concepts || [];
    //                 suggestedVehicleTypes = data_response_OpenAI?.suggested_vehicle_types || [];
    //                 console.log('200: data_response_by_api_OpenAI', data_response_OpenAI);
    //                 break;
    //             case 204:
    //                 console.log('204: No se encontró respuesta del assistant');
    //                 break;
    //             case 400:
    //                 console.log('400: ', data_response_OpenAI.error);
    //                 break;
    //             case 409:
    //                 console.log('409: ', data_response_OpenAI.error);
    //                 break;
    //             case 500:
    //                 console.log('500: ', data_response_OpenAI.error);
    //                 break;
    //             default:
    //                 console.log('Default case: ', data_response_OpenAI);
    //                 break;
    //         }
    //     } catch (error) {
    //         console.error('Error en la petición:', error);
    //     }
    //     try {
    //         await this.orm.write(
    //             subServiceResModel,
    //             [subServiceResId],
    //             {
    //                 suggested_vehicle_types: suggestedVehicleTypes.map(v => v.name.toUpperCase()),
    //                 service_vehicle_type_ids: [[6, 0, suggestedVehicleTypes.map(v => v.id)]],
    //             }
    //         );
    //         await this.orm.write("ike.event", [eventId], {
    //             ia_suggestion_product_ids: suggestedConcepts?.map(c => c.id),
    //             ia_suggestion_done: true,
    //         });
    //     } catch (error) {
    //         console.error('Error guardando datos de sugerencia de vehículos', error);
    //     }
    // }
};

IkeEventScreenFormController.template = "ike_event.IkeEventScreenFormView";
IkeEventScreenFormController.components = {
    ...FormController.components,
    View,
};

export const ikeEventScreenFormView = {
    ...formView,
    Controller: IkeEventScreenFormController,
}

registry.category("views").add("ike_event_screen_form", ikeEventScreenFormView);
