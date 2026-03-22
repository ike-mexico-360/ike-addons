import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { effect } from "@web/core/utils/reactive";
import { FormController } from '@web/views/form/form_controller';
import { formView } from "@web/views/form/form_view";

import { markup, onMounted, status, useState, useSubEnv } from "@odoo/owl";


export class IkeSurveyInputScreenFormController extends FormController {
    setup() {
        console.log("Survey User Input", this);
        useSubEnv({
            ...this.env,
            config: {
                ...this.env.config,
                setDisplayName: (newDisplayName) => { },
            },
        });
        super.setup();

        this.state = useState({
            surveyId: null,
            surveyData: {},
            showErrors: false,
        });
        this.title = _t("Service Details");

        useBus(this.env.bus, "IKE_EVENT_SAVE_DATA", async (ev) => {
            const record = this.model.root;
            await record.save({});
        });

        onMounted(() => {
            this.onMounted();
            // console.log("record", this.model.root);
        });
    }
    onMounted() {
        effect(async (model) => {
            if (status(this) === "mounted") {
                let surveyId = model.root.data.survey_id ? model.root.data.survey_id[0] : null;
                if (surveyId != this.state.surveyId) {
                    this.state.surveyId = surveyId;
                    const surveyData = await this.env.services.orm.webSearchRead(
                        "survey.survey", [['id', '=', surveyId]], {
                        specification: {
                            title: {},
                            question_ids: {
                                fields: {
                                    title: {},
                                    description: {},
                                    question_type: {},
                                    is_page: {},
                                    triggering_answer_ids: {},
                                    suggested_answer_ids: {
                                        fields: {
                                            value: {},
                                            display_name: {},
                                            sequence: {},
                                        }
                                    },
                                    question_placeholder: {},
                                    validation_required: {},
                                    validation_min_float_value: {},
                                    validation_max_float_value: {},
                                    validation_length_min: {},
                                    validation_length_max: {},
                                    validation_error_msg: {},
                                    constr_mandatory: {},
                                    constr_error_msg: {},
                                    comments_allowed: {},
                                    comments_message: {},
                                }
                            }
                        },
                    });
                    for (let question of surveyData.records[0].question_ids) {
                        if (!['simple_choice', 'multiple_choice'].includes(question.question_type)) {
                            const answerLines = this.getAnswerLines(question);
                            if (answerLines.length) {
                                question.answer_value = answerLines[0]['value_' + question.question_type];
                            }

                        }
                    }
                    this.state.surveyData = surveyData.records[0];
                    console.log("surveyData", surveyId, this.state.surveyData);
                }
            }
        }, [this.model]);
    }
    get input_lines() {
        return this.model.root.data.user_input_line_ids.records.map((line_id) => ({
            id: line_id.id,
            resId: line_id.resId,
            question_id: line_id.data.question_id[0],
            answer_type: line_id.answer_type,
            skipped: line_id.data.skipped,
            suggested_answer_id: line_id.data.suggested_answer_id ? line_id.data.suggested_answer_id[0] : null,
            value_numerical_box: line_id.data.value_numerical_box,
            value_text_box: line_id.data.value_text_box,
            value_char_box: line_id.data.value_char_box,
        }));
    }
    get suggested_answer_ids() {
        return this.input_lines.map(line_id => line_id.suggested_answer_id);
    }
    get showButtons() {
        return this.model.root?.context.ike_event_screen;
    }

    getMarkupValue(value) {
        return markup(value);
    }

    displayQuestion(question) {
        if (!question.triggering_answer_ids.length) {
            return true;
        }
        return question.triggering_answer_ids.every(num => this.suggested_answer_ids.includes(num));
    }

    getAnswerLines(question) {
        return this.input_lines.filter(answer => answer.question_id == question.id);
    }

    isAnswerSelected(question, label_id) {
        const answer_lines = this.getAnswerLines(question);
        const input_line = answer_lines.find(line_id => line_id.suggested_answer_id == label_id.id)
        return input_line ? true : false;
    }

