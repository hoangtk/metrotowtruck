# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from openerp.osv import fields,osv


class project_issue(osv.osv):
    _inherit = "project.issue"
    _columns = {
        'create_by': fields.many2one('res.users', 'Created By'),
        'database':fields.selection([('metro_prod', 'Metro Production'),('metro_uat', 'Metro UAT'),],'Database'),
        'database_test':fields.selection([('metro_prod', 'Metro Production'),('metro_uat', 'Metro UAT'),],'Testing Database'),
        'type':fields.selection([('defect', 'Defect'),('change_request', 'Change Request'),('feature_request', 'Feature Request'),],'Type')
    }
    _defaults = {
        'database': 'metro_prod',
        'database_test': 'metro_uat',
    }