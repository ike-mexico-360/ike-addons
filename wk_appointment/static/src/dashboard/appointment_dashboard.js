/** @odoo-module **/

import { Component, useRef, onWillStart, useEffect, onWillUnmount,useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";

export class ChartRenderer extends Component{
    static template = "wk_appointment.AppointmentDashboardChartRenderer";
    setup() {
        this.chartRef = useRef("chart")
        //loading chart.js on onWillStart because our users don't need to load it everytime
        onWillStart(async () => {
            await loadJS("https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js")
        })

        useEffect(() => {
            this.renderChart()
        }, () => [this.props.config])

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy()
            }
        })
    }
    renderChart() {
        const chartConfigs = {
            bar: {
                type: 'bar',
                options: {
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            },
            line: {
                type: 'line',
                options: {
                    fill: false
                }
            },
            pie: {
                type: 'pie',
                options: {
                    circumference: Math.PI,
                    rotation: -Math.PI,

                }
            },
            doughnut: {
                type: 'doughnut',
                options: {
                    circumference: Math.PI / 2,
                    rotation: -Math.PI / 2
                }
            }
        };

        const old_chartjs = document.querySelector('script[src="/web/static/lib/Chart/Chart.js"]')
        if (old_chartjs) {
            return
        }
        if (this.chart) {
            // Destroy old chart if present
            this.chart.destroy()
        }
        const chartConfig = chartConfigs[this.props.type]
        if (!chartConfig) {
            console.log("chartConfig not available")
            return;
        }

        this.chart = new Chart(this.chartRef.el, {
            type: chartConfig.type,
            data: this.props.config['data'],
            options: this.props.config['options']
        })
    }
}

export class AppointmentDashboardBody extends Component{
    static template = "wk_appointment.AppointmentDashboardView"
    
    static components = {
        ChartRenderer
    }

    async setup(){
        this.orm = useService('orm');
        this.actionService = useService('action');
        // this.props.chart = 'Line chart';
        this.state = useState({
            chartType: 'Line Chart',
            StatusChartType: 'Pie Chart',
            timeInterval: 'Weekly',
            selectedAppointeeId: -1,
        })
        this.selectedAppointeeId = -1;
        onWillStart(this.initializeDashboard.bind(this));
    }

    async initializeDashboard() {
        const promises = [
            await this.getAppointmentEarningDashboardData(this.selectedAppointeeId),
            await this.getAppointmentStatusDashboardData(this.selectedAppointeeId),
        ]
    }

    onEarningChartChange(ev){
        const selected_chart = ev.target.value;
        this.state.chartType = selected_chart;
    }
    onStatusChartChange(ev){
        const selected_chart = ev.target.value;
        this.state.StatusChartType = selected_chart;
    }
    async onTimeInternalChange(ev){
        const selected_interval = ev.target.value;
        this.state.timeInterval = selected_interval;
        await this.getAppointmentEarningDashboardData(this.state.selectedAppointeeId)
    }

    async onAppointeeChange(ev) {
        const appointeeId = parseInt(ev.target.value, 10);
        if (appointeeId === -1) {
            this.state.selectedAppointeeId = -1;  // for all appointees
        } else {
            this.state.selectedAppointeeId = appointeeId;
        }
        await this.getAppointmentEarningDashboardData(this.state.selectedAppointeeId)
        await this.getAppointmentStatusDashboardData(this.state.selectedAppointeeId)
    }