    async selectAnswer(question, label_id) {
        if (question.locked) {
            return;
        }
        try {
            question.locked = true;
            const answer_line_ids = this.model.root.data.user_input_line_ids.records.filter(
                answer_id => answer_id.data.question_id[0] == question.id
            );
            const answer_line_id = answer_line_ids.find(
                line_id => (line_id.data.suggested_answer_id ? line_id.data.suggested_answer_id[0] : null) == label_id.id
            );
            // console.log(question, label_id, answer_line_ids, answer_line_id);
            if (answer_line_id) {
                await this.model.root.data.user_input_line_ids.delete(answer_line_id);
                // await this.model.root.update({
                //     user_input_line_ids: [[2, answer_line_id.resId]],
                // });
                // await this.model.root.save();
            } else {
                if (question.question_type == 'simple_choice' && answer_line_ids.length) {
                    answer_line_ids[0].update({
                        suggested_answer_id: [label_id.id, label_id.display_name],
                    });
                    // await this.model.root.update({
                    //     user_input_line_ids: [
                    //         [1, answer_line_ids[0].resId, {
                    //             suggested_answer_id: [label_id.id, label_id.display_name]
                    //         }],
                    //     ],
                    // });
                } else {
                    const newRecord = await this.model.root.data.user_input_line_ids.addNewRecord({
                        context: {
                            default_user_input_id: this.model.root.resId,
                            default_question_id: question.id,
                            default_answer_type: "suggestion",
                            default_suggested_answer_id: label_id.id,
                            default_skipped: false,
                        },
                    });
                    newRecord.update({});
                }
            }
        } finally {
            question.locked = false;
        }
    }

    async inputAnswer(ev, question) {
        question.locked = true;
        const answer_line_ids = this.model.root.data.user_input_line_ids.records.find(
            answer_id => answer_id.data.question_id[0] == question.id
        );
        const value = ev.srcElement.value;
        if (answer_line_ids) {
            let params = {};
            if (question.question_type == 'text_box') {
                params = {
                    value_text_box: value || "",
                };
            } else if (question.question_type == 'char_box') {
                params = {
                    value_char_box: value || "",
                };
            } else if (question.question_type == 'numerical_box') {
                params = {
                    value_numerical_box: parseFloat(value || 0),
                };
            }
            await answer_line_ids.update(params);
        } else {
            let params = {};
            let answer_type = question.question_type;
            if (question.question_type == 'text_box') {
                params = {
                    default_value_text_box: value || "",
                };
            } else if (question.question_type == 'char_box') {
                params = {
                    default_value_char_box: value || "",
                };
            } else if (question.question_type == 'numerical_box') {
                params = {
                    default_value_numerical_box: parseFloat(value || 0),
                };
            }
            const newRecord = await this.model.root.data['user_input_line_ids'].addNewRecord({
                context: {
                    default_user_input_id: this.model.root.resId,
                    default_question_id: question.id,
                    default_answer_type: answer_type,
                    default_skipped: false,
                    ...params,
                },
            });
            newRecord.update({});
        }
    }

    async onSubmit(ev) {
        // console.log("onSubmit");
        let anyError = false;
        for (let question of this.state.surveyData.question_ids) {
            if (!this.displayQuestion(question)) {
                continue;
            }
            const inputLine = this.input_lines.find(answer => answer.question_id == question.id);
            if (question.constr_mandatory) {
                let requiredError = false;
                if (['text_box', 'char_box', 'numerical_box'].includes(question.question_type)) {
                    const value = inputLine ? inputLine['value_' + question.question_type] : null;
                    if (!value) {
                        anyError = true;
                        requiredError = true;
                    }
                } else if (['simple_choice', 'multiple_choice'].includes(question.question_type) && !inputLine) {
                    anyError = true;
                    requiredError = true;
                }
                question.requiredError = requiredError;
            } else {
                question.requiredError = false;
            }
            if (question.validation_required) {
                let validationError = false;
                const value = inputLine ? inputLine['value_' + question.question_type] : null;
                if (['numerical_box'].includes(question.question_type)) {
                    const min = question.validation_min_float_value;
                    const max = question.validation_max_float_value;
                    if (!value || min && value < min || max && value > max) {
                        anyError = true;
                        validationError = true;
                    }
                }
                if (['char_box', 'text_box'].includes(question.question_type)) {
                    const min = question.validation_length_min;
                    const max = question.validation_length_max;
                    if (!value || min && value.length < min || max && value.length > max) {
                        anyError = true;
                        validationError = true;
                    }
                }
                question.validationError = validationError;
            }
        }
        if (anyError) {
            return;
        }
        // SPECIAL SAVE
        const clickParams = {
            special: "save",
        };
        this.beforeExecuteActionButton(clickParams);
    }

    onReturn(ev) {
        ev.preventDefault();
        // SPECIAL DISCARD
        const clickParams = {
            special: "cancel",
        };
        this.beforeExecuteActionButton(clickParams);
    }
};

IkeSurveyInputScreenFormController.template = "ike_event.IkeSurveyInputScreenFormView";
IkeSurveyInputScreenFormController.components = {
    ...FormController.components,
};

export const ikeSurveyInputScreenFormController = {
    ...formView,
    Controller: IkeSurveyInputScreenFormController,
}

registry.category("views").add("ike_survey_input_screen_form", ikeSurveyInputScreenFormController);
