/** @odoo-module **/

import { onMounted, onWillRender, onWillUnmount, useState } from "@odoo/owl";
import { useDateTimePicker } from "@web/core/datetime/datetime_hook";
import { areDatesEqual } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { DateTimeField, dateTimeField } from "@web/views/fields/datetime/datetime_field";

export class DateTimeWidget extends DateTimeField {
    setup() {
        let observer;

        const getAppointmentMinDate = () => {
            return this.props.record.data.appointment_min_date;
        };

        const getSelectedValue = () => {
            const value = Array.isArray(this.state?.value)
                ? this.state.value[0]
                : this.state?.value;

            return value || this.getRecordValue() || getAppointmentMinDate();
        };

        const getPickerProps = () => {
            const value = this.getRecordValue();
            const appointmentMinDate = getAppointmentMinDate();

            const pickerProps = {
                value,
                type: this.field.type,
                range: this.isRange(value),
            };

            if (appointmentMinDate) {
                pickerProps.minDate = appointmentMinDate.startOf("day");
            } else if (this.props.minDate) {
                pickerProps.minDate = this.parseLimitDate(this.props.minDate);
            }

            if (this.props.maxDate) {
                pickerProps.maxDate = this.parseLimitDate(this.props.maxDate);
            }

            if (!isNaN(this.props.rounding)) {
                pickerProps.rounding = this.props.rounding;
            } else if (!this.props.showSeconds) {
                pickerProps.rounding = 0;
            }

            if (this.props.maxPrecision) {
                pickerProps.maxPrecision = this.props.maxPrecision;
            }

            if (this.props.minPrecision) {
                pickerProps.minPrecision = this.props.minPrecision;
            }

            return pickerProps;
        };

        const filterInvalidTimeOptions = () => {
            const appointmentMinDate = getAppointmentMinDate();
            const selectedValue = getSelectedValue();

            if (!appointmentMinDate || !selectedValue) {
                return;
            }

            const picker = document.querySelector(".o_datetime_picker");
            if (!picker) {
                return;
            }

            const selects = picker.querySelectorAll("select");
            const hourSelect = selects[0];
            const minuteSelect = selects[1];

            if (!hourSelect || !minuteSelect) {
                return;
            }

            const isMinDay = selectedValue.hasSame(appointmentMinDate, "day");

            for (const option of hourSelect.options) {
                const hour = Number(option.value || option.textContent);
                const shouldHide = isMinDay && hour < appointmentMinDate.hour;

                option.hidden = shouldHide;
                option.disabled = shouldHide;
            }

            const selectedHour = Number(hourSelect.value);

            for (const option of minuteSelect.options) {
                const minute = Number(option.value || option.textContent);
                const shouldHide =
                    isMinDay &&
                    selectedHour === appointmentMinDate.hour &&
                    minute < appointmentMinDate.minute;

                option.hidden = shouldHide;
                option.disabled = shouldHide;
            }
        };

        const filterInvalidTimeOptionsSoon = () => {
            requestAnimationFrame(() => {
                filterInvalidTimeOptions();
                setTimeout(filterInvalidTimeOptions, 25);
                setTimeout(filterInvalidTimeOptions, 75);
                setTimeout(filterInvalidTimeOptions, 150);
                setTimeout(filterInvalidTimeOptions, 300);
            });
        };

        const dateTimePicker = useDateTimePicker({
            target: "root",
            showSeconds: this.props.showSeconds,
            condensed: this.props.condensed,

            get pickerProps() {
                return getPickerProps();
            },

            onChange: () => {
                this.state.range = this.isRange(this.state.value);
                filterInvalidTimeOptionsSoon();
            },

            onApply: async () => {
                const toUpdate = {};

                if (Array.isArray(this.state.value)) {
                    [toUpdate[this.startDateField], toUpdate[this.endDateField]] =
                        this.state.value;
                } else {
                    toUpdate[this.props.name] = this.state.value;
                }

                for (const fieldName in toUpdate) {
                    if (
                        areDatesEqual(
                            toUpdate[fieldName],
                            this.props.record.data[fieldName]
                        )
                    ) {
                        delete toUpdate[fieldName];
                    }
                }

                if (Object.keys(toUpdate).length) {
                    await this.props.record.update(toUpdate);
                }
            },
        });

        this.state = useState(dateTimePicker.state);

        this.openPicker = (...args) => {
            dateTimePicker.open(...args);
            filterInvalidTimeOptionsSoon();
        };

        onMounted(() => {
            observer = new MutationObserver(filterInvalidTimeOptionsSoon);
            observer.observe(document.body, {
                childList: true,
                subtree: true,
            });
        });

        onWillUnmount(() => {
            if (observer) {
                observer.disconnect();
            }
        });

        onWillRender(() => this.triggerIsDirty());
    }
}

export const datetimeWidgetField = {
    ...dateTimeField,
    component: DateTimeWidget,
};

registry.category("fields").add("datetime_widget", datetimeWidgetField);