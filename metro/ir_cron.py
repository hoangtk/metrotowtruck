# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import logging

from openerp.osv import fields, osv
from openerp.tools.translate import _

def str2tuple(s):
    return eval('tuple(%s)' % (s or ''))

class ir_cron(osv.osv):
    _inherit = "ir.cron"

    def manual_run(self, cr, uid, ids, context):
        cron_id = ids[0]
        cron_data = self.browse(cr, uid, cron_id, context=context)
        args = str2tuple(cron_data.args)
        model = self.pool.get(cron_data.model)
        if model and hasattr(model, cron_data.function):
            method = getattr(model, cron_data.function)
            method(cr, uid, *args)
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
