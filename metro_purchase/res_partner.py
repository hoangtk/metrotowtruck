# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from operator import itemgetter
import time

from openerp.osv import fields, osv


class res_partner(osv.osv):
    _inherit = 'res.partner'

    def _get_main_product_supplier(self, cr, uid, product, context=None):
        """Determines the main (best) product supplier for ``product``,
        returning the corresponding ``supplierinfo`` record, or False
        if none were found. The default strategy is to select the
        supplier with the highest priority (i.e. smallest sequence).

        :param browse_record product: product to supply
        :rtype: product.supplierinfo browse_record or False
        """
        sellers = [(seller_info.sequence, seller_info)
                       for seller_info in product.seller_ids or []
                       if seller_info and isinstance(seller_info.sequence, (int, long))]
        return sellers and sellers[0][1] or False

    def _calc_bank(self, cr, uid, ids, fields, arg, context=None):
        result = dict((id, 
                       dict((field,None) for field in fields)
                       ) for id in ids)        
        for partner in self.browse(cr, uid, ids, context=context):
            if not partner.bank_ids:
                continue
            result[partner.id]['bank_name'] = partner.bank_ids[0].bank_name
            result[partner.id]['bank_account'] = partner.bank_ids[0].acc_number
        return result
        
    _columns={
        #bank_name
        'bank_name': fields.function(_calc_bank, type='char', size=64, string="Bank Name", multi="bank_info"),
        #acc_number
        'bank_account': fields.function(_calc_bank, type='char', size=32, string='Bank Account Number', multi="bank_info"),
    }

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
