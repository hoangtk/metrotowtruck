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

import time
from lxml import etree

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class account_rptcn_line(osv.osv_memory):
    _name = "account.rptcn.line"
    _description = "China Account Report Lines"
    _order = 'seq'
    _columns = {
        'rpt_id': fields.many2one('account.rptcn', ),
        'seq': fields.integer('Seq', ),
        #report objects code/name, object can be: account, partner, product, journal...
        'code': fields.char('Code', size=64, ),
        'name': fields.char('Name', size=256, ),
        
        #for GL
        'period_id': fields.many2one('account.period', 'Period',),
        
        #for detail
        'aml_id': fields.many2one('account.move.line', 'Move Line', ),
        'date': fields.date('Move Date', ),
        'am_name': fields.char('Move Name', size=64, ),
        
        #for both Gl and detail, move line name or static:期初,本期合计,本年合计
        'notes': fields.char('Notes', size=64, ),
        
        #for all
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        #debit/credit direction:Debit(借)/Credit(贷)
        'bal_direct': fields.char('Balance Direction', size=16, ),
        'balance': fields.float('Balance', digits_compute=dp.get_precision('Account')),
        }

account_rptcn_line()

class account_rptcn(osv.osv_memory):
    _name = "account.rptcn"
    _description = "Account Report China"
    _columns = {
#        'filter': fields.selection([('filter_date', 'Date'), ('filter_period', 'Periods')], "Filter by", required=True),
        'filter': fields.selection([('filter_period', 'Periods')], "Filter by", required=True),        
        'period_from': fields.many2one('account.period', 'Start Period'),
        'period_to': fields.many2one('account.period', 'End Period'),
        'date_from': fields.date("Start Date"),
        'date_to': fields.date("End Date"),
        'target_move': fields.selection([('posted', 'All Posted Entries'),
                                         ('all', 'All Entries'),
                                        ], 'Target Moves', required=True),
        'account_ids': fields.many2many('account.account', string='Accounts', required=True),
        'company_id': fields.many2one('res.company','Company',required=True,),
        #report data lines
        'rpt_lines': fields.one2many('account.rptcn.line', 'rpt_id', string='Report Line'),
        #report type
        'rpt_type': fields.selection([('account_gl', 'Account GL'),
                                    ('account_detail', 'Account Detail'),
                                    ('partner_gl', 'Partner GL'),
                                    ('partner_detail', 'Partner Detail'),
                                    ('product_gl', 'Product General Ledger'),
                                    ('product_detail', 'Product Detail'),], "Report Type", required=True),        
        #show/hide search fields on GUI
        'show_search': fields.boolean('Show Searching', ),
        }
    
    def _get_accounts_default(self, cr, uid, context=None):
        company_id = self.pool.get('res.users').browse(cr,uid,uid,context).company_id.id
        return self.pool.get('account.account').search(cr, uid ,[('company_id','=',company_id),'|',('type','=','liquidity'),('type','=','payable')])
        
    _defaults = {
        'filter': 'filter_period',        
        'target_move': 'posted',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.rptcn', context=c),
        'account_ids': _get_accounts_default,
        'rpt_type': 'account_gl',
        'show_search': True,        
    }
    def _check_periods(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.period_from and wiz.period_from.company_id.id != wiz.period_to.company_id.id:
                return False
        return True

    _constraints = [
        (_check_periods, 'The chosen periods have to belong to the same company.', ['period_from','period_to']),
    ]

    def onchange_filter(self, cr, uid, ids, filter, company_id, context=None):
        res = {'value': {}}
        if filter == 'filter_no':
            res['value'] = {'period_from': False, 'period_to': False, 'date_from': False ,'date_to': False}
        if filter == 'filter_date':
            res['value'] = {'period_from': False, 'period_to': False, 'date_from': time.strftime('%Y-01-01'), 'date_to': time.strftime('%Y-%m-%d')}
        if filter == 'filter_period' and company_id:
            start_period = end_period = False
            cr.execute('''
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               WHERE p.company_id = %s
                               AND p.special = false
                               AND p.state = 'draft'
                               ORDER BY p.date_start ASC, p.special ASC
                               LIMIT 1) AS period_start
                UNION ALL
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               WHERE p.company_id = %s
                               AND p.date_start < NOW()
                               AND p.special = false
                               AND p.state = 'draft'
                               ORDER BY p.date_stop DESC
                               LIMIT 1) AS period_stop''', (company_id, company_id))
            periods =  [i[0] for i in cr.fetchall()]
            if periods and len(periods) > 1:
                start_period = periods[0]
                end_period = periods[1]
#            res['value'] = {'period_from': start_period, 'period_to': end_period, 'date_from': False, 'date_to': False}
            res['value'] = {'period_from': end_period, 'period_to': end_period, 'date_from': False, 'date_to': False}
        return res

    def _get_date_range(self, cr, uid, data, context=None):
        if data.filter == 'filter_date':
            return data.date_from, data.date_to
        elif data.filter == 'filter_period':
            if not data.period_from or not data.period_to:
                raise osv.except_osv(_('Error!'),_('Select a starting and an ending period.'))
            return data.period_from.date_start, data.period_to.date_stop
        
    def _get_period_range(self, cr, uid, data, context=None):
        if data.filter == 'filter_date':
            return data.date_from, data.date_to
        elif data.filter == 'filter_period':
            if not data.period_from or not data.period_to:
                raise osv.except_osv(_('Error!'),_('Select a starting and an ending period.'))
            return data.period_from.date_start, data.period_to.date_stop  
        
    def _get_account_balance(self, account, debit, credit):
        if debit == credit: bal_direct = 'balanced'
        if debit > credit: bal_direct = 'debit'
        if debit < credit: bal_direct = 'credit'
        balance = account.bal_direct == 'credit' and (credit-debit) or (debit-credit) 
        return balance, bal_direct          
    
    def run_report(self, cr, uid, ids, context=None):
        rpt = self.browse(cr, uid, ids, context=context)[0]
        rpt_method = getattr(self, 'run_%s'%(rpt.rpt_type,))
        return rpt_method(cr, uid, ids, context)
        
    def run_account_gl(self, cr, uid, ids, context=None):
        if context is None: context = {}         
        rpt = self.browse(cr, uid, ids, context=context)[0]
        account_obj = self.pool.get('account.account')
        period_obj = self.pool.get('account.period') 
        
        labels = {'init_bal':_('Initial balance'),
                            'period_sum':_('Period total'),
                            'year_sum':_('Year total'),
                            'bal_direct_debit':_('Debit'),
                            'bal_direct_credit':_('Credit'),
                            'bal_direct_balanced':_('Balanced')}          
        company_id = rpt.company_id.id
        date_from,date_to = self._get_date_range(cr, uid, rpt, context)
        period_ids = period_obj.build_ctx_periods(cr, uid, rpt.period_from.id, rpt.period_to.id)
        move_state = ['draft','posted']
        if rpt.target_move == 'posted':
            move_state = ['posted']        
        #move line common query where
        aml_common_query = 'aml.company_id=%s'%(company_id,)
        seq = 1
        rpt_lns = []
        balance_sum = 0.0
        for account in rpt.account_ids:
            search_account_ids = tuple(account_obj._get_children_and_consol(cr, uid, [account.id], context=context))
            #1.the initial balance line
            cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                    FROM account_move_line aml \
                    JOIN account_move am ON (am.id = aml.move_id) \
                    WHERE (aml.account_id IN %s) \
                    AND (am.state IN %s) \
                    AND (am.date < %s) \
                    AND '+ aml_common_query +' '
                    ,(search_account_ids, tuple(move_state), date_from))
            row = cr.fetchone()
            debit = row[0]
            credit = row[1]            
            balance, direction = self._get_account_balance(account, debit, credit)
            rpt_ln = {'seq':seq,
                        'code':account.code, 
                        'name':account.name,
                        'period_id':rpt.period_from.id,
                        'notes':labels['init_bal'],
                        'bal_direct':labels['bal_direct_%s'%(direction,)],
                        'balance':balance}
            seq += 1
            rpt_lns.append(rpt_ln)
            balance_sum += balance
            
            #2.loop by periods            
            year_initial = {}
            for period in period_obj.browse(cr, uid, period_ids,context=context):
                #the year initial balance
                if not year_initial.get(period.fiscalyear_id.code,False):
                    if period.fiscalyear_id.date_start < date_from:
                        #Only when we start from the middle of a year, then need to sum initial balance
                        cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                                FROM account_move_line aml \
                                JOIN account_move am ON (am.id = aml.move_id) \
                                WHERE (aml.account_id IN %s) \
                                AND (am.state IN %s) \
                                AND (am.date >= %s) \
                                AND (am.date < %s) \
                                AND '+ aml_common_query +' '
                                ,(search_account_ids, tuple(move_state), period.fiscalyear_id.date_start, date_from))
                        row = cr.fetchone()            
                        year_initial[period.fiscalyear_id.code] = {'debit':row[0],'credit':row[1]}   
                    else:
                        year_initial[period.fiscalyear_id.code] = {'debit':0.0,'credit':0.0}
                
                #the period credit/debit
                cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                        FROM account_move_line aml \
                        JOIN account_move am ON (am.id = aml.move_id) \
                        WHERE (aml.account_id IN %s) \
                        AND (am.state IN %s) \
                        AND (am.period_id = %s) \
                        AND '+ aml_common_query +' '
                        ,(search_account_ids, tuple(move_state), period.id))
                row = cr.fetchone()
                #period sum line
                debit = row[0]
                credit = row[1]            
                balance, direction = self._get_account_balance(account, debit, credit)
                balance_sum += balance
                rpt_ln = {'seq':seq,
                            'code':'', 
                            'name':'',
                            'period_id':period.id,
                            'notes':labels['period_sum'],
                            'debit':debit,
                            'credit':credit,
                            'bal_direct':labels['bal_direct_%s'%(direction,)],
                            'balance':balance_sum}
                rpt_lns.append(rpt_ln)    
                seq += 1  
                
                #year sum line  
                debit_year = debit + year_initial[period.fiscalyear_id.code]['debit']
                credit_year = credit + year_initial[period.fiscalyear_id.code]['credit']
                balance_year, direction_year = self._get_account_balance(account, debit_year, credit_year)
                balance_year = balance_sum + year_initial[period.fiscalyear_id.code]['credit']
                rpt_ln = {'seq':seq,
                            'code':'', 
                            'name':'',
                            'period_id':period.id,
                            'notes':labels['year_sum'],
                            'debit':debit_year,
                            'credit':credit_year,
                            'bal_direct':labels['bal_direct_%s'%(direction_year,)],
                            'balance':balance_year,}
                rpt_lns.append(rpt_ln)     
                seq += 1      
        rpt_line_obj = self.pool.get('account.rptcn.line')
        #remove the old lines
        unlink_ids = rpt_line_obj.search(cr, uid, [('rpt_id','=',rpt.id)], context=context)
        rpt_line_obj.unlink(cr ,uid, unlink_ids, context=context)
        #create new lines
        for rpt_line in rpt_lns:
            rpt_line['rpt_id'] = rpt.id
            rpt_line_obj.create(cr ,uid, rpt_line, context=context)
        self.write(cr, uid, rpt.id, {'show_search':False},context=context)
        
#        upt_lines = [(0,0,rpt_ln) for rpt_ln in rpt_lns]
#        self.write(cr, uid, rpt.id, {'rpt_lines':upt_lines,'show_search':False},context=context)
        
        return True
    
account_rptcn()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
