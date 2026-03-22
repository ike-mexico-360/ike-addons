from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PortalUserAccount(CustomerPortal):

    @http.route(
        ["/provider/portal/users", "/provider/portal/users/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_users_list(self, page=1, sortby=None, **kw):
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

    # ------------------------------------------------------------
    # CREATE NEW USER (FORM)
    # ------------------------------------------------------------
    @http.route(["/provider/portal/user/new"], type="http", auth="user", website=True)
    def portal_new_user_form(self, **kw):
        values = {
            "page_name": "new_user",
            "countries": request.env["res.country"].search([]),
        }
        return request.render("ike_event_portal.portal_ike_event_user_new", values)

    @http.route(
        ["/provider/portal/user/create"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_create_system_user(self, **kw):
        """
        Creates a res.users record.
        """
        # 1. Extract basic data
        name = kw.get("name")
        email = kw.get("email")  # Login is usually the email
        password = "P@ssw0rd123"  # You might want to generate a random password or get it from the form
        role = kw.get("x_user_role")

        # 2. Validate
        if not name or not email or not password:
            return request.render(
                "ike_event_portal.portal_ike_event_user_new",
                {"error_message": "Name, Email, and Password are required."},
            )

        # Map radio value to group XML IDs
        role_group_xml = {
            "admin": "ike_event_portal.custom_group_portal_admin",
            "supervisor": "ike_event_portal.custom_group_portal_supervisor",
            "operator": "ike_event_portal.custom_group_portal_operator",
        }
        role_xml_id = role_group_xml.get(role)

        # Resolve group IDs
        portal_group_id = request.env.ref("base.group_portal").id
        role_group_id = request.env.ref(role_xml_id).id

        # Assign groups: Portal + role group
        groups = [portal_group_id, role_group_id]

        try:
            # 3. Create the User (res.users)
            # Odoo will automatically create the related res.partner
            new_user = (
                request.env["res.users"]
                .sudo()
                .create(
                    {
                        "name": name,
                        "login": email,
                        "password": password,
                        "email": email,
                        # Assign a group (e.g., Portal User)
                        "groups_id": [(6, 0, groups)],
                        # Optional: Link to a specific company if needed
                        # 'company_id': request.env.company.id,
                    }
                )
            )

            # Optional: Update extra partner fields if you have them in the form
            new_user.partner_id.sudo().write(
                {
                    "phone": kw.get("phone"),
                    "street": kw.get("street"),
                    "city": kw.get("city"),
                    "country_id": (
                        int(kw.get("country_id")) if kw.get("country_id") else False
                    ),
                    "zip": kw.get("zip"),
                    "street2": kw.get("street2"),
                    "vat": kw.get("x_license_number"),
                }
            )

            return request.redirect(f"/provider/portal/user/{new_user.partner_id.id}")

        except Exception as e:
            # Handle errors (e.g., login already exists)
            return request.render(
                "ike_event_portal.portal_ike_event_user_new",
                {
                    "error_message": f"Error creating user: {str(e)}",
                    "default_values": kw,
                },
            )

    @http.route(
        ["/provider/portal/user/<int:user_id>"], type="http", auth="user", website=True
    )
    def portal_user_detail(self, user_id, **kw):
        try:
            user = request.env["res.users"].sudo().browse(user_id)
            if not user.exists():
                return request.redirect("/provider/portal/users")
            partner = user.partner_id
        except (AccessError, MissingError):
            return request.redirect("/provider/portal/users")

        values = {
            "partner": partner,
            "user": user,
            "page_name": "user_detail",
        }
        return request.render("ike_event_portal.portal_ike_event_user_detail", values)

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
            print("AAAAAAAAAAAAAAAAAAAAAAAAAA")
            # 1. Extract and validate data
            name = kw.get("name")
            email = kw.get("email") or kw.get("login")
            password = kw.get("password", "P@ssw0rd123")

            user_type = kw.get("user_type")
            if user_type == "administrator":
                groups_id = request.env.ref(
                    "ike_event_portal.custom_group_portal_admin"
                ).id
            if user_type == "supervisor":
                groups_id = request.env.ref(
                    "ike_event_portal.custom_group_portal_supervisor"
                ).id
            if user_type == "operator":
                groups_id = request.env.ref(
                    "ike_event_portal.custom_group_portal_operator"
                ).id

            _logger.info(f"Creating user with data: name={name}, email={email}")

            # Validate required fields
            if not name or not email:
                return {"success": False, "error": "Name and Email are required."}

            # Check if user already exists
            existing_user = (
                request.env["res.users"]
                .sudo()
                .search(["|", ("login", "=", email), ("email", "=", email)], limit=1)
            )

            if existing_user:
                return {
                    "success": False,
                    "error": f"A user with email {email} already exists.",
                }

            # 2. Prepare user data
            user_vals = {
                "name": name,
                "login": email,
                "password": password,
                "email": email,
                "groups_id": [(6, 0, [groups_id, request.env.ref("base.group_portal").id])],
                "active": True,
                "company_id": request.env.company.id,
                "lang": "es_MX",
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
                "message": "User created successfully.",
            }

        except Exception as e:
            _logger.error(f"Error creating user: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Error creating user: {str(e)}"}

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
            users = request.env['res.users'].sudo().search_read(
                domain=domain,
                fields=fields
            )

            _logger.info(f"User {request.env.user.login} retrieved {len(users)} users")

            return users

        except Exception as e:
            _logger.error(f"Error searching users: {str(e)}")
            return []

    @http.route(
        ["/provider/portal/groups/search"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def search_groups(self, group_ids=None, fields=None, **kw):
        """
        Search groups by IDs

        Args:
            group_ids: List of group IDs to search
            fields: List of field names to return

        Returns:
            list: List of dictionaries with group data
        """
        try:
            if not group_ids:
                return []

            # Use default fields if not specified
            if fields is None:
                fields = ['id', 'name']

            # Search groups
            groups = request.env['res.groups'].search_read(
                domain=[['id', 'in', group_ids]],
                fields=fields
            )

            _logger.info(f"User {request.env.user.login} retrieved {len(groups)} groups")

            return groups

        except Exception as e:
            _logger.error(f"Error searching groups: {str(e)}")
            return []
