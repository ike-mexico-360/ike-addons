odoo.define('sh_all_in_one_helpdesk.sh_helpdesk_ticket_kanban_examples', function(require) {
    'use strict';

    var core = require('web.core');
    var kanbanExamplesRegistry = require('web.kanban_examples_registry');
    var _lt = core._lt;
    kanbanExamplesRegistry.add('sh_helpdesk', {
        ghostColumns: [_lt('New'), _lt('In Progress'), _lt('Done'), _lt('Closed'), _lt('Reopened'), _lt('Cancelled')],
    });
});