    async getAppointmentEarningDashboardData(appointee_id) {
        if (appointee_id == -1){
            appointee_id = '';
        }
        var response = await rpc('/get/appointment/earning/dashboard-data', {'appointee_id': appointee_id,"selected_interval": this.state.timeInterval})
        if(response){
            let chart_labels, chart_data;
            if (this.state.timeInterval == 'Weekly'){
                chart_labels = response['week_labels']
                chart_data = response['earnings_data']['earnings']
            }
            else if (this.state.timeInterval == 'Monthly'){
                chart_labels = response['month_labels']
                chart_data = response['earnings_data']['earnings']
            }
            else{
                chart_labels = response['year_labels']
                chart_data = response['earnings_data']['earnings']
            }
        this.state.appointmentEarning = {
            data: {
                labels: chart_labels,
                datasets: [{
                    maxBarThickness: 14,
                    barPercentage: 0.5,
                    label: 'Appointment Earnings',
                    data: chart_data,
                    hoverOffset: 4,
                    borderColor: 'rgb(35, 116, 143)',
                    backgroundColor: ['#2DAA9E'],
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                tension: 0.4,
                scales: {
                    x: {
                        type: 'category', 
                        grid: {
                            display: false,
                        }
                    },
                    y: {
                        ticks: {
                            stepsize: 1,
                        },
                        min: 0,
                    }
                },
            },
        }

        this.state.appointmentEarningBarChart = {
            data: {
                labels: chart_labels,
                datasets: [{
                    label: 'Appointment Status',
                    data: chart_data,
                    hoverOffset: 4,
                    backgroundColor: [
                        "#C0D8FF",
                        "#D8B1D8",  
                        "#5CB85C", 
                        "#F0F8FF", 
                        "#F2A2CE", 
                        "#FFCC80",
                        "#FF6347", 
                        "#90EE90",
                        "#FFC300",
                        "#D8709C",
                        "#A0522D",
                        "#BF0030"
                    ],
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        labels: {
						    usePointStyle: true
					    }
                    },
                    tooltip: {
                        enabled: true,
                    },
                },
				legend: {
					labels: {
						usePointStyle: true
					}
                },
                tension: 0.4,
                scales: {
                    x: {
                        type: 'category',
                        display: false,
                    },
                    y: { 
                        display: false,
                    }
                },
                maintainAspectRatio: true,
                radius: 150,
            },
        }
            this.props.appointee_list = response['appointee_list']
            this.props.is_manager = response['is_manager_group']
            this.props.is_officer = response['is_officer_group'] 
            const appointment_earning_count = response['earnings_data']['earnings'].reduce((partialSum, a) => partialSum + a, 0);
            this.props.earning_count = appointment_earning_count;
        }       
    }

    async getAppointmentStatusDashboardData(appointee_id){
        if (appointee_id == -1){
            appointee_id = '';
        }
        
        var response = await rpc('/get/appointment/status/dashboard-data', {'appointee_id': appointee_id});
        
        this.state.appointmentStatus = {
            data: {
                labels: response['status_labels'],
                datasets: [{
                    maxBarThickness: 14,
                    barPercentage: 0.5,
                    label: 'Appointment Status',
                    data: Object.values(response['appointment_status_count_list']),
                    hoverOffset: 4,
                    borderColor: 'rgb(35, 116, 143)',
                    backgroundColor: ['#2DAA9E', '#00879E', '#FFB200','#3A7D44', '#E52020'],
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                // width: 10,
                tension: 0.4,
                scales: {
                    x: {
                        type: 'category',  
                        grid: {
                            display: false,
                        }
                    },
                    y: {
                        ticks: {
                            stepsize: 1,
                        },
                        min: 0,
                    }
                },
            },
        }

        this.state.appointmentStatusBarChart = {
            data: {
                labels: response['status_labels'],
                datasets: [{
                    label: 'Appointment Status',
                    data: Object.values(response['appointment_status_count_list']),
                    hoverOffset: 4,
                    backgroundColor: ['#2DAA9E', '#00879E', '#FFB200','#3A7D44', '#E52020'],
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        labels: {
						    usePointStyle: true
					    }
                    },
                    tooltip: {
                        enabled: true,
                    },
                },
				legend: {
					labels: {
						usePointStyle: true
					}
                },
                tension: 0.4,
                scales: {
                    x: {
                        type: 'category',
                        display: false,
                    },
                    y: { 
                        display: false,
                    }
                },
                maintainAspectRatio: true,
                radius: 150,
            },
        }

        const appointment_count = response['appointment_status_count_list'].reduce((partialSum, a) => partialSum + a, 0);
        this.props.status_count = appointment_count;
        this.props.appointment_data = response['appointment_status']
    }

    getListViewonClick(ev) {
        let domain = [];
        if (this.state.selectedAppointeeId !== -1 && this.state.selectedAppointeeId !== undefined && this.state.selectedAppointeeId !== null) {
            domain.push(['appoint_person_id', '=', this.state.selectedAppointeeId]);
        }
        if (ev.target.classList.contains('new_appointment')) {
            let newAppointmentDomain = [
                ['appoint_state', '=', 'new']
            ];
            const finalDomain = [...newAppointmentDomain, ...domain];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'New Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: finalDomain,
            });
        }
        else if (ev.target.classList.contains('pending_appointment')) {
            var pendingAppointmentDomain = [
                ['appoint_state', '=', 'pending']
            ];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Pending Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: pendingAppointmentDomain.concat(domain),
            });
        }
        else if (ev.target.classList.contains('approved_appointment')) {
            var approvedAppointmentDomain = [
                ['appoint_state', '=', 'approved']
            ];
            
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Approved Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: approvedAppointmentDomain.concat(domain),
            });
        }
        else if (ev.target.classList.contains('done_appointment')) {
            var doneAppointmentDomain = [
                ['appoint_state', '=', 'done']
            ];
            
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Done Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: doneAppointmentDomain.concat(domain),
            });
        }
        else if (ev.target.classList.contains('cancelled_appointment')) {
            var cancelledAppointmentDomain = [
                ['appoint_state', '=', 'rejected']
            ];
            
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Cancelled Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: cancelledAppointmentDomain.concat(domain),
            });
        }
    }
}
registry.category("actions").add("appointment_dashboard_view", AppointmentDashboardBody);