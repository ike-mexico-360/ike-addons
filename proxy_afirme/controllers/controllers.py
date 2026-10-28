# controllers/proxy.py
from odoo import _, http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request
import requests
import json
from datetime import datetime

class ProxyController(http.Controller):

    @http.route('/portal/afirme', type='http', auth='user', website=True)
    def portal_afirme_dashboard(self, **kwargs):
        """Render the AFIRME dashboard only for specifically authorized users."""
        user = request.env.user
        if not (
            user.has_group('base.group_system')
            or user.x_afirme_portal_access
        ):
            return request.redirect('/my')
        months = [
            ('01', _('January')), ('02', _('February')), ('03', _('March')),
            ('04', _('April')), ('05', _('May')), ('06', _('June')),
            ('07', _('July')), ('08', _('August')), ('09', _('September')),
            ('10', _('October')), ('11', _('November')), ('12', _('December')),
        ]
        texts = {
            'provider_completed': _('Provider completed.'),
            'within_first_third': _('Within the first third of the estimated time.'),
            'within_second_third': _('Within the second third of the estimated time.'),
            'within_third_third': _('Within the third third of the estimated time.'),
            'estimated_time_overdue': _('Estimated time overdue.'),
            'calculation_unavailable': _('Calculation unavailable.'),
            'provider_made_contact': _('Provider made contact.'),
            'loading_open_cases': _('Loading open cases...'),
            'unable_retrieve_cases': _('Unable to retrieve the cases.'),
            'unable_load_cases': _('Unable to load cases: %s'),
            'showing_results': _('Showing %s of %s results'),
            'showing_open_cases': _('Showing %s of %s open cases'),
            'page': _('Page %s of %s'),
            'no_open_cases': _('There are no open cases in the selected period.'),
            'loading': _('Loading'),
        }
        return request.render(
            'proxy_afirme.portal_afirme_template',
            {'afirme_months': months, 'afirme_texts': texts},
        )

    def _formatear_fecha(self, fecha_str):
        if not fecha_str:
            return '—'
        try:
            dt = datetime.strptime(fecha_str, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d/%m/%Y %H:%M')
        except (ValueError, TypeError):
            return '—'

    def _convertir_minutos_a_hhmm(self, minutos_str):
        try:
            minutos = int(minutos_str)
            if minutos <= 0:
                return '—'
            horas = minutos // 60
            mins = minutos % 60
            return f"{horas:02d}:{mins:02d}"
        except (ValueError, TypeError):
            return '—'

    def _formatear_vehiculo(self, exp):
        partes = [
            exp.get('marca'),
            exp.get('tipoAuto'),
            f"({exp.get('anio')})" if exp.get('anio') else None,
            exp.get('color'),
            exp.get('placa', '').strip() if exp.get('placa') else None
        ]
        return ' • '.join([p for p in partes if p])

    def _formatear_direccion(self, calle, municipio, estado):
        partes = [calle, municipio, estado]
        return ', '.join([p for p in partes if p]) or '—'

    @http.route('/api/proxy/expedientes', type='http', methods=['POST'], auth='public', csrf=False)
    def proxy_expedientes(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data)
            variables = data.get('variables', {})
            clcuenta = variables.get('clcuenta')
            fechaDesde = variables.get('fechaDesde')
            fechaHasta = variables.get('fechaHasta')

            request_body = {
                "query": """
                    query ($clcuenta: Int!, $fechaIni: String!, $fechaFin: String!, $clEstatus: Int) {
                        expedientesPorCuenta(clcuenta: $clcuenta, fechaIni: $fechaIni, fechaFin: $fechaFin, clEstatus: $clEstatus) {
                            clExpediente
                            servicio
                            subservicio
                            nombre
                            apellidoPaterno
                            apellidoMaterno
                            vin
                            marca
                            tipoAuto
                            anio
                            color
                            placa
                            estadoOrigen
                            municipioOrigen
                            calleOrigen
                            estadoDestino
                            municipioDestino
                            calleDestino
                            eta
                            estatus
                            fechaAsignacion
                            fechaContacto
                            semaforoSeguimiento
                        }
                    }
                """,
                "variables": {
                    "clcuenta": clcuenta,
                    "fechaIni": fechaDesde,
                    "fechaFin": fechaHasta,
                    "clEstatus": 0
                }
            }

            response = requests.post(
                'https://cltemx.ikeasistencia.com/graphql',
                #'https://cltemx-qa.dev-pruebas.com/graphql',
                json=request_body,
                headers={'Content-Type': 'application/json'},
                timeout=120
            )

            if response.status_code != 200:
                return http.Response(
                    json.dumps({'error': _("External API error: %s") % response.status_code}),
                    status=500,
                    headers=[('Content-Type', 'application/json')]
                )

            api_response = response.json()
            expedientes = api_response.get('data', {}).get('expedientesPorCuenta', [])
            expedientes_limpios = []
            
            for exp in expedientes:
                nombre_parts = [exp.get('nombre'), exp.get('apellidoPaterno'), exp.get('apellidoMaterno')]
                expedientes_limpios.append({
                    "clExpediente": exp.get('clExpediente'),
                    "vin_limpio": exp.get('vin', '').strip() or '—',
                    "nombre_completo": ' '.join([p for p in nombre_parts if p]).upper() or '—',
                    "servicio": exp.get('servicio'),
                    "subservicio": exp.get('subservicio'),
                    "vehiculo_formateado": self._formatear_vehiculo(exp) or '—',
                    "origen_formateado": self._formatear_direccion(exp.get('calleOrigen'), exp.get('municipioOrigen'), exp.get('estadoOrigen')),
                    "destino_formateado": self._formatear_direccion(exp.get('calleDestino'), exp.get('municipioDestino'), exp.get('estadoDestino')),
                    "eta_formateado": self._convertir_minutos_a_hhmm(exp.get('eta')),
                    "fechaAsignacion_formateada": self._formatear_fecha(exp.get('fechaAsignacion')),
                    "fechaContacto_formateada": self._formatear_fecha(exp.get('fechaContacto')),
                    "idSeguimiento": exp.get('semaforoSeguimiento'),
                })
                
            response_data = {
                "data": {
                    "expedientesPorCuentaFiltrado": {
                        "content": expedientes_limpios
                    }
                }
            }

            return http.Response(
                json.dumps(response_data),
                status=200,
                headers=[('Content-Type', 'application/json')]
            )

        except requests.exceptions.Timeout:
            return http.Response(
                json.dumps({'error': _("The query is taking too long. Try a smaller date range.")}),
                status=504,
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return http.Response(
                json.dumps({'error': str(e)}),
                status=500,
                headers=[('Content-Type', 'application/json')]
            )


class AfirmePortal(CustomerPortal):
    """Send authorized portal users directly to their AFIRME dashboard."""

    @http.route()
    def home(self, **kw):
        user = request.env.user
        if user.share and user.x_afirme_portal_access:
            return request.redirect('/portal/afirme')
        return super().home(**kw)
