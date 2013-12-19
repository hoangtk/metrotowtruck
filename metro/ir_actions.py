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
import logging

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from socket import gethostname

from openerp import netsvc
from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.config import config

import logging
import os
import re
from socket import gethostname
import time

from openerp import SUPERUSER_ID
from openerp import netsvc, tools
from openerp.osv import fields, osv
from openerp.report.report_sxw import report_sxw, report_rml
from openerp.tools.config import config
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)

class actions_server(osv.osv):  
    _name="ir.actions.server"
    _inherit = "ir.actions.server"
    _columns = {
        'email_cc': fields.char('CC Address', size=512),
#        'email_bcc': fields.char('BCC Address', size=512, help="Expression that returns the email address to bcc. Can be based on the same values as for the condition field.\n"
#                                                             "Example: object.invoice_address_id.email, or 'me@example.com'"),
#        'email_reply_to': fields.char('Reploy To Address', size=512, help="Expression that returns the email address to reply to. Can be based on the same values as for the condition field.\n"
#                                                             "Example: object.invoice_address_id.email, or 'me@example.com'"),
#        'email_subtype': fields.selection([('plain','Plain'),('html','Html')], 'Content Type', readonly=True, help="The contenct type of the email", select=True),                
    }
actions_server()  
             
