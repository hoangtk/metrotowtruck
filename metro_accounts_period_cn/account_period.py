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

from openerp.osv import fields, osv
from openerp.tools.translate import _

from datetime import datetime
from dateutil.relativedelta import relativedelta

class account_period(osv.osv):
    _inherit = "account.period"
    _columns = {
        #生成月度结账凭证的时候设置,相关凭证信息
        'close_journal_period_id':fields.many2one('account.journal.period','Close Journal Period', readonly=True),
        'close_move_id':fields.many2one('account.move','Close Account Entries', readonly=True),
        #结转凭证已生成标志, True则证明已经进行了生成月度结账凭证的操作, 但是如果损益类科目没有余额, 没必要生成转账凭证, 则close_journal_period_id/close_move_id没有数据
        'close_entry_done':fields.boolean('Close entry done', readonly=True),
    }
    def action_draft(self, cr, uid, ids, context=None):
        open_ids = []
        for period in self.browse(cr, uid, ids, context=context):
            if period.state != 'done':
                continue
            period_obj = self.pool.get('account.period')
            #此期间的前一个期间状态必须为close, 例如前一个期间可能已经生成转帐凭证但是没有close(close_entry_done=True and state != 'done'), 此种状态则没有可以进行结账的可用期间
            domain = [('date_start', '>', period.date_stop), ('special','!=',True),  ('company_id','=',period.company_id.id), '|', ('close_entry_done', '=', True), ('state','=','done')]
            new_periods = period_obj.search(cr, uid, domain, context=context)            
            if new_periods:
                raise osv.except_osv(_('Invalid Action!'), _('%s: there are periods closed or in closing after this period, please open them first.')%(period.name,))            
            open_ids.append(period.id)
            
        return super(account_period, self).action_draft(cr, uid, ids)
            
account_period()

class account_fiscalyear(osv.osv):
    _inherit = "account.fiscalyear"
    _columns = {
        #do we need generate the opening period for this  year when do peridos generating
        'need_open_period':fields.boolean('Generate Opening Period'),
    }

    def create_period(self, cr, uid, ids, context=None, interval=1):
        period_obj = self.pool.get('account.period')
        for fy in self.browse(cr, uid, ids, context=context):
            ds = datetime.strptime(fy.date_start, '%Y-%m-%d')
#            period_obj.create(cr, uid, {
#                    'name':  "%s %s" % (_('Opening Period'), ds.strftime('%Y')),
#                    'code': ds.strftime('00/%Y'),
#                    'date_start': ds,
#                    'date_stop': ds,
#                    'special': True,
#                    'fiscalyear_id': fy.id,
#                })
            #johnw, add the checking of need_open_period
            if fy.need_open_period:
                period_obj.create(cr, uid, {
                        'name':  "%s %s" % (_('Opening Period'), ds.strftime('%Y')),
                        'code': ds.strftime('00/%Y'),
                        'date_start': ds,
                        'date_stop': ds,
                        'special': True,
                        'fiscalyear_id': fy.id,
                    })
            while ds.strftime('%Y-%m-%d') < fy.date_stop:
                de = ds + relativedelta(months=interval, days=-1)

                if de.strftime('%Y-%m-%d') > fy.date_stop:
                    de = datetime.strptime(fy.date_stop, '%Y-%m-%d')

                period_obj.create(cr, uid, {
                    'name': ds.strftime('%m/%Y'),
                    'code': ds.strftime('%m/%Y'),
                    'date_start': ds.strftime('%Y-%m-%d'),
                    'date_stop': de.strftime('%Y-%m-%d'),
                    'fiscalyear_id': fy.id,
                })
                ds = ds + relativedelta(months=interval)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
