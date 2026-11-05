import io

import xlsxwriter
from odoo import SUPERUSER_ID, fields, http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import content_disposition, request
import logging
import re

_logger = logging.getLogger(__name__)


class PortalUserAccount(CustomerPortal):

    @http.route(
        ["/provider/portal/users", "/provider/portal/users/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_users_list(self, page=1, sortby=None, **kw):
        try:
            if not request.env.user.has_group('ike_event_portal.custom_group_portal_admin'):
                return request.redirect('/my')

            values = self._prepare_portal_layout_values()

            User = request.env["res.users"].sudo()
            domain = []  # adjust if you want to filter (e.g., by groups or company)
            groups = (
                request.env.ref("ike_event_portal.custom_group_portal_admin"),
                request.env.ref("ike_event_portal.custom_group_portal_supervisor"),
                request.env.ref("ike_event_portal.custom_group_portal_operator"),
            )
            single_user = request.env.user
            ad = request.env.user.has_group("ike_event_portal.custom_group_portal_admin")
            add = request.env.user.has_group("custom_group_portal_admin")

            print(groups)
            print(single_user)
            print(ad)
            print(add)

            total = User.search_count(domain)
            pager = portal_pager(
                url="/provider/portal/users",
                url_args={"sortby": sortby},
                total=total,
                page=page,
                step=20,
            )

            users = User.search(domain, order="id desc")

            values.update({"users": users, "pager": pager, "page_name": "users_list"})
            return request.render("ike_event_portal.portal_ike_event_users_list", values)
        except Exception as e:
            _logger.error("Error in portal_users_list: %s", str(e))
            return request.redirect('/my')

    # ------------------------------------------------------------
    # CREATE NEW USER (JSON ENDPOINT FOR JAVASCRIPT)
    # ------------------------------------------------------------
    @http.route(
        ["/provider/portal/user/create/json"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def portal_create_user_json(self, **kw):
        """
        Creates a res.users record from JavaScript/JSON request.
        Returns: {'success': True/False, 'user_id': id, 'message': str}
        """
        try:
            # 1. Extract and validate data
            name = kw.get("name")
            password = kw.get("password", "P@ssw0rd123")
            user_type = kw.get("user_type")

            # Group user
            group_xmlids = {
                "financial": "ike_event_portal.custom_group_portal_finance",
                "supervisor": "ike_event_portal.custom_group_portal_supervisor",
                "operator": "ike_event_portal.custom_group_portal_operator",
            }
            if user_type not in group_xmlids:
                return {"success": False, "error": f"Invalid user type: {user_type}"}
            groups_id = request.env.ref(group_xmlids[user_type]).id

            # Valid password
            password_error = self._x_ike_check_password_policy(password)
            if password_error:
                return {"success": False, "error": password_error}
            if user_type == "operator":
                # Operador: se crea con el login generado y sin email
                login = kw.get("login")
                email = False

                required_fields = {
                    "name": _("Name"),
                    "login": _("Login"),
                    "password": _("Password"),
                    "phone": _("Phone"),
                    "licence_type": _("License Type"),
                    "vat": _("License number"),
                    "license_validity": _("Expiration Date"),
                }
                missing = [label for field, label in required_fields.items() if not kw.get(field)]
                if missing:
                    return {"success": False, "error": _("Required fields: %s", ', '.join(missing))}

                # Login único: abgonzalez, abgonzalez1, abgonzalez2...
                login = self._x_ike_get_unique_login(login)
                if not login:
                    return {"success": False, "error": "Could not generate a login using the provided first and last names."}

                duplicate_domain = [("login", "=", login)]
            else:
                # Financieros / Supervisor: igual que antes
                email = kw.get("email") or kw.get("login")
                login = email

                if not name or not email:
                    return {"success": False, "error": "Name and Email are required."}

                duplicate_domain = ["|", ("login", "=", email), ("email", "=", email)]

            _logger.info(f"Creating user with data: name={name}, login={login}, groups_id={groups_id}, user_type={user_type}")

            # Check if user already exists (incluye archivados: el login es único aunque esté inactivo)
            existing_user = (
                request.env["res.users"]
                .sudo()
                .with_context(active_test=False)
                .search(duplicate_domain, limit=1)
            )
            if existing_user:
                return {"success": False, "error": f"Already exist user with email {login}."}

            # 2. Prepare user data
            user_vals = {
                "name": name,
                "login": login,
                "password": password,
                "email": email,
                "groups_id": [(6, 0, [groups_id, request.env.ref("base.group_portal").id])],
                "active": True,
                "company_id": request.env.company.id,
                "lang": request.env.company.x_get_ike_company_language(),
            }

            # 3. Create the user
            new_user = request.env["res.users"].sudo().create(user_vals)

            # 4. Update partner fields if provided
            partner_vals = {}
            optional_fields = [
                "phone",
                "mobile",
                "street",
                "street2",
                "city",
                "zip",
                "country_id",
                "state_id",
                "vat",
            ]
            for field in optional_fields:
                if field in kw and kw[field]:
                    partner_vals[field] = kw[field]

            # Campos del payload que en res.partner tienen otro nombre
            partner_field_map = {
                "licence_type": "x_license_type",
                "license_validity": "x_license_expiration_date",
                "birthdate": "x_birthdate",
            }
            for payload_key, partner_field in partner_field_map.items():
                if kw.get(payload_key):
                    partner_vals[partner_field] = kw[payload_key]

            if partner_vals:
                new_user.partner_id.sudo().write(partner_vals)

            _logger.info(
                f"User created successfully: {new_user.login} (ID: {new_user.id})"
            )

            vals = {
                "user_id": new_user.id,
                "partner_id": new_user.partner_id.id,
                "user_type": user_type,
                "supplier_id": kw.get("supplier_id"),
                "center_of_attention_id": kw.get("center_of_attention_id"),
            }
            new_supplier_driver = (
                request.env["res.partner.supplier_users.rel"].sudo().create(vals)
            )
            _logger.info(f"new_supplier_driver: {new_supplier_driver}")
            # -----------------------------------
            return {
                "success": True,
                "user_id": new_user.id,
                "partner_id": new_user.partner_id.id,
                "login": new_user.login,
                "message": "User created successfully.",
            }

        except Exception as e:
            _logger.error(f"Error creating user: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error creating user: {str(e)}"}

    def _x_ike_get_unique_login(self, base_login):
        base_login = (base_login or "").strip().lower()
        if not base_login:
            return False

        # Logins que ya empiezan igual (una sola consulta; incluye usuarios archivados)
        existing_logins = (
            request.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search([("login", "=ilike", f"{base_login}%")])
            .mapped("login")
        )
        used_logins = {login.lower() for login in existing_logins}

        new_login = base_login
        counter = 1
        while new_login in used_logins:
            new_login = f"{base_login}{counter}"
            counter += 1
        return new_login

    @staticmethod
    def _x_ike_check_password_policy(password):
        """
        Mínimo 8 caracteres, con al menos una mayúscula, una minúscula y un número.
        Devuelve el mensaje de error, o False si la contraseña cumple.
        """
        if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$", password or ""):
            return _("The password must have at least 8 characters, one uppercase letter, one lowercase letter and one number")
        return False

    @http.route(
        ["/provider/portal/user/check_admin"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def check_user_is_admin(self, **kw):
        """
        Check if the current logged-in user is a portal admin
        Returns: True/False directly
        """
        try:
            is_admin = request.env.user.has_group(
                "ike_event_portal.custom_group_portal_admin"
            )

            return is_admin

        except Exception as e:
            _logger.error(f"Error checking admin status: {str(e)}")
            return {"success": False, "is_admin": False, "error": str(e)}

    @http.route("/api/partners/centers", type="json", auth="user", methods=["POST"])
    def get_supplier_centers(self, partner_id=None, **kwargs):
        try:
            Partner = request.env["res.partner"]

            domain = [
                ("id", "=", partner_id),
            ]

            res_partner = Partner.search(domain)

            # Get list of child IDs using .ids
            center_ids = res_partner.child_ids.ids

            supplier_centers = Partner.search(
                [("id", "in", center_ids), ("type", "=", "center")]
            )

            return [{"id": center.id, "name": center.name} for center in supplier_centers]
        except Exception as e:
            _logger.error("Error in get_supplier_centers: %s", str(e))
            return {"error": str(e)}

    @http.route(
        ["/provider/portal/users/search"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def search_users(self, domain=None, fields=None, **kw):
        """
        Search users with domain and fields (mimics orm.searchRead behavior)

        Args:
            domain: Search domain (list of tuples)
            fields: List of field names to return

        Returns:
            list: List of dictionaries with user data (same format as searchRead)
        """
        try:
            # Perform searchRead on res.users
            users = request.env['res.users'].sudo().with_context(active_test=False).search_read(
                domain=domain,
                fields=fields
            )

            _logger.info(f"User {request.env.user.login} retrieved {len(users)} users")

            return users

        except Exception as e:
            _logger.error(f"Error searching users: {str(e)}")
            return {"error": str(e)}

    @http.route(["/provider/portal/user/update/json"], type="json", auth="user", methods=["POST"], csrf=False)
    def portal_update_user_json(self, user_id=None, **kw):
        """Update portal user."""
        try:
            current_user = request.env.user
            if not current_user.has_group("ike_event_portal.custom_group_portal_admin"):
                return {"success": False, "error": "You are not allowed to edit users."}

            Rel = request.env["res.partner.supplier_users.rel"].sudo()
            admin_rel = Rel.search([("user_id", "=", current_user.id)], limit=1)
            user_rel = Rel.search([("user_id", "=", int(user_id or 0))], limit=1)

            if not admin_rel or not user_rel or user_rel.supplier_id != admin_rel.supplier_id:
                return {"success": False, "error": "User not found."}

            name = (kw.get("name") or "").strip()
            if not name:
                return {"success": False, "error": _("Name is required.")}

            # Operador: mismos obligatorios que al crear
            if user_rel.user_type == "operator":
                required_fields = {
                    "phone": _("Phone"),
                    "vat": _("License number"),
                    "license_validity": _("License validity"),
                }
                missing = [label for field, label in required_fields.items() if not kw.get(field)]
                if missing:
                    return {"success": False, "error": _("Required fields: %s", ', '.join(missing))}

            center = request.env["res.partner"].sudo().browse(int(kw.get("center_of_attention_id") or 0)).exists()
            if not center or center.type != "center" or center.parent_id != admin_rel.supplier_id:
                return {"success": False, "error": "Invalid attention center."}

            password = kw.get("password")
            if password:
                password_error = self._x_ike_check_password_policy(password)
                if password_error:
                    return {"success": False, "error": password_error}

            # Status: only applied when the form sends it
            active = kw.get("active")
            if active is not None and not active and user_rel.user_id == current_user:
                return {"success": False, "error": request.env._("You cannot deactivate your own user.")}

            user = user_rel.user_id

            user.partner_id.sudo().write({
                "name": name,
                "phone": kw.get("phone") or False,
                "vat": kw.get("vat") or False,
                "x_birthdate": kw.get("birthdate") or False,
                "x_license_expiration_date": kw.get("license_validity") or False,
                "street": kw.get("street") or False,
                "street2": kw.get("street2") or False,
                "l10n_mx_edi_colony": kw.get("colony") or False,
                "zip": kw.get("zip") or False,
                "city": kw.get("city") or False,
                "country_id": int(kw.get("country_id") or 0) or False,
                "state_id": int(kw.get("state_id") or 0) or False,
            })

            if password:
                user.sudo().write({"password": password})
            # Inactive users cannot log in; Odoo also invalidates their open sessions
            if active is not None and user.active != bool(active):
                user.sudo().write({"active": bool(active)})
            if user_rel.center_of_attention_id != center:
                user_rel.write({"center_of_attention_id": center.id})

            return {"success": True}

        except Exception as e:
            _logger.error(f"Error updating user: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error updating user: {str(e)}"}

    def _x_ike_get_editable_user_rel(self, user_id):
        """
        Return the supplier relation of a user that the current portal admin can edit,
        or False when not allowed (not an admin, or the user belongs to another supplier).
        """
        current_user = request.env.user
        if not current_user.has_group("ike_event_portal.custom_group_portal_admin"):
            return False
        Rel = request.env["res.partner.supplier_users.rel"].sudo()
        admin_rel = Rel.search([("user_id", "=", current_user.id)], limit=1)
        user_rel = Rel.search([("user_id", "=", int(user_id or 0))], limit=1)
        if not admin_rel or not user_rel or user_rel.supplier_id != admin_rel.supplier_id:
            return False
        return user_rel

    @http.route(
        ["/provider/portal/user/password/json"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def portal_change_user_password_json(self, user_id=None, password=None, **kw):
        """Change the password of a supplier user from the portal."""
        try:
            user_rel = self._x_ike_get_editable_user_rel(user_id)
            if not user_rel:
                return {"success": False, "error": request.env._("User not found.")}

            password_error = self._x_ike_check_password_policy(password)
            if password_error:
                return {"success": False, "error": password_error}

            user_rel.user_id.sudo().write({"password": password})
            return {"success": True}

        except Exception as e:
            _logger.error(f"Error changing password: {str(e)}", exc_info=True)
            return {"success": False, "error": request.env._("The password could not be changed.")}

    @http.route(["/provider/portal/user/set_active"], type="json", auth="user", methods=["POST"], csrf=False)
    def portal_set_user_active(self, user_id=None, active=True, **kw):
        """Activate or deactivate a supplier user from the list's actions menu."""
        try:
            user_rel = self._x_ike_get_editable_user_rel(user_id)
            if not user_rel:
                return {"success": False, "error": request.env._("User not found.")}
            if not active and user_rel.user_id == request.env.user:
                return {"success": False, "error": request.env._("You cannot deactivate your own user.")}
            # Inactive users cannot log in; Odoo also invalidates their open sessions
            user_rel.user_id.sudo().write({"active": bool(active)})
            return {"success": True}
        except Exception as e:
            _logger.error(f"Error changing user status: {str(e)}", exc_info=True)
            return {"success": False, "error": request.env._("The user status could not be changed.")}

    def _x_ike_get_supplier_user_rels(self, user_ids):
        """Supplier relations of `user_ids` that belong to the current user's supplier."""
        Rel = request.env["res.partner.supplier_users.rel"].sudo()
        own_rel = Rel.search([("user_id", "=", request.env.user.id)], limit=1)
        if not own_rel or not own_rel.supplier_id:
            return Rel
        return Rel.with_context(active_test=False).search([
            ("user_id", "in", [int(user_id) for user_id in user_ids or []]),
            ("supplier_id", "=", own_rel.supplier_id.id),
        ])

    def _x_ike_get_users_last_changes(self, rels):
        """
        {user_id: {'date': datetime (UTC), 'user': name, 'is_system': bool}}: the latest write among
        the user, its contact and its supplier relation (name, phone, status, center, password...).
        """
        result = {}
        for rel in rels:
            user = rel.user_id
            changes = [
                (record.write_date, record.write_uid)
                for record in (user, user.partner_id, rel)
                if record.write_date
            ]
            if not changes:
                continue
            date, author = max(changes, key=lambda change: change[0])
            # Records written by crons, installs or automations run as OdooBot (superuser).
            is_system = not author or author.id == SUPERUSER_ID
            result[user.id] = {
                "date": date,
                "user": "" if is_system else author.name,
                "is_system": is_system,
            }
        return result

    @http.route(["/provider/portal/users/last_changes"], type="json", auth="user", methods=["POST"], csrf=False)
    def portal_users_last_changes(self, user_ids=None, **kw):
        """Last change of each listed user: {user_id: {'date': 'YYYY-MM-DD HH:MM:SS' (UTC), 'user', 'is_system'}}"""
        try:
            changes = self._x_ike_get_users_last_changes(self._x_ike_get_supplier_user_rels(user_ids))
            for change in changes.values():
                change["date"] = fields.Datetime.to_string(change["date"])
            return {"success": True, "changes": changes}
        except Exception as e:
            _logger.error(f"Error loading users last changes: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    @http.route(["/provider/portal/users/download/xlsx"], type="http", auth="user", website=True)
    def portal_users_xlsx(self, ids="", **kw):
        """Export the users shown in the portal list, in the order given by `ids` (comma-separated)."""
        _ = request.env._
        user_ids = [int(user_id) for user_id in ids.split(",") if user_id.strip().isdigit()]
        # Only users of the current user's supplier; keep the list's sort order.
        rels_by_user = {rel.user_id.id: rel for rel in self._x_ike_get_supplier_user_rels(user_ids)}
        rels = [rels_by_user[user_id] for user_id in user_ids if user_id in rels_by_user]

        last_changes = self._x_ike_get_users_last_changes(rels)
        # English labels, translated through this module's i18n files (as in the portal list).
        type_labels = dict(request.env["res.partner.supplier_users.rel"]._fields["user_type"].selection)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet(_("Users"))

        header_format = workbook.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#16006F",
            "border": 1, "border_color": "#16006F", "align": "center", "valign": "vcenter",
        })
        text_format = workbook.add_format({"border": 1, "border_color": "#DFE3F1", "valign": "top"})
        datetime_format = workbook.add_format({
            "border": 1, "border_color": "#DFE3F1", "valign": "top", "num_format": "dd/mm/yyyy hh:mm",
        })

        headers = [
            _("Name"), _("Email"), _("Attention center"), _("Type"), _("Status"),
            _("Last change"), _("Last change user"),
        ]
        for column, title in enumerate(headers):
            worksheet.write(0, column, title, header_format)
        worksheet.set_column("A:B", 32)
        worksheet.set_column("C:C", 45)
        worksheet.set_column("D:E", 16)
        worksheet.set_column("F:F", 18)
        worksheet.set_column("G:G", 26)

        for row, rel in enumerate(rels, start=1):
            user = rel.user_id
            last_change = last_changes.get(user.id)
            worksheet.write(row, 0, user.name or "-", text_format)
            worksheet.write(row, 1, user.email or user.login or "-", text_format)
            worksheet.write(row, 2, rel.center_of_attention_id.display_name or "-", text_format)
            worksheet.write(row, 3, _(type_labels[rel.user_type]) if rel.user_type in type_labels else "-", text_format)
            worksheet.write(row, 4, _("Active") if user.active else _("Inactive"), text_format)
            if last_change:
                # xlsxwriter has no timezone support: write the time as the user sees it.
                local_date = fields.Datetime.context_timestamp(request.env.user, last_change["date"])
                worksheet.write_datetime(row, 5, local_date.replace(tzinfo=None), datetime_format)
                worksheet.write(row, 6, _("System") if last_change["is_system"] else last_change["user"], text_format)
            else:
                worksheet.write(row, 5, "-", text_format)
                worksheet.write(row, 6, "", text_format)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(rels), len(headers) - 1)
        workbook.close()
        xlsx_content = output.getvalue()

        return request.make_response(
            xlsx_content,
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Length", len(xlsx_content)),
                ("Content-Disposition", content_disposition("usuarios.xlsx")),
            ],
        )